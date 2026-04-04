import os
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from config import YOUTUBE_CLIENT_SECRETS, YOUTUBE_TOKEN_FILE

# If modifying these scopes, delete the file youtube_token.json.
SCOPES = ['https://www.googleapis.com/auth/youtube.upload']

def main():
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists(YOUTUBE_TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(YOUTUBE_TOKEN_FILE, SCOPES)
        
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing expired credentials...")
            creds.refresh(Request())
        else:
            if not os.path.exists(YOUTUBE_CLIENT_SECRETS):
                print(f"Error: Missing {YOUTUBE_CLIENT_SECRETS}.")
                print("1. Go to Google Cloud Console.")
                print("2. Create an OAuth 2.0 Client ID (Desktop App).")
                print(f"3. Download JSON and rename to '{YOUTUBE_CLIENT_SECRETS}'.")
                return
                
            print("Launching browser for YouTube Authentication...")
            flow = InstalledAppFlow.from_client_secrets_file(YOUTUBE_CLIENT_SECRETS, SCOPES)
            creds = flow.run_local_server(port=8080)
            
        # Save the credentials for the next run
        print(f"Saving credentials to {YOUTUBE_TOKEN_FILE}...")
        with open(YOUTUBE_TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
            
    print("YouTube Authentication Successful! You can now run the main script.")

if __name__ == '__main__':
    main()
