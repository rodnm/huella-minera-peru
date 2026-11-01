"""faster-whisper `large-v3-turbo` in int8 on the CPU: transcripts, word timestamps and WER.

Audio is passed already decoded (16 kHz mono float32), so faster-whisper never needs PyAV to open
files (a problem the course pipeline hit).
"""
from __future__ import annotations

import gc

import jiwer
import numpy as np

from .config import ASR_MODEL, PHYSICAL_CORES
from .text import Word, merge_fragments, normalize_for_wer
from .voice import Segment

SR = 16_000


def wer(reference: str, heard: str) -> float:
    """Word error rate after normalizing numbers, accents and punctuation on both sides."""
    ref, hyp = normalize_for_wer(reference), normalize_for_wer(heard)
    if not ref:
        return 0.0 if not hyp else 1.0
    return float(jiwer.wer(ref, hyp)) if hyp else 1.0


class Transcriber:
    """Loads Whisper once; call `close()` before loading the TTS model (one model in RAM at a time)."""

    def __init__(self, model: str = ASR_MODEL):
        from faster_whisper import WhisperModel

        self.model = WhisperModel(model, device="cpu", compute_type="int8",
                                  cpu_threads=PHYSICAL_CORES, num_workers=1)

    def segments(self, audio16k: np.ndarray, **options) -> list[Segment]:
        segs, _ = self.model.transcribe(np.asarray(audio16k, np.float32), language="es", **options)
        return [Segment(s.start, s.end, s.text.strip(), s.avg_logprob, s.no_speech_prob)
                for s in segs if s.text.strip()]

    def text(self, audio16k: np.ndarray) -> str:
        """Plain transcript, with no script prompt: an honest intelligibility check."""
        return " ".join(s.text for s in self.segments(audio16k, beam_size=5, condition_on_previous_text=False))

    def words(self, audio16k: np.ndarray, prompt: str | None = None) -> list[Word]:
        """Word timestamps; the script goes in as context so names and figures are spelled right."""
        segs, _ = self.model.transcribe(np.asarray(audio16k, np.float32), language="es", beam_size=5,
                                        word_timestamps=True, initial_prompt=prompt)
        raw = [Word(w.start, w.end, w.word.strip()) for s in segs for w in (s.words or []) if w.word.strip()]
        return merge_fragments(raw)

    def close(self) -> None:
        del self.model
        gc.collect()
