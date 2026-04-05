import os
import ffmpeg
from config import OUTPUT_DIR, DOWNLOAD_DIR, TARGET_WIDTH, TARGET_HEIGHT


def process_video(input_files):
    """
    Takes a list of file paths. Finds video clips and a voiceover (.wav).
    Concatenates videos with their audio, mixes in the voiceover,
    scales to vertical (1080x1920), and exports final_video.mp4.
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    final_output_path = os.path.join(OUTPUT_DIR, "final_video.mp4")

    if not input_files:
        raise ValueError("No input files provided to process_video.")

    video_files = sorted([f for f in input_files if f.lower().endswith((".mp4", ".mov"))])
    audio_files = [f for f in input_files if f.lower().endswith(".wav")]
    voiceover_path = audio_files[0] if audio_files else None

    if not video_files:
        raise ValueError("No video files found to process.")

    print(f"Processing {len(video_files)} video files with voiceover: {voiceover_path}")

    # Prepare input streams
    inputs = [ffmpeg.input(v) for v in video_files]
    
    # Each video input has [v] and [a]. We need to concat BOTH.
    # We use the filter_complex for safe concatenation of mixed sources.
    streams = []
    for i in inputs:
        streams.append(i.video)
        streams.append(i.audio)

    # Concat video and audio streams
    concat = ffmpeg.concat(*streams, v=1, a=1).node
    v_stream = concat[0]
    a_stream = concat[1]

    # Handle Voiceover mixing
    if voiceover_path:
        vo_input = ffmpeg.input(voiceover_path).audio
        # amix: duration=longest ensures we don't cut off if voiceover is longer than clips
        # or vice versa (usually voiceover defines the length)
        a_stream = ffmpeg.filter([a_stream, vo_input], 'amix', duration='longest')

    # Scale and Pad Visuals
    v_stream = ffmpeg.filter(
        v_stream,
        "scale",
        TARGET_WIDTH,
        TARGET_HEIGHT,
        force_original_aspect_ratio="decrease",
    )
    v_stream = ffmpeg.filter(
        v_stream,
        "pad",
        TARGET_WIDTH,
        TARGET_HEIGHT,
        "(ow-iw)/2",
        "(oh-ih)/2",
        "black",
    )

    try:
        # Final Output
        ffmpeg.output(
            v_stream,
            a_stream,
            final_output_path,
            vcodec="libx264",
            acodec="aac",
            strict="experimental"
        ).overwrite_output().run(capture_stdout=True, capture_stderr=True)
    except ffmpeg.Error as e:
        err_msg = e.stderr.decode() if e.stderr else "Unknown FFmpeg error"
        print(f"FFmpeg error: {err_msg}")
        raise

    print(f"Video processing complete: {final_output_path}")
    return final_output_path
