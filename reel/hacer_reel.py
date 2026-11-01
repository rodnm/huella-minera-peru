"""guion.json -> narration in the author's cloned voice -> 1080x1920 reel with subtitles and music.

    uv run python hacer_reel.py --guion guion.json --musica recursos/musica/pista.mp3 --autor "Nombre"
    uv run python hacer_reel.py --guion guion.json --solo-visual --autor "Nombre"   # layout check, no TTS

Outputs in salidas/: reel.mp4, subtitulos.srt, portada.png and informe.json (WER per scene, timings,
loudness). With --solo-visual: reel_visual.mp4 and portada_visual.png, silent, with placeholder timing.

Built on the course pipeline: d2cml-ai/Data-Science-Python, sessions/15-texto-a-reel (reel.py,
hacer_reel.py), by the course "Python Intermedio". Voice reference: run preparar_voz.py first.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from reelkit import config  # noqa: F401  (sets CPU thread variables before any model library loads)
from reelkit.config import OUTPUT_DIR, REEL_DIR, TTS_MODEL, VOICE_DIR, load_colors
from reelkit.text import Word, group_words, placeholder_words, to_srt
from reelkit.timeline import build_timeline

WORDS_PER_SECOND = 2.6   # placeholder pace for --solo-visual (the course measured 2.5 to 3.0)
COVER_AT = 0.6           # the cover is scene 1 at 60 % of its time on screen


def _clock(t0: float, msg: str) -> None:
    print(f"[{time.time() - t0:6.1f} s] {msg}", flush=True)


def _summary(path: Path, t0: float) -> dict:
    from reelkit.media import probe

    info = probe(path)
    _clock(t0, f"{path.name}: {info.get('width')}x{info.get('height')}, {info.get('fps')} fps, "
               f"{info.get('duration', 0):.2f} s" + (f", audio {info['audio_codec']} {info['sample_rate']} Hz "
                                                     f"{info['channels']}" if "audio_codec" in info else ", sin audio"))
    return info


def _s5_checks(duration: float, scenes: int) -> list[str]:
    notes = []
    if not 45 <= duration <= 75:
        notes.append(f"duración {duration:.1f} s fuera de 45-75 s (S5)")
    if not 5 <= scenes <= 7:
        notes.append(f"{scenes} escenas; el reel final pide entre 5 y 7 (S5)")
    return notes


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):  # accents survive Git Bash and redirected output
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--guion", type=Path, required=True, help="guion JSON (rutas de visuales relativas a reel/)")
    ap.add_argument("--autor", required=True, help="nombre que aparece en el pie y en los créditos")
    ap.add_argument("--musica", type=Path, help="pista de música con licencia (mp3, wav, m4a, ogg)")
    ap.add_argument("--solo-visual", action="store_true", help="sin voz: tiempos estimados, para revisar el diseño")
    ap.add_argument("--voz", type=Path, default=VOICE_DIR / "referencia.wav",
                    help="referencia de 15 a 25 s (la escribe preparar_voz.py)")
    ap.add_argument("--salidas", type=Path, default=OUTPUT_DIR)
    ap.add_argument("--max-wer", type=float, default=0.25)
    ap.add_argument("--musica-db", type=float, default=19.0, help="dB de la música bajo la voz (18 a 20)")
    ap.add_argument("--tts", default=TTS_MODEL)
    args = ap.parse_args()

    from reelkit.script import load_script

    t0 = time.time()
    guion = args.guion if args.guion.is_absolute() else (Path.cwd() / args.guion)
    try:
        script = load_script(guion, base=REEL_DIR)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2
    for w in script.warnings:
        print(f"  aviso: {w}")
    out = args.salidas
    out.mkdir(parents=True, exist_ok=True)
    colors = load_colors()

    from reelkit import fonts
    from reelkit.render import Renderer, encode

    fonts.ensure_fonts(quiet=True)
    frases = [s.frase for s in script.escenas]
    report: dict = {"guion": str(guion), "escenas": [], "modo": "solo-visual" if args.solo_visual else "completo"}

    if args.solo_visual:
        durations = [max(2.5, len(f.split()) / WORDS_PER_SECOND) for f in frases]
        timeline = build_timeline(durations)
        words = [w for i, f in enumerate(frases) for w in placeholder_words(f, *timeline.scenes[i])]
        renderer = Renderer(script, timeline, words, args.autor, colors, fonts.font)
        _clock(t0, f"{len(frases)} escenas, {timeline.duration:.1f} s con tiempos estimados")
        cover = out / "portada_visual.png"
        a, b = renderer.shows[0], renderer.shows[1]
        renderer.frame(a + COVER_AT * (b - a), subtitles=False).save(cover)
        seconds = encode(renderer, out / "reel_visual.mp4", log=lambda m: _clock(t0, m))
        _clock(t0, f"cuadros dibujados y codificados en {seconds:.0f} s")
        _summary(out / "reel_visual.mp4", t0)
        for note in _s5_checks(timeline.duration, len(frases)):
            print(f"  aviso: {note}")
        return 0

    ref_text_file = args.voz.with_suffix(".txt")
    if not args.voz.exists() or not ref_text_file.exists():
        print(f"Falta la referencia de voz ({args.voz} y {ref_text_file.name}). "
              "Primero: uv run python preparar_voz.py --voz <su grabación>", file=sys.stderr)
        return 2
    if args.musica is not None and not args.musica.exists():
        print(f"No existe la música {args.musica}", file=sys.stderr)
        return 2

    import numpy as np

    from reelkit.audio import mix_music
    from reelkit.media import decode_audio, loudness, resample, write_wav
    from reelkit.narration import narrate
    from reelkit.timeline import assemble_narration

    # 1. voice, per scene (cached), with the WER check
    _clock(t0, "narración con la voz clonada")
    scenes = narrate(frases, args.voz, ref_text_file.read_text(encoding="utf-8").strip(), out / "cache" / "tts",
                     model=args.tts, max_wer=args.max_wer, log=lambda m: _clock(t0, m))
    for i, s in enumerate(scenes, 1):
        flag = "ok" if s.wer <= args.max_wer else "REVISAR"
        print(f"  escena {i}: {s.duration:5.1f} s  WER {s.wer:.2f} {flag}  intentos {s.attempts}"
              f"{'  (caché)' if s.cached else ''}")
        if s.wer > 0:
            print(f"      Whisper oyó: {s.heard}")

    # 2. one timeline for audio, frames and subtitles
    timeline = build_timeline([s.duration for s in scenes])
    words = []
    for i, s in enumerate(scenes):
        clamped = [Word(max(0.0, w.start), min(s.duration, w.end), w.text) for w in s.words]
        words += timeline.shift_words(i, clamped)
    (out / "subtitulos.srt").write_text(to_srt(group_words(words)), encoding="utf-8")
    _clock(t0, f"subtítulos: {len(words)} palabras en {out / 'subtitulos.srt'}")

    # 3. audio: narration (+ music), measured for -14 LUFS
    sr = 48_000
    narration = assemble_narration([resample(s.audio, s.sr, sr) for s in scenes], sr, timeline)
    voice = np.stack([narration, narration], axis=1)
    music_report = None
    if args.musica is not None:
        music = decode_audio(args.musica, sr, channels=2)
        mixed = mix_music(narration, music, sr, under_db=args.musica_db)
        audio = mixed.mix
        music_report = {"archivo": args.musica.name, "db_bajo_la_voz": round(mixed.under_db, 1)}
        _clock(t0, f"música mezclada: {mixed.under_db:.1f} dB bajo la voz mientras habla")
        if not any(c.lower().startswith("música") for c in script.creditos):
            print("  aviso: hay música pero ningún crédito empieza con 'Música:'; añadan su crédito y licencia")
    else:
        audio = voice
        print("  aviso: sin --musica. El reel final necesita una pista con licencia bajo la voz (S5).")
    mix_file = write_wav(out / "cache" / "mezcla.wav", audio, sr)
    before = loudness(mix_file)
    gain = -14.0 - before["lufs"]

    # 4. frames + encode
    renderer = Renderer(script, timeline, words, args.autor, colors, fonts.font)
    a, b = renderer.shows[0], renderer.shows[1]
    renderer.frame(a + COVER_AT * (b - a), subtitles=False).save(out / "portada.png")
    seconds = encode(renderer, out / "reel.mp4", audio=mix_file, gain_db=gain, log=lambda m: _clock(t0, m))
    _clock(t0, f"cuadros dibujados y codificados en {seconds:.0f} s")
    info = _summary(out / "reel.mp4", t0)
    final = loudness(out / "reel.mp4")
    _clock(t0, f"sonoridad final {final['lufs']:.1f} LUFS, pico {final['true_peak']:.1f} dBTP")
    notes = _s5_checks(timeline.duration, len(frases))
    for note in notes:
        print(f"  aviso: {note}")

    report.update({
        "duracion_s": round(timeline.duration, 2), "video": info, "sonoridad": final, "musica": music_report,
        "escenas": [{"frase": s.frase, "duracion_s": round(s.duration, 2), "wer": round(s.wer, 3),
                     "whisper_oyo": s.heard, "intentos": s.attempts, "tts_s": round(s.tts_seconds, 1),
                     "inicio_s": round(timeline.scenes[i][0], 3)} for i, s in enumerate(scenes)],
        "avisos_s5": notes, "tiempo_total_s": round(time.time() - t0, 1),
    })
    (out / "informe.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
