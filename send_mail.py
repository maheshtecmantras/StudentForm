import os
import pymysql
import smtplib
from dotenv import load_dotenv
from email.message import EmailMessage
import sys

# Load environment variables
load_dotenv()

# Email configuration
EMAIL_HOST = os.getenv("EMAIL_HOST")
EMAIL_PORT = int(os.getenv("SMTP_PORT"))
EMAIL_USER = os.getenv("EMAIL_ADDRESS")
EMAIL_PASS = os.getenv("EMAIL_PASSWORD")


# MySQL config
DB_HOST = os.getenv('DB_HOST')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_NAME = os.getenv('DB_NAME')
DB_PORT = os.getenv('DB_PORT')

#Base URL
BASE_URL = os.getenv("BASE_URL")

# Resume upload directory
RESUME_DIR = "uploads/"

# Connect to MySQL
conn = pymysql.connect(
    host=DB_HOST,
    user=DB_USER,
    password=DB_PASSWORD,
    database=DB_NAME,
    port=int(DB_PORT),
    cursorclass=pymysql.cursors.DictCursor
)

def send_mail_to_faculty():
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT s.id, s.name AS student_name, s.email AS student_email, s.resume as resume_path, 
                   t.name AS tech_name, t.faculty_email as interviewer_email , t.faculty_name as interviewer_name
            FROM candidates s
            JOIN technologies t ON s.technology_id = t.id
            WHERE s.status = 1
        """)
        students = cursor.fetchall()
        for student in students:
            msg = EmailMessage()
            msg['Subject'] = f"[Action Required] Interview Slot Selection for {student['student_name']}"
            msg['From'] = EMAIL_USER
            msg['To'] = student['interviewer_email']
            availability_form_url = f"{BASE_URL}/availability_form?student_id={student['id']}"


            msg.set_content(f"""
                Dear {student['interviewer_name']},

                A new candidate has been added under the technology: {student['tech_name']}.

                Please review their resume and provide your availability using this form:
                🔗 {availability_form_url}

                Instructions:
                - Select up to 3 time slots per day
                - Choose slots for the next 5 working days (excluding today)

                Candidate Details:
                Name: {student['student_name']}
                Email: {student['student_email']}

                Thank you,
                TecMantras
                """)

            resume_path = os.path.join(RESUME_DIR, student['resume_path'])
            if resume_path and os.path.exists(resume_path):
                with open(resume_path, 'rb') as f:
                    resume_data = f.read()
                    msg.add_attachment(resume_data, maintype='application', subtype='octet-stream',
                                       filename=os.path.basename(resume_path))
            else:
                print(f" Resume not found for {student['student_name']} at {resume_path}")

            try:
                with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as smtp:
                    smtp.starttls()
                    smtp.login(EMAIL_USER, EMAIL_PASS)
                    smtp.send_message(msg)
                    print(f"✅ Email sent to faculty: {student['interviewer_email']}")

                cursor.execute("UPDATE candidates SET status = 2 WHERE id = %s", (student['id'],))
                conn.commit()

            except Exception as e:
                print(f"❌ Failed to send email to {student['interviewer_email']}: {e}")

def send_mail_to_student():
    with conn.cursor() as cursor:
        # Get student_ids with availability AND status = 2
        cursor.execute("""
            SELECT DISTINCT c.id AS student_id, c.name, c.email
            FROM candidates c
            JOIN availability a ON c.id = a.student_id
            WHERE c.status = 2
        """)
        students = cursor.fetchall()
        print(students)
        for student in students:
            student_id = student['student_id']
            
            msg = EmailMessage()
            msg['Subject'] = "Select Your Interview Slot - Action Required"
            msg['From'] = EMAIL_USER
            msg['To'] = student['email']

            slot_selection_url = f"{BASE_URL}/get_availability?student_id={student_id}"
            msg.set_content(f"""
                Dear {student['name']},

                Your interviewer has shared their available time slots for the interview.

                Please select your preferred interview slot using the link below:
                🔗 {slot_selection_url}

                Note:
                - Only one slot can be selected.
                - Please confirm your slot at the earliest.

                All the best,  
                TecMantras
            """)

            try:
                with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as smtp:
                    smtp.starttls()
                    smtp.login(EMAIL_USER, EMAIL_PASS)
                    smtp.send_message(msg)
                    print(f"✅ Slot selection email sent to student: {student['email']}")
                
                cursor.execute("UPDATE candidates SET status = 3 WHERE id = %s", (student_id,))
                conn.commit()
            except Exception as e:
                print(f"❌ Failed to send email to student {student['email']}: {e}")

def send_feedback_form_to_faculty(faculty_email, student_id):
    # Connect to DB and get student name
    conn = pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        port=int(DB_PORT),
        cursorclass=pymysql.cursors.DictCursor
    )

    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT name FROM candidates WHERE id = %s", (student_id,))
            student = cursor.fetchone()

            if not student:
                print(f"❌ Student with ID {student_id} not found.")
                return

            msg = EmailMessage()
            msg['Subject'] = f"Feedback Form for {student['name']}"
            msg['From'] = EMAIL_USER
            msg['To'] = faculty_email

            feedback_form_url = f"{BASE_URL}/feedback_form?student_id={student_id}"
            msg.set_content(f"""
                Dear Interviewer,

                Please provide your feedback for {student['name']} using the link below:
                🔗 {feedback_form_url}

                Thank you,
                TecMantras
            """)

            try:
                with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as smtp:
                    smtp.starttls()
                    smtp.login(EMAIL_USER, EMAIL_PASS)
                    smtp.send_message(msg)
                    print(f"✅ Feedback form sent to: {faculty_email}")
            except Exception as e:
                print(f"❌ Failed to send email: {e}")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
    finally:
        conn.close()
    

def send_mail_to_hr(candidate_id):


    conn = pymysql.connect(
    host=DB_HOST,
    user=DB_USER,
    password=DB_PASSWORD,
    database=DB_NAME,
    port=int(DB_PORT),
    cursorclass=pymysql.cursors.DictCursor
    )

    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT c.name AS candidate_name, c.review, c.description, c.decision,
                    t.faculty_name, t.faculty_email, t.name AS technology_name
                FROM candidates c
                JOIN technologies t ON c.technology_id = t.id
                WHERE c.id = %s
            """, (candidate_id,))
            candidate = cursor.fetchone()

            if not candidate:
                print(f"❌ Candidate with ID {candidate_id} not found.")
                return

            msg = EmailMessage()
            msg['Subject'] = f"LLM Review Result - {candidate['candidate_name']}"
            msg['From'] = EMAIL_USER
            msg['To'] = candidate['faculty_email']

            msg.set_content(f"""
                        Dear HR,

                        The interview review for the candidate has been processed using LLM evaluation.

                        📌 Candidate Name: {candidate['candidate_name']}
                        💼 Technology: {candidate['technology_name']}
                        🧑‍🏫 Interviewer: {candidate['faculty_name']}

                        📝 Interviewer Review:
                        {candidate['review']}

                        🤖 LLM Response:
                        {candidate['description']}

                        ✅ Final Decision: {candidate['decision']}

                        Best regards,  
                        TecMantras
                        """)

            try:
                with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as smtp:
                    smtp.starttls()
                    smtp.login(EMAIL_USER, EMAIL_PASS)
                    smtp.send_message(msg)
                    print(f"✅ Email sent to: {candidate['faculty_email']}")
            except Exception as e:
                print(f"❌ Failed to send email: {e}")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
    finally:
        conn.close()
# === Execute functions ===
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python send_mail.py [faculty|student]")
        sys.exit(1)

    task = sys.argv[1].lower()

    if task == "faculty":
        send_mail_to_faculty()
    elif task == "student":
        send_mail_to_student()
    else:
        print("Invalid argument. Use 'faculty' or 'student'.")