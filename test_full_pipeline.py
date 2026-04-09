#!/usr/bin/env python3
"""
Full Pipeline Test Script
==========================
Tests the ENTIRE automation pipeline:
1. Video Processing (FFmpeg) - creates a test video
2. Content Generation (AI) - generates SEO metadata
3. YouTube Upload - uploads video (if credentials exist)
4. Facebook Upload - uploads video (if credentials exist)
5. Instagram Upload - uploads video (if credentials exist)
6. Telegram Report - sends full result to Telegram

Usage:
    python test_full_pipeline.py
    
    # Or with force upload (skip window/rate-limit checks):
    FORCE_RUN=true python test_full_pipeline.py
"""

import os
import sys
import json
import time
import logging
import subprocess
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger("TEST_PIPELINE")

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

import config

# ── Test Results Tracker ──────────────────────────────────────────────────────
results = {}


def record_test(name, success, message="", url=""):
    results[name] = {"success": success, "message": message, "url": url}
    icon = "✅" if success else "❌"
    logger.info(f"{icon} {name}: {message}")


def check_env_var(name, desc):
    """Check if an environment variable is set."""
    val = getattr(config, name, None) or os.getenv(name)
    if val:
        return True, str(val)[:20] + "..."
    else:
        return False, "NOT SET"


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1: CHECK ENVIRONMENT
# ══════════════════════════════════════════════════════════════════════════════

def check_environment():
    logger.info("=" * 60)
    logger.info("🔍 STEP 0: ENVIRONMENT CHECK")
    logger.info("=" * 60)

    checks = {
        "GOOGLE_SERVICE_ACCOUNT_FILE": ("Google Drive", config.GOOGLE_SERVICE_ACCOUNT_FILE and os.path.exists(config.GOOGLE_SERVICE_ACCOUNT_FILE)),
        "GOOGLE_DRIVE_FOLDER_ID": ("Google Drive Folder", bool(config.GOOGLE_DRIVE_FOLDER_ID)),
        "TELEGRAM_BOT_TOKEN": ("Telegram Bot", bool(config.TELEGRAM_BOT_TOKEN)),
        "TELEGRAM_CHAT_IDS": ("Telegram Chat IDs", bool(config.TELEGRAM_CHAT_IDS)),
        "GEMINI_API_KEY": ("Gemini AI", bool(config.GEMINI_API_KEY)),
        "NVIDIA_API_KEY": ("NVIDIA AI", bool(config.NVIDIA_API_KEY)),
        "YOUTUBE_TOKEN_FILE": ("YouTube Token", config.YOUTUBE_TOKEN_FILE and os.path.exists(config.YOUTUBE_TOKEN_FILE)),
        "FACEBOOK_PAGE_ACCESS_TOKEN": ("Facebook Token", bool(config.FACEBOOK_PAGE_ACCESS_TOKEN)),
        "FACEBOOK_PAGE_ID": ("Facebook Page ID", bool(config.FACEBOOK_PAGE_ID)),
        "INSTAGRAM_BUSINESS_ACCOUNT_ID": ("Instagram Account", bool(config.INSTAGRAM_BUSINESS_ACCOUNT_ID)),
        "INSTAGRAM_PAGE_ACCESS_TOKEN": ("Instagram Token", bool(config.INSTAGRAM_PAGE_ACCESS_TOKEN)),
    }

    for var, (desc, ok) in checks.items():
        icon = "✅" if ok else "❌"
        status = "SET" if ok else "MISSING"
        logger.info(f"  {icon} {desc}: {status}")

    # Check FFmpeg
    try:
        result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            version = result.stdout.split("\n")[0]
            logger.info(f"  ✅ FFmpeg: {version}")
        else:
            logger.info("  ❌ FFmpeg: Not working")
    except Exception:
        logger.info("  ❌ FFmpeg: Not installed")

    # Check Python packages
    packages = ["googleapiclient", "pytz", "requests"]
    for pkg in packages:
        try:
            __import__(pkg)
            logger.info(f"  ✅ Python: {pkg}")
        except ImportError:
            logger.info(f"  ❌ Python: {pkg} NOT INSTALLED")

    logger.info("")
    return all(ok for _, (_, ok) in checks.items())


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1: VIDEO PROCESSING
# ══════════════════════════════════════════════════════════════════════════════

def test_video_processing():
    logger.info("=" * 60)
    logger.info("📹 STEP 1: VIDEO PROCESSING")
    logger.info("=" * 60)

    # Create test videos if they don't exist
    test_dir = Path("test_videos")
    test_dir.mkdir(exist_ok=True)

    # Generate test clips using FFmpeg (if they don't exist or are too small)
    clips_needed = [
        ("test_clip1.mp4", 3, 720, 1280),   # 3s, portrait 720x1280
        ("test_clip2.mp4", 3, 480, 854),    # 3s, different resolution
        ("test_clip3.mp4", 4, 1080, 1920),  # 4s, full HD vertical
    ]

    test_files = []
    for filename, duration, w, h in clips_needed:
        filepath = test_dir / filename
        if not filepath.exists() or os.path.getsize(filepath) < 1000:
            logger.info(f"  🎬 Generating test clip: {filename} ({w}x{h}, {duration}s)...")
            cmd = [
                "ffmpeg", "-y",
                "-f", "lavfi", "-i", f"color=c=blue:s={w}x{h}:d={duration}:r=30",
                "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}",
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
                "-c:a", "aac", "-b:a", "128k",
                "-pix_fmt", "yuv420p",
                "-shortest",
                str(filepath)
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                logger.error(f"  ❌ Failed to generate {filename}: {result.stderr[:200]}")
                continue

        test_files.append(str(filepath))
        info = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height,duration",
             "-of", "csv=p=0", str(filepath)],
            capture_output=True, text=True
        )
        logger.info(f"  📹 {filename}: {info.stdout.strip()}")

    if not test_files:
        record_test("Video Processing", False, "No test clips available")
        return None

    # Process videos using our fixed processor
    logger.info(f"\n  ⚙️  Processing {len(test_files)} clips → 1080x1920...")
    t0 = time.time()

    try:
        from src.video_processor import process_video
        video_file = process_video(test_files)
        elapsed = time.time() - t0

        # Verify output
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height,duration",
             "-of", "csv=p=0", video_file],
            capture_output=True, text=True
        )
        parts = probe.stdout.strip().split(",")
        width, height = parts[0], parts[1]
        duration = parts[2]
        fsize = os.path.getsize(video_file)

        ok = width == "1080" and height == "1920"
        msg = f"{width}x{height}, {duration}s, {fsize/1024:.0f}KB ({elapsed:.1f}s)"
        record_test("Video Processing", ok, msg)
        return video_file

    except Exception as e:
        record_test("Video Processing", False, str(e)[:100])
        return None


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2: CONTENT GENERATION
# ══════════════════════════════════════════════════════════════════════════════

def test_content_generation():
    logger.info("\n" + "=" * 60)
    logger.info("📝 STEP 2: CONTENT GENERATION")
    logger.info("=" * 60)

    try:
        from src.content_generator import generate_content
        content = generate_content("TEST - AI Video Automation Pipeline")

        ok = bool(content.get("title")) and bool(content.get("description"))
        msg = f"Title: {content.get('title', 'N/A')[:50]}"
        record_test("Content Generation", ok, msg)

        logger.info(f"  📌 Title: {content.get('title')}")
        logger.info(f"  📝 Description: {content.get('description', '')[:100]}...")
        logger.info(f"  #️⃣  Hashtags: {content.get('hashtags', '')[:60]}...")
        return content

    except Exception as e:
        record_test("Content Generation", False, str(e)[:100])
        return {"title": "Test Upload", "description": "Test", "hashtags": "#test", "tags": "test"}


# ══════════════════════════════════════════════════════════════════════════════
# STEP 3: YOUTUBE UPLOAD
# ══════════════════════════════════════════════════════════════════════════════

def test_youtube_upload(video_path, content):
    logger.info("\n" + "=" * 60)
    logger.info("🔴 STEP 3: YOUTUBE UPLOAD")
    logger.info("=" * 60)

    if not config.ENABLE_YOUTUBE_UPLOAD:
        record_test("YouTube Upload", False, "Disabled in config")
        return

    if not (config.YOUTUBE_TOKEN_FILE and os.path.exists(config.YOUTUBE_TOKEN_FILE)):
        record_test("YouTube Upload", False, "Token file not found")
        return

    try:
        from src.uploaders.youtube import upload_youtube
        logger.info("  🚀 Uploading to YouTube...")
        url = upload_youtube(str(video_path), content)
        record_test("YouTube Upload", True, "Uploaded!", url)
        return url
    except Exception as e:
        record_test("YouTube Upload", False, str(e)[:150])
        return None


# ══════════════════════════════════════════════════════════════════════════════
# STEP 4: FACEBOOK UPLOAD
# ══════════════════════════════════════════════════════════════════════════════

def test_facebook_upload(video_path, content):
    logger.info("\n" + "=" * 60)
    logger.info("📘 STEP 4: FACEBOOK UPLOAD")
    logger.info("=" * 60)

    if not config.ENABLE_FACEBOOK_UPLOAD:
        record_test("Facebook Upload", False, "Disabled in config")
        return

    if not (config.FACEBOOK_PAGE_ACCESS_TOKEN and config.FACEBOOK_PAGE_ID):
        record_test("Facebook Upload", False, "Credentials not configured")
        return

    try:
        from src.uploaders.facebook import upload_video
        logger.info("  🚀 Uploading to Facebook...")
        result = upload_video(str(video_path), content["title"], content["description"])
        ok = result.get("success", False)
        url = result.get("url", "")
        msg = result.get("message", result.get("video_id", ""))
        record_test("Facebook Upload", ok, msg, url)
        return result
    except Exception as e:
        record_test("Facebook Upload", False, str(e)[:150])
        return None


# ══════════════════════════════════════════════════════════════════════════════
# STEP 5: INSTAGRAM UPLOAD
# ══════════════════════════════════════════════════════════════════════════════

def test_instagram_upload(video_path, content):
    logger.info("\n" + "=" * 60)
    logger.info("🟣 STEP 5: INSTAGRAM UPLOAD")
    logger.info("=" * 60)

    if not config.ENABLE_INSTAGRAM_UPLOAD:
        record_test("Instagram Upload", False, "Disabled in config")
        return

    if not (config.INSTAGRAM_BUSINESS_ACCOUNT_ID and config.INSTAGRAM_PAGE_ACCESS_TOKEN):
        record_test("Instagram Upload", False, "Credentials not configured")
        return

    try:
        from src.uploaders.instagram import upload_instagram
        logger.info("  🚀 Uploading to Instagram Reel...")
        result = upload_instagram(str(video_path), content)
        ok = result.get("success", False)
        url = result.get("url", "")
        msg = result.get("message", result.get("media_id", ""))
        record_test("Instagram Upload", ok, msg, url)
        return result
    except Exception as e:
        record_test("Instagram Upload", False, str(e)[:150])
        return None


# ══════════════════════════════════════════════════════════════════════════════
# STEP 6: TELEGRAM REPORT
# ══════════════════════════════════════════════════════════════════════════════

def send_test_report():
    logger.info("\n" + "=" * 60)
    logger.info("📤 STEP 6: TELEGRAM REPORT")
    logger.info("=" * 60)

    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_IDS:
        record_test("Telegram Report", False, "Bot token or chat IDs not configured")
        return

    # Build report
    lines = ["🧪 <b>FULL PIPELINE TEST REPORT</b>\n"]

    passed = sum(1 for r in results.values() if r["success"])
    total = len(results)

    lines.append(f"📊 <b>Result: {passed}/{total} Tests Passed</b>\n")

    for name, r in results.items():
        icon = "✅" if r["success"] else "❌"
        msg = r.get("message", "")
        url = r.get("url", "")
        line = f"{icon} <b>{name}</b>: {msg}"
        if url:
            line += f"\n   🔗 <a href=\"{url}\">{url}</a>"
        lines.append(line)

    lines.append(f"\n⏰ Test time: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    message = "\n".join(lines)

    try:
        from src.telegram_reporter import send_telegram_report
        result = send_telegram_report(message)
        ok = isinstance(result, list) and any(r.get("success") for r in result)
        record_test("Telegram Report", ok, f"Sent to {len(config.TELEGRAM_CHAT_IDS)} chat(s)")
        logger.info(f"  ✅ Telegram message sent!")
    except Exception as e:
        record_test("Telegram Report", False, str(e)[:150])


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    start_time = time.time()
    logger.info("╔══════════════════════════════════════════════════════════╗")
    logger.info("║   🧪 AI VIDEO AUTOMATION — FULL PIPELINE TEST           ║")
    logger.info("╚══════════════════════════════════════════════════════════╝\n")

    # Check environment
    check_environment()

    # Step 1: Video Processing
    video_file = test_video_processing()
    if not video_file:
        logger.error("❌ Video processing failed. Cannot continue.")
        send_test_report()
        return

    # Step 2: Content Generation
    content = test_content_generation()

    # Step 3-5: Uploads (only if enabled)
    test_youtube_upload(video_file, content)
    test_facebook_upload(video_file, content)
    test_instagram_upload(video_file, content)

    # Step 6: Send Telegram Report
    send_test_report()

    # Final Summary
    elapsed = time.time() - start_time
    passed = sum(1 for r in results.values() if r["success"])
    total = len(results)

    logger.info("\n" + "=" * 60)
    logger.info(f"🏁 FINAL RESULT: {passed}/{total} PASSED ({elapsed:.1f}s)")
    logger.info("=" * 60)

    for name, r in results.items():
        icon = "✅" if r["success"] else "❌"
        logger.info(f"  {icon} {name}")

    if passed == total:
        logger.info("\n🏆 EVERYTHING WORKING! Automation is ready! 🎉")
    else:
        failed = [name for name, r in results.items() if not r["success"]]
        logger.info(f"\n⚠️  {len(failed)} test(s) failed: {', '.join(failed)}")
        logger.info("💡 Check the credentials in .env file for failed tests.")


if __name__ == "__main__":
    main()
