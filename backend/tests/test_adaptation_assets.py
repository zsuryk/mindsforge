import shutil
import subprocess
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.core.config import get_settings
from app.db.base import get_session_factory
from app.models.adaptation import ClipAdaptation
from app.models.clip import Clip
from app.models.job import Job
from app.services import media, minds
from app.services.adaptation_assets import (
    render_adaptation_assets,
    write_chapters,
    write_srt,
)
from app.services.transcription import TranscriptSegment

ffmpeg = shutil.which(get_settings().FFMPEG_BIN)
needs_ffmpeg = pytest.mark.skipif(ffmpeg is None, reason="ffmpeg not available")

LONG_FORM_FEATURES = {
    "chapters": [{"title": "Intro", "timestamp": 0.5}],
    "tags": ["editing"],
    "poll": {"question": "Which?", "options": ["A", "B"]},
    "quiz": [{"question": "What?", "answer": "This"}],
    "thumbnail_briefs": [
        {"frame_timestamp": 1.5, "overlay_text": "Wait for it"},
        {"frame_timestamp": 2.5, "overlay_text": "The reveal"},
        {"frame_timestamp": 3.5, "overlay_text": "You won't believe"},
    ],
    "shorts_link": "Why I left",
}

FAKE_SEGMENTS = [
    TranscriptSegment(text="intro.", start=0.0, end=1.2),
    TranscriptSegment(text="setup.", start=1.2, end=2.4),
    TranscriptSegment(text="punchline.", start=2.4, end=3.6),
    TranscriptSegment(text="reveal.", start=3.6, end=4.8),
    TranscriptSegment(text="outro.", start=4.8, end=6.0),
]

CLIP_START = 1.0
CLIP_END = 5.0


def _stub_extract_frame(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace the ffmpeg frame extraction step with a Pillow-drawn frame so
    the render path runs without a real ffmpeg binary."""

    def fake_extract(source: Path, dest: Path, timestamp: float) -> None:
        shade = int((timestamp % 1.0) * 255)
        Image.new("RGB", (320, 240), (shade, shade, 255 - shade)).save(dest)

    monkeypatch.setattr(media, "extract_frame_at_timestamp", fake_extract)


@needs_ffmpeg
def _make_sample_video(path: Path, duration: int = 6) -> None:
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
            f"sine=frequency=440:duration={duration}",
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


def make_clip(db, tmp_path: Path, video: Path, title: str = "Asset clip") -> Clip:
    job = Job(
        id=str(uuid4()),
        title="Source",
        source_url="https://example.com/video",
        file_path=str(video),
        transcript_segments=[
            {"text": s.text, "start": s.start, "end": s.end} for s in FAKE_SEGMENTS
        ],
    )
    db.add(job)
    db.commit()
    clip = Clip(
        id=str(uuid4()),
        job_id=job.id,
        title=title,
        start_time=CLIP_START,
        end_time=CLIP_END,
        transcript_text="intro. setup. punchline. reveal. outro.",
        file_path=str(video),
    )
    db.add(clip)
    db.commit()
    db.refresh(clip)
    return clip


def make_adaptation(
    db, clip: Clip, *, platform: str, surface: str, features: dict
) -> ClipAdaptation:
    adaptation = ClipAdaptation(
        clip_id=clip.id, platform=platform, surface=surface, features=features
    )
    db.add(adaptation)
    db.commit()
    db.refresh(adaptation)
    return adaptation


def _count_whiteish_pixels(image: Image.Image) -> int:
    pixels = list(image.getdata())
    return sum(1 for r, g, b in pixels if r > 200 and g > 200 and b > 200)


@needs_ffmpeg
def test_render_long_form_creates_three_thumbnails_srt_and_chapters(
    client: tuple[TestClient, Path],
) -> None:
    test_client, tmp_path = client
    video = tmp_path / "source.mp4"
    _make_sample_video(video)

    with get_session_factory()() as db:
        clip = make_clip(db, tmp_path, video)
        adaptation = make_adaptation(
            db,
            clip,
            platform="youtube",
            surface="LONG_FORM",
            features=LONG_FORM_FEATURES,
        )
        assets = render_adaptation_assets(db, adaptation)

    variants = assets["thumbnail_variants"]
    assert [variant["id"] for variant in variants] == ["thumb_1", "thumb_2", "thumb_3"]
    assert [variant["overlay_text"] for variant in variants] == [
        "Wait for it",
        "The reveal",
        "You won't believe",
    ]
    for variant in variants:
        path = Path(variant["file_path"])
        assert path.is_file()
        with Image.open(path) as image:
            assert image.size == (1280, 720)

    captions = Path(assets["captions_file"])
    content = captions.read_text(encoding="utf-8")
    assert content.startswith("1\n00:00:00,000 --> 00:00:00,200\nintro.\n")
    assert "00:00:01,400 --> 00:00:02,600\npunchline.\n" in content
    assert "00:00:03,800 --> 00:00:05,000\noutro.\n"

    chapters = Path(assets["chapters_file"])
    assert chapters.read_text(encoding="utf-8").splitlines() == ["00:01 Intro"]


@needs_ffmpeg
def test_render_shorts_and_tiktok_use_vertical_ratio(
    client: tuple[TestClient, Path],
) -> None:
    test_client, tmp_path = client
    video = tmp_path / "source.mp4"
    _make_sample_video(video)

    shorts_features = {
        "thumbnail_briefs": [
            {"frame_timestamp": 1.5, "overlay_text": "one"},
            {"frame_timestamp": 2.5, "overlay_text": "two"},
            {"frame_timestamp": 3.5, "overlay_text": "three"},
        ],
        "platform_hooks": ["hook"],
    }
    tiktok_features = {
        "overlay_spec": [
            {"text": "punchline!", "placement": "center", "style": "bold"},
            {"text": "reveal...", "placement": "top", "style": "italic"},
        ],
        "caption_style": "bold white",
        "stickers": [{"emoji": "fire", "placement": "top-right"}],
        "pinned_comment": "First!",
    }

    with get_session_factory()() as db:
        clip = make_clip(db, tmp_path, video)

        shorts = make_adaptation(
            db, clip, platform="youtube", surface="SHORTS", features=shorts_features
        )
        shorts_assets = render_adaptation_assets(db, shorts)
        assert len(shorts_assets["thumbnail_variants"]) == 3
        for variant in shorts_assets["thumbnail_variants"]:
            with Image.open(Path(variant["file_path"])) as image:
                assert image.size == (1080, 1920)

        tiktok = make_adaptation(
            db, clip, platform="tiktok", surface="POST", features=tiktok_features
        )
        tiktok_assets = render_adaptation_assets(db, tiktok)
        assert len(tiktok_assets["thumbnail_variants"]) == 2
        assert tiktok_assets["thumbnail_variants"][0]["overlay_text"] == "punchline!"
        assert tiktok_assets["thumbnail_variants"][1]["overlay_text"] == "reveal..."
        for variant in tiktok_assets["thumbnail_variants"]:
            with Image.open(Path(variant["file_path"])) as image:
                assert image.size == (1080, 1920)


def test_render_composites_overlay_text_onto_frames(
    client: tuple[TestClient, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    _stub_extract_frame(monkeypatch)
    test_client, tmp_path = client
    video = tmp_path / "source.mp4"
    video.write_bytes(b"video")

    features = {
        "thumbnail_briefs": [
            {"frame_timestamp": 1.5, "overlay_text": "WAIT"},
            {"frame_timestamp": 2.5, "overlay_text": "REVEAL"},
            {"frame_timestamp": 3.5, "overlay_text": ""},
        ],
        "platform_hooks": ["hook"],
    }
    with get_session_factory()() as db:
        clip = make_clip(db, tmp_path, video)
        adaptation = make_adaptation(
            db, clip, platform="youtube", surface="SHORTS", features=features
        )
        assets = render_adaptation_assets(db, adaptation)

    with Image.open(Path(assets["thumbnail_variants"][0]["file_path"])) as image:
        assert _count_whiteish_pixels(image) > 50
    with Image.open(Path(assets["thumbnail_variants"][2]["file_path"])) as image:
        assert _count_whiteish_pixels(image) < 10


def test_write_srt_offsets_to_clip_start(tmp_path: Path) -> None:
    path = tmp_path / "captions.srt"
    write_srt(path, FAKE_SEGMENTS, clip_start=CLIP_START)
    content = path.read_text(encoding="utf-8")
    assert content.startswith("1\n00:00:00,000 --> 00:00:00,200\nintro.\n")
    assert "00:00:01,400 --> 00:00:02,600\npunchline.\n" in content
    assert content.strip().endswith("outro.")


def test_write_chapters_maps_to_nearest_segment_boundary(tmp_path: Path) -> None:
    path = tmp_path / "chapters.txt"
    write_chapters(
        path,
        [{"title": "Intro", "timestamp": 0.5}, {"title": "Reveal", "timestamp": 2.8}],
        FAKE_SEGMENTS,
        clip_start=CLIP_START,
    )
    assert path.read_text(encoding="utf-8").splitlines() == [
        "00:01 Intro",
        "00:03 Reveal",
    ]


def test_render_fails_closed_when_source_missing(
    client: tuple[TestClient, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    _stub_extract_frame(monkeypatch)
    test_client, tmp_path = client
    video = tmp_path / "source.mp4"
    video.write_bytes(b"video")

    from app.services.adaptation_assets import AdaptationAssetError

    with get_session_factory()() as db:
        clip = make_clip(db, tmp_path, video)
        adaptation = make_adaptation(
            db,
            clip,
            platform="youtube",
            surface="LONG_FORM",
            features=LONG_FORM_FEATURES,
        )
        Path(video).unlink()
        with pytest.raises(AdaptationAssetError, match="Source media missing"):
            render_adaptation_assets(db, adaptation)


@needs_ffmpeg
def test_adaptation_api_serves_rendered_assets(
    client: tuple[TestClient, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    test_client, tmp_path = client
    video = tmp_path / "source.mp4"
    _make_sample_video(video)

    with get_session_factory()() as db:
        clip = make_clip(db, tmp_path, video)
        clip_id = clip.id

    def _stub_features(clip, platform, surface, segments, memory_context=None):
        return minds.AdaptationFeatures(
            platform=platform, surface=surface, **LONG_FORM_FEATURES
        )

    monkeypatch.setattr(minds, "generate_adaptation_features", _stub_features)

    res = test_client.post(f"/api/v1/clips/{clip_id}/adaptations/youtube/LONG_FORM")
    assert res.status_code == 202
    detail = test_client.get(
        f"/api/v1/clips/{clip_id}/adaptations/{res.json()['id']}"
    ).json()
    assert detail["status"] == "READY"
    assets = detail["assets"]
    assert assets is not None
    assert len(assets["thumbnail_variants"]) == 3
    first_url = assets["thumbnail_variants"][0]["url"]
    assert first_url.startswith("/media/adaptations/")
    assert first_url.endswith("/thumb_1.png")
    assert assets["captions_url"].endswith("/captions.srt")
    assert assets["chapters_url"].endswith("/chapters.txt")

    fetched = test_client.get(first_url)
    assert fetched.status_code == 200
    assert fetched.headers["content-type"] == "image/png"