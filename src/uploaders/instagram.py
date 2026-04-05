import os
import sys
import requests
import time
import logging
from datetime import datetime

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
from config import INSTAGRAM_BUSINESS_ACCOUNT_ID, FACEBOOK_PAGE_ACCESS_TOKEN

logger = logging.getLogger(__name__)

# ── Error Log Setup ──────────────────────────────────────────────────────────
ERROR_LOG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "logs", "instagram_upload_errors.txt"
)
os.makedirs(os.path.dirname(ERROR_LOG_PATH), exist_ok=True)


def _log_error(video_name, host_used, status, error_message):
    """Write a structured error entry to the instagram error log."""
    with open(ERROR_LOG_PATH, "a") as f:
        f.write(
            f"[{datetime.now().isoformat()}] "
            f"video={video_name} | host={host_used} | "
            f"status={status} | error={error_message}\n"
        )


# ── Temp Hosting Functions ───────────────────────────────────────────────────

def _upload_catbox(video_path):
    """Primary host: catbox.moe"""
    with open(video_path, "rb") as f:
        files = {
            "reqtype": (None, "fileupload"),
            "fileToUpload": (os.path.basename(video_path), f, "video/mp4")
        }
        response = requests.post("https://catbox.moe/user/api.php", files=files, timeout=120)
    if response.status_code == 200 and response.text.strip().startswith("http"):
        return response.text.strip()
    raise Exception(f"Catbox failed: {response.text[:200]}")


def _upload_fileio(video_path):
    """Backup host 1: file.io (auto-expire after 1 download)"""
    with open(video_path, "rb") as f:
        response = requests.post(
            "https://file.io/?expires=1h",
            files={"file": (os.path.basename(video_path), f, "video/mp4")},
            timeout=120
        )
    data = response.json()
    if data.get("success") and data.get("link"):
        return data["link"]
    raise Exception(f"file.io failed: {data}")


def _upload_transfersh(video_path):
    """Backup host 2: transfer.sh"""
    filename = os.path.basename(video_path)
    with open(video_path, "rb") as f:
        response = requests.put(
            f"https://transfer.sh/{filename}",
            data=f,
            headers={"Max-Days": "1"},
            timeout=120
        )
    if response.status_code == 200 and response.text.strip().startswith("http"):
        return response.text.strip()
    raise Exception(f"transfer.sh failed: {response.text[:200]}")


# ── Main Upload Flow ─────────────────────────────────────────────────────────

HOSTS = [
    ("catbox.moe", _upload_catbox),
    ("file.io", _upload_fileio),
    ("transfer.sh", _upload_transfersh),
]

MAX_RETRIES = 3
RETRY_DELAY = 30  # seconds


def _get_public_url(video_path):
    """
    Try each host with up to MAX_RETRIES attempts.
    Returns (url, host_name) or raises Exception.
    """
    video_name = os.path.basename(video_path)

    for host_name, upload_fn in HOSTS:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                print(f"IG: Uploading to {host_name} (attempt {attempt}/{MAX_RETRIES})...")
                url = upload_fn(video_path)
                print(f"IG: ✅ URL from {host_name}: {url}")
                return url, host_name
            except Exception as e:
                print(f"IG: ❌ {host_name} attempt {attempt} failed: {e}")
                _log_error(video_name, host_name, f"attempt_{attempt}_fail", str(e))
                if attempt < MAX_RETRIES:
                    print(f"IG: Waiting {RETRY_DELAY}s before retry...")
                    time.sleep(RETRY_DELAY)

        print(f"IG: All {MAX_RETRIES} attempts failed on {host_name}. Trying next host...")

    raise Exception("All hosts exhausted. Instagram upload aborted.")


def upload_instagram(video_path, content):
    """
    Uploads a video to Instagram as a Reel with full failsafe.
    Returns dict with success, media_id, url.
    """
    if not INSTAGRAM_BUSINESS_ACCOUNT_ID or not FACEBOOK_PAGE_ACCESS_TOKEN:
        return {"success": False, "message": "Missing credentials"}

    video_name = os.path.basename(video_path)
    print(f"IG: Starting upload for {video_path}")

    # ── Step 0: Get Public URL (with retry + fallback hosts) ─────────────────
    try:
        public_video_url, host_used = _get_public_url(video_path)
    except Exception as e:
        _log_error(video_name, "all_hosts", "TOTAL_FAIL", str(e))
        return {"success": False, "message": str(e)}

    # ── Build Caption ─────────────────────────────────────────────────────────
    if isinstance(content, str):
        caption = content
    else:
        caption = f"{content.get('title', '')}\n\n{content.get('hashtags', '')}"

    # ── Step 1: Create Media Container ───────────────────────────────────────
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
        err = str(container_res)
        _log_error(video_name, host_used, "CONTAINER_FAIL", err)
        return {"success": False, "message": err}

    creation_id = container_res["id"]
    print(f"IG: Container created: {creation_id}")

    # ── Step 2: Poll Processing Status ───────────────────────────────────────
    url_status = (
        f"https://graph.facebook.com/v19.0/{creation_id}"
        f"?fields=status_code&access_token={FACEBOOK_PAGE_ACCESS_TOKEN}"
    )
    for i in range(40):  # max 200 seconds
        status_res = requests.get(url_status).json()
        status_code = status_res.get("status_code")
        print(f"IG: Status Check {i+1}: {status_code}")
        if status_code == "FINISHED":
            break
        elif status_code == "ERROR":
            err = f"IG processing error: {status_res}"
            _log_error(video_name, host_used, "PROCESSING_ERROR", err)
            return {"success": False, "message": err}
        time.sleep(5)

    # ── Step 3: Publish ───────────────────────────────────────────────────────
    print("IG: Publishing reel...")
    url_publish = f"https://graph.facebook.com/v19.0/{INSTAGRAM_BUSINESS_ACCOUNT_ID}/media_publish"
    publish_res = requests.post(
        url_publish,
        data={"creation_id": creation_id, "access_token": FACEBOOK_PAGE_ACCESS_TOKEN}
    ).json()

    if "id" not in publish_res:
        err = str(publish_res)
        _log_error(video_name, host_used, "PUBLISH_FAIL", err)
        return {"success": False, "message": err}

    media_id = publish_res["id"]
    print(f"IG SUCCESS: Published. ID: {media_id} via {host_used}")

    # ── Step 4: Fetch Public Permalink ────────────────────────────────────────
    try:
        url_link = (
            f"https://graph.facebook.com/v19.0/{media_id}"
            f"?fields=permalink&access_token={FACEBOOK_PAGE_ACCESS_TOKEN}"
        )
        link_res = requests.get(url_link).json()
        public_url = link_res.get("permalink", f"https://www.instagram.com/reels/{media_id}/")
    except Exception:
        public_url = f"https://www.instagram.com/reels/{media_id}/"

    print(f"IG: Public URL: {public_url}")
    return {"success": True, "media_id": media_id, "url": public_url, "host": host_used}
