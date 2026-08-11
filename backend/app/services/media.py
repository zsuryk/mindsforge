import logging
import shutil
import subprocess
from pathlib import Path

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class MediaError(RuntimeError):
    pass


def _ffmpeg_bin() -> Path:
    configured = get_settings().FFMPEG_BIN
    found = shutil.which(configured)
    if found:
        return Path(found).resolve()
    path = Path(configured)
    if path.is_file():
        return path.resolve()
    raise MediaError(f"FFmpeg binary not found: {configured}")


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
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0 or not dest.is_file():
        stderr = result.stderr.strip()
        raise MediaError(
            f"FFmpeg audio extraction failed for {source}: {stderr or 'unknown error'}"
        )
    return dest
