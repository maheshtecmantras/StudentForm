from flask import Flask, render_template, request, jsonify
import pymysql
import os
import uuid
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from datetime import datetime
import smtplib
from email.message import EmailMessage
from google.auth.transport.requests import Request

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB

# MySQL config
DB_HOST = os.getenv('DB_HOST')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_NAME = os.getenv('DB_NAME')
DB_PORT = os.getenv('DB_PORT')

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Function to get DB connection
def get_db_connection():
    return pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        port=int(DB_PORT),
        cursorclass=pymysql.cursors.DictCursor
    )

# Main student form (existing)
@app.route('/', methods=['GET', 'POST'])
def index():
    connection = get_db_connection()
    cursor = connection.cursor()
    
    cursor.execute("SELECT id, name FROM technologies")
    technologies = cursor.fetchall()

    if request.method == 'POST':
        unique_id = str(uuid.uuid4())
        name = request.form['name']
        email = request.form['email']
        mobile = request.form['mobile']
        total_exp = request.form['total_exp']
        relevant_exp = request.form['relevant_exp']
        location = request.form['location']
        relocation = request.form['relocation']
        notice_period = request.form['notice_period']
        ctc = request.form['ctc']
        ectc = request.form['ectc']
        technology_id = request.form['technology']

        file = request.files['resume']
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            filename = f"{unique_id}_{filename}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
        else:
            filename = None

        cursor.execute("""
            INSERT INTO candidates 
            (id, name, email, mobile, total_exp, relevant_exp, location, relocation, notice_period, ctc, ectc, resume, technology_id, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, '1')
        """, (unique_id, name, email, mobile, total_exp, relevant_exp, location, relocation, notice_period, ctc, ectc, filename, technology_id))
        
        connection.commit()
        cursor.close()
        connection.close()
        return "Form submitted successfully!"

    cursor.close()
    connection.close()
    return render_template('form.html', technologies=technologies)


# ---------------------- NEW ROUTE -----------------------

# Route to show interviewer availability form
@app.route('/availability_form', methods=['GET'])
def availability_form():
    connection = get_db_connection()
    cursor = connection.cursor()
    student_id = request.args.get('student_id')
    print(student_id)
    cursor.execute("SELECT id, faculty_name FROM technologies")
    technologies = cursor.fetchall()
    cursor.close()
    connection.close()
    return render_template('availability_form.html', technologies=technologies,student_id=student_id)


# Route to handle availability submission
@app.route('/submit_availability', methods=['POST'])
def submit_availability():   

    tech_id = request.form['faculty_id']
    dates = request.form.getlist('selected_dates[]')  # list of selected dates
    times = request.form.getlist('selected_times[]')  # list of corresponding time slots
    student_id = str(request.form.get('student_id'))
    if len(dates) != len(times):
        return "Mismatch between selected dates and time slots.", 400

    connection = get_db_connection()
    cursor = connection.cursor()

    for date, time_slot in zip(dates, times):
        unique_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO availability (id, technology_id, student_id, date, time_slot)
            VALUES (%s, %s, %s, %s, %s)
        """, (unique_id, tech_id,student_id,date, time_slot))

    connection.commit()
    cursor.close()
    connection.close()  
    return "Availability submitted!"

@app.route('/get_availability', methods=['GET'])
def get_availability():
    student_id = request.args.get('student_id')

    if not student_id:
        return "Missing student_id", 400

    connection = get_db_connection()
    cursor = connection.cursor()

    # Fetch all availability slots for this student
    cursor.execute("""
        SELECT a.id, a.date, a.time_slot, t.faculty_name
        FROM availability a
        JOIN technologies t ON a.technology_id = t.id
        WHERE a.student_id = %s
    """, (student_id,))
    slots = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template('availablity_selection.html', slots=slots, student_id=student_id)


@app.route('/book_slot', methods=['POST'])
def book_slot():
    student_id = request.form.get('student_id')
    availability_id = request.form.get('availability_id')

    if not student_id or not availability_id:
        return "Missing student ID or availability ID", 400

    connection = get_db_connection()
    cursor = connection.cursor()

    # Step 1: Get technology_id, student email, and resume filename
    cursor.execute("SELECT technology_id, email,name,resume FROM candidates WHERE id = %s", (student_id,))
    tech_row = cursor.fetchone()
    if not tech_row:
        cursor.close()
        connection.close()
        return "Invalid student ID", 400

    technology_id = tech_row['technology_id']
    student_email = tech_row['email']
    resume_filename = tech_row['resume']
    student_name=tech_row['name']
    resume_path = os.path.join("uploads/", resume_filename) if resume_filename else None
    print(resume_path)
    # Step 2: Get slot date and time
    cursor.execute("SELECT date, time_slot FROM availability WHERE id = %s", (availability_id,))
    slot = cursor.fetchone()
    if not slot:
        cursor.close()
        connection.close()
        return "Invalid availability_id submitted", 400

    date = slot['date']  # YYYY-MM-DD
    time_slot = slot['time_slot']  # e.g., '13:00 - 14:00'

    # Step 3: Parse start and end times
    try:
        start_str, end_str = [t.strip() for t in time_slot.split(" - ")]
        start_datetime = datetime.strptime(f"{date} {start_str}", "%Y-%m-%d %H:%M")
        end_datetime = datetime.strptime(f"{date} {end_str}", "%Y-%m-%d %H:%M")
    except Exception as e:
        cursor.close()
        connection.close()
        return f"Error parsing time slot: {e}", 400

    # Step 4: Get faculty email using technology_id
    cursor.execute("SELECT faculty_email,name FROM technologies WHERE id = %s", (technology_id,))
    faculty_row = cursor.fetchone()
    if not faculty_row:
        cursor.close()
        connection.close()
        return "Faculty email not found", 500

    faculty_email = faculty_row['faculty_email']
    technology=faculty_row['name']
    # Step 5: Create Google Meet event
    try:
        meet_link = create_google_meet_event(
            summary=f"Interview Invite - {date} Time : {time_slot}  : {technology} Intern - {student_name} ",
            start_time=start_datetime,
            end_time=end_datetime,
            student_email=student_email,
            faculty_email=faculty_email
        )
    except Exception as e:
        cursor.close()
        connection.close()
        return f"Error creating Google Meet: {e}", 500

    # Step 6: Store booking
    booking_id = str(uuid.uuid4())
    cursor.execute("""
        INSERT INTO bookings (id, availability_id, technology_id, candidate_id, meet_link)
        VALUES (%s, %s, %s, %s, %s)
    """, (booking_id, availability_id, technology_id, student_id, meet_link))
    connection.commit()

    cursor.close()
    connection.close()

    # # Step 7: Send email to student and faculty
    # subject = "Interview Slot Confirmed"
    # body = f"""
    #             Dear Candidate and Interviewer,

    #             The interview slot has been successfully booked.

    #             📅 Date: {date}
    #             ⏰ Time: {time_slot}
    #             🔗 Google Meet Link: {meet_link}

    #             The candidate's resume is attached with this email.

    #             Regards,  
    #             TecMantras
    #             """
    # send_meeting_email([student_email, faculty_email], subject, body, attachment_path=resume_path)

    return f"Slot confirmed! Google Meet link: {meet_link}"
# ---------------------- END ROUTE -----------------------

# def send_meeting_email(to_emails, subject, body, attachment_path=None):
#     msg = EmailMessage()
#     msg["Subject"] = subject
#     msg["From"] = os.getenv("EMAIL_ADDRESS")
#     msg["To"] = ", ".join(to_emails)
#     msg.set_content(body)

#     if attachment_path:
#         try:
#             with open(attachment_path, 'rb') as attachment_file:
#                 msg.add_attachment(attachment_file.read(), maintype='application', subtype='octet-stream', filename=os.path.basename(attachment_path))
#         except Exception as e:
#             print(f"Error attaching file: {e}")
#             return False

#     # Sending email using SMTP and starttls() on port 587
#     try:
#         with smtplib.SMTP(os.getenv("EMAIL_HOST"), int(os.getenv("EMAIL_PORT"))) as server:
#             server.starttls()  # Upgrade the connection to a secure encrypted SSL/TLS connection
#             server.login(os.getenv("EMAIL_ADDRESS"), os.getenv("EMAIL_PASSWORD"))
#             server.send_message(msg)
#         return True
#     except Exception as e:
#         print(f"Error sending email: {e}")
#         return False

def create_google_meet_event(summary, start_time, end_time, student_email, faculty_email):
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    import os

    SCOPES = ['https://www.googleapis.com/auth/calendar.events']
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    print(student_email,faculty_email)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    service = build('calendar', 'v3', credentials=creds)
    event = {
        'summary': summary,
        'start': {
            'dateTime': start_time.isoformat(),
            'timeZone': 'Asia/Kolkata',
        },
        'end': {
            'dateTime': end_time.isoformat(),
            'timeZone': 'Asia/Kolkata',
        },
        'attendees': [
            {'email': student_email},
            {'email': faculty_email},  # Add faculty as attendee
        ],
        'conferenceData': {
            'createRequest': {
                'requestId': f"meet-{uuid.uuid4()}",
                'conferenceSolutionKey': {'type': 'hangoutsMeet'},
            }
        }
    }

    event = service.events().insert(
        calendarId='primary',
        body=event,
        conferenceDataVersion=1,
        sendUpdates='all'
    ).execute()

    return event.get('hangoutLink')


if __name__ == '__main__':
    app.run(debug=True)
