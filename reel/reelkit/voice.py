"""Choosing the voice reference: a 15-25 s span of the author's recording that ends on a full sentence.

The course asks for "entre 15 y 25 segundos de su propia voz como referencia". Whisper splits the long
recording into segments; this module picks the clearest run of consecutive segments that lasts 15 to
25 s, has no long pause inside and ends where a sentence ends. The approach follows the author's
earlier `texto-a-voz-reel-1/preparar_voz.py` (confidence and volume-stability score).
"""
from __future__ import annotations

from dataclasses import dataclass, field

SENTENCE_END = (".", "?", "!", "…")


@dataclass(frozen=True)
class Segment:
    """A Whisper segment: time span, text and confidence."""

    start: float
    end: float
    text: str
    avg_logprob: float = 0.0
    no_speech_prob: float = 0.0


@dataclass(frozen=True)
class Window:
    """The chosen cut, already padded, in seconds of the original recording."""

    start: float
    end: float
    text: str
    score: float
    segments: list[Segment] = field(default_factory=list, compare=False)

    @property
    def duration(self) -> float:
        return self.end - self.start


def _padded(segs: list[Segment], i: int, j: int, pad_before: float, pad_after: float) -> tuple[float, float]:
    """Pad the window a little without reaching into the neighbouring speech."""
    start = segs[i].start - pad_before
    if i > 0:
        start = max(start, (segs[i - 1].end + segs[i].start) / 2)
    end = segs[j].end + pad_after
    if j + 1 < len(segs):
        end = min(end, (segs[j].end + segs[j + 1].start) / 2)
    return max(0.0, start), end


def choose_reference_window(segments: list[Segment], min_s: float = 15.0, max_s: float = 25.0,
                            max_gap: float = 0.8, pad_before: float = 0.10, pad_after: float = 0.25,
                            volume_std=None) -> Window | None:
    """Best window of consecutive segments lasting `min_s`..`max_s` and ending on a sentence end.

    Score: mean log-probability (clearer speech is higher), minus the worst no-speech probability,
    minus volume instability when `volume_std(start, end)` (dB) is given, plus a small bonus when the
    window also starts at the beginning of a sentence. Returns None when nothing qualifies.
    """
    segs = [s for s in segments if s.text.strip()]
    best: Window | None = None
    for i in range(len(segs)):
        for j in range(i, len(segs)):
            if j > i and segs[j].start - segs[j - 1].end > max_gap:
                break
            start, end = _padded(segs, i, j, pad_before, pad_after)
            if end - start > max_s:
                break
            if end - start < min_s or not segs[j].text.rstrip().endswith(SENTENCE_END):
                continue
            window = segs[i:j + 1]
            score = sum(s.avg_logprob for s in window) / len(window)
            score -= 0.5 * max(s.no_speech_prob for s in window)
            if volume_std is not None:
                score -= 0.02 * volume_std(start, end)
            if i == 0 or segs[i - 1].text.rstrip().endswith(SENTENCE_END):
                score += 0.05
            if best is None or score > best.score:
                best = Window(start, end, " ".join(s.text.strip() for s in window), score, window)
    return best
