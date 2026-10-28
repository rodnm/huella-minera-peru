"""Paths, design tokens and CPU settings shared by the reel pipeline.

CPU rules for this machine (Ryzen 5 5600G, 6 cores / 12 threads, AVX2, 31 GB RAM, no CUDA), taken from
the author's earlier `texto-a-voz-reel-1/reel/recursos.py`: models use one thread per physical core,
only one model is loaded at a time, Qwen3-TTS runs in float32 and Whisper in int8.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

REEL_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = REEL_DIR.parent
TOKENS_FILE = REPO_DIR / "design" / "tokens.json"
FONTS_DIR = REEL_DIR / "recursos" / "fuentes"
VOICE_DIR = REEL_DIR / "voz"
OUTPUT_DIR = REEL_DIR / "salidas"

TTS_MODEL = "Qwen/Qwen3-TTS-12Hz-0.6B-Base"
ASR_MODEL = "large-v3-turbo"
LANGUAGE = "Spanish"

USER_AGENT = ("paradoja-del-brillo-reel/0.1 (course project, Python Intermedio; "
              "downloads OFL fonts from google/fonts; python-urllib)")

PHYSICAL_CORES = max(1, (os.cpu_count() or 2) // 2)
# ctranslate2 and torch read these when they load, so set them before importing either
os.environ.setdefault("OMP_NUM_THREADS", str(PHYSICAL_CORES))
os.environ.setdefault("MKL_NUM_THREADS", str(PHYSICAL_CORES))
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")


def load_colors(path: Path = TOKENS_FILE) -> dict:
    """Reel colours from design/tokens.json (the same file feeds the web and the charts)."""
    tokens = json.loads(path.read_text(encoding="utf-8"))
    surface, series, ramps = tokens["surface"], tokens["series"], tokens["ramps"]
    return {
        "background": surface["background"],
        "panel": surface["panel"],
        "grid": surface["grid"],
        "text": surface["text"],
        "text_muted": surface["text_muted"],
        "accent": series["mining"],
        "paradox": series["paradox"],
        "highlight": ramps["radiance"][-1],
        "radiance": ramps["radiance"],
        "poverty_gap": ramps["poverty_gap"],
    }
