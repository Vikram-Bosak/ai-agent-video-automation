import os
import ffmpeg
from config import OUTPUT_DIR, DOWNLOAD_DIR, TARGET_WIDTH, TARGET_HEIGHT


def process_video(input_files):
    """
    Takes a list of file paths (videos), merges them,
    scales to vertical (1080x1920), and exports a single final_video.mp4.
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    final_output_path = os.path.join(OUTPUT_DIR, "final_video.mp4")

    if not input_files:
        raise ValueError("No input files provided to process_video.")

    video_files = [f for f in input_files if f.lower().endswith((".mp4", ".mov"))]

    if not video_files:
        raise ValueError("No video files found to process.")

    print(f"Processing {len(video_files)} video files...")

    if len(video_files) == 1:
        single_video = video_files[0]
        try:
            stream = ffmpeg.input(single_video)
            stream = ffmpeg.filter(
                stream,
                "scale",
                TARGET_WIDTH,
                TARGET_HEIGHT,
                force_original_aspect_ratio="decrease",
            )
            stream = ffmpeg.filter(
                stream,
                "pad",
                TARGET_WIDTH,
                TARGET_HEIGHT,
                "(ow-iw)/2",
                "(oh-ih)/2",
                "black",
            )
            ffmpeg.output(
                stream, final_output_path, vcodec="libx264", acodec="aac"
            ).overwrite_output().run(capture_stdout=True, capture_stderr=True)
        except ffmpeg.Error as e:
            print(f"FFmpeg error: {e.stderr.decode()}")
            raise
        print(f"Video processing complete: {final_output_path}")
        return final_output_path

    concat_file_path = os.path.join(DOWNLOAD_DIR, "concat.txt")
    with open(concat_file_path, "w") as f:
        for vf in video_files:
            f.write(f"file '{os.path.abspath(vf)}'\n")

    temp_merged = os.path.join(OUTPUT_DIR, "temp_merged.mp4")

    try:
        ffmpeg.input(concat_file_path, format="concat", safe=0).output(
            temp_merged, c="copy"
        ).overwrite_output().run(capture_stdout=True, capture_stderr=True)
    except ffmpeg.Error as e:
        print(f"Concat copy failed, re-encoding: {e.stderr.decode()}")
        ffmpeg.input(concat_file_path, format="concat", safe=0).output(
            temp_merged, vcodec="libx264", acodec="aac"
        ).overwrite_output().run(capture_stdout=True, capture_stderr=True)

    try:
        stream = ffmpeg.input(temp_merged)
        stream = ffmpeg.filter(
            stream,
            "scale",
            TARGET_WIDTH,
            TARGET_HEIGHT,
            force_original_aspect_ratio="decrease",
        )
        stream = ffmpeg.filter(
            stream,
            "pad",
            TARGET_WIDTH,
            TARGET_HEIGHT,
            "(ow-iw)/2",
            "(oh-ih)/2",
            "black",
        )
        ffmpeg.output(
            stream, final_output_path, vcodec="libx264", acodec="aac"
        ).overwrite_output().run(capture_stdout=True, capture_stderr=True)
    except ffmpeg.Error as e:
        print(f"Scale failed: {e.stderr.decode()}")
        ffmpeg.input(temp_merged).output(
            final_output_path,
            vcodec="libx264",
            acodec="aac",
            **{"s": f"{TARGET_WIDTH}x{TARGET_HEIGHT}"},
        ).overwrite_output().run()

    if os.path.exists(temp_merged):
        os.remove(temp_merged)
    if os.path.exists(concat_file_path):
        os.remove(concat_file_path)

    print(f"Video processing complete: {final_output_path}")
    return final_output_path
