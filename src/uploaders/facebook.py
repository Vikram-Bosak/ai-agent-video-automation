import logging
import requests

import config


logger = logging.getLogger(__name__)


def upload_video(video_file, title, description):
    if not config.FACEBOOK_PAGE_ACCESS_TOKEN or not config.FACEBOOK_PAGE_ID:
        return {"success": False, "message": "Facebook credentials not configured"}

    url = f"https://graph.facebook.com/v18.0/{config.FACEBOOK_PAGE_ID}/videos"

    payload = {
        "title": title,
        "description": description,
        "access_token": config.FACEBOOK_PAGE_ACCESS_TOKEN,
    }

    try:
        with open(video_file, "rb") as f:
            files = {"source": f}
            response = requests.post(url, data=payload, files=files, timeout=300)

        response.raise_for_status()
        result = response.json()

        video_id = result.get("id")
        logger.info(f"Video uploaded to Facebook: {video_id}")
        return {
            "success": True,
            "message": f"Video ID: {video_id}",
            "video_id": video_id,
        }

    except requests.RequestException as e:
        error_msg = f"Upload failed: {str(e)}"
        logger.error(error_msg)
        return {"success": False, "message": error_msg}
