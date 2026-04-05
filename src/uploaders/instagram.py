import os
import sys
import requests
import time

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
from config import INSTAGRAM_BUSINESS_ACCOUNT_ID, FACEBOOK_PAGE_ACCESS_TOKEN


def upload_instagram(video_path, content):
    """
    Uploads a video to Instagram as a Reel.
    Note: Instagram requires the video to be publicly accessible via URL.
    Google Drive service accounts may not have storage quota - in that case, returns mock.
    """
    if not INSTAGRAM_BUSINESS_ACCOUNT_ID or not FACEBOOK_PAGE_ACCESS_TOKEN:
        raise ValueError(
            "Missing INSTAGRAM_BUSINESS_ACCOUNT_ID or FACEBOOK_PAGE_ACCESS_TOKEN"
        )

    print(f"Preparing to upload {video_path} to Instagram...")

    # Try to upload to Drive first
    public_video_url = None
    try:
        from src.drive_manager import upload_to_drive_and_get_link

        public_video_url = upload_to_drive_and_get_link(video_path)
        print(f"Video uploaded to Drive: {public_video_url}")
    except Exception as e:
        print(f"Drive upload failed: {e}")
        print(
            "WARNING: Instagram API requires a PUBLIC URL. Skipping Instagram upload."
        )
        return {"success": False, "message": f"Drive upload failed: {e}"}

    if isinstance(content, str):
        caption = content
    else:
        caption = (
            content.get("title", "")
            + "\n"
            + content.get("description", "")
            + f"\n\n{content.get('hashtags', '')}"
        )

    # Step 1: Create Container
    url_container = (
        f"https://graph.facebook.com/v19.0/{INSTAGRAM_BUSINESS_ACCOUNT_ID}/media"
    )

    payload = {
        "media_type": "REELS",
        "video_url": public_video_url,
        "caption": caption,
        "access_token": FACEBOOK_PAGE_ACCESS_TOKEN,
    }

    container_res = requests.post(url_container, data=payload).json()
    print(f"Container response: {container_res}")

    if "id" not in container_res:
        raise Exception(f"Failed to create IG container: {container_res}")

    creation_id = container_res["id"]
    print(f"Container created: {creation_id}. Waiting for processing...")

    # Step 2: Check processing status
    url_status = f"https://graph.facebook.com/v19.0/{creation_id}?fields=status_code&access_token={FACEBOOK_PAGE_ACCESS_TOKEN}"

    max_attempts = 60
    for i in range(max_attempts):
        status_res = requests.get(url_status).json()
        status_code = status_res.get("status_code")
        print(f"Status check {i + 1}: {status_code}")
        if status_code == "FINISHED":
            break
        elif status_code == "ERROR":
            raise Exception(f"IG container processing failed: {status_res}")
        time.sleep(5)

    # Step 3: Publish
    url_publish = f"https://graph.facebook.com/v19.0/{INSTAGRAM_BUSINESS_ACCOUNT_ID}/media_publish"

    publish_payload = {
        "creation_id": creation_id,
        "access_token": FACEBOOK_PAGE_ACCESS_TOKEN,
    }

    publish_res = requests.post(url_publish, data=publish_payload).json()
    print(f"Publish response: {publish_res}")

    if "id" in publish_res:
        ig_media_id = publish_res["id"]
        print("Instagram upload complete!")
        return {
            "success": True,
            "media_id": ig_media_id,
            "url": f"https://www.instagram.com/reel/{ig_media_id}",
        }
    else:
        raise Exception(f"Failed to publish IG container: {publish_res}")
