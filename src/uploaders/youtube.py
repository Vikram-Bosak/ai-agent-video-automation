import os
import sys
# Ensure we can import from config
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from config import YOUTUBE_TOKEN_FILE

def upload_youtube(video_path, content):
    """
    Uploads the video to YouTube using the authenticated credentials.
    Returns the video URL if successful, otherwise raises Exception/returns None.
    """
    if not os.path.exists(YOUTUBE_TOKEN_FILE):
        raise FileNotFoundError(f"Missing {YOUTUBE_TOKEN_FILE}. Run auth_youtube.py first.")

    creds = Credentials.from_authorized_user_file(YOUTUBE_TOKEN_FILE, ['https://www.googleapis.com/auth/youtube.upload'])
    youtube = build('youtube', 'v3', credentials=creds)

    body = {
        'snippet': {
            'title': content.get('title', 'Untitled'),
            'description': content.get('description', '') + f"\n\n{content.get('hashtags', '')}",
            'tags': [t.strip() for t in content.get('tags', '').split(',')],
            'categoryId': '22' # 22 is People & Blogs. Adjust as necessary.
        },
        'status': {
            'privacyStatus': 'public',
            # Short videos are automatically classified as Shorts
        }
    }

    media = MediaFileUpload(video_path, mimetype='video/mp4', resumable=True)

    print(f"Uploading {video_path} to YouTube...")
    request = youtube.videos().insert(
        part=','.join(body.keys()),
        body=body,
        media_body=media
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Uploaded {int(status.progress() * 100)}%")

    print("YouTube upload complete.")
    video_id = response.get('id')
    return f"https://youtube.com/shorts/{video_id}"
