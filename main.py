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
    move_to_error,
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


def get_upload_count_24h():
    tracker_file = Path("upload_tracker.json")
    if not tracker_file.exists():
        return 0
    try:
        with open(tracker_file, "r") as f:
            data = json.load(f)

        now = time.time()
        # Keep only uploads from the last 24 hours
        recent_uploads = [t for t in data.get("uploads", []) if now - t < 24 * 3600]

        with open(tracker_file, "w") as f:
            json.dump({"uploads": recent_uploads}, f)

        return len(recent_uploads)
    except Exception as e:
        logger.error(f"Error reading tracker: {e}")
        return 0


def record_upload():
    tracker_file = Path("upload_tracker.json")
    try:
        data = {"uploads": []}
        if tracker_file.exists():
            with open(tracker_file, "r") as f:
                data = json.load(f)

        data["uploads"].append(time.time())
        with open(tracker_file, "w") as f:
            json.dump(data, f)
    except Exception as e:
        logger.error(f"Error updating tracker: {e}")


def get_video_duration(file_path):
    try:
        import ffmpeg

        probe = ffmpeg.probe(str(file_path))
        video_stream = next(
            (stream for stream in probe["streams"] if stream["codec_type"] == "video"),
            None,
        )
        if video_stream:
            duration = float(video_stream["duration"])
            return f"{int(duration // 60)}m {int(duration % 60)}s"
    except Exception as e:
        logger.error(f"Error getting duration: {e}")
    return "Unknown"


def get_est_now():
    import datetime
    import pytz

    try:
        # Use pytz for accurate timezone - India Standard Time
        ist = pytz.timezone("Asia/Kolkata")
        now = datetime.datetime.now(ist)
        return now.hour, now.minute
    except:
        # Fallback: UTC+5:30 for India (not just +5)
        utc_now = time.gmtime()
        # Add 5 hours and 30 minutes
        total_minutes = utc_now.tm_hour * 60 + utc_now.tm_min + 5 * 60 + 30
        ist_hour = (total_minutes // 60) % 24
        ist_min = total_minutes % 60
        return ist_hour, ist_min


def is_in_upload_window():
    """
    Checks if current IST time is within one of the 5 windows:
    1. 07:30 - 08:30 (Morning)
    2. 09:30 - 10:30 (Mid-Morning)
    3. 12:30 - 13:30 (Lunch)
    4. 14:30 - 15:30 (Afternoon)
    5. 16:30 - 17:30 (Evening)
    """
    h, m = get_est_now()
    windows = [(7, 30), (9, 30), (12, 30), (14, 30), (16, 30)]

    for wh, wm in windows:
        # Start time in minutes
        start_m = wh * 60 + wm
        # End time (1 hour later)
        end_m = start_m + 60
        # Current time in minutes
        current_m = h * 60 + m

        if start_m <= current_m < end_m:
            return True, f"{wh:02d}:{wm:02d} IST"

    return False, None


def get_next_scheduled_run():
    h, m = get_est_now()
    windows = [(7, 30), (9, 30), (12, 30), (14, 30), (16, 30)]
    current_m = h * 60 + m

    for wh, wm in windows:
        if wh * 60 + wm > current_m:
            return f"{wh:02d}:{wm:02d} IST"
    return "07:30 AM IST (Tomorrow)"


def main():
    start_time = time.time()

    config.DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # logger.info("Starting video automation system")

    # Check for bypass flag
    import os

    bypass = os.getenv("FORCE_RUN", "false").lower() == "true"

    # 1. Time Window Check
    in_window, window_name = is_in_upload_window()
    if not in_window and not bypass:
        next_run = get_next_scheduled_run()
        # logger.info(f"Not in a valid upload window. Next run at {next_run}. Skipping.")
        return
    elif bypass:
        # logger.info("FORCE_RUN enabled - bypassing window check!")
        pass

    # logger.info(f"Current time is in US Window: {window_name}. Proceeding...")

    # Rate Limit Check (Max 5 per 24h)
    upload_count = get_upload_count_24h()
    if upload_count >= 5:
        # logger.warning(
        #     f"Rate limit reached: {upload_count} uploads in last 24h. Skipping."
        # )
        return

    folder_id, folder_name = pick_next_folder()

    if not folder_id:
        return

    local_files = download_folder_files(folder_id)

    if not local_files:
        return

    video_file = process_video(local_files)

    content = generate_content(folder_name)

    upload_results = {}

    if config.ENABLE_YOUTUBE_UPLOAD:
        try:
            yt_result = upload_youtube(str(video_file), content)
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
        # logger.info("MAIN: Triggering Instagram upload...")
        try:
            from src.uploaders.instagram import upload_instagram

            ig_result = upload_instagram(str(video_file), content)
            # logger.info(f"MAIN: Instagram response: {ig_result}")
            if ig_result.get("success"):
                upload_results["Instagram"] = ig_result
            else:
                upload_results["Instagram"] = ig_result
                logger.error(
                    "MAIN: All Instagram hosts exhausted — moving to ERROR folder"
                )
                from src.drive_manager import move_to_error

                move_to_error(
                    folder_id, folder_name, reason=ig_result.get("message", "unknown")
                )
                return  # Stop processing — folder is in ERROR
        except Exception as e:
            logger.error(f"MAIN: Instagram workflow failed: {e}")
            upload_results["Instagram"] = {"success": False, "message": str(e)}

    # Record success if at least one upload worked
    if any(
        res.get("success") for res in upload_results.values() if isinstance(res, dict)
    ):
        record_upload()

    mark_folder_processed(folder_id, folder_name)
    # logger.info(f"Marked folder as processed")

    elapsed = time.time() - start_time
    elapsed_mins = max(1, int(elapsed / 60))

    # Final Simple Message (No complex HTML)
    # Capture Links
    yt_url = (
        upload_results.get("YouTube")
        if isinstance(upload_results.get("YouTube"), str)
        else upload_results.get("YouTube", {}).get("url", "N/A")
    )
    fb_url = upload_results.get("Facebook", {}).get("url", "N/A")
    ig_url = upload_results.get("Instagram", {}).get("url", "N/A")

    # Final Status Summary
    yt_status = (
        "✅ OK"
        if yt_url != "N/A"
        else "❌ Fail"
        if "YouTube" in upload_results
        else "⏭️ Skip"
    )
    fb_status = (
        "✅ OK"
        if fb_url != "N/A"
        else "❌ Fail"
        if "Facebook" in upload_results
        else "⏭️ Skip"
    )
    ig_status = (
        "✅ OK"
        if ig_url != "N/A"
        else "❌ Fail"
        if "Instagram" in upload_results
        else "⏭️ Skip"
    )

    # Escape HTML special characters
    safe_title = (
        content.get("title", "No Title")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )

    elapsed = time.time() - start_time
    # Get real duration from processed video
    duration_str = get_video_duration(video_file)

    # Get total uploads in 24h for stats
    total_24h = get_upload_count_24h()

    # Construct Premium Message
    message = (
        "🎉 <b>Video Processing Complete</b>\n\n"
        f"📹 <b>Video:</b> {folder_name}\n"
        f"⏱️ <b>Duration:</b> {duration_str}\n"
        f"⏱️ <b>Process Time:</b> {elapsed:.1f}s\n"
        f'📂 <b>Raw Drive:</b> <a href="https://drive.google.com/drive/folders/{folder_id}">Open Folder</a>\n\n'
        "🚀 <b>Upload Links:</b>\n"
        f"• <b>YouTube:</b> {yt_url}\n"
        f"• <b>Instagram:</b> {ig_url}\n"
        f"• <b>Facebook:</b> {fb_url}\n\n"
        "📊 <b>Stats:</b>\n"
        f"• Total 24h: {total_24h}/5 videos\n"
        f"⏭️ <b>Next Run:</b> {get_next_scheduled_run()}"
    )

    # Commented out as requested by the user: "mujha nahi need hai"
    # print("--- Telegram Message Debug ---")
    # print(message)
    # print("------------------------------")

    response = send_telegram_report(message)
    # logger.info(f"Telegram report sent. Response: {response}")
    # logger.info(f"Automation complete in {elapsed:.2f}s")


if __name__ == "__main__":
    main()
