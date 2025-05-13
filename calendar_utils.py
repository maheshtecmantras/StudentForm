from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from datetime import datetime, timedelta, UTC
import os

# If modifying these SCOPES, delete the token.json file.
SCOPES = ['https://www.googleapis.com/auth/calendar.events']

def get_calendar_service():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    else:
        flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
        creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('calendar', 'v3', credentials=creds)

def create_event(student_name, student_email, interviewer_email, resume_link=None):
    service = get_calendar_service()

    # Use timezone-aware UTC datetime
    now = datetime.now(UTC) + timedelta(days=1)
    start_time_utc = now.replace(hour=10, minute=30, second=0, microsecond=0)
    end_time_utc = start_time_utc + timedelta(minutes=30)

    event = {
        'summary': f"Interview: {student_name}",
        'location': 'Google Meet',
        'description': f"""
New candidate added for interview.

Name: {student_name}
Email: {student_email}
Resume: {resume_link or 'Attached in email'}

Please select a time if this works for you.
""",
        'start': {
            'dateTime': start_time_utc.isoformat(),
            'timeZone': 'Asia/Kolkata',
        },
        'end': {
            'dateTime': end_time_utc.isoformat(),
            'timeZone': 'Asia/Kolkata',
        },
        'attendees': [
            {'email': interviewer_email},
        ],
        'reminders': {
            'useDefault': True,
        },
    }

    event = service.events().insert(calendarId='primary', body=event, sendUpdates='all').execute()
    return event.get('htmlLink')

if __name__ == '__main__':
    print(create_event('Het', 'hetthakkar158@gmail.com', 'divyab.tecmantras@gmail.com'))
