import shutil
import subprocess
from pathlib import Path

import pytest

from app.core.config import get_settings
from app.services.media import extract_audio

ffmpeg = shutil.which(get_settings().FFMPEG_BIN)


@pytest.mark.skipif(ffmpeg is None, reason="ffmpeg not available")
def test_extract_audio_produces_16khz_mono_wav(tmp_path: Path) -> None:
    source = tmp_path / "sample.mp4"
    ffprobe = Path(ffmpeg).with_name("ffprobe")
    if not ffprobe.is_file():
        ffprobe = shutil.which("ffprobe") or "ffprobe"
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=duration=1:size=320x240:rate=24",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=1",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            str(source),
        ],
        capture_output=True,
        check=True,
    )

    dest = extract_audio(source, tmp_path / "audio.wav")

    probe = subprocess.run(
        [ffprobe, "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=codec_name,sample_rate,channels", "-of", "csv=p=0", str(dest)],
        capture_output=True,
        text=True,
        check=True,
    )
    assert probe.stdout.strip() == "pcm_s16le,16000,1"


def test_extract_audio_missing_binary_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FFMPEG_BIN", "/nonexistent/ffmpeg")
    get_settings.cache_clear()

    from app.services.media import MediaError

    with pytest.raises(MediaError, match="FFmpeg binary not found"):
        extract_audio(tmp_path / "input.mp4", tmp_path / "out.wav")

    get_settings.cache_clear()
