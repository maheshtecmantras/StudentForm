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
from llm_util import evaluate_candidate
from send_mail import send_review_mail_to_hr,send_feedback_form_to_faculty,send_details_mail_to_hr,send_rejection_mail,send_round2_selection_mail


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
            (id, name, email, mobile, total_exp, relevant_exp, location, relocation, notice_period, ctc, ectc, resume, technology_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (unique_id, name, email, mobile, total_exp, relevant_exp, location, relocation, notice_period, ctc, ectc, filename, technology_id))
        
        connection.commit()
        cursor.close()
        connection.close()
        send_details_mail_to_hr(unique_id)
        return "Form submitted successfully!"

    cursor.close()
    connection.close()
   
    return render_template('form.html', technologies=technologies)


# ---------------------- NEW ROUTE -----------------------
@app.route('/availability_form', methods=['GET'])
def availability_form():
    connection = get_db_connection()
    cursor = connection.cursor()
    
    student_id = request.args.get('student_id')
    round_num = request.args.get('round')  # Default to round 1

    if round_num == "1":
        cursor.execute("""
            SELECT i.name AS interviewer_name
            FROM candidates c
            JOIN interviewer i ON c.round1_interviewer_id = i.id
            WHERE c.id = %s
        """, (student_id,))
    elif round_num == "2":
        cursor.execute("""
            SELECT i.name AS interviewer_name
            FROM candidates c
            JOIN interviewer i ON c.round2_interviewer_id = i.id
            WHERE c.id = %s
        """, (student_id,))
    else:
        interviewer_name = 'Unknown'
        return f"❌ Invalid round number: {round_num}", 400

    result = cursor.fetchone()
    interviewer_name = result['interviewer_name'] if result else 'Unknown'
    cursor.close()
    connection.close()

    return render_template('availability_form.html', interviewer_name=interviewer_name, student_id=student_id,round_num=round_num)


# Route to handle availability submission
@app.route('/submit_availability', methods=['POST'])
def submit_availability():   
    # Get the selected dates and time slots from the form
    dates = request.form.getlist('selected_dates[]')  # list of selected dates
    times = request.form.getlist('selected_times[]')  # list of corresponding time slots
    round = int(request.form.get("round"))
    student_id = str(request.form.get('student_id'))
    if len(dates) != len(times):
        return "Mismatch between selected dates and time slots.", 400

    connection = get_db_connection()
    cursor = connection.cursor()

    for date, time_slot in zip(dates, times):
        unique_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO availability (id, student_id, date, time_slot,round)
            VALUES (%s, %s, %s, %s, %s)
        """, (unique_id, student_id,date, time_slot, round))

    connection.commit()
    cursor.close()
    connection.close()  
    return "Availability submitted!"


@app.route('/get_availability', methods=['GET'])
def get_availability():
    student_id = request.args.get('student_id')
    round_number = request.args.get('round')

    if not student_id or not round_number:
        return "Missing student_id or round", 400

    try:
        round_number = int(round_number)
    except ValueError:
        return "Invalid round number", 400

    if round_number not in [1, 2]:
        return "Round must be 1 or 2", 400

    connection = get_db_connection()
    cursor = connection.cursor()

    # Dynamically pick the correct interviewer column based on round
    interviewer_column = "round1_interviewer_id" if round_number == 1 else "round2_interviewer_id"

    # Build dynamic query using Python formatting only for column name
    query = f"""
        SELECT a.id, a.date, a.time_slot, i.name as interviewer_name
        FROM availability a
        JOIN candidates c ON a.student_id = c.id
        JOIN interviewer i ON c.{interviewer_column} = i.id
        WHERE a.student_id = %s AND a.round = %s
    """

    cursor.execute(query, (student_id, round_number))
    slots = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        'availablity_selection.html',
        slots=slots,
        student_id=student_id,
        round_number=round_number
    )


@app.route('/book_slot', methods=['POST'])
def book_slot():
    student_id = request.form.get('student_id')
    availability_id = request.form.get('availability_id')
    round_number = request.form.get('round')
    try:
        round_number = int(round_number)
        if round_number not in [1, 2]:
            raise ValueError
    except:
        return "Invalid round", 400

    if not student_id or not availability_id:
        return "Missing student ID or availability ID", 400

    connection = get_db_connection()
    cursor = connection.cursor()
    interviewer_id_column = 'round1_interviewer_id' if round_number == 1 else 'round2_interviewer_id'
    # Step 1: Get technology_id, student email, and resume filename
    cursor.execute(
    f"SELECT {interviewer_id_column}, email, candidates.name, t.name as technology_name, candidates.technology_id FROM candidates JOIN technologies t ON candidates.technology_id = t.id WHERE candidates.id = %s",
    (student_id,))
    tech_row = cursor.fetchone()

    if not tech_row:
        cursor.close()
        connection.close()
        return "Invalid student ID", 400
    
    technology_id = tech_row['technology_id']
    student_email = tech_row['email']
    interviewer_id = tech_row[interviewer_id_column]
    student_name=tech_row['name']
    technology_name=tech_row['technology_name']
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
    cursor.execute("SELECT email,name FROM interviewer WHERE id = %s", (interviewer_id,))
    faculty_row = cursor.fetchone()
    if not faculty_row:
        cursor.close()
        connection.close()
        return "Faculty email not found", 500

    faculty_email = faculty_row['email']
    # Step 5: Create Google Meet event
    try:
        meet_link = create_google_meet_event(
            summary=f"Interview Invite - {date} Time : {time_slot}  : {technology_name} Intern - {student_name} ",
            start_time=start_datetime,
            end_time=end_datetime,
            student_email=student_email,
            faculty_email=faculty_email,
            hr_email="hr.tecmantras@gmail.com"
        )
    except Exception as e:
        cursor.close()
        connection.close()
        return f"Error creating Google Meet: {e}", 500

    # Step 6: Store booking
    booking_id = str(uuid.uuid4())
    cursor.execute("""
        INSERT INTO bookings (id, availability_id, technology_id, candidate_id, meet_link,round)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (booking_id, availability_id, technology_id, student_id, meet_link,round_number))
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


    # Send feedback form email to the faculty

    send_feedback_form_to_faculty(faculty_email, student_id,round_number)
    return f"Slot confirmed! Google Meet link: {meet_link}"


@app.route('/feedback_form', methods=['GET', 'POST'])
def feedback_form():
    
    candidate_id = request.args.get('student_id')
    round_number = request.args.get('round')
    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        round_number = int(round_number)
        if round_number not in [1, 2]:
            raise ValueError
    except ValueError:
        return "Invalid round number", 400
    cursor.execute("""
        SELECT candidates.id, technologies.name as technology_name
        FROM candidates 
        JOIN technologies ON candidates.technology_id = technologies.id 
        WHERE candidates.id = %s
    """, (candidate_id,))
    candidate = cursor.fetchone()

    if not candidate:
        cursor.close()
        connection.close()
        return "Candidate not found", 404

    if request.method == 'POST':
        review = request.form['review']
        tech_name = candidate['technology_name']
        decision, description = evaluate_candidate(tech_name, review)
        
        if round_number == 1:
            cursor.execute("""
                UPDATE candidates
                SET round1_review = %s, round1_description = %s, round1_decision = %s
                WHERE id = %s
            """, (review, description, decision, candidate_id))
        else:  # round 2
            cursor.execute("""
                UPDATE candidates
                SET round2_review = %s, round2_description = %s, round2_decision = %s
                WHERE id = %s
            """, (review, description, decision, candidate_id))

        connection.commit()

        # Notify HR
        send_review_mail_to_hr(candidate_id,round_number)

        cursor.close()
        connection.close()
        return "✅ Review submitted and mail sent successfully."



    return render_template("feedback_form.html")

@app.route("/approve_candidate")
def approve_candidate():
    candidate_id = request.args.get("candidate_id")
    round_num = (request.args.get("round"))  # Default to round 1
    connection = get_db_connection()
    cursor = connection.cursor()

    # JOIN interviewer with candidate to get interviewers for the same technology
    cursor.execute("""
        SELECT i.id, i.name
        FROM candidates c
        JOIN interviewer i ON c.technology_id = i.technology_id
        WHERE c.id = %s
    """, (candidate_id,))
    interviewers = cursor.fetchall()
    connection.close()
    return render_template("select_interviewer.html", candidate_id=candidate_id, interviewers=interviewers, round_num=round_num)

@app.route("/assign_interviewer", methods=["POST"])
def assign_interviewer():
    candidate_id = request.form["candidate_id"]
    interviewer_id = request.form["interviewer_id"]
    current_round = request.form["round_num"]
    print('round:',current_round)

    connection = get_db_connection()
    cursor = connection.cursor()
   
    try:
        if current_round == "screening":
            cursor.execute("""
                UPDATE candidates
                SET round1_interviewer_id = %s, status = 2
                WHERE id = %s
            """, (interviewer_id, candidate_id))
        elif current_round == "1":
            cursor.execute("""
                UPDATE candidates
                SET round2_interviewer_id = %s, status = 5
                WHERE id = %s
            """, (interviewer_id, candidate_id))
            send_round2_selection_mail(candidate_id)
        else:
            return "❌ Invalid round", 400
        connection.commit()
        return f"✅ Interviewer for next round assigned successfully!"
    except Exception as e:
        return f"❌ Error assigning interviewer: {e}"
    finally:
        cursor.close()
        connection.close()


@app.route('/reject_candidate')
def reject_candidate():
    candidate_id = request.args.get('candidate_id')
    round_stage = request.args.get('round')  # "1" or "2"
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        if round_stage == "screening":
            # Set rejection reason as 'screening' only, no mail
            cursor.execute("""
                UPDATE candidates
                SET is_rejected = 'screening'
                WHERE id = %s
            """, (candidate_id,))
        elif round_stage == "1":
            # Set rejection reason as 'round1' and send mail
            cursor.execute("""
                UPDATE candidates
                SET is_rejected = 'round1'
                WHERE id = %s
            """, (candidate_id,))
            send_rejection_mail(candidate_id)
            message = "Candidate rejected after Round 1 and email sent."
        connection.commit()
        cursor.close()
        connection.close()
        return f"✅ {message}"

    except Exception as e:
        return f"❌ Error: {e}", 500




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

def create_google_meet_event(summary, start_time, end_time, student_email, faculty_email,hr_email):
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
            {'email': hr_email}  # Add HR as attendee
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
