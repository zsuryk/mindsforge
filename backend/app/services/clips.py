from dataclasses import dataclass

from app.services.transcription import TranscriptSegment

MIN_CLIP_DURATION = 15.0
MAX_CLIP_DURATION = 60.0
MIN_TAIL_DURATION = 5.0
TITLE_MAX_WORDS = 8

SENTENCE_END_CHARS = ".!?…"

WHITESPACE = " \t\n"


@dataclass
class ClipCandidate:
    title: str
    start: float
    end: float
    transcript_text: str


def _is_sentence_end(text: str) -> bool:
    stripped = text.rstrip(WHITESPACE)
    return bool(stripped) and stripped[-1] in SENTENCE_END_CHARS


def _segment_text(segments: list[TranscriptSegment]) -> str:
    return " ".join(segment.text.strip() for segment in segments).strip()


def _title_from_text(text: str) -> str:
    words = [word for word in text.split() if word]
    title = " ".join(words[:TITLE_MAX_WORDS])
    if not words:
        return "Untitled clip"
    if len(words) > TITLE_MAX_WORDS:
        return f"{title}…"
    return title


def build_clip_candidates(
    segments: list[TranscriptSegment],
    *,
    min_duration: float = MIN_CLIP_DURATION,
    max_duration: float = MAX_CLIP_DURATION,
) -> list[ClipCandidate]:
    """Split timed transcript segments into short-form clip candidates.

    Segments accumulate into a buffer; the buffer is flushed as a candidate
    when it reaches min_duration on a sentence boundary, or at max_duration
    as a hard cut (falling back to the last sentence boundary when it still
    satisfies min_duration). Any remaining tail is emitted when long enough
    to stand alone, otherwise folded into the previous candidate.
    """
    if not segments:
        return []

    candidates: list[ClipCandidate] = []
    buffer: list[TranscriptSegment] = []
    last_sentence_end_index = -1

    def flush(close_index: int, cap_duration: float | None = None) -> None:
        nonlocal buffer, last_sentence_end_index
        close = buffer[close_index]
        end = close.end
        if cap_duration is not None:
            end = min(end, buffer[0].start + cap_duration)
        candidate = ClipCandidate(
            title=_title_from_text(_segment_text(buffer[: close_index + 1])),
            start=buffer[0].start,
            end=end,
            transcript_text=_segment_text(buffer[: close_index + 1]),
        )
        candidates.append(candidate)
        buffer = buffer[close_index + 1 :]
        last_sentence_end_index = -1
        for index, segment in enumerate(buffer):
            if _is_sentence_end(segment.text):
                last_sentence_end_index = index

    for segment in segments:
        buffer.append(segment)
        if _is_sentence_end(segment.text):
            last_sentence_end_index = len(buffer) - 1

        buffer_duration = buffer[-1].end - buffer[0].start
        if buffer_duration >= max_duration:
            if last_sentence_end_index >= 0:
                boundary_end = buffer[last_sentence_end_index].end
                if boundary_end - buffer[0].start >= min_duration:
                    flush(last_sentence_end_index)
                    continue
            if len(buffer) > 1:
                flush(len(buffer) - 2)
            else:
                flush(0, cap_duration=max_duration)
        elif buffer_duration >= min_duration and last_sentence_end_index == len(buffer) - 1:
            flush(last_sentence_end_index)

    if buffer:
        tail_duration = buffer[-1].end - buffer[0].start
        if tail_duration >= MIN_TAIL_DURATION or not candidates:
            flush(len(buffer) - 1)
        else:
            previous = candidates[-1]
            previous.end = buffer[-1].end
            previous.transcript_text = (
                f"{previous.transcript_text} {_segment_text(buffer)}".strip()
            )

    return candidates
