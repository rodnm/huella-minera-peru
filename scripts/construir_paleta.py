"""Build design/tokens.json, the single source of colors for the dashboard, the charts and the reel.

Run from the repository root: uv run python -m scripts.construir_paleta

Every ramp records the LearnUI data color picker inputs (mode, ends, sliders, stops) that produce it, so anyone can
re-create it on https://www.learnui.design/tools/data-color-picker.html or with brillo.paleta.

Validation (dataviz skill validator, OKLab ΔE×100, Machado 2009 CVD simulation) on 2026-10-28:
- radiance, ordinal on #0b1020: monotone lightness, adjacent ΔL >= 0.06, light end >= 2:1, one hue.
- categorical, all pairs on #121a2e: lightness band, chroma floor, CVD ΔE 13.4, normal-vision ΔE 21.6, contrast >= 3:1.
"""
import json
from pathlib import Path

from brillo.paleta import divergent_scale, palette_scale, single_scale

TOKENS = Path(__file__).resolve().parent.parent / "design" / "tokens.json"

PICKER = {
    # Night-light radiance: one gold hue from a deep amber to an almost white glow (Single hue mode)
    "radiance": {"mode": "single", "first": "#7a4208", "chroma": 60, "lightness": 95, "stops": 7},
    # Poverty gap against the department median: teal = less poor, coral = poorer, gray middle (Divergent mode)
    "poverty_gap": {"mode": "divergent", "first": "#29b6c6", "last": "#ff6b5e",
                    "mid_chroma": 0, "mid_lightness": 32, "stops": 7},
    # Series identity: mining district and "paradox" district (Palette mode, 2 stops = the two ends).
    # Mining gold is close to a radiance step, so on the map mining footprints are drawn as neutral outlines.
    "categorical": {"mode": "palette", "first": "#c18414", "last": "#e8559a", "stops": 2, "direction": "short"},
}

SURFACE = {
    "background": "#0b1020",  # night sky
    "panel": "#121a2e",
    "grid": "#263049",        # 1.3:1 on panel, recessive by design
    "text": "#f3efe6",        # 15.1:1 on panel
    "text_muted": "#a9b0c4",  # 8.0:1 on panel
    "context": "#4e5870",     # districts without mining: context marks, never identity
}


# Shared type: an editorial serif for headlines, a sans with tabular figures for text, its condensed cut for big
# numbers (all SIL Open Font License, on Google Fonts)
TYPE = {
    "display": {"family": "Fraunces", "weights": [600, 700], "use": "titulares y títulos de escena"},
    "text": {"family": "IBM Plex Sans", "weights": [400, 500, 600], "use": "cuerpo, etiquetas y ejes"},
    "figures": {"family": "IBM Plex Sans Condensed", "weights": [600, 700], "use": "KPIs y cifras del reel"},
}


def build_ramp(spec: dict) -> list[str]:
    if spec["mode"] == "single":
        return single_scale(spec["first"], spec["chroma"], spec["lightness"], spec["stops"])
    if spec["mode"] == "divergent":
        return divergent_scale(spec["first"], spec["last"], spec["mid_chroma"], spec["mid_lightness"], spec["stops"])
    return palette_scale(spec["first"], spec["last"], spec["stops"], spec["direction"])


def build_tokens() -> dict:
    ramps = {name: build_ramp(spec) for name, spec in PICKER.items()}
    mining, paradox = ramps.pop("categorical")
    return {
        "theme": "dark",
        "surface": SURFACE,
        "series": {"mining": mining, "paradox": paradox},
        "ramps": ramps,
        "type": TYPE,
        "picker_inputs": PICKER,
    }


def main() -> None:
    TOKENS.parent.mkdir(exist_ok=True)
    TOKENS.write_text(json.dumps(build_tokens(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"tokens -> {TOKENS}")


if __name__ == "__main__":
    main()
