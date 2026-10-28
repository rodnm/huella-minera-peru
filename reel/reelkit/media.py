"""ffmpeg helpers (the binary bundled with imageio-ffmpeg): decode, resample, loudness and probing.

imageio-ffmpeg ships `ffmpeg` but not `ffprobe`, so `probe` reads the stream header that `ffmpeg -i`
prints, and `loudness` runs the EBU R128 `loudnorm` filter in measurement mode.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import imageio_ffmpeg
import numpy as np
import soundfile as sf

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


def decode_audio(source: Path | str, sr: int, channels: int = 1) -> np.ndarray:
    """Any audio file (wav, m4a, mp3, ogg) to float32 at `sr`: shape (n,) for mono, (n, channels) otherwise."""
    raw = subprocess.run([FFMPEG, "-v", "error", "-i", str(source), "-ac", str(channels), "-ar", str(sr),
                          "-f", "f32le", "-"], capture_output=True, check=True).stdout
    audio = np.frombuffer(raw, np.float32).copy()
    return audio if channels == 1 else audio.reshape(-1, channels)


def resample(audio: np.ndarray, sr_in: int, sr_out: int) -> np.ndarray:
    """Mono float32 resampling through ffmpeg's resampler."""
    if sr_in == sr_out:
        return np.asarray(audio, np.float32)
    raw = subprocess.run([FFMPEG, "-v", "error", "-f", "f32le", "-ar", str(sr_in), "-ac", "1", "-i", "-",
                          "-ar", str(sr_out), "-f", "f32le", "-"],
                         input=np.asarray(audio, np.float32).tobytes(), capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).copy()


def write_wav(path: Path, audio: np.ndarray, sr: int) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(path, np.asarray(audio, np.float32), sr, subtype="FLOAT")
    return path


def loudness(path: Path) -> dict:
    """Integrated loudness (LUFS), true peak (dBTP) and loudness range (LU) of a file's audio."""
    result = subprocess.run([FFMPEG, "-hide_banner", "-nostats", "-i", str(path), "-vn",
                             "-af", "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"],
                            capture_output=True, text=True, encoding="utf-8", errors="replace", check=True)
    block = result.stderr[result.stderr.rindex("{"): result.stderr.rindex("}") + 1]
    data = json.loads(block)
    return {"lufs": float(data["input_i"]), "true_peak": float(data["input_tp"]), "lra": float(data["input_lra"])}


def probe(path: Path) -> dict:
    """Resolution, frame rate, duration and audio format, read from `ffmpeg -i`."""
    err = subprocess.run([FFMPEG, "-hide_banner", "-i", str(path)], capture_output=True, text=True,
                         encoding="utf-8", errors="replace").stderr
    info: dict = {}
    if m := re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", err):
        h, mnt, s = m.groups()
        info["duration"] = int(h) * 3600 + int(mnt) * 60 + float(s)
    if m := re.search(r"Video: (\w+).*?, (\d{2,5})x(\d{2,5})[, ].*?(\d+(?:\.\d+)?) fps", err):
        info.update(video_codec=m.group(1), width=int(m.group(2)), height=int(m.group(3)), fps=float(m.group(4)))
    if m := re.search(r"Audio: (\w+).*?, (\d+) Hz, (\w+)", err):
        info.update(audio_codec=m.group(1), sample_rate=int(m.group(2)), channels=m.group(3))
    return info


def trim_silence(audio: np.ndarray, sr: int, threshold_db: float = -45.0, keep: float = 0.05) -> np.ndarray:
    """Drop leading and trailing silence (below `threshold_db` relative to the peak), keeping `keep` s."""
    audio = np.asarray(audio, np.float32)
    if not audio.size:
        return audio
    level = np.abs(audio)
    loud = np.flatnonzero(level > level.max() * 10 ** (threshold_db / 20))
    if not loud.size:
        return audio
    pad = int(keep * sr)
    return audio[max(0, loud[0] - pad): min(len(audio), loud[-1] + pad + 1)]
