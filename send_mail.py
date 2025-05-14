import os
import pymysql
import smtplib
from dotenv import load_dotenv
from email.message import EmailMessage
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
            availability_form_url = f"http://localhost:5000/availability_form?student_id={student['id']}"

            msg.set_content(f"""
Dear {student['interviewer_name']},

A new candidate has been added under the technology: {student['tech_name']}.

Please review their resume and provide your availability using this form:
🔗 {availability_form_url}

Instructions:
- Select up to 3 time slots per day
- Choose slots for the next 5 working days (excluding today)

Student Details:
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
        cursor.execute("""
            SELECT DISTINCT student_id
            FROM availability
        """)
        student_ids = cursor.fetchall()

        for entry in student_ids:
            student_id = entry['student_id']

            cursor.execute("""
                SELECT name, email
                FROM candidates
                WHERE id = %s
            """, (student_id,))
            student = cursor.fetchone()

            if not student:
                print(f"❌ Student with ID {student_id} not found.")
                continue

            msg = EmailMessage()
            msg['Subject'] = f"Select Your Interview Slot - Action Required"
            msg['From'] = EMAIL_USER
            msg['To'] = student['email']

            slot_selection_url = f"http://localhost:5000/get_availability?student_id={student_id}"

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

# === Execute functions ===
with conn:
    # send_mail_to_faculty()
    send_mail_to_student()
