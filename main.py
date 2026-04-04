#!/usr/bin/env python3

import os
import sys
import json
import logging
import time
from pathlib import Path

import config
from src.drive_manager import (
    pick_next_folder,
    download_folder_files,
    mark_folder_processed,
)
from src.video_processor import process_video
from src.content_generator import generate_content
from src.telegram_reporter import send_telegram_report

from src.uploaders.youtube import upload_youtube
from src.uploaders.facebook import upload_video as upload_facebook
from src.uploaders.instagram import upload_instagram


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    start_time = time.time()

    config.DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("Starting video automation system")

    folder_id, folder_name = pick_next_folder()

    if not folder_id:
        logger.info("No unprocessed folders found")
        send_telegram_report("📭 No unprocessed folders found in Google Drive")
        return

    logger.info(f"Found folder: {folder_name} ({folder_id})")

    local_files = download_folder_files(folder_id)
    logger.info(f"Downloaded {len(local_files)} files")

    if not local_files:
        logger.error("No files downloaded")
        send_telegram_report("❌ No files found in folder")
        return

    downloaded_path = config.DOWNLOAD_DIR
    video_file = process_video(local_files)
    logger.info(f"Processed video: {video_file}")

    content = generate_content(folder_name)
    logger.info(f"Generated content: {content['title']}")

    upload_results = {}

    if config.ENABLE_YOUTUBE_UPLOAD:
        try:
            yt_result = upload_youtube(
                str(video_file),
                content["title"],
                content["description"],
                content["tags"],
            )
            upload_results["YouTube"] = yt_result
        except Exception as e:
            logger.error(f"YouTube upload failed: {e}")
            upload_results["YouTube"] = {"success": False, "message": str(e)}

    if config.ENABLE_FACEBOOK_UPLOAD:
        try:
            fb_result = upload_facebook(
                str(video_file), content["title"], content["description"]
            )
            upload_results["Facebook"] = fb_result
        except Exception as e:
            logger.error(f"Facebook upload failed: {e}")
            upload_results["Facebook"] = {"success": False, "message": str(e)}

    if config.ENABLE_INSTAGRAM_UPLOAD:
        try:
            ig_result = upload_instagram(
                str(video_file), f"{content['title']} {content['hashtags']}"
            )
            upload_results["Instagram"] = ig_result
        except Exception as e:
            logger.error(f"Instagram upload failed: {e}")
            upload_results["Instagram"] = {"success": False, "message": str(e)}

    mark_folder_processed(folder_id, folder_name)
    logger.info(f"Marked folder as processed")

    message = f"📹 <b>Video Processing Complete</b>\n\n"
    message += f"📁 Folder: {folder_name}\n"
    message += f"🎬 Video: {video_file}\n\n"
    message += f"📝 <b>Generated Content:</b>\n"
    message += f"Title: {content.get('title', 'N/A')}\n"
    message += f"Description: {content.get('description', 'N/A')[:200]}...\n"
    message += f"Tags: {content.get('tags', 'N/A')}\n"
    message += f"Hashtags: {content.get('hashtags', 'N/A')}\n\n"

    if upload_results:
        message += f"📤 <b>Upload Results:</b>\n"
        for platform, result in upload_results.items():
            status = "✅" if result.get("success") else "❌"
            message += f"{status} {platform}: {result.get('message', 'Unknown')}\n"
    else:
        message += f"📤 No uploads attempted\n"

    send_telegram_report(message)

    elapsed = time.time() - start_time
    logger.info(f"Automation complete in {elapsed:.2f}s")


if __name__ == "__main__":
    main()
