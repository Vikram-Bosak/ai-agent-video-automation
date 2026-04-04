# Video Automation System

Automated video processing pipeline that pulls clips from Google Drive, processes them, generates SEO content via AI, and uploads to multiple platforms.

## Features

- **Google Drive Integration**: Automatically finds and downloads video folders
- **Smart Video Processing**: Merges clips, syncs to audio, scales to 9:16 vertical format
- **AI Content Generation**: Generates titles, descriptions, tags using Google Gemini
- **Multi-Platform Upload**: YouTube, Facebook, Instagram Reels
- **Telegram Notifications**: Reports processing status and upload results
- **Duplicate Prevention**: Tracks processed folders to avoid reprocessing

## Requirements

- Python 3.11+
- FFmpeg
- Google Cloud Service Account (for Drive & Gemini)
- Telegram Bot Token

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Google Cloud Setup

1. Create a Google Cloud project
2. Enable APIs:
   - Google Drive API
   - Generative Language API (Gemini)
3. Create Service Account and download JSON key
4. Share your Drive folder with the service account email

### 3. Environment Variables

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

Or set GitHub Secrets (recommended for CI/CD):

| Variable | Description |
|----------|-------------|
| `DRIVE_FOLDER_PREFIX` | Prefix for folders to process (default: `TODO_`) |
| `PROCESSED_FOLDER_PREFIX` | Prefix for processed folders (default: `DONE_`) |
| `GOOGLE_SERVICE_ACCOUNT_FILE` | Path to service account JSON |
| `GOOGLE_DRIVE_FOLDER_ID` | ID of Drive folder to monitor |
| `GEMINI_API_KEY` | Google Gemini API key |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token |
| `TELEGRAM_CHAT_IDS` | Comma-separated chat IDs for reports |
| `YOUTUBE_TOKEN_FILE` | YouTube OAuth token file |
| `FACEBOOK_PAGE_ACCESS_TOKEN` | Facebook Page access token |
| `FACEBOOK_PAGE_ID` | Facebook Page ID |
| `INSTAGRAM_PAGE_ACCESS_TOKEN` | Instagram access token |
| `INSTAGRAM_BUSINESS_ACCOUNT_ID` | Instagram Business Account ID |
| `ENABLE_YOUTUBE_UPLOAD` | Enable YouTube upload (default: true) |
| `ENABLE_FACEBOOK_UPLOAD` | Enable Facebook upload (default: true) |
| `ENABLE_INSTAGRAM_UPLOAD` | Enable Instagram upload (default: true) |

### 4. YouTube OAuth Setup

Run locally once to generate refresh token:

```bash
python auth_youtube.py
```

Requires `client_secrets.json` from Google Cloud Console.

## Usage

### Local Run

```bash
python main.py
```

### GitHub Actions

The workflow runs daily at midnight or can be triggered manually.

## Folder Structure

Expected Drive folder structure:

```
📁 TODO_VideoName/
├── clip1.mp4
├── clip2.mp4
├── clip3.mp4
├── voice.mp3      # Optional voiceover
└── music.mp3      # Optional background music
```

After processing, folder is renamed to `DONE_VideoName`.

## Output

- `final_video.mp4` - Processed video (1080x1920, 9:16)
- Uploaded to configured platforms
- Telegram report sent with results
