import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent
DOWNLOAD_DIR = BASE_DIR / "downloads"
OUTPUT_DIR = BASE_DIR / "output"

DRIVE_FOLDER_PREFIX = os.getenv("DRIVE_FOLDER_PREFIX", "TODO_")
PROCESSED_FOLDER_PREFIX = os.getenv("PROCESSED_FOLDER_PREFIX", "DONE_")

# Telegram Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# Parse TELEGRAM_CHAT_IDS (comma-separated list)
_chat_ids = os.getenv("TELEGRAM_CHAT_IDS", "")
if _chat_ids:
    TELEGRAM_CHAT_IDS = [cid.strip() for cid in _chat_ids.split(",") if cid.strip()]
else:
    TELEGRAM_CHAT_IDS = []

# Also support single TELEGRAM_CHAT_ID (backward compatibility)
_telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
if _telegram_chat_id:
    chat_id_str = str(_telegram_chat_id).strip()
    if chat_id_str and chat_id_str not in TELEGRAM_CHAT_IDS:
        TELEGRAM_CHAT_IDS.append(chat_id_str)

# Validate Telegram config at startup
if not TELEGRAM_BOT_TOKEN:
    print("WARNING: TELEGRAM_BOT_TOKEN is not set!")
if not TELEGRAM_CHAT_IDS:
    print("WARNING: TELEGRAM_CHAT_IDS is empty! Set it in GitHub Secrets.")
else:
    print(f"Telegram configured: {len(TELEGRAM_CHAT_IDS)} chat ID(s)")

GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv(
    "GOOGLE_SERVICE_ACCOUNT_FILE", "service_account.json"
)
GOOGLE_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
DONE_FOLDER_ID = os.getenv("DONE_FOLDER_ID", "1cSG-oqex-qLqf2SN2LJhwwDU6htjz0VH")
ERROR_FOLDER_ID = os.getenv("ERROR_FOLDER_ID", "1cSG-oqex-qLqf2SN2LJhwwDU6htjz0VH")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")

YOUTUBE_TOKEN_FILE = os.getenv("YOUTUBE_TOKEN_FILE", "youtube_token.json")
YOUTUBE_CLIENT_SECRETS = os.getenv("YOUTUBE_CLIENT_SECRETS", "client_secrets.json")

FACEBOOK_PAGE_ACCESS_TOKEN = os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN", "")
FACEBOOK_PAGE_ID = os.getenv("FACEBOOK_PAGE_ID")
INSTAGRAM_PAGE_ACCESS_TOKEN = os.getenv("INSTAGRAM_PAGE_ACCESS_TOKEN", "")
INSTAGRAM_BUSINESS_ACCOUNT_ID = os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID")

ENABLE_YOUTUBE_UPLOAD = os.getenv("ENABLE_YOUTUBE_UPLOAD", "true").lower() == "true"
ENABLE_FACEBOOK_UPLOAD = os.getenv("ENABLE_FACEBOOK_UPLOAD", "true").lower() == "true"
ENABLE_INSTAGRAM_UPLOAD = os.getenv("ENABLE_INSTAGRAM_UPLOAD", "true").lower() == "true"

TARGET_WIDTH = 1080
TARGET_HEIGHT = 1920
