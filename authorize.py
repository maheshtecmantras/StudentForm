from __future__ import print_function
import os.path
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials

# ✅ Required scopes for Calendar with Meet link creation
SCOPES = ['https://www.googleapis.com/auth/calendar.events']

def main():
    """Generates token.json with required scopes."""
    creds = None

    # If token already exists and is valid, use it
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    # If token is not valid, refresh or re-authenticate
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # Load credentials.json and create new token
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)

        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    print("✅ Token generated and saved to token.json.")

if __name__ == '__main__':
    main()
