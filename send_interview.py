import os
import pymysql
import smtplib
from dotenv import load_dotenv
from email.message import EmailMessage
from calendar_utils import create_event
load_dotenv()

# Email configuration
EMAIL_HOST = os.getenv("EMAIL_HOST")
EMAIL_PORT = int(os.getenv("SMTP_PORT"))
EMAIL_USER = os.getenv("EMAIL_ADDRESS")
EMAIL_PASS = os.getenv("EMAIL_PASSWORD")
FORM_LINK = os.getenv("GOOGLE_FORM_LINK")

# MySQL config (used in connection)
DB_HOST = os.getenv('DB_HOST')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_NAME = os.getenv('DB_NAME')
DB_PORT=os.getenv('DB_PORT')

# Connect to your PostgreSQL (update credentials)
conn = pymysql.connect(
    host=DB_HOST,
    user=DB_USER,
    password=DB_PASSWORD,
    database=DB_NAME,
    port=int(DB_PORT),
    cursorclass=pymysql.cursors.DictCursor
)

with conn:
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

            msg.set_content(f"""
Dear {student['interviewer_name']},

A new candidate has been added under the technology: {student['tech_name']}.

Please review their resume and provide your availability using this form:
🔗 {FORM_LINK}

Instructions:
- Select up to 3 time slots per day
- Choose slots for the next 5 working days (excluding today)

Student Details:
Name: {student['student_name']}
Email: {student['student_email']}

Thank you,
TecMantras
""")

            # Attach resume
            RESUME_DIR = "uploads/"

            resume_path = os.path.join(RESUME_DIR, student['resume_path'])
            if resume_path and os.path.exists(resume_path):
                with open(resume_path, 'rb') as f:
                    resume_data = f.read()
                    msg.add_attachment(resume_data, maintype='application', subtype='octet-stream',
                                       filename=os.path.basename(resume_path))
            else:
                print(f" Resume not found for {student['student_name']} at {resume_path}")

            # Send email
            try:
                with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as smtp:
                    smtp.starttls()
                    smtp.login(EMAIL_USER, EMAIL_PASS)
                    smtp.send_message(msg)
                    print(f"✅ Email sent to {student['interviewer_email']}")

                # Update status to 2
                cursor.execute("UPDATE candidates SET status = 2 WHERE id = %s", (student['id'],))
                conn.commit()

            except Exception as e:
                print(f"❌ Failed to send email to {student['interviewer_email']}: {e}")