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
    """
    if not INSTAGRAM_BUSINESS_ACCOUNT_ID or not FACEBOOK_PAGE_ACCESS_TOKEN:
        print("ERROR: Instagram credentials missing.")
        return {"success": False, "message": "Missing credentials"}

    print(f"IG: Starting upload for {video_path}")

    # Step 0: Get Public URL via Catbox (Failsafe for Drive Quota)
    public_video_url = None
    try:
        print("IG: Uploading to temporary host (Catbox)...")
        with open(video_path, "rb") as f:
            files = {
                "reqtype": (None, "fileupload"),
                "fileToUpload": (os.path.basename(video_path), f, "video/mp4")
            }
            response = requests.post("https://catbox.moe/user/api.php", files=files)
            
        if response.status_code == 200 and response.text.startswith("http"):
            public_video_url = response.text.strip()
            print(f"IG: Temporary URL created: {public_video_url}")
        else:
            raise Exception(f"Catbox upload failed: {response.text}")
    except Exception as e:
        print(f"IG: Temporary upload failed: {e}")
        return {"success": False, "message": f"Temp upload failed: {e}"}

    if isinstance(content, str):
        caption = content
    else:
        caption = f"{content.get('title', '')}\n\n{content.get('hashtags', '')}"

    # Step 1: Create Container
    print("IG: Creating media container...")
    url_container = f"https://graph.facebook.com/v19.0/{INSTAGRAM_BUSINESS_ACCOUNT_ID}/media"
    payload = {
        "media_type": "REELS",
        "video_url": public_video_url,
        "caption": caption,
        "access_token": FACEBOOK_PAGE_ACCESS_TOKEN,
    }

    container_res = requests.post(url_container, data=payload).json()
    if "id" not in container_res:
        print(f"IG ERROR: Container creation failed: {container_res}")
        return {"success": False, "message": str(container_res)}

    creation_id = container_res["id"]
    print(f"IG: Container created: {creation_id}. Checking status...")

    # Step 2: Check Status
    url_status = f"https://graph.facebook.com/v19.0/{creation_id}?fields=status_code&access_token={FACEBOOK_PAGE_ACCESS_TOKEN}"
    for i in range(40): # 200 seconds max
        status_res = requests.get(url_status).json()
        status_code = status_res.get("status_code")
        print(f"IG: Status Check {i+1}: {status_code}")
        if status_code == "FINISHED":
            break
        elif status_code == "ERROR":
            print(f"IG ERROR: Processing failed: {status_res}")
            return {"success": False, "message": "Processing ERROR"}
        time.sleep(5)

    # Step 3: Publish
    print("IG: Publishing reel...")
    url_publish = f"https://graph.facebook.com/v19.0/{INSTAGRAM_BUSINESS_ACCOUNT_ID}/media_publish"
    publish_payload = {"creation_id": creation_id, "access_token": FACEBOOK_PAGE_ACCESS_TOKEN}
    publish_res = requests.post(url_publish, data=publish_payload).json()

    if "id" in publish_res:
        media_id = publish_res['id']
        print(f"IG SUCCESS: Published. ID: {media_id}")
        
        # Step 4: Get Public Permalink
        try:
            url_link = f"https://graph.facebook.com/v19.0/{media_id}?fields=permalink&access_token={FACEBOOK_PAGE_ACCESS_TOKEN}"
            link_res = requests.get(url_link).json()
            public_url = link_res.get("permalink", f"https://www.instagram.com/reels/{media_id}/")
            print(f"IG: Public URL: {public_url}")
            return {
                "success": True,
                "media_id": media_id,
                "url": public_url,
            }
        except Exception as e:
            print(f"IG: Failed to fetch permalink: {e}")
            return {
                "success": True,
                "media_id": media_id,
                "url": f"https://www.instagram.com/reels/{media_id}/",
            }
    
    print(f"IG ERROR: Publish failed: {publish_res}")
    return {"success": False, "message": str(publish_res)}
