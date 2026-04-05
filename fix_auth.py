import os
import json
from google_auth_oauthlib.flow import InstalledAppFlow
from config import YOUTUBE_CLIENT_SECRETS, YOUTUBE_TOKEN_FILE

# This script will handle the Manual Auth flow properly by keeping the flow object alive
# to ensure the code_verifier matches the initial request.

SCOPES = ['https://www.googleapis.com/auth/youtube.upload']

def main():
    if not os.path.exists(YOUTUBE_CLIENT_SECRETS):
        print(f"Error: Missing {YOUTUBE_CLIENT_SECRETS}")
        return

    # Initialize the flow
    flow = InstalledAppFlow.from_client_secrets_file(
        YOUTUBE_CLIENT_SECRETS, 
        SCOPES, 
        redirect_uri='http://localhost:8080/'
    )
    
    # Generate the authorization URL
    auth_url, _ = flow.authorization_url(prompt='consent', access_type='offline')
    
    print("\n--- YOUTUBE AUTHENTICATION ---")
    print("1. Open this URL in your browser and log in with the CORRECT channel:")
    print(f"\n{auth_url}\n")
    print("2. After allowing, you will see a 'Page Not Found' error.")
    print("3. Copy the FULL URL from your browser address bar and paste it below.")
    
    full_url = input("\nPaste the full URL here: ").strip()
    
    try:
        # Extract the code from the URL
        if 'code=' in full_url:
            code = full_url.split('code=')[1].split('&')[0]
            # URL unquoting might be needed if there are special chars, but for standard codes it should be fine
            import urllib.parse
            code = urllib.parse.unquote(code)
            
            # Fetch the token using the SAME flow object (so verifier matches)
            flow.fetch_token(code=code)
            creds = flow.credentials
            
            # Save the credentials
            with open(YOUTUBE_TOKEN_FILE, 'w') as token:
                token.write(creds.to_json())
            
            print(f"\n✅ SUCCESS! Token saved to {YOUTUBE_TOKEN_FILE}")
            print("Now future uploads will go to this channel.")
        else:
            print("\n❌ Error: Could not find 'code' in the URL provided.")
    except Exception as e:
        print(f"\n❌ Error during token fetch: {e}")

if __name__ == "__main__":
    main()
