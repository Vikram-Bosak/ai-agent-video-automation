import os
import subprocess
from config import OUTPUT_DIR


def process_video(input_files):
    """
    Videos are already in short/Reels format (9:16 vertical).
    Just join clips together and add voiceover.
    """
    import os
    import subprocess
    from config import OUTPUT_DIR

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    final_output_path = os.path.join(OUTPUT_DIR, "final_video.mp4")

    if not input_files:
        raise ValueError("No input files provided.")

    video_files = sorted(
        [f for f in input_files if f.lower().endswith((".mp4", ".mov"))]
    )
    audio_files = [f for f in input_files if f.lower().endswith(".wav")]
    voiceover_path = audio_files[0] if audio_files else None

    if not video_files:
        raise ValueError("No video files found.")

    # Create concat list file
    concat_file = os.path.join(OUTPUT_DIR, "concat_list.txt")
    with open(concat_file, "w") as f:
        for v in video_files:
            f.write(f"file '{v}'\n")

    if voiceover_path:
        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            concat_file,
            "-i",
            voiceover_path,
            "-filter_complex",
            "[0:a]volume=0.4[a0];[1:a][a0]amix=inputs=2:duration=longest[a]",
            "-map",
            "0:v",
            "-map",
            "[a]",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-shortest",
            final_output_path,
        ]
    else:
        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            concat_file,
            "-c",
            "copy",
            final_output_path,
        ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception("FFmpeg failed")

    if os.path.exists(concat_file):
        os.remove(concat_file)

    return final_output_path
