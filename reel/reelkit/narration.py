"""Narration in the author's cloned voice: Qwen3-TTS per scene, cached, with a WER check.

Each scene is synthesized once and cached under a key made of the model, the reference recording, its
transcript and the sentence, so editing one sentence only re-synthesizes that scene. Whisper then
transcribes each new scene without the script as a prompt (an honest intelligibility check); a scene
whose WER is above `max_wer` is generated again once and the better take is kept. The TTS model and
Whisper are never in memory at the same time.

Adapted from the course pipeline (d2cml-ai/Data-Science-Python, sessions/15-texto-a-reel/reel.py:
`Voz`, `narrar`, `_wer`), with the cache, the per-scene retry and the model swapping added here.
"""
from __future__ import annotations

import gc
import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import soundfile as sf

from .asr import SR as ASR_SR
from .asr import Transcriber, wer
from .config import LANGUAGE, PHYSICAL_CORES, TTS_MODEL
from .media import resample, trim_silence, write_wav
from .text import Word

CACHE_VERSION = 1


class Narrator:
    """Qwen3-TTS Base clones the voice from the reference audio and its transcript (ICL mode)."""

    def __init__(self, ref_wav: Path, ref_text: str, model: str = TTS_MODEL):
        import torch
        from qwen_tts import Qwen3TTSModel

        torch.set_num_threads(PHYSICAL_CORES)
        self.torch = torch
        self.model = Qwen3TTSModel.from_pretrained(model, device_map="cpu", dtype=torch.float32)
        audio, sr = sf.read(str(ref_wav), dtype="float32", always_2d=False)
        if audio.ndim == 2:
            audio = audio.mean(axis=1)
        self.prompt = self.model.create_voice_clone_prompt(ref_audio=(audio, sr), ref_text=ref_text)

    def say(self, text: str, seed: int) -> tuple[np.ndarray, int]:
        self.torch.manual_seed(seed)
        wavs, sr = self.model.generate_voice_clone(text=[text], language=[LANGUAGE],
                                                   voice_clone_prompt=self.prompt)
        return np.asarray(wavs[0], np.float32), sr

    def close(self) -> None:
        del self.model, self.prompt
        gc.collect()


@dataclass
class SceneAudio:
    frase: str
    audio: np.ndarray
    sr: int
    wer: float | None = None
    heard: str = ""
    words: list[Word] = field(default_factory=list)  # relative to the start of this scene's audio
    attempts: int = 1
    tts_seconds: float = 0.0
    cached: bool = False

    @property
    def duration(self) -> float:
        return len(self.audio) / self.sr


def scene_key(frase: str, ref_wav: Path, ref_text: str, model: str) -> str:
    ref_hash = hashlib.sha256(Path(ref_wav).read_bytes()).hexdigest()
    blob = json.dumps({"v": CACHE_VERSION, "model": model, "ref": ref_hash, "ref_text": ref_text,
                       "frase": frase, "language": LANGUAGE}, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:20]


def _save(cache: Path, key: str, item: SceneAudio) -> None:
    write_wav(cache / f"{key}.wav", item.audio, item.sr)
    meta = {"frase": item.frase, "wer": item.wer, "heard": item.heard, "attempts": item.attempts,
            "tts_seconds": round(item.tts_seconds, 2), "audio_seconds": round(item.duration, 3),
            "words": [[round(w.start, 3), round(w.end, 3), w.text] for w in item.words]}
    (cache / f"{key}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")


def _load(cache: Path, key: str) -> SceneAudio | None:
    wav, meta_file = cache / f"{key}.wav", cache / f"{key}.json"
    if not (wav.exists() and meta_file.exists()):
        return None
    meta = json.loads(meta_file.read_text(encoding="utf-8"))
    audio, sr = sf.read(str(wav), dtype="float32")
    return SceneAudio(meta["frase"], audio, sr, meta["wer"], meta.get("heard", ""),
                      [Word(*w) for w in meta.get("words", [])], meta.get("attempts", 1),
                      meta.get("tts_seconds", 0.0), cached=True)


def _synthesize(items: dict[int, SceneAudio | None], frases: list[str], ref_wav: Path, ref_text: str,
                model: str, attempt: int, log, persist=None) -> dict[int, SceneAudio]:
    """Synthesize each scene; ``persist`` saves it right away so a later failure does not lose the CPU work."""
    t0 = time.time()
    narrator = Narrator(ref_wav, ref_text, model)
    log(f"  Qwen3-TTS cargado en {time.time() - t0:.0f} s")
    out = {}
    for i in items:
        t = time.time()
        audio, sr = narrator.say(frases[i], seed=1234 + 101 * attempt + i)
        audio = trim_silence(audio, sr)
        out[i] = SceneAudio(frases[i], audio, sr, attempts=attempt, tts_seconds=time.time() - t)
        if persist is not None:
            persist(i, out[i])
        log(f"  escena {i + 1}: {len(audio) / sr:.1f} s de voz en {out[i].tts_seconds:.0f} s (intento {attempt})")
    narrator.close()
    return out


def _check(items: dict[int, SceneAudio], asr: Transcriber) -> None:
    for item in items.values():
        audio16k = resample(item.audio, item.sr, ASR_SR)
        item.heard = asr.text(audio16k)
        item.wer = wer(item.frase, item.heard)
        item.words = asr.words(audio16k, prompt=item.frase)


def narrate(frases: list[str], ref_wav: Path, ref_text: str, cache: Path, model: str = TTS_MODEL,
            max_wer: float = 0.25, retries: int = 1, log=print) -> list[SceneAudio]:
    """One SceneAudio per sentence, reusing cached scenes; regenerates a scene once if WER > max_wer."""
    cache.mkdir(parents=True, exist_ok=True)
    keys = [scene_key(f, ref_wav, ref_text, model) for f in frases]
    scenes: list[SceneAudio | None] = [_load(cache, k) for k in keys]
    missing = {i: None for i, s in enumerate(scenes) if s is None}
    # synthesized in an earlier run that failed before Whisper could check them
    unchecked = {i: s for i, s in enumerate(scenes) if s is not None and s.wer is None}
    log(f"  escenas en caché: {len(frases) - len(missing)} de {len(frases)}")

    if missing or unchecked:
        fresh = dict(unchecked)
        if missing:
            fresh.update(_synthesize(missing, frases, ref_wav, ref_text, model, attempt=1, log=log,
                                     persist=lambda i, item: _save(cache, keys[i], item)))
        t = time.time()
        asr = Transcriber()
        _check(fresh, asr)
        for i, item in fresh.items():
            scenes[i] = item
            _save(cache, keys[i], item)
        log(f"  WER medido con Whisper en {time.time() - t:.0f} s")

        bad = {i: None for i, s in fresh.items() if s.wer > max_wer and s.attempts <= retries}
        if bad:
            asr.close()
            log(f"  WER > {max_wer} en escenas {[i + 1 for i in bad]}: se generan otra vez")
            retry = _synthesize(bad, frases, ref_wav, ref_text, model, attempt=2, log=log)
            asr = Transcriber()
            _check(retry, asr)
            for i, item in retry.items():
                old = scenes[i]
                best = item if item.wer < old.wer else old
                best.attempts = 2
                scenes[i] = best
                _save(cache, keys[i], best)
        asr.close()
    return scenes
