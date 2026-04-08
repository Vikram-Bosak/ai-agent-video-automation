import os
import io
import time
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


def get_drive_service():
    if not os.path.exists(GOOGLE_SERVICE_ACCOUNT_FILE):
        raise FileNotFoundError(
            f"Service account file {GOOGLE_SERVICE_ACCOUNT_FILE} not found."
        )
    creds = service_account.Credentials.from_service_account_file(
        GOOGLE_SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    service = build("drive", "v3", credentials=creds)
    return service


def pick_next_folder():
    """
    Finds the first folder that isn't the DONE folder.
    """
    import logging
    logger = logging.getLogger(__name__)

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

    for idx, f in enumerate(files):
        # print(f"Downloading {f['name']}...")
        request = service.files().get_media(fileId=f["id"])
        local_filepath = os.path.join(DOWNLOAD_DIR, f"{idx}_{f['name']}")

        with io.FileIO(local_filepath, "wb") as fh:
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while done is False:
                status, done = downloader.next_chunk()

        local_files.append(local_filepath)

    # Sort files just in case we need a specific order (e.g. by name)
    return sorted(local_files)


def mark_folder_processed(folder_id, folder_name):
    """
    Moves the folder to the DONE subfolder and renames it.
    """
    import logging
    logger = logging.getLogger(__name__)

    service = get_drive_service()
    from config import DONE_FOLDER_ID, GOOGLE_DRIVE_FOLDER_ID

    if not DONE_FOLDER_ID:
        logger.error("DONE_FOLDER_ID is not configured! Cannot move folder.")
        return

    # 1. Rename the folder (Remove TODO_ and add DONE_)
    clean_name = folder_name
    if clean_name.upper().startswith(DRIVE_FOLDER_PREFIX.upper()):
        clean_name = clean_name[len(DRIVE_FOLDER_PREFIX) :]

    new_name = f"{PROCESSED_FOLDER_PREFIX}{clean_name}"

    # 2. Move to DONE folder
    try:
        # Get current parents to remove them
        file = service.files().get(fileId=folder_id, fields="parents").execute()
        previous_parents = ",".join(file.get("parents"))

        # Update metadata and move
        service.files().update(
            # ... existing update call ...
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
    import logging
    logger = logging.getLogger(__name__)

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


from googleapiclient.http import MediaFileUpload


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

    # Use MediaFileUpload instead of MediaIoBaseUpload for better resumability and quota handling
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

    # print(f"IG TEMP UPLOAD SUCCESS: {link}")
    return link
