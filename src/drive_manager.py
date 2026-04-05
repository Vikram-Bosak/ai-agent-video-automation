import os
import io
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
        if folder_name.startswith(PROCESSED_FOLDER_PREFIX.upper()):
            continue
        return folder["id"], folder["name"]

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


def upload_to_drive_and_get_link(file_path, folder_id=None):
    """
    Uploads a file to Google Drive and returns a public URL.
    """
    service = get_drive_service()

    file_name = os.path.basename(file_path)
    file_metadata = {
        "name": file_name,
        "mimeType": "video/mp4",
    }

    # Use the main drive folder if no specific folder
    target_folder = folder_id if folder_id else GOOGLE_DRIVE_FOLDER_ID
    file_metadata["parents"] = [target_folder]

    with io.FileIO(file_path, "rb") as f:
        media = MediaIoBaseUpload(f, mimetype="video/mp4", resumable=True)

    file = (
        service.files()
        .create(
            body=file_metadata,
            media_body=media,
            fields="id",
        )
        .execute()
    )

    file_id = file.get("id")

    # Make publicly accessible
    service.permissions().create(
        fileId=file_id,
        body={"type": "anyone", "role": "reader"},
    ).execute()

    # Get public URL
    public_url = f"https://drive.google.com/uc?export=download&id={file_id}"

    print(f"Uploaded {file_name} to Drive: {public_url}")
    return public_url
