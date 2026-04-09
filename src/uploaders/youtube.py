import os
import sys
import logging

# Ensure we can import from config
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from config import YOUTUBE_TOKEN_FILE

logger = logging.getLogger(__name__)


def _get_authenticated_service():
    """
    Loads YouTube credentials and auto-refreshes if expired.
    Returns (youtube_service, credentials).
    """
    if not os.path.exists(YOUTUBE_TOKEN_FILE):
        raise FileNotFoundError(
            f"Missing {YOUTUBE_TOKEN_FILE}. Run auth_youtube.py first to authenticate."
        )

    creds = Credentials.from_authorized_user_file(
        YOUTUBE_TOKEN_FILE, ["https://www.googleapis.com/auth/youtube.upload"]
    )

    # Auto-refresh expired credentials
    if creds and creds.expired and creds.refresh_token:
        logger.info("YouTube token expired — refreshing...")
        try:
            creds.refresh(Request())
            # Save refreshed credentials back to file
            with open(YOUTUBE_TOKEN_FILE, "w") as token_file:
                token_file.write(creds.to_json())
            logger.info("YouTube token refreshed and saved successfully.")
        except Exception as e:
            raise RuntimeError(
                f"Failed to refresh YouTube token. Re-run auth_youtube.py. Error: {e}"
            )

    if not creds or not creds.valid:
        raise RuntimeError(
            "YouTube credentials are invalid and cannot be refreshed. "
            "Please run auth_youtube.py again to re-authenticate."
        )

    youtube = build("youtube", "v3", credentials=creds)
    return youtube


def upload_youtube(video_path, content):
    """
    Uploads the video to YouTube using authenticated credentials.
    Auto-refreshes token if expired.
    Returns the video URL if successful, otherwise raises Exception.
    """
    youtube = _get_authenticated_service()

    # Build tags list safely
    tags_raw = content.get("tags", "")
    tags_list = [t.strip() for t in tags_raw.split(",") if t.strip()]
    # Limit to 500 chars total for tags (YouTube limit)
    tags_list = tags_list[:20]  # Max 20 tags

    # Build description with hashtags
    description = content.get("description", "")
    hashtags = content.get("hashtags", "")
    if hashtags and hashtags not in description:
        description = f"{description}\n\n{hashtags}"

    body = {
        "snippet": {
            "title": content.get("title", "Untitled")[:100],  # Max 100 chars
            "description": description[:5000],  # Max 5000 chars
            "tags": tags_list,
            "categoryId": "22",  # People & Blogs
        },
        "status": {
            "privacyStatus": "public",
        },
    }

    media = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True)

    request = youtube.videos().insert(
        part=",".join(body.keys()),
        body=body,
        media_body=media,
    )

    logger.info(f"Uploading to YouTube: {content.get('title', 'Untitled')}")

    response = None
    while response is None:
        try:
            status, response = request.next_chunk()
            if status:
                logger.info(f"YouTube upload progress: {int(status.progress() * 100)}%")
        except Exception as e:
            logger.error(f"YouTube upload failed during chunk transfer: {e}")
            raise

    video_id = response.get("id")
    url = f"https://youtube.com/shorts/{video_id}"
    logger.info(f"YouTube upload successful: {url}")
    return url
