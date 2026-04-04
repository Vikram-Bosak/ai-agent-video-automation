import os
import io
from googleapiclient.discovery import build
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
    Finds the first unprocessed folder or folder with videos in the input directory.
    Returns (folder_id, folder_name) or (None, None).
    """
    service = get_drive_service()
    query = f"'{GOOGLE_DRIVE_FOLDER_ID}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
    results = (
        service.files().list(q=query, fields="nextPageToken, files(id, name)").execute()
    )
    folders = results.get("files", [])

    for folder in folders:
        folder_name = folder["name"].upper()
        if "PROCESSED" in folder_name:
            continue
        return folder["id"], folder["name"]

    # Fallback: Check if there are videos directly in the root folder
    root_query = f"'{GOOGLE_DRIVE_FOLDER_ID}' in parents and mimeType contains 'video' and trashed=false"
    root_results = (
        service.files().list(q=root_query, fields="files(id, name)").execute()
    )
    videos = root_results.get("files", [])

    if videos:
        return GOOGLE_DRIVE_FOLDER_ID, "Root_Videos"

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
        print(f"Downloading {f['name']}...")
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
    Renames the folder by appending the PROCESSED_FOLDER_PREFIX to mark it as done.
    """
    service = get_drive_service()

    # Remove TODO prefix if exists
    clean_name = folder_name
    if clean_name.startswith(DRIVE_FOLDER_PREFIX):
        clean_name = clean_name[len(DRIVE_FOLDER_PREFIX) :]

    new_name = f"{PROCESSED_FOLDER_PREFIX}{clean_name}"
    file_metadata = {"name": new_name}
    service.files().update(fileId=folder_id, body=file_metadata).execute()
    print(f"Marked folder '{folder_name}' as processed ({new_name}).")
