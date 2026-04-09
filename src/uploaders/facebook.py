import logging
import requests
import time

import config


logger = logging.getLogger(__name__)


def upload_video(video_file, title, description):
    """
    Uploads a video to a Facebook Page using the Graph API.
    Uses resumable upload for large files (>50MB).
    """
    if not config.FACEBOOK_PAGE_ACCESS_TOKEN or not config.FACEBOOK_PAGE_ID:
        return {"success": False, "message": "Facebook credentials not configured. Set FACEBOOK_PAGE_ACCESS_TOKEN and FACEBOOK_PAGE_ID in .env"}

    # Get file size for upload strategy
    try:
        file_size = os.path.getsize(video_file)
    except Exception:
        file_size = 0

    # Use Graph API v21.0 (latest stable)
    api_version = "v21.0"
    base_url = f"https://graph.facebook.com/{api_version}/{config.FACEBOOK_PAGE_ID}/videos"

    # For files > 50MB, use resumable upload (start/upload/finish flow)
    RESUMABLE_THRESHOLD = 50 * 1024 * 1024  # 50 MB

    if file_size > RESUMABLE_THRESHOLD:
        return _upload_resumable(base_url, video_file, title, description)
    else:
        return _upload_simple(base_url, video_file, title, description)


def _upload_simple(url, video_file, title, description):
    """Simple single-request upload for smaller files."""
    import os

    payload = {
        "title": title,
        "description": description,
        "access_token": config.FACEBOOK_PAGE_ACCESS_TOKEN,
    }

    try:
        with open(video_file, "rb") as f:
            files = {"source": f}
            response = requests.post(url, data=payload, files=files, timeout=600)

        if response.status_code != 200:
            error_data = response.json()
            error_msg = error_data.get("error", {}).get("message", f"HTTP {response.status_code}")
            logger.error(f"Facebook upload failed: {error_msg}")
            return {"success": False, "message": error_msg}

        result = response.json()
        video_id = result.get("id")
        video_url = f"https://www.facebook.com/watch/?v={video_id}"

        logger.info(f"Video uploaded to Facebook: {video_id} -> {video_url}")
        return {
            "success": True,
            "message": f"Video ID: {video_id}",
            "video_id": video_id,
            "url": video_url,
        }

    except requests.RequestException as e:
        error_msg = f"Upload failed: {str(e)}"
        logger.error(error_msg)
        return {"success": False, "message": error_msg}


def _upload_resumable(base_url, video_file, title, description):
    """
    Resumable upload for large files using Facebook's start/upload/finish flow.
    """
    import os

    access_token = config.FACEBOOK_PAGE_ACCESS_TOKEN
    file_size = os.path.getsize(video_file)

    try:
        # Step 1: Start upload session
        start_payload = {
            "upload_phase": "start",
            "file_size": file_size,
            "access_token": access_token,
        }
        start_res = requests.post(base_url, data=start_payload, timeout=30).json()
        video_id = start_res.get("video_id")
        upload_session_id = start_res.get("upload_session_id")

        if not video_id:
            error_msg = f"Failed to start resumable upload: {start_res}"
            logger.error(error_msg)
            return {"success": False, "message": error_msg}

        logger.info(f"Facebook resumable upload started: video_id={video_id}")

        # Step 2: Upload binary data in chunks
        chunk_size = 10 * 1024 * 1024  # 10 MB chunks
        upload_payload = {
            "upload_phase": "upload",
            "upload_session_id": upload_session_id,
            "start_offset": "0",
            "access_token": access_token,
            "video_file_chunk": (os.path.basename(video_file), open(video_file, "rb"), "video/mp4"),
        }

        upload_res = requests.post(
            f"https://rupload.facebook.com/video-upload/v21.0/{video_id}",
            data=upload_payload,
            timeout=600,
        ).json()

        if upload_res.get("success") is not True:
            error_msg = f"Chunk upload failed: {upload_res}"
            logger.error(error_msg)
            return {"success": False, "message": error_msg}

        logger.info("Facebook video chunks uploaded successfully.")

        # Step 3: Finish upload
        finish_payload = {
            "upload_phase": "finish",
            "upload_session_id": upload_session_id,
            "access_token": access_token,
            "title": title,
            "description": description,
        }
        finish_res = requests.post(base_url, data=finish_payload, timeout=60).json()

        final_video_id = finish_res.get("id") or finish_res.get("video_id") or video_id
        video_url = f"https://www.facebook.com/watch/?v={final_video_id}"

        logger.info(f"Facebook resumable upload complete: {final_video_id}")
        return {
            "success": True,
            "message": f"Video ID: {final_video_id}",
            "video_id": final_video_id,
            "url": video_url,
        }

    except Exception as e:
        error_msg = f"Resumable upload failed: {str(e)}"
        logger.error(error_msg)
        return {"success": False, "message": error_msg}
