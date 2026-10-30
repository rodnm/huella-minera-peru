"""Loading and checking a reel script (`guion.json`).

Schema (session 15 fields plus `visual`):

    {
      "titulo": "La huella de la minería en el Perú",
      "fuente": "Fuente: NASA Black Marble, MINEM, INEI",
      "creditos": ["Datos: ...", "Música: ...", "Voz generada con IA a partir de la voz del autor"],
      "escenas": [
        {"frase": "texto hablado, con los números escritos en palabras",
         "cifra": "+38 %",                      # short on-screen figure, digits ("" for none)
         "etiqueta": "de tres a ocho palabras",
         "visual": "escenas/01_peru/",           # PNG/JPG or a folder of numbered PNG frames
         "encaje": "contener",                   # optional: "contener" (default) or "cubrir"
         "zoom": 0.04}                           # optional: slow zoom on still images, 0 to turn off
      ]
    }
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .config import REEL_DIR
from .visuals import VisualSource, resolve_visual

FIT_MODES = {"contener": "contain", "cubrir": "cover"}


@dataclass(frozen=True)
class Scene:
    frase: str
    cifra: str
    etiqueta: str
    visual: str
    source: VisualSource
    fit: str = "contain"
    zoom: float = 0.04

    def as_dict(self) -> dict:
        return {"frase": self.frase, "cifra": self.cifra, "etiqueta": self.etiqueta}


@dataclass(frozen=True)
class Script:
    titulo: str
    fuente: str
    creditos: list[str]
    escenas: list[Scene]
    path: Path
    warnings: list[str]


def _text(value) -> str:
    return value.strip() if isinstance(value, str) else ""


def load_script(path: Path, base: Path = REEL_DIR) -> Script:
    """Read and validate a script; raise ValueError listing every problem found."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"No se pudo leer el guion {path}: {exc}") from exc
    problems, warnings, scenes = [], [], []
    titulo, fuente = _text(data.get("titulo")), _text(data.get("fuente"))
    if not titulo:
        problems.append("falta 'titulo'")
    if not fuente:
        problems.append("falta 'fuente' (la fuente principal de los datos)")
    creditos = data.get("creditos")
    if not isinstance(creditos, list) or not all(_text(c) for c in creditos) or not creditos:
        problems.append("'creditos' debe ser una lista de textos (fuentes, música, aviso de voz con IA)")
        creditos = []
    elif not any("IA" in c for c in creditos):
        warnings.append("ningún crédito menciona la voz generada con IA")
    escenas = data.get("escenas")
    if not isinstance(escenas, list) or not escenas:
        problems.append("'escenas' debe ser una lista con al menos una escena")
        escenas = []
    for k, raw in enumerate(escenas, 1):
        if not isinstance(raw, dict):
            problems.append(f"escena {k}: no es un objeto")
            continue
        frase, etiqueta = _text(raw.get("frase")), _text(raw.get("etiqueta"))
        cifra = raw.get("cifra") or ""
        if not frase:
            problems.append(f"escena {k}: falta 'frase'")
        elif re.search(r"\d", frase):
            warnings.append(f"escena {k}: 'frase' tiene dígitos; escríbanlos en palabras para la voz")
        if not etiqueta:
            problems.append(f"escena {k}: falta 'etiqueta'")
        if not isinstance(cifra, str):
            problems.append(f"escena {k}: 'cifra' debe ser texto")
            cifra = ""
        visual = _text(raw.get("visual"))
        fit = raw.get("encaje", "contener")
        zoom = raw.get("zoom", 0.04)
        if fit not in FIT_MODES:
            problems.append(f"escena {k}: 'encaje' debe ser 'contener' o 'cubrir'")
        if not isinstance(zoom, (int, float)) or not 0 <= zoom <= 0.3:
            problems.append(f"escena {k}: 'zoom' debe ser un número entre 0 y 0.3")
            zoom = 0.0
        if not visual:
            problems.append(f"escena {k}: falta 'visual' (imagen o carpeta de cuadros)")
            continue
        try:
            source = resolve_visual(base, visual)
        except ValueError as exc:
            problems.append(f"escena {k}: {exc}")
            continue
        scenes.append(Scene(frase, cifra.strip(), etiqueta, visual, source, FIT_MODES.get(fit, "contain"), float(zoom)))
    if problems:
        raise ValueError(f"El guion {path} tiene problemas:\n  - " + "\n  - ".join(problems))
    return Script(titulo, fuente, [c.strip() for c in creditos], scenes, Path(path), warnings)
