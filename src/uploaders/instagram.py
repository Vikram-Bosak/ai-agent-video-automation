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
    "logs",
    "instagram_upload_errors.txt",
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


# ── Graph API Version (keep consistent with facebook.py) ─────────────────────
GRAPH_API_VERSION = "v21.0"


# ── Temp Hosting Functions ───────────────────────────────────────────────────

def _upload_catbox(video_path):
    """Primary host: catbox.moe"""
    with open(video_path, "rb") as f:
        files = {
            "reqtype": (None, "fileupload"),
            "fileToUpload": (os.path.basename(video_path), f, "video/mp4"),
        }
        response = requests.post(
            "https://catbox.moe/user/api.php", files=files, timeout=120
        )
    if response.status_code == 200 and response.text.strip().startswith("http"):
        return response.text.strip()
    raise Exception(f"Catbox failed: {response.text[:200]}")


def _upload_litterbox(video_path):
    """Backup host: litterbox.catbox.moe (temporary upload, auto-delete)"""
    with open(video_path, "rb") as f:
        files = {
            "reqtype": (None, "fileupload"),
            "time": (None, "24h"),  # Delete after 24 hours
            "fileToUpload": (os.path.basename(video_path), f, "video/mp4"),
        }
        response = requests.post(
            "https://litterbox.catbox.moe/resources/internals/api.php", files=files, timeout=120
        )
    if response.status_code == 200 and response.text.strip().startswith("http"):
        return response.text.strip()
    raise Exception(f"Litterbox failed: {response.text[:200]}")


def _upload_transfersh(video_path):
    """Backup host: transfer.sh"""
    filename = os.path.basename(video_path)
    with open(video_path, "rb") as f:
        response = requests.put(
            f"https://transfer.sh/{filename}",
            data=f,
            headers={"Max-Days": "1"},
            timeout=120,
        )
    if response.status_code == 200 and response.text.strip().startswith("http"):
        return response.text.strip()
    raise Exception(f"transfer.sh failed: {response.text[:200]}")


def _upload_gofile(video_path):
    """Backup host: gofile.io"""
    # Step 1: Get server
    server = "store1.gofile.io"
    try:
        server_res = requests.get("https://api.gofile.io/getServer", timeout=10)
        if server_res.status_code == 200:
            server_data = server_res.json()
            if server_data.get("status") == "ok":
                server = server_data.get("data", {}).get("server", server)
    except Exception:
        pass

    # Step 2: Upload
    with open(video_path, "rb") as f:
        response = requests.post(
            f"https://{server}/uploadFile",
            files={"file": (os.path.basename(video_path), f, "video/mp4")},
            timeout=180,
        )
    data = response.json()
    if data.get("status") == "ok":
        file_data = data.get("data", {})
        download_page = file_data.get("downloadPage") or file_data.get("link")
        if download_page:
            return download_page
    raise Exception(f"gofile.io failed: {data}")


# ── Main Upload Flow ─────────────────────────────────────────────────────────

HOSTS = [
    ("catbox.moe", _upload_catbox),
    ("litterbox.catbox.moe", _upload_litterbox),
    ("gofile.io", _upload_gofile),
    ("transfer.sh", _upload_transfersh),
]

MAX_RETRIES = 3
RETRY_DELAY = 15  # seconds


def _get_public_url(video_path):
    """
    Try each host with up to MAX_RETRIES attempts.
    Returns (url, host_name) or raises Exception.
    """
    video_name = os.path.basename(video_path)

    for host_name, upload_fn in HOSTS:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                logger.info(f"IG: Uploading to {host_name} (attempt {attempt}/{MAX_RETRIES})...")
                url = upload_fn(video_path)
                logger.info(f"IG: Got URL from {host_name}: {url}")
                return url, host_name
            except Exception as e:
                logger.warning(f"IG: {host_name} attempt {attempt} failed: {e}")
                _log_error(video_name, host_name, f"attempt_{attempt}_fail", str(e))
                if attempt < MAX_RETRIES:
                    logger.info(f"IG: Waiting {RETRY_DELAY}s before retry...")
                    time.sleep(RETRY_DELAY)

        logger.warning(f"IG: All {MAX_RETRIES} attempts failed on {host_name}. Trying next host...")

    raise Exception("All temporary hosting services failed. Instagram upload aborted.")


def upload_instagram(video_path, content):
    """
    Uploads a video to Instagram as a Reel with full failsafe.
    Returns dict with success, media_id, url.
    """
    if not INSTAGRAM_BUSINESS_ACCOUNT_ID or not FACEBOOK_PAGE_ACCESS_TOKEN:
        return {"success": False, "message": "Missing Instagram credentials. Set INSTAGRAM_BUSINESS_ACCOUNT_ID and FACEBOOK_PAGE_ACCESS_TOKEN in .env"}

    video_name = os.path.basename(video_path)
    logger.info(f"IG: Starting upload for {video_name}")

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
    url_container = (
        f"https://graph.facebook.com/{GRAPH_API_VERSION}/{INSTAGRAM_BUSINESS_ACCOUNT_ID}/media"
    )
    payload = {
        "media_type": "REELS",
        "video_url": public_video_url,
        "caption": caption,
        "access_token": FACEBOOK_PAGE_ACCESS_TOKEN,
    }
    logger.info("IG: Creating media container...")

    container_res = requests.post(url_container, data=payload, timeout=60).json()

    if "id" not in container_res:
        err = str(container_res)
        _log_error(video_name, host_used, "CONTAINER_FAIL", err)
        return {"success": False, "message": err}

    creation_id = container_res["id"]
    logger.info(f"IG: Container created: {creation_id}")

    # ── Step 2: Poll Processing Status ───────────────────────────────────────
    url_status = (
        f"https://graph.facebook.com/{GRAPH_API_VERSION}/{creation_id}"
        f"?fields=status_code&access_token={FACEBOOK_PAGE_ACCESS_TOKEN}"
    )

    max_polls = 50  # Max 250 seconds (50 * 5s)
    for i in range(max_polls):
        time.sleep(5)
        try:
            status_res = requests.get(url_status, timeout=15).json()
        except Exception as e:
            logger.warning(f"IG: Status poll {i+1} network error: {e}")
            continue

        status_code = status_res.get("status_code")
        logger.info(f"IG: Status Check {i+1}/{max_polls}: {status_code}")

        if status_code == "FINISHED":
            break
        elif status_code == "ERROR":
            err = f"IG processing error: {status_res}"
            _log_error(video_name, host_used, "PROCESSING_ERROR", err)
            return {"success": False, "message": err}
        elif status_code == "IN_PROGRESS":
            continue
        else:
            logger.warning(f"IG: Unknown status: {status_code}")
    else:
        # Timeout after max polls
        err = f"IG processing timed out after {max_polls * 5}s. Status: {status_res}"
        _log_error(video_name, host_used, "TIMEOUT", err)
        return {"success": False, "message": err}

    # ── Step 3: Publish ───────────────────────────────────────────────────────
    logger.info("IG: Publishing reel...")
    url_publish = (
        f"https://graph.facebook.com/{GRAPH_API_VERSION}/{INSTAGRAM_BUSINESS_ACCOUNT_ID}/media_publish"
    )
    publish_res = requests.post(
        url_publish,
        data={"creation_id": creation_id, "access_token": FACEBOOK_PAGE_ACCESS_TOKEN},
        timeout=60,
    ).json()

    if "id" not in publish_res:
        err = str(publish_res)
        _log_error(video_name, host_used, "PUBLISH_FAIL", err)
        return {"success": False, "message": err}

    media_id = publish_res["id"]
    logger.info(f"IG: Reel published. Media ID: {media_id} via {host_used}")

    # ── Step 4: Fetch Public Permalink ────────────────────────────────────────
    try:
        url_link = (
            f"https://graph.facebook.com/{GRAPH_API_VERSION}/{media_id}"
            f"?fields=permalink&access_token={FACEBOOK_PAGE_ACCESS_TOKEN}"
        )
        link_res = requests.get(url_link, timeout=15).json()
        public_url = link_res.get(
            "permalink", f"https://www.instagram.com/reels/{media_id}/"
        )
    except Exception:
        public_url = f"https://www.instagram.com/reels/{media_id}/"

    logger.info(f"IG: Public URL: {public_url}")
    return {"success": True, "media_id": media_id, "url": public_url, "host": host_used}
