"""Words with timestamps: karaoke blocks, SRT output and text normalization for WER.

Adapted from the course pipeline (d2cml-ai/Data-Science-Python, sessions/15-texto-a-reel/reel.py):
`_bloques`, `a_srt` and `_normalizar`, with millisecond rounding, silence-aware grouping and
decimal handling added here.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from num2words import num2words

SENTENCE_PUNCTUATION = ".,;:?!…"


@dataclass(frozen=True)
class Word:
    """One spoken word and its time span in seconds."""

    start: float
    end: float
    text: str


# --- SRT ----------------------------------------------------------------------

def srt_timestamp(t: float) -> str:
    """Seconds to `HH:MM:SS,mmm`, rounded to the nearest millisecond."""
    ms = max(0, round(t * 1000))
    hours, ms = divmod(ms, 3_600_000)
    minutes, ms = divmod(ms, 60_000)
    seconds, ms = divmod(ms, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{ms:03}"


def to_srt(blocks: list[list[Word]]) -> str:
    """Numbered SRT cues, one per block. A cue ends where the next one starts if they overlap."""
    lines: list[str] = []
    for i, block in enumerate(blocks):
        start, end = block[0].start, block[-1].end
        if i + 1 < len(blocks):
            end = min(end, blocks[i + 1][0].start)
        lines += [str(i + 1), f"{srt_timestamp(start)} --> {srt_timestamp(end)}",
                  " ".join(w.text for w in block), ""]
    return "\n".join(lines) + ("\n" if lines else "")


# --- karaoke blocks -----------------------------------------------------------

def group_words(words: list[Word], max_words: int = 4, max_chars: int = 26,
                max_gap: float = 0.6) -> list[list[Word]]:
    """Short blocks for reading on a phone: at most `max_words`, closed at punctuation or a pause."""
    blocks: list[list[Word]] = []
    current: list[Word] = []
    for word in words:
        if current and word.start - current[-1].end > max_gap:
            blocks.append(current)
            current = []
        current.append(word)
        length = sum(len(w.text) + 1 for w in current)
        if len(current) >= max_words or length >= max_chars or word.text[-1] in SENTENCE_PUNCTUATION:
            blocks.append(current)
            current = []
    if current:
        blocks.append(current)
    return blocks


def merge_fragments(words: list[Word]) -> list[Word]:
    """Whisper sometimes splits "8.7" into "8" + ".7" or "126%" into "126" + "%": glue them back."""
    merged: list[Word] = []
    for word in words:
        text = word.text.strip()
        if not text:
            continue
        if merged and re.match(r"^[.,%]", text):
            prev = merged.pop()
            merged.append(Word(prev.start, word.end, prev.text + text))
        else:
            merged.append(Word(word.start, word.end, text))
    return merged


# --- normalization for WER ----------------------------------------------------

def _number_to_words(match: re.Match) -> str:
    whole, decimals = match.group("whole"), match.group("dec")
    spoken = num2words(int(whole), lang="es")
    if decimals:
        if decimals.startswith("0"):  # "3.05" is read digit by digit: "tres punto cero cinco"
            tail = " ".join(num2words(int(d), lang="es") for d in decimals)
        else:
            tail = num2words(int(decimals), lang="es")
        spoken += " punto " + tail
    return f" {spoken} "


def normalize_for_wer(text: str) -> str:
    """Make a script line and a Whisper transcript comparable.

    Numbers become Spanish words ("126%" -> "ciento veintiseis por ciento"), a separator followed by
    exactly three digits is a thousands separator ("12,984" and "12.984" -> 12984), any other separator
    is a decimal read as "punto", and accents, case and punctuation are dropped.
    """
    s = text.lower().replace("%", " por ciento ")
    s = re.sub(r"(?<=\d)[,.](?=\d{3}(?!\d))", "", s)
    s = re.sub(r"(?P<whole>\d+)(?:[.,](?P<dec>\d+))?", _number_to_words, s)
    s = unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode()
    return " ".join(re.sub(r"[^\w\s]", " ", s).split())


# --- placeholder timing -------------------------------------------------------

def placeholder_words(sentence: str, start: float, end: float) -> list[Word]:
    """Evenly spaced words for layout checks when there is no narration yet."""
    tokens = sentence.split()
    if not tokens:
        return []
    step = (end - start) / len(tokens)
    return [Word(start + i * step, start + (i + 1) * step, tok) for i, tok in enumerate(tokens)]
