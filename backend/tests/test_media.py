import shutil
import subprocess
from pathlib import Path

import pytest

from app.core.config import get_settings
from app.services.media import cut_clip, extract_audio, extract_frame_at_timestamp

ffmpeg = shutil.which(get_settings().FFMPEG_BIN)


def _make_sample_video(path: Path, duration: int = 3) -> None:
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"testsrc2=duration={duration}:size=320x240:rate=24",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=3",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            str(path),
        ],
        capture_output=True,
        check=True,
    )


def _probe(ffprobe: str, path: Path, *entries: str) -> str:
    result = subprocess.run(
        [ffprobe, "-v", "error", "-select_streams", "v:0", *entries, "-of", "csv=p=0", str(path)],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


@pytest.mark.skipif(ffmpeg is None, reason="ffmpeg not available")
def test_extract_audio_produces_16khz_mono_wav(tmp_path: Path) -> None:
    source = tmp_path / "sample.mp4"
    ffprobe = Path(ffmpeg).with_name("ffprobe")
    if not ffprobe.is_file():
        ffprobe = shutil.which("ffprobe") or "ffprobe"
    _make_sample_video(source)

    dest = extract_audio(source, tmp_path / "audio.wav")

    probe = subprocess.run(
        [ffprobe, "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=codec_name,sample_rate,channels", "-of", "csv=p=0", str(dest)],
        capture_output=True,
        text=True,
        check=True,
    )
    assert probe.stdout.strip() == "pcm_s16le,16000,1"


@pytest.mark.skipif(ffmpeg is None, reason="ffmpeg not available")
def test_cut_clip_produces_h264_mp4_of_requested_duration(tmp_path: Path) -> None:
    source = tmp_path / "sample.mp4"
    ffprobe = Path(ffmpeg).with_name("ffprobe")
    if not ffprobe.is_file():
        ffprobe = shutil.which("ffprobe") or "ffprobe"
    _make_sample_video(source, duration=3)

    dest = cut_clip(source, tmp_path / "clip.mp4", start=0.5, end=2.0)

    assert dest.is_file()
    assert dest.suffix == ".mp4"
    assert "h264" in _probe(ffprobe, dest, "-show_entries", "stream=codec_name")

    duration = float(
        subprocess.run(
            [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(dest)],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    )
    assert 0.9 <= duration <= 2.1


@pytest.mark.skipif(ffmpeg is None, reason="ffmpeg not available")
def test_extract_frame_at_timestamp_captures_png(tmp_path: Path) -> None:
    source = tmp_path / "sample.mp4"
    ffprobe = Path(ffmpeg).with_name("ffprobe")
    if not ffprobe.is_file():
        ffprobe = shutil.which("ffprobe") or "ffprobe"
    _make_sample_video(source, duration=3)

    dest = extract_frame_at_timestamp(source, tmp_path / "thumb.png", timestamp=1.0)

    assert dest.is_file()
    assert dest.suffix == ".png"
    assert _probe(ffprobe, dest, "-show_entries", "stream=codec_name") == "png"


def test_extract_audio_missing_binary_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FFMPEG_BIN", "/nonexistent/ffmpeg")
    get_settings.cache_clear()

    from app.services.media import MediaError

    with pytest.raises(MediaError, match="FFmpeg binary not found"):
        extract_audio(tmp_path / "input.mp4", tmp_path / "out.wav")

    get_settings.cache_clear()
