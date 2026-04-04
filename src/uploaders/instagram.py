import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import requests
import time
from config import INSTAGRAM_BUSINESS_ACCOUNT_ID, FACEBOOK_PAGE_ACCESS_TOKEN

def upload_instagram(video_path, content):
    """
    Uploads a video to Instagram as a Reel.
    This requires a Facebook Page Access Token and the associated Instagram Business Account ID.
    NOTE: Instagram API requires the video to be publicly hosted. We cannot upload a local file directly.
    In a real scenario, you either upload to AWS S3/Drive first, or use an unofficial library.
    For this boilerplate, we'll simulate an S3 upload or return a mock if it can't be done directly.
    """
    if not INSTAGRAM_BUSINESS_ACCOUNT_ID or not FACEBOOK_PAGE_ACCESS_TOKEN:
        raise ValueError("Missing INSTAGRAM_BUSINESS_ACCOUNT_ID or FACEBOOK_PAGE_ACCESS_TOKEN")

    print(f"Preparing to upload {video_path} to Instagram...")

    # Instagram API needs a public 'video_url', not a local file.
    # To truly use this via Graph API, you must temporarily host `video_path` publicly.
    # For now, we will raise a NotImplementedError or mock it to let the user know.
    # You would use AWS boto3, or Google Cloud Storage to get a public URL here.
    
    # public_video_url = upload_to_s3(video_path)
    public_video_url = "MOCK_URL_WAITING_FOR_HOSTING"
    
    if public_video_url == "MOCK_URL_WAITING_FOR_HOSTING":
        print("WARNING: Instagram API requires a PUBLIC URL. Skipping actual upload because no public URL mechanism is provided. Returning mock link.")
        return f"https://instagram.com/p/MOCK_ID"

    # Step 1: Create Container
    url_container = f"https://graph.facebook.com/v19.0/{INSTAGRAM_BUSINESS_ACCOUNT_ID}/media"
    
    payload = {
        'media_type': 'REELS',
        'video_url': public_video_url,
        'caption': content.get('title', '') + "\n" + content.get('description', '') + f"\n\n{content.get('hashtags', '')}",
        'access_token': FACEBOOK_PAGE_ACCESS_TOKEN
    }
    
    container_res = requests.post(url_container, data=payload).json()
    if 'id' not in container_res:
         raise Exception(f"Failed to create IG container: {container_res}")
    
    creation_id = container_res['id']
    print(f"Container created: {creation_id}. Waiting for processing...")
    
    # Step 2: Check processing status
    url_status = f"https://graph.facebook.com/v19.0/{creation_id}?fields=status_code&access_token={FACEBOOK_PAGE_ACCESS_TOKEN}"
    while True:
        status_res = requests.get(url_status).json()
        status_code = status_res.get('status_code')
        if status_code == 'FINISHED':
             break
        elif status_code == 'ERROR':
             raise Exception(f"IG container processing failed: {status_res}")
        time.sleep(5)
    
    # Step 3: Publish
    url_publish = f"https://graph.facebook.com/v19.0/{INSTAGRAM_BUSINESS_ACCOUNT_ID}/media_publish"
    publish_payload = {
        'creation_id': creation_id,
        'access_token': FACEBOOK_PAGE_ACCESS_TOKEN
    }
    
    publish_res = requests.post(url_publish, data=publish_payload).json()
    if 'id' in publish_res:
        ig_media_id = publish_res['id']
        print("Instagram upload complete.")
        return f"https://instagram.com/p/{ig_media_id}" # ID format varies, this is a placeholder
    else:
        raise Exception(f"Failed to publish IG container: {publish_res}")
