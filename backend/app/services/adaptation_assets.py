import logging
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

from app.core.config import get_settings
from app.models.adaptation import ClipAdaptation
from app.services import media
from app.services.transcription import TranscriptSegment

logger = logging.getLogger(__name__)

SURFACE_DIMENSIONS = {
    "LONG_FORM": (1280, 720),
    "SHORTS": (1080, 1920),
    "POST": (1080, 1920),
}

FONT_CANDIDATES: dict[str, tuple[str, ...]] = {
    "bold": (
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ),
    "italic": (
        "/usr/share/fonts/dejavu/DejaVuSans-Oblique.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Italic.ttf",
    ),
}

PLACEMENT_ZONES = {"top": 0.08, "center": 0.5, "bottom": 0.78}


class AdaptationAssetError(RuntimeError):
    pass


def _caption_style_keyword(caption_style: str | None) -> str | None:
    """Map the brief's caption style text to a font style keyword."""
    lowered = (caption_style or "").lower()
    if "italic" in lowered:
        return "italic"
    if "bold" in lowered:
        return "bold"
    return None


def _clip_window_segments(
    segments: list[TranscriptSegment], clip_start: float, clip_end: float
) -> list[TranscriptSegment]:
    return [
        segment
        for segment in segments
        if segment.end > clip_start and segment.start < clip_end
    ]


def _thumbnail_briefs(
    adaptation: ClipAdaptation,
    segments: list[TranscriptSegment],
) -> list[dict]:
    """Decide which frames carry overlay text for this adaptation's surface."""
    features = adaptation.features or {}
    surface = adaptation.surface.value
    if surface in ("SHORTS", "LONG_FORM"):
        return [
            {
                "frame_timestamp": float(brief.get("frame_timestamp") or 0.0),
                "overlay_text": str(brief.get("overlay_text") or ""),
                "placement": "bottom",
            }
            for brief in (features.get("thumbnail_briefs") or [])
        ]
    if surface == "POST":
        specs = features.get("overlay_spec") or []
        if len(specs) > len(segments):
            raise AdaptationAssetError(
                f"{len(specs)} overlay specs for only {len(segments)} segments "
                "in the clip window; the manifest cannot be rendered"
            )
        caption_keyword = _caption_style_keyword(features.get("caption_style"))
        briefs = []
        for spec, segment in zip(specs, segments):
            placement = spec.get("placement", "center")
            briefs.append(
                {
                    "frame_timestamp": segment.start,
                    "overlay_text": str(spec.get("text") or ""),
                    "placement": placement,
                    "style": (
                        caption_keyword
                        if placement == "center" and caption_keyword
                        else spec.get("style") or "bold"
                    ),
                }
            )
        return briefs
    return []


def _font_for(
    size: int, style: str = "bold"
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    bold_candidates = FONT_CANDIDATES["bold"]
    preferred = FONT_CANDIDATES.get(style) or bold_candidates
    candidates = (
        preferred if preferred is bold_candidates else [*preferred, *bold_candidates]
    )
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in str(text).split("\n"):
        words = paragraph.split()
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if draw.textlength(candidate, font=font) <= max_width or not current:
                current = candidate
            else:
                lines.append(current)
                current = word
        if current:
            lines.append(current)
    return lines or [""]


def _compose_overlay(
    frame_path: Path,
    text: str,
    placement: str,
    surface: str,
    style: str = "bold",
) -> None:
    """Center-crop to the surface aspect ratio and composite the overlay text.

    `style` selects the font family (bold/italic) so the rendered asset
    matches the brief instead of every overlay getting identical bold text.
    """
    dimensions = SURFACE_DIMENSIONS.get(surface, (1280, 720))
    with Image.open(frame_path) as image:
        image = ImageOps.fit(image, dimensions, method=Image.Resampling.LANCZOS)
        draw = ImageDraw.Draw(image)
        font_size = max(24, dimensions[0] // 16)
        font = _font_for(font_size, style)
        max_width = dimensions[0] - 2 * (dimensions[0] // 16)
        lines = _wrap_text(draw, text, font, max_width)
        line_height = font_size
        block_height = len(lines) * line_height
        anchor_y = int(PLACEMENT_ZONES.get(placement, 0.78) * dimensions[1])
        if placement == "top":
            start_y = max(block_height // 2, dimensions[1] // 14)
        elif placement == "center":
            start_y = anchor_y - block_height // 2
        else:
            start_y = min(anchor_y, dimensions[1] - block_height - dimensions[1] // 16)
        stroke_width = max(4, dimensions[0] // 200)
        for index, line in enumerate(lines):
            y = min(
                max(start_y + index * line_height + line_height // 2, line_height),
                dimensions[1] - line_height,
            )
            draw.text(
                (dimensions[0] / 2, y),
                line,
                font=font,
                fill="white",
                stroke_width=stroke_width,
                stroke_fill="black",
                anchor="mm",
            )
        image.save(frame_path)


def _srt_timestamp(seconds: float) -> str:
    total_ms = round(max(0.0, seconds) * 1000)
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _chapter_timestamp(seconds: float) -> str:
    minutes, secs = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def write_srt(path: Path, segments: list[TranscriptSegment], clip_start: float) -> Path:
    """Write clip-relative SRT captions for the clip-window segments."""
    blocks = []
    for index, segment in enumerate(segments, start=1):
        start = max(0.0, segment.start - clip_start)
        end = max(start, segment.end - clip_start)
        blocks.append(
            f"{index}\n"
            f"{_srt_timestamp(start)} --> {_srt_timestamp(end)}\n"
            f"{segment.text.strip()}\n"
        )
    path.write_text("\n\n".join(blocks), encoding="utf-8")
    return path


def write_chapters(path: Path, chapters: list[dict]) -> Path:
    """Write a chapter list with the manifest timestamps verbatim, so the
    file matches the chapter panels the creator copies from (no snapping to
    segment boundaries, no clip-start offset)."""
    lines = [
        f"{_chapter_timestamp(float(chapter.get('timestamp') or 0.0))} "
        f"{chapter.get('title', '')}"
        for chapter in chapters
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def render_adaptation_assets(adaptation: ClipAdaptation) -> dict:
    """Render the downloadable assets for an adaptation into
    `media/adaptations/{id}/` and return the assets JSON (file paths).

    Raises on any failure (missing source media, ffmpeg frame extraction,
    Pillow compositing, excess overlay specs) so the caller fails the
    adaptation closed.
    """
    clip = adaptation.clip
    if clip is None:
        raise AdaptationAssetError("Adaptation references a missing clip")
    job = clip.job
    if job is None or not job.file_path:
        raise AdaptationAssetError("Clip job has no source media for frame extraction")
    source = Path(job.file_path)
    if not source.is_file():
        raise AdaptationAssetError(f"Source media missing: {source}")

    raw_segments = [
        TranscriptSegment(**segment) for segment in (job.transcript_segments or [])
    ]
    segments = _clip_window_segments(raw_segments, clip.start_time, clip.end_time)

    out_dir = get_settings().MEDIA_DIR / "adaptations" / adaptation.id
    out_dir.mkdir(parents=True, exist_ok=True)

    assets: dict = {
        "thumbnail_variants": [],
        "captions_file": None,
        "chapters_file": None,
    }

    for index, brief in enumerate(_thumbnail_briefs(adaptation, segments), start=1):
        frame_path = out_dir / f"thumb_{index}.png"
        media.extract_frame_at_timestamp(source, frame_path, brief["frame_timestamp"])
        _compose_overlay(
            frame_path,
            brief["overlay_text"],
            brief["placement"],
            adaptation.surface.value,
            brief.get("style", "bold"),
        )
        assets["thumbnail_variants"].append(
            {
                "id": f"thumb_{index}",
                "frame_timestamp": brief["frame_timestamp"],
                "overlay_text": brief["overlay_text"],
                "file_path": str(frame_path),
            }
        )

    captions_path = out_dir / "captions.srt"
    write_srt(captions_path, segments, clip.start_time)
    assets["captions_file"] = str(captions_path)

    if adaptation.surface.value == "LONG_FORM":
        chapters_path = out_dir / "chapters.txt"
        write_chapters(
            chapters_path,
            (adaptation.features or {}).get("chapters") or [],
        )
        assets["chapters_file"] = str(chapters_path)

    logger.info("Adaptation %s: rendered assets in %s", adaptation.id, out_dir)
    return assets