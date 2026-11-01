"""Cut the voice reference: 15 to 25 s of the author's own recording, ending on a full sentence.

    uv run python preparar_voz.py --voz "C:/ruta/a/mi_voz.m4a"
    uv run python preparar_voz.py --voz "C:/ruta/a/mi_voz.m4a" --inicio 42.5 --fin 61.0   # by hand

Writes voz/referencia.wav (24 kHz mono, what Qwen3-TTS uses) and voz/referencia.txt (what that cut
says, transcribed again by Whisper; the TTS needs it as `ref_text`). The recording is biometric data:
it is only read from where it is; voz/ is git-ignored and nothing is uploaded or printed.

Based on the author's earlier texto-a-voz-reel-1/preparar_voz.py, adapted to the course's 15-25 s rule.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np

from reelkit import config  # noqa: F401  (CPU thread variables before ctranslate2 loads)
from reelkit.config import VOICE_DIR
from reelkit.media import decode_audio, write_wav
from reelkit.voice import choose_reference_window

SR_ASR, SR_TTS = 16_000, 24_000


def volume_std(audio: np.ndarray, sr: int):
    """dB spread of one-second RMS values inside [start, end]: lower is steadier."""
    def measure(start: float, end: float) -> float:
        part = audio[int(start * sr):int(end * sr)]
        rms = [np.sqrt(np.mean(part[i:i + sr] ** 2) + 1e-12) for i in range(0, len(part) - sr + 1, sr)]
        return float(np.std(20 * np.log10(rms))) if len(rms) > 1 else 0.0
    return measure


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):  # accents survive Git Bash and redirected output
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--voz", type=Path, required=True, help="grabación completa de su voz (.m4a, .ogg, .wav)")
    ap.add_argument("--salida", type=Path, default=VOICE_DIR)
    ap.add_argument("--inicio", type=float, help="segundo inicial del tramo (elección manual)")
    ap.add_argument("--fin", type=float, help="segundo final del tramo")
    args = ap.parse_args()
    if (args.inicio is None) != (args.fin is None):
        ap.error("--inicio y --fin van juntos")
    if not args.voz.exists():
        ap.error(f"no existe {args.voz}")

    from reelkit.asr import Transcriber

    t0 = time.time()
    audio16 = decode_audio(args.voz, SR_ASR)
    print(f"Grabación: {len(audio16) / SR_ASR:.1f} s")
    asr = Transcriber()
    if args.inicio is not None:
        start, end = args.inicio, args.fin
        if not 15 <= end - start <= 25:
            print(f"  aviso: el tramo dura {end - start:.1f} s; conviene que dure entre 15 y 25 s")
    else:
        segments = asr.segments(audio16, vad_filter=True, beam_size=5, condition_on_previous_text=False)
        window = choose_reference_window(segments, volume_std=volume_std(audio16, SR_ASR))
        if window is None:
            print("Ningún tramo de 15 a 25 s termina en frase completa sin pausas largas. "
                  "Elijan uno con --inicio y --fin, o graben de nuevo.", file=sys.stderr)
            return 1
        start, end = window.start, window.end
        print(f"{len(segments)} segmentos; elegido {start:.2f}-{end:.2f} s "
              f"({len(window.segments)} segmentos, puntaje {window.score:.3f})")

    full = decode_audio(args.voz, SR_TTS)
    cut = full[int(start * SR_TTS):int(end * SR_TTS)]
    peak = float(np.abs(cut).max()) if cut.size else 0.0
    if peak > 0.95:  # decoded m4a can overshoot 1.0; Qwen3-TTS warns and clips above it
        cut = cut * (0.95 / peak)
    ref = write_wav(args.salida / "referencia.wav", cut, SR_TTS)
    # transcribe the cut itself: the text must say exactly what sounds in it
    text = asr.text(audio16[int(start * SR_ASR):int(end * SR_ASR)])
    (args.salida / "referencia.txt").write_text(text + "\n", encoding="utf-8")
    asr.close()
    print(f"Referencia: {ref} ({len(cut) / SR_TTS:.1f} s, {len(text.split())} palabras transcritas) "
          f"en {time.time() - t0:.0f} s")
    print("Escúchenla antes de usarla; si no les convence, repitan con --inicio y --fin.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
