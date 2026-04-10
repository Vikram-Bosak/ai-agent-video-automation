import os
import json
import subprocess
import logging
import re
import config
from config import OUTPUT_DIR

logger = logging.getLogger(__name__)


def natural_sort_key(s):
    """Natural sort key for handling numeric filenames correctly."""
    return [int(text) if text.isdigit() else text.lower()
            for text in re.split(r'(\d+)', s)]


def get_video_info(file_path):
    """
    Probes a video file for duration, resolution, rotation, and audio presence.
    Returns a dict with keys: duration, has_audio, width, height, rotation
    """
    try:
        cmd = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=duration,width,height,displaymatrix",
            "-of", "json",
            str(file_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)

        video_stream = data.get("streams", [{}])[0]

        # Detect rotation from displaymatrix side data
        rotation = 0
        displaymatrix = video_stream.get("displaymatrix", "")
        if displaymatrix:
            if "rotate:-90" in displaymatrix:
                rotation = -90
            elif "rotate:90" in displaymatrix:
                rotation = 90
            elif "rotate:180" in displaymatrix:
                rotation = 180
            elif "rotate:-180" in displaymatrix:
                rotation = -180

        # Also check 'tags' rotation if displaymatrix is not present
        if rotation == 0:
            tags = video_stream.get("tags", {})
            tag_rotation = tags.get("rotate", "0")
            try:
                rotation = int(tag_rotation)
            except (ValueError, TypeError):
                pass

        width = int(video_stream.get("width", 0))
        height = int(video_stream.get("height", 0))
        duration = float(video_stream.get("duration", 0))

        # Calculate effective display dimensions after rotation
        if abs(rotation) in (90, 270):
            effective_width, effective_height = height, width
        else:
            effective_width, effective_height = width, height

        # Audio check
        audio_check = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-select_streams", "a",
                "-show_entries", "stream=index",
                "-of", "csv=p=0",
                str(file_path),
            ],
            capture_output=True, text=True, check=True,
        )

        has_audio = bool(audio_check.stdout.strip())

        return {
            "duration": duration,
            "has_audio": has_audio,
            "width": width,
            "height": height,
            "rotation": rotation,
            "effective_width": effective_width,
            "effective_height": effective_height,
        }
    except Exception as e:
        logger.error(f"Error probing {file_path}: {e}")
        return {"duration": 0, "has_audio": False, "width": 0, "height": 0, "rotation": 0, "effective_width": 0, "effective_height": 0}


def _build_transpose_filter(rotation):
    """
    Returns the FFmpeg transpose filter chain needed to correct the given rotation.
    Transpose filter values:
      1 = 90° clockwise
      2 = 90° counter-clockwise
      3 = 90° counter-clockwise + vertical flip
    """
    if rotation == -90 or rotation == 270:
        return "transpose=1,"  # Rotate 90° CW to undo -90° CCW
    elif rotation == 90:
        return "transpose=2,"  # Rotate 90° CCW to undo 90° CW
    elif abs(rotation) == 180:
        return "transpose=1,transpose=1,"  # Two 90° CW = 180°
    return ""


def process_video(input_files):
    """
    Normalizes resolution to 1080x1920, handles rotation, and joins clips together.
    Handles missing audio streams by adding silent audio of exact duration.

    Key fix: All clips are now explicitly normalized to TARGET_WIDTH x TARGET_HEIGHT
    regardless of original resolution or rotation metadata, so the concat filter
    always receives identically-sized video streams.
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    final_output_path = os.path.join(OUTPUT_DIR, "final_video.mp4")

    if not input_files:
        raise ValueError("No input files provided.")

    video_files = sorted(
        [f for f in input_files if f.lower().endswith((".mp4", ".mov", ".mkv"))],
        key=natural_sort_key
    )
    audio_files = [f for f in input_files if f.lower().endswith((".wav", ".mp3"))]
    voiceover_path = audio_files[0] if audio_files else None

    if not video_files:
        raise ValueError("No video files found.")

    logger.info(f"Processing {len(video_files)} video clips...")
    if voiceover_path:
        logger.info(f"Voiceover detected: {os.path.basename(voiceover_path)}")

    v_filter = ""
    a_filter = ""
    concat_map = ""

    for i, v_path in enumerate(video_files):
        info = get_video_info(v_path)
        duration = info["duration"]
        has_audio = info["has_audio"]
        rotation = info["rotation"]
        eff_w = info["effective_width"]
        eff_h = info["effective_height"]

        logger.info(
            f"Clip {i}: {os.path.basename(v_path)} | "
            f"Raw: {info['width']}x{info['height']} | "
            f"Rotation: {rotation}° | "
            f"Display: {eff_w}x{eff_h} | "
            f"Duration: {duration:.1f}s | "
            f"Audio: {'Yes' if has_audio else 'No'}"
        )

        # ── Build per-clip video filter ──
        # Step 1: Correct rotation first (if any)
        transpose_filter = _build_transpose_filter(rotation)

        # Step 2: Scale to fit within TARGET, then pad to exact TARGET
        # After rotation correction, the dimensions are the "effective" display size.
        # We force everything to 1080x1920 (9:16 vertical).
        v_filter += (
            f"[{i}:v]"
            f"{transpose_filter}"
            f"scale={config.TARGET_WIDTH}:{config.TARGET_HEIGHT}:force_original_aspect_ratio=decrease,"
            f"pad={config.TARGET_WIDTH}:{config.TARGET_HEIGHT}:(ow-iw)/2:(oh-ih)/2,"
            f"fps=30,format=yuv420p,setsar=1[v{i}];"
        )

        # ── Build per-clip audio filter ──
        # Normalize to 44.1kHz / Stereo / FLTP
        if has_audio:
            a_filter += (
                f"[{i}:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo[a{i}];"
            )
        else:
            # Generate silent audio matching EXACT duration of the video clip
            a_filter += (
                f"anullsrc=r=44100:cl=stereo:d={duration},"
                f"aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo[a{i}];"
            )

        concat_map += f"[v{i}][a{i}]"

    # ── Concatenate all normalized streams ──
    filter_complex = (
        f"{v_filter}{a_filter}"
        f"{concat_map}concat=n={len(video_files)}:v=1:a=1[v_full][a_full]"
    )

    # ── Mix voiceover if present ──
    if voiceover_path:
        vo_idx = len(video_files)
        # Background at 0.8 volume, voiceover at 1.2 (slightly boosted)
        filter_complex += (
            f";[a_full]volume=0.8[a0];"
            f"[{vo_idx}:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo,"
            f"volume=1.2[a_vo];"
            f"[a0][a_vo]amix=inputs=2:duration=first:dropout_transition=2[a_final]"
        )

    # ── Build FFmpeg command ──
    cmd = ["ffmpeg", "-y"]
    for v in video_files:
        cmd.extend(["-i", v])
    if voiceover_path:
        cmd.extend(["-i", voiceover_path])

    cmd.extend(["-filter_complex", filter_complex])
    cmd.extend(["-map", "[v_full]"])

    if voiceover_path:
        cmd.extend(["-map", "[a_final]"])
    else:
        cmd.extend(["-map", "[a_full]"])

    cmd.extend([
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "192k",
        "-movflags", "+faststart",
        "-shortest",
        final_output_path,
    ])

    logger.info(f"Running FFmpeg to create {final_output_path}")
    logger.info(f"FFmpeg command: {' '.join(cmd[:10])}... ({len(cmd)} args)")

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error(f"FFmpeg failed (exit code {result.returncode}). stderr:\n{result.stderr[-2000:]}")
        raise Exception(f"FFmpeg failed with exit code {result.returncode}")

    logger.info(f"Video created successfully: {final_output_path}")
    return final_output_path
