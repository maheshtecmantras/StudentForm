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

def send_mail_to_faculty(round_num):
    # Map round number to status, interviewer column and next status
    round_config = {
        1: {
            'current_status': 2,
            'interviewer_field': 'round1_interviewer_id',
            'next_status': 3
        },
        2: {
            'current_status': 5,
            'interviewer_field': 'round2_interviewer_id',
            'next_status': 6
        }
    }

    config = round_config.get(round_num)
    if not config:
        print(f"❌ Invalid round number: {round_num}")
        return

    with conn.cursor() as cursor:
        # Dynamic SQL using format string only for column names (safe)
        query = f"""
            SELECT s.id, s.name AS student_name, s.email AS student_email, 
                   s.resume AS resume_path, s.technology_id, s.{config['interviewer_field']},
                   t.name AS tech_name,
                   i.name AS interviewer_name, i.email AS interviewer_email
            FROM candidates s
            JOIN technologies t ON s.technology_id = t.id
            JOIN interviewer i ON s.{config['interviewer_field']} = i.id
            WHERE s.status = %s
        """
        cursor.execute(query, (config['current_status'],))
        students = cursor.fetchall()

        for student in students:
            msg = EmailMessage()
            msg['Subject'] = f"[Action Required] Interview Slot Selection for Round {round_num}: {student['student_name']}"
            msg['From'] = EMAIL_USER
            msg['To'] = student['interviewer_email']
            availability_form_url = f"{BASE_URL}/availability_form?student_id={student['id']}&round={round_num}"

            msg.set_content(f"""
                Dear {student['interviewer_name']},

                A candidate has been assigned to you for **Round {round_num}** under the technology: {student['tech_name']}.

                Please review their resume and submit your availability:
                🔗 {availability_form_url}

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
                    print(f"✅ Email sent to {student['interviewer_email']} for {student['student_name']}")
                # Update status to next stage
                cursor.execute("UPDATE candidates SET status = %s WHERE id = %s", (config['next_status'], student['id']))
                conn.commit()
            except Exception as e:
                print(f"❌ Failed to send email to {student['interviewer_email']}: {e}")



def send_mail_to_student(round_number):
    # Define internal mapping of round to statuses
    round_status_map = {
        1: {"current_status": 3, "next_status": 4},
        2: {"current_status": 6, "next_status": 7}
    }   
    print(round_number)
    if round_number not in round_status_map:
        print(f"❌ Invalid round number: {round_number}")
        return

    current_status = round_status_map[round_number]["current_status"]
    next_status = round_status_map[round_number]["next_status"]
    with conn.cursor() as cursor:
        # Fetch students who match round and status
        cursor.execute("""
            SELECT DISTINCT c.id AS student_id, c.name, c.email
            FROM candidates c
            JOIN availability a ON c.id = a.student_id
            WHERE c.status = %s AND a.round = %s
        """, (current_status, round_number))
        
        students = cursor.fetchall()
        print(f"📬 Sending Round {round_number} emails to students: {students}")

        for student in students:
            student_id = student['student_id']

            msg = EmailMessage()
            msg['Subject'] = f"Select Your Interview Slot - Round {round_number}"
            msg['From'] = EMAIL_USER
            msg['To'] = student['email']

            slot_selection_url = f"{BASE_URL}/get_availability?student_id={student_id}&round={round_number}"
            msg.set_content(f"""
                Dear {student['name']},

                Your interviewer has shared their available time slots for **Round {round_number}** of the interview.

                Please select your preferred interview slot using the link below:
                🔗 {slot_selection_url}

                Note:
                - Only one slot can be selected.
                - Please confirm your slot at the earliest.

                Best regards,  
                TecMantras
            """)

            try:
                with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as smtp:
                    smtp.starttls()
                    smtp.login(EMAIL_USER, EMAIL_PASS)
                    smtp.send_message(msg)
                    print(f"✅ Round {round_number} email sent to: {student['email']}")

                # Update status to next
                cursor.execute("UPDATE candidates SET status = %s WHERE id = %s", (next_status, student_id))
                conn.commit()

            except Exception as e:
                print(f"❌ Failed to send Round {round_number} email to {student['email']}: {e}")

def send_feedback_form_to_faculty(faculty_email, student_id,round_number):
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

            feedback_form_url = f"{BASE_URL}/feedback_form?student_id={student_id}&round={round_number}"
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
    

def send_review_mail_to_hr(candidate_id, round_number):
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
            if round_number == 1:
                cursor.execute("""
                    SELECT c.name AS candidate_name, c.round1_review AS review, 
                           c.round1_description AS description, c.round1_decision AS decision,
                           t.name AS technology_name, i.name AS interviewer_name
                    FROM candidates c
                    JOIN technologies t ON c.technology_id = t.id
                    JOIN interviewer i ON c.round1_interviewer_id = i.id
                    WHERE c.id = %s
                """, (candidate_id,))
            elif round_number == 2:
                cursor.execute("""
                    SELECT c.name AS candidate_name, c.round2_review AS review, 
                           c.round2_description AS description, c.round2_decision AS decision,
                           t.name AS technology_name, i.name AS interviewer_name
                    FROM candidates c
                    JOIN technologies t ON c.technology_id = t.id
                    JOIN interviewer i ON c.round2_interviewer_id = i.id
                    WHERE c.id = %s
                """, (candidate_id,))
            else:
                print("❌ Invalid round number")
                return

            candidate = cursor.fetchone()
            if not candidate:
                print(f"❌ Candidate with ID {candidate_id} not found.")
                return

            msg = EmailMessage()
            msg['Subject'] = f"LLM Review Result (Round {round_number}) - {candidate['candidate_name']}"
            msg['From'] = EMAIL_USER
            msg['To'] = "meet.tecmantras@gmail.com"

            approve_url = f"{BASE_URL}/approve_candidate?candidate_id={candidate_id}&round={round_number}"
            reject_url = f"{BASE_URL}/reject_candidate?candidate_id={candidate_id}&round={round_number}"

            msg.add_alternative(f"""
            <html>
            <body>
                <p>Dear HR,</p>
                <p>The interview review for the candidate has been processed using LLM evaluation.</p>

                <h3>Candidate Review Summary (Round {round_number})</h3>
                <ul>
                    <li><strong>📌 Candidate Name:</strong> {candidate['candidate_name']}</li>
                    <li><strong>💼 Technology:</strong> {candidate['technology_name']}</li>
                    <li><strong>🧑‍🏫 Interviewer:</strong> {candidate['interviewer_name']}</li>
                </ul>

                <h4>📝 Interviewer Review</h4>
                <p>{candidate['review']}</p>

                <h4>🤖 LLM Response</h4>
                <p>{candidate['description']}</p>

                <h4>✅ Final Decision</h4>
                <p>{candidate['decision']}</p>

                <p>
                    <a href="{approve_url}" style="padding:10px 20px; background-color:#28a745; color:white; text-decoration:none; border-radius:5px;">✅ Approve & Assign Interviewer</a>
                    &nbsp;
                    <a href="{reject_url}" style="padding:10px 20px; background-color:#dc3545; color:white; text-decoration:none; border-radius:5px;">❌ Reject</a>
                </p>

                <p>Best regards,<br/>TecMantras</p>
            </body>
            </html>
            """, subtype='html')

            try:
                with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as smtp:
                    smtp.starttls()
                    smtp.login(EMAIL_USER, EMAIL_PASS)
                    smtp.send_message(msg)
                    print(f"✅ Email sent to HR for candidate: {candidate['candidate_name']}")
            except Exception as e:
                print(f"❌ Failed to send email: {e}")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
    finally:
        conn.close()


def send_details_mail_to_hr(candidate_id):
    # Connect to DB and get candidate details
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
            SELECT s.id, s.name AS student_name, s.email AS student_email, s.resume as resume_path,
                   s.mobile, s.total_exp, s.relevant_exp, s.ctc, s.ectc, s.notice_period,
                   s.relocation, s.location, t.name AS tech_name
            FROM candidates s
            INNER JOIN technologies t ON s.technology_id = t.id
            WHERE s.id = %s
            """,(candidate_id))
            candidate = cursor.fetchone()

            if not candidate:
                    print(f"❌ Candidate with ID {candidate_id} not found.")
                    return
    
            msg = EmailMessage()
        msg['Subject'] = f"[Approval Required] Candidate: {candidate['student_name']}"
        msg['From'] = EMAIL_USER
        msg['To'] = "meet.tecmantras@gmail.com"  # Replace with actual HR email

        approve_url = f"{BASE_URL}/approve_candidate?candidate_id={candidate['id']}&round=screening"
        reject_url = f"{BASE_URL}/reject_candidate?candidate_id={candidate['id']}&round=screening"

        msg.add_alternative(f"""
            <html>
                <body>
                    <p>Dear HR,</p>
                    <p>A new candidate has submitted their details. Please review and take action below.</p>

                    <h3>Candidate Details</h3>
                    <table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse;">
                        <tr><td><strong>Name</strong></td><td>{candidate['student_name']}</td></tr>
                        <tr><td><strong>Email</strong></td><td>{candidate['student_email']}</td></tr>
                        <tr><td><strong>Mobile</strong></td><td>{candidate['mobile']}</td></tr>
                        <tr><td><strong>Location</strong></td><td>{candidate['location']}</td></tr>
                        <tr><td><strong>Relocation</strong></td><td>{candidate['relocation']}</td></tr>
                        <tr><td><strong>Technology</strong></td><td>{candidate['tech_name']}</td></tr>
                        <tr><td><strong>Total Experience</strong></td><td>{candidate['total_exp']}</td></tr>
                        <tr><td><strong>Relevant Experience</strong></td><td>{candidate['relevant_exp']}</td></tr>
                        <tr><td><strong>Current CTC</strong></td><td>{candidate['ctc']}</td></tr>
                        <tr><td><strong>Expected CTC</strong></td><td>{candidate['ectc']}</td></tr>
                        <tr><td><strong>Notice Period</strong></td><td>{candidate['notice_period']}</td></tr>
                    </table>

                    <p><strong>Resume:</strong> Attached below.</p>

                    <p>
                        <a href="{approve_url}" style="padding:10px 20px; background-color:#28a745; color:white; text-decoration:none; border-radius:5px;">✅ Approve & Assign Interviewer</a>
                        &nbsp;
                        <a href="{reject_url}" style="padding:10px 20px; background-color:#dc3545; color:white; text-decoration:none; border-radius:5px;">❌ Reject</a>
                    </p>


                    <p>Regards,<br/>TecMantras</p>
                </body>
            </html>
        """, subtype='html')

        resume_path = os.path.join(RESUME_DIR, candidate['resume_path'])
        if resume_path and os.path.exists(resume_path):
            with open(resume_path, 'rb') as f:
                resume_data = f.read()
                msg.add_attachment(resume_data, maintype='application', subtype='octet-stream',
                                   filename=os.path.basename(resume_path))
        else:
            print(f"❌ Resume not found for {candidate['student_name']} at {resume_path}")

        try:
            with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as smtp:
                smtp.starttls()
                smtp.login(EMAIL_USER, EMAIL_PASS)
                smtp.send_message(msg)
                print(f"✅ Email sent to HR for candidate: {candidate['student_name']}")

        except Exception as e:
            print(f"❌ Failed to send email to HR for candidate {candidate['student_name']}: {e}")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
    finally:
        conn.close()
            
def send_rejection_mail(candidate_id):
    # Connect to DB and get candidate details
    conn = pymysql.connect(
    host=DB_HOST,
    user=DB_USER,
    password=DB_PASSWORD,
    database=DB_NAME,
    port=int(DB_PORT),
    cursorclass=pymysql.cursors.DictCursor
    )


    # Fetch candidate details
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT candidates.name, email, t.name AS technology_name
                FROM candidates 
                JOIN technologies t ON candidates.technology_id = t.id
                WHERE candidates.id = %s
            """, (candidate_id,))
            candidate = cursor.fetchone()

            if not candidate:
                cursor.close()
                conn.close()
                print(f"❌ Candidate with ID {candidate_id} not found.")
                return

            msg = EmailMessage()
            msg['Subject'] = "Interview Result - Round 1"
            msg['From'] = EMAIL_USER
            msg['To'] = candidate['email']

            msg.set_content(f"""
                Dear {candidate['name']},

                Thank you for participating in the Round 1 interview for the {candidate['technology_name']} internship.

                Unfortunately, we will not be moving forward with your application at this time.

                We appreciate your interest in TecMantras and encourage you to apply again in the future.

                Best regards,  
                TecMantras HR Team
            """)
            try:
                with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as smtp:
                    smtp.starttls()
                    smtp.login(EMAIL_USER, EMAIL_PASS)
                    smtp.send_message(msg)
                    print(f"✅ Rejection email sent to: {candidate['email']}")
            except Exception as e:
                print(f"❌ Failed to send rejection email: {e}")

        cursor.close()
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
    finally:
        conn.close()

def send_round2_selection_mail(candidate_id):

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
                SELECT candidates.name, email, t.name as technology
                FROM candidates
                JOIN technologies t ON candidates.technology_id = t.id
                WHERE candidates.id = %s
            """, (candidate_id,))
            candidate = cursor.fetchone()
            print(candidate)
            if not candidate:
                print(f"❌ Candidate with ID {candidate_id} not found.")
                return

            msg = EmailMessage()
            msg['Subject'] = "Congratulations! You’ve been shortlisted for Round 2"
            msg['From'] = EMAIL_USER
            msg['To'] = candidate['email']

            msg.set_content(f"""
                Dear {candidate['name']},

                🎉 Congratulations! You have been selected for Round 2 of the interview process for the {candidate['technology']} internship.

                Please wait for further instructions regarding the interview schedule.

                Best regards,
                TecMantras HR Team
            """)

            try:
                with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as smtp:
                    smtp.starttls()
                    smtp.login(EMAIL_USER, EMAIL_PASS)
                    smtp.send_message(msg)
                    print(f"✅ Round 2 selection email sent to: {candidate['email']}")
            except Exception as e:
                print(f"❌ Failed to send email: {e}")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
    finally:
        conn.close()
# === Execute functions ===
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python send_mail.py [faculty|student] [round_number_if_faculty]")
        sys.exit(1)

    task = sys.argv[1].lower()

    if task == "faculty":
        if len(sys.argv) < 3:
            print("❌ Please provide a round number for 'faculty'.")
            sys.exit(1)
        try:
            round_num = int(sys.argv[2])
            send_mail_to_faculty(round_num)
        except ValueError:
            print("❌ Invalid round number. Must be an integer.")
    elif task == "student":
        if len(sys.argv) < 3:
            print("❌ Please provide a round number for 'student'.")
            sys.exit(1)
        try:
            round_num = int(sys.argv[2])
            print(round_num)
            send_mail_to_student(round_num)
        except ValueError:
            print("❌ Invalid round number. Must be an integer.")
    else:
        print("❌ Invalid argument. Use 'faculty' or 'student'.")



