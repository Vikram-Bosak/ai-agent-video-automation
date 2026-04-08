import os
import json
import subprocess
import logging
import config
from config import OUTPUT_DIR

logger = logging.getLogger(__name__)


def get_video_info(file_path):
    try:
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=duration,width,height",
            "-of",
            "json",
            str(file_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        
        # Audio check
        audio_check = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "a",
                "-show_entries",
                "stream=index",
                "-of",
                "csv=p=0",
                str(file_path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        
        duration = float(data["streams"][0].get("duration", 0))
        has_audio = bool(audio_check.stdout.strip())
        return {"duration": duration, "has_audio": has_audio}
    except Exception as e:
        logger.error(f"Error probing {file_path}: {e}")
        return {"duration": 0, "has_audio": False}


def process_video(input_files):
    """
    Normalizes resolution to 1080x1920 and joins clips together.
    Handles missing audio streams by adding silent audio of exact duration.
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    final_output_path = os.path.join(OUTPUT_DIR, "final_video.mp4")

    if not input_files:
        raise ValueError("No input files provided.")

    video_files = sorted(
        [f for f in input_files if f.lower().endswith((".mp4", ".mov", ".mkv"))]
    )
    audio_files = [f for f in input_files if f.lower().endswith((".wav", ".mp3"))]
    voiceover_path = audio_files[0] if audio_files else None

    if not video_files:
        raise ValueError("No video files found.")

    v_filter = ""
    a_filter = ""
    concat_map = ""

    for i, v_path in enumerate(video_files):
        info = get_video_info(v_path)
        duration = info["duration"]
        has_audio = info["has_audio"]

        # Video normalization: Scale, Pad, FPS 30, Format
        v_filter += (
            f"[{i}:v]scale={config.TARGET_WIDTH}:{config.TARGET_HEIGHT}:force_original_aspect_ratio=decrease,"
            f"pad={config.TARGET_WIDTH}:{config.TARGET_HEIGHT}:(ow-iw)/2:(oh-ih)/2,"
            f"fps=30,format=yuv420p,setsar=1[v{i}];"
        )

        # Audio normalization: Ensure 44.1k/Stereo
        if has_audio:
            a_filter += f"[{i}:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo[a{i}];"
        else:
            # Generate silent audio matching EXACT duration of the video clip
            # We use d={duration} to ensure it stops exactly with the video
            v_filter += f"anullsrc=r=44100:cl=stereo:d={duration}[asilent{i}];"
            a_filter += f"[asilent{i}]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo[a{i}];"

        concat_map += f"[v{i}][a{i}]"

    # Concatenate all normalized streams
    filter_complex = f"{v_filter}{a_filter}{concat_map}concat=n={len(video_files)}:v=1:a=1[v_full][a_full]"

    if voiceover_path:
        vo_idx = len(video_files)
        # Mix audio: background at 0.8, voiceover at 1.2 (Slightly boosted)
        filter_complex += (
            f";[a_full]volume=0.8[a0];"
            f"[{vo_idx}:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo,volume=1.2[a_vo];"
            f"[a0][a_vo]amix=inputs=2:duration=first:dropout_transition=2[a_final]"
        )

    # Build command
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

    cmd.extend(
        [
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "192k",
            "-movflags", "+faststart"
        ]
    )

    # Shortest to ensure video duration is the master
    cmd.append("-shortest")
    cmd.append(final_output_path)

    logger.info(f"Running FFmpeg to create {final_output_path}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error(f"FFmpeg failed. stderr: {result.stderr}")
        raise Exception(f"FFmpeg failed with exit code {result.returncode}")

    return final_output_path
