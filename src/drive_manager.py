import os
import io
import json
import re
import time
import logging
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2 import service_account
from config import (
    GOOGLE_SERVICE_ACCOUNT_FILE,
    GOOGLE_DRIVE_FOLDER_ID,
    DOWNLOAD_DIR,
    DRIVE_FOLDER_PREFIX,
    PROCESSED_FOLDER_PREFIX,
)

SCOPES = ["https://www.googleapis.com/auth/drive"]
logger = logging.getLogger(__name__)


def natural_sort_key(s):
    """Natural sort key for handling numeric filenames correctly."""
    return [int(text) if text.isdigit() else text.lower()
            for text in re.split(r'(\d+)', s)]


def _repair_service_account_file(filepath):
    """
    Repairs a service account JSON file that has corrupted PEM private keys.

    This commonly happens when the JSON is stored in GitHub Secrets,
    which strips or corrupts newline characters in the private_key field.

    Fixes applied:
    1. Strip literal "\\n" strings and replace with actual newlines
    2. Ensure PEM headers are on their own lines
    3. Validate JSON structure
    4. Save repaired file

    Returns True if repair was needed and successful, False if no repair needed.
    Raises if repair fails.
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            raw = f.read()
    except Exception as e:
        raise FileNotFoundError(f"Cannot read service account file {filepath}: {e}")

    # Check if the private_key needs repair
    needs_repair = False
    repaired = raw

    # Fix 1: Replace escaped newlines \\n with actual newlines
    # (happens when JSON is stored with escaped newlines in secrets)
    if "\\n" in repaired and "private_key" in repaired:
        # Only fix within string values — not the JSON structural newlines
        # We need to parse carefully: find the private_key value and fix it
        needs_repair = True

    # Fix 2: Restore PEM line breaks
    # PEM keys should have -----BEGIN PRIVATE KEY----- on one line,
    # then base64 content on multiple lines, then -----END PRIVATE KEY-----
    if "-----BEGIN PRIVATE KEY-----" in repaired:
        # Ensure PEM boundaries have newlines before and after
        repaired = re.sub(
            r'"-----BEGIN PRIVATE KEY-----"',
            r'"-----BEGIN PRIVATE KEY-----\\n',
            repaired,
        )
        repaired = re.sub(
            r'-----END PRIVATE KEY-----"',
            r'\\n-----END PRIVATE KEY-----"',
            repaired,
        )

        # If the entire key is on one line, insert newlines every 64 chars
        def fix_pem_block(match):
            header = match.group(1)
            body = match.group(2)
            footer = match.group(3)
            # Insert newlines every 64 characters in the body
            if len(body) > 64 and "\\n" not in body:
                lines = [body[i:i+64] for i in range(0, len(body), 64)]
                body = "\\n".join(lines)
            return f"{header}{body}{footer}"

        repaired = re.sub(
            r'(-----BEGIN PRIVATE KEY-----\\\\n)(.+?)(\\\\n-----END PRIVATE KEY-----)',
            fix_pem_block,
            repaired,
            flags=re.DOTALL,
        )
        needs_repair = True

    # Fix 3: Handle the case where the entire JSON is on one line (no newlines at all)
    # and the private_key value has literal \n instead of escaped \\n
    if not needs_repair and "private_key" in repaired:
        try:
            data = json.loads(repaired)
            pk = data.get("private_key", "")
            # If the key has no actual newlines but should (PEM keys always have newlines)
            if "BEGIN" in pk and "\n" not in pk:
                needs_repair = True
        except json.JSONDecodeError:
            needs_repair = True

    # Fix 4: JSONDecodeError — try to parse and rebuild
    if needs_repair:
        try:
            data = json.loads(repaired)
        except json.JSONDecodeError:
            # The JSON itself is broken — try harder to fix
            # Maybe the secret was stored without proper JSON escaping
            logger.warning("Service account JSON is corrupted. Attempting repair...")

            # Try replacing literal newlines in the raw file content
            repaired = raw.strip()

            # If it starts with { and has no proper structure, try to fix
            if repaired.startswith("{"):
                # Find the private_key section and fix it
                pass

            try:
                data = json.loads(repaired)
            except json.JSONDecodeError as e:
                raise ValueError(
                    f"Service account JSON is completely corrupted and cannot be auto-repaired. "
                    f"Error: {e}. "
                    f"Please re-upload the service account JSON to GitHub Secrets "
                    f"(use base64 encoding — see setup_github_secrets.py)."
                )

        # Fix the private_key field specifically
        if "private_key" in data:
            pk = data["private_key"]
            original_pk = pk

            # Replace literal \n with actual newlines
            if "\\n" in pk:
                pk = pk.replace("\\n", "\n")

            # If still no newlines in PEM block, add them
            if "-----BEGIN" in pk and "\n" not in pk:
                # Extract parts
                begin_marker = "-----BEGIN PRIVATE KEY-----"
                end_marker = "-----END PRIVATE KEY-----"
                if begin_marker in pk and end_marker in pk:
                    start = pk.index(begin_marker) + len(begin_marker)
                    end = pk.index(end_marker)
                    body = pk[start:end].strip()
                    # Add newlines every 64 chars
                    lines = [body[i:i+64] for i in range(0, len(body), 64)]
                    pk = f"{begin_marker}\n" + "\n".join(lines) + f"\n{end_marker}\n"

            if pk != original_pk:
                data["private_key"] = pk
                logger.info("Service account private_key repaired (newlines restored).")

        # Write repaired file
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        logger.info(f"Service account file repaired: {filepath}")
        return True

    return False


def _load_service_account_from_env():
    """
    Alternative: Load service account credentials from an environment variable.
    The env var should contain the full JSON string.
    Supports base64-encoded values.
    """
    sa_json_env = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")

    if not sa_json_env:
        return None

    # Try base64 decode first
    import base64
    try:
        decoded = base64.b64decode(sa_json_env).decode("utf-8")
        data = json.loads(decoded)
    except Exception:
        # Not base64, try as raw JSON
        try:
            data = json.loads(sa_json_env)
        except json.JSONDecodeError:
            logger.warning("GOOGLE_SERVICE_ACCOUNT_JSON env var is not valid JSON or base64.")
            return None

    # Fix private key if needed
    if "private_key" in data:
        pk = data["private_key"]
        if "\\n" in pk:
            pk = pk.replace("\\n", "\n")
            data["private_key"] = pk
        elif "-----BEGIN" in pk and "\n" not in pk:
            begin_marker = "-----BEGIN PRIVATE KEY-----"
            end_marker = "-----END PRIVATE KEY-----"
            if begin_marker in pk and end_marker in pk:
                start = pk.index(begin_marker) + len(begin_marker)
                end = pk.index(end_marker)
                body = pk[start:end].strip()
                lines = [body[i:i+64] for i in range(0, len(body), 64)]
                pk = f"{begin_marker}\n" + "\n".join(lines) + f"\n{end_marker}\n"
                data["private_key"] = pk

    return data


def get_drive_service():
    """
    Creates an authenticated Google Drive service.
    Handles PEM corruption auto-repair.
    Falls back to GOOGLE_SERVICE_ACCOUNT_JSON env var if file not found.
    """
    import json

    creds = None
    sa_data = None

    # Method 1: Try environment variable first (most reliable for GitHub Actions)
    sa_data = _load_service_account_from_env()
    if sa_data:
        logger.info("Loaded service account from GOOGLE_SERVICE_ACCOUNT_JSON env var.")
        creds = service_account.Credentials.from_service_account_info(sa_data, scopes=SCOPES)
    else:
        # Method 2: Try file path
        if not os.path.exists(GOOGLE_SERVICE_ACCOUNT_FILE):
            raise FileNotFoundError(
                f"Service account file '{GOOGLE_SERVICE_ACCOUNT_FILE}' not found. "
                f"Either set GOOGLE_SERVICE_ACCOUNT_JSON env var or provide the file."
            )

        # Auto-repair if needed
        try:
            creds = service_account.Credentials.from_service_account_file(
                GOOGLE_SERVICE_ACCOUNT_FILE, scopes=SCOPES
            )
        except ValueError as e:
            if "PEM" in str(e) or "InvalidPadding" in str(e) or "JSONDecodeError" in str(e):
                logger.warning(f"PEM error detected: {e}. Attempting auto-repair...")
                try:
                    repaired = _repair_service_account_file(GOOGLE_SERVICE_ACCOUNT_FILE)
                    if repaired:
                        creds = service_account.Credentials.from_service_account_file(
                            GOOGLE_SERVICE_ACCOUNT_FILE, scopes=SCOPES
                        )
                        logger.info("Auto-repair successful!")
                    else:
                        raise
                except Exception as repair_error:
                    raise ValueError(
                        f"Failed to load AND repair service account file. "
                        f"Original error: {e}\nRepair error: {repair_error}\n\n"
                        f"SOLUTION: Re-upload your service account JSON to GitHub Secrets "
                        f"using base64 encoding. Run: python setup_github_secrets.py"
                    ) from repair_error
            else:
                raise

    service = build("drive", "v3", credentials=creds)
    return service


def pick_next_folder():
    """
    Finds the first folder that isn't the DONE folder.
    """
    service = get_drive_service()
    from config import DONE_FOLDER_ID

    query = f"'{GOOGLE_DRIVE_FOLDER_ID}' in parents and trashed=false"
    logger.info(f"Checking Google Drive parent folder: {GOOGLE_DRIVE_FOLDER_ID}")

    results = (
        service.files()
        .list(
            q=query,
            fields="files(id, name, mimeType)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        )
        .execute()
    )

    items = results.get("files", [])
    logger.info(f"Found {len(items)} items in parent folder.")

    for item in items:
        if item["mimeType"] != "application/vnd.google-apps.folder":
            continue

        # Skip specific system folders
        if item["id"] == DONE_FOLDER_ID:
            continue

        folder_name = item["name"]
        if folder_name.startswith("ERROR_"):
            continue

        logger.info(f"Candidate folder found: '{folder_name}' ({item['id']})")
        return item["id"], folder_name

    logger.warning("No valid candidate folders found to process.")
    return None, None


def download_folder_files(folder_id):
    """
    Downloads all mp4 files from the specified folder.
    Returns a list of local file paths.
    """
    service = get_drive_service()
    # Also match audio files if present
    query = f"'{folder_id}' in parents and (mimeType contains 'video/' or mimeType contains 'audio/') and trashed=false"
    results = (
        service.files().list(q=query, fields="nextPageToken, files(id, name)").execute()
    )
    files = results.get("files", [])

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    local_files = []

    for f in files:
        request = service.files().get_media(fileId=f["id"])
        local_filepath = os.path.join(DOWNLOAD_DIR, f["name"])

        with io.FileIO(local_filepath, "wb") as fh:
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while done is False:
                status, done = downloader.next_chunk()

        local_files.append(local_filepath)

    # Sort files naturally to handle numeric filenames correctly
    return sorted(local_files, key=natural_sort_key)


def mark_folder_processed(folder_id, folder_name):
    """
    Moves the folder to the DONE subfolder and renames it.
    """
    service = get_drive_service()
    from config import DONE_FOLDER_ID, GOOGLE_DRIVE_FOLDER_ID

    if not DONE_FOLDER_ID:
        logger.error("DONE_FOLDER_ID is not configured! Cannot move folder.")
        return

    # 1. Rename the folder (Remove TODO_ and add DONE_)
    clean_name = folder_name
    if clean_name.upper().startswith(DRIVE_FOLDER_PREFIX.upper()):
        clean_name = clean_name[len(DRIVE_FOLDER_PREFIX):]

    new_name = f"{PROCESSED_FOLDER_PREFIX}{clean_name}"

    # 2. Move to DONE folder
    try:
        file = service.files().get(fileId=folder_id, fields="parents").execute()
        previous_parents = ",".join(file.get("parents"))

        service.files().update(
            fileId=folder_id,
            body={"name": new_name},
            removeParents=previous_parents,
            addParents=DONE_FOLDER_ID,
            fields="id, parents",
        ).execute()
        logger.info(f"Successfully moved '{folder_name}' to DONE.")
    except Exception as e:
        logger.error(f"Failed to move folder to DONE: {e}")


def move_to_error(folder_id, folder_name, reason="upload_failed"):
    """
    Moves the folder to the ERROR subfolder if all upload attempts fail.
    """
    service = get_drive_service()
    from config import ERROR_FOLDER_ID, GOOGLE_DRIVE_FOLDER_ID

    if not ERROR_FOLDER_ID:
        logger.error("ERROR_FOLDER_ID is not configured! Cannot move folder.")
        return

    new_name = f"ERROR_{folder_name}"

    try:
        file = service.files().get(fileId=folder_id, fields="parents").execute()
        previous_parents = ",".join(file.get("parents"))

        service.files().update(
            fileId=folder_id,
            body={"name": new_name},
            removeParents=previous_parents,
            addParents=ERROR_FOLDER_ID,
            fields="id, parents",
        ).execute()

        logger.warning(f"Moved '{folder_name}' to ERROR folder. Reason: {reason}")
    except Exception as e:
        logger.error(f"Failed to move folder to ERROR: {e}")


def upload_ig_temp(file_path):
    """
    Dedicated function for IG temp uploads to bypass Service Account quota.
    Uploads directly to the DONE_FOLDER_ID shared folder.
    """
    service = get_drive_service()
    from config import DONE_FOLDER_ID

    file_metadata = {
        "name": f"temp_ig_{int(time.time())}_{os.path.basename(file_path)}",
        "parents": [DONE_FOLDER_ID],
    }

    media = MediaFileUpload(file_path, mimetype="video/mp4", resumable=True)

    file = (
        service.files()
        .create(
            body=file_metadata,
            media_body=media,
            fields="id, webContentLink",
            supportsAllDrives=True,
        )
        .execute()
    )

    file_id = file.get("id")

    # Make publicly accessible
    service.permissions().create(
        fileId=file_id,
        body={"type": "anyone", "role": "reader"},
        supportsAllDrives=True,
    ).execute()

    link = file.get("webContentLink")
    if not link:
        link = f"https://drive.google.com/uc?export=download&id={file_id}"

    return link
