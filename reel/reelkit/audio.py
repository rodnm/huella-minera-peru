"""Mixing licensed background music under the narration.

The music is scaled against the narration's speaking level: `under_db` (default 19 dB) under the voice
while it speaks, and it rises to `gap_db` under that level only in long silences (the intro and the
credits card). Short pauses between scenes keep the music down, so it never pumps between sentences.
Loudness normalization to -14 LUFS happens afterwards on the whole mix (see `render.encode`).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class MixResult:
    mix: np.ndarray     # voice + music, same length as the voice
    voice: np.ndarray   # the voice stem (unchanged)
    music: np.ndarray   # the music stem as mixed (looped, scaled, ducked, faded)
    under_db: float     # measured: voice RMS minus music RMS while the voice speaks


def _rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(x, dtype=np.float64)))) if x.size else 0.0


def _db(x: float) -> float:
    return 20 * np.log10(max(x, 1e-12))


def speech_mask(voice: np.ndarray, sr: int, window: float = 0.05, floor_db: float = 40.0) -> np.ndarray:
    """Per-sample boolean: True inside windows whose RMS is within `floor_db` of the loudest window."""
    hop = max(1, int(window * sr))
    n_win = int(np.ceil(len(voice) / hop))
    padded = np.zeros(n_win * hop, np.float32)
    padded[: len(voice)] = voice
    rms = np.sqrt(np.mean(np.square(padded.reshape(n_win, hop), dtype=np.float64), axis=1))
    peak = rms.max() if rms.size else 0.0
    active = (rms > 1e-5) & (rms > peak * 10 ** (-floor_db / 20))
    return np.repeat(active, hop)[: len(voice)]


def _fill_short_gaps(mask: np.ndarray, max_len: int) -> np.ndarray:
    """Mark inactive runs shorter than `max_len` samples (between two active parts) as active."""
    out = mask.copy()
    idx = np.flatnonzero(np.diff(mask.astype(np.int8)))
    edges = np.concatenate([[0], idx + 1, [len(mask)]])
    for a, b in zip(edges[:-1], edges[1:]):
        if not mask[a] and a > 0 and b < len(mask) and b - a < max_len:
            out[a:b] = True
    return out


def _dilate(mask: np.ndarray, n: int) -> np.ndarray:
    """Grow every active run by `n` samples on both sides (running sum, linear time)."""
    if n <= 0 or not mask.any():
        return mask
    cs = np.concatenate([[0], np.cumsum(mask, dtype=np.int64)])
    i = np.arange(len(mask))
    counts = cs[np.minimum(i + n + 1, len(mask))] - cs[np.maximum(i - n, 0)]
    return counts > 0


def _moving_average(x: np.ndarray, n: int) -> np.ndarray:
    if n <= 1:
        return x
    padded = np.pad(x, (n // 2, n - 1 - n // 2), mode="edge")
    return np.convolve(padded, np.ones(n) / n, mode="valid")


def loop_to_length(music: np.ndarray, n: int, sr: int, crossfade: float = 0.5) -> np.ndarray:
    """Repeat a short track until it covers `n` samples, crossfading each seam."""
    if len(music) >= n:
        return music[:n]
    xf = int(min(crossfade * sr, len(music) // 4))
    out = music.copy()
    ramp = np.linspace(0, 1, xf, dtype=np.float32)
    if music.ndim == 2:
        ramp = ramp[:, None]
    while len(out) < n:
        seam = out[-xf:] * (1 - ramp) + music[:xf] * ramp if xf else music[:0]
        out = np.concatenate([out[: len(out) - xf], seam, music[xf:]])
    return out[:n]


def mix_music(voice: np.ndarray, music: np.ndarray, sr: int, under_db: float = 19.0,
              gap_db: float = 8.0, min_gap: float = 1.0, hold: float = 0.35, ramp: float = 0.4,
              fade_in: float = 0.5, fade_out: float = 2.5) -> MixResult:
    """Mix `music` under a mono `voice`. Mono music gives a mono mix; stereo (n, 2) gives stereo."""
    voice = np.asarray(voice, np.float32)
    music = loop_to_length(np.asarray(music, np.float32), len(voice), sr)

    speaking = speech_mask(voice, sr)
    voice_level = _rms(voice[speaking]) if speaking.any() else _rms(voice)
    music_level = _rms(music)
    if music_level == 0 or voice_level == 0:
        silent = np.zeros_like(music)
        return MixResult(_add(voice, silent), voice, silent, float("inf"))

    ducked = _dilate(_fill_short_gaps(speaking, int(min_gap * sr)), int(hold * sr))
    gain_db = np.where(ducked, -under_db, -gap_db).astype(np.float64)
    # smooth on a coarse grid (cheap), then back to samples
    step = max(1, sr // 100)
    coarse = _moving_average(gain_db[::step], max(1, int(ramp * 100)))
    gain_db = np.interp(np.arange(len(voice)), np.arange(len(coarse)) * step, coarse)
    gain = (voice_level / music_level) * 10 ** (gain_db / 20)

    n = len(voice)
    envelope = np.ones(n)
    k_in, k_out = min(n, int(fade_in * sr)), min(n, int(fade_out * sr))
    envelope[:k_in] *= np.linspace(0, 1, k_in)
    envelope[n - k_out:] *= np.linspace(1, 0, k_out)
    gain = (gain * envelope).astype(np.float32)
    stem = music * (gain[:, None] if music.ndim == 2 else gain)

    measured = _db(voice_level) - _db(_rms(stem[speaking])) if speaking.any() else float("inf")
    return MixResult(_add(voice, stem), voice, stem, measured)


def _add(voice: np.ndarray, music: np.ndarray) -> np.ndarray:
    return (voice[:, None] + music) if music.ndim == 2 else voice + music
