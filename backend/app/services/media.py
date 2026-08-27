import logging
import shutil
import subprocess
from pathlib import Path

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class MediaError(RuntimeError):
    pass


def media_url(path: str | None) -> str | None:
    """Render a stored media path as a servable /media/... URL, or None when
    the path lives outside the configured media directory."""
    if not path:
        return None
    media_dir = get_settings().MEDIA_DIR.resolve()
    try:
        relative = Path(path).resolve().relative_to(media_dir)
    except ValueError:
        return None
    return f"/media/{relative.as_posix()}"


def _ffmpeg_bin() -> Path:
    configured = get_settings().FFMPEG_BIN
    found = shutil.which(configured)
    if found:
        return Path(found).resolve()
    path = Path(configured)
    if path.is_file():
        return path.resolve()
    raise MediaError(f"FFmpeg binary not found: {configured}")


def fetch_video_title(url: str) -> str | None:
    """Extract the video title from a URL without downloading."""
    import yt_dlp

    opts = {
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return info.get("title")
    except Exception as exc:
        logger.warning("Could not extract title for %s: %s", url, exc)
        return None


def download_video(url: str, target_dir: Path) -> Path:
    """Download a source URL into target_dir and return the media file path."""
    import yt_dlp

    target_dir.mkdir(parents=True, exist_ok=True)
    opts = {
        "format": "bestvideo+bestaudio/best",
        "outtmpl": str(target_dir / "%(id)s.%(ext)s"),
        "merge_output_format": "mp4",
        "ffmpeg_location": str(_ffmpeg_bin().parent),
        "quiet": True,
        "no_warnings": True,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.extract_info(url, download=True)
    except Exception as exc:
        raise MediaError(f"Failed to download {url}: {exc}") from exc

    files = [
        p
        for p in target_dir.iterdir()
        if p.is_file() and p.suffix not in (".part", ".ytdl")
    ]
    if not files:
        raise MediaError(f"Download of {url} produced no media file")
    return max(files, key=lambda p: p.stat().st_size)


def extract_audio(source: Path, dest: Path) -> Path:
    """Extract a Whisper-ready 16kHz mono WAV from a media file."""
    cmd = [
        str(_ffmpeg_bin()),
        "-y",
        "-nostdin",
        "-i",
        str(source),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        "-loglevel",
        "error",
        str(dest),
    ]
    return _run_ffmpeg(cmd, "audio extraction", source, dest)


def _run_ffmpeg(cmd: list[str], action: str, source: Path, dest: Path) -> Path:
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0 or not dest.is_file():
        stderr = result.stderr.strip()
        raise MediaError(
            f"FFmpeg {action} failed for {source}: {stderr or 'unknown error'}"
        )
    return dest


def cut_clip(source: Path, dest: Path, start: float, end: float) -> Path:
    """Cut [start, end] from a media file via lossless stream copy.

    Uses fast-seek (-ss before -i) with ``-c copy`` so no re-encoding
    occurs. Cuts land on the nearest preceding keyframe, making this
    near-instant regardless of clip duration. Start/end points may be
    a few frames off due to keyframe alignment.
    """
    duration = max(0.0, end - start)
    cmd = [
        str(_ffmpeg_bin()),
        "-y",
        "-nostdin",
        "-ss",
        f"{start:.3f}",
        "-i",
        str(source),
        "-t",
        f"{duration:.3f}",
        "-map",
        "0:v:0?",
        "-map",
        "0:a:0?",
        "-c",
        "copy",
        "-movflags",
        "+faststart",
        "-loglevel",
        "error",
        str(dest),
    ]
    return _run_ffmpeg(cmd, "clip cut", source, dest)


def extract_frame_at_timestamp(source: Path, dest: Path, timestamp: float) -> Path:
    """Capture a single PNG frame from a media file at the given timestamp."""
    cmd = [
        str(_ffmpeg_bin()),
        "-y",
        "-nostdin",
        "-ss",
        f"{timestamp:.3f}",
        "-i",
        str(source),
        "-frames:v",
        "1",
        "-loglevel",
        "error",
        str(dest),
    ]
    return _run_ffmpeg(cmd, "frame extraction", source, dest)
