import subprocess
from pathlib import Path


def create_portrait_trailer(
    full_video: Path,
    output_path: Path,
    duration_seconds: int = 180,
    subtitle_file: Path | None = None,
) -> Path:
    """2-minute portrait trailer for TikTok and Instagram Reels.

    Burns EN subtitles into the video when subtitle_file is provided — these
    platforms auto-mute on scroll so burned subs are essential for retention.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Portrait crop: take centre 607px of 1920w frame → scale to 1080x1920
    vf = "crop=607:1080:656:0,scale=1080:1920"
    if subtitle_file and subtitle_file.exists():
        # subtitles filter path must use forward slashes and escaped colons on all platforms
        srt_path = str(subtitle_file.resolve()).replace("\\", "/").replace(":", "\\:")
        vf += f",subtitles='{srt_path}':force_style='FontSize=18,PrimaryColour=&HFFFFFF,OutlineColour=&H000000,Outline=2'"

    subprocess.run([
        "ffmpeg", "-y",
        "-i", str(full_video),
        "-t", str(duration_seconds),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "192k",
        str(output_path)
    ], check=True, capture_output=True)

    sub_note = " + burned subtitles" if subtitle_file and subtitle_file.exists() else ""
    print(f"Trailer created: {output_path} ({duration_seconds}s, portrait 9:16{sub_note})")
    return output_path


def create_landscape_trailer(full_video: Path, output_path: Path, duration_seconds: int = 180) -> Path:
    """2-minute landscape trailer."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    subprocess.run([
        "ffmpeg", "-y",
        "-i", str(full_video),
        "-t", str(duration_seconds),
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "192k",
        str(output_path)
    ], check=True, capture_output=True)

    print(f"Landscape trailer created: {output_path} ({duration_seconds}s)")
    return output_path
