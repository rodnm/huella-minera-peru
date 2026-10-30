"""Build design/tokens.json, the single source of colors for the dashboard, the charts and the reel.

Run from the repository root: uv run python -m scripts.construir_paleta

Every ramp records the LearnUI data color picker inputs (mode, ends, sliders, stops) that produce it, so anyone can
re-create it on https://www.learnui.design/tools/data-color-picker.html or with brillo.paleta.

VALIDATION_NOTE
"""
import json
from pathlib import Path

from brillo.paleta import divergent_scale, palette_scale, single_scale

TOKENS = Path(__file__).resolve().parent.parent / "design" / "tokens.json"

PICKER = {
    # Mining footprint: exposed soil, from dark ochre to pale sediment (Single hue mode)
    "footprint": {"mode": "single", "first": "#8a5413", "chroma": 55, "lightness": 94, "stops": 7},
    # Night lights: from deep river blue to almost white (Single hue mode)
    "light": {"mode": "single", "first": "#2a6496", "chroma": 35, "lightness": 94, "stops": 7},
    # INEI monetary poverty: from dark plum to pale pink (Single hue mode)
    "poverty": {"mode": "single", "first": "#7a3a66", "chroma": 45, "lightness": 92, "stops": 7},
    # Series identity: MapBiomas soil and Amazon Mining Watch, the color of the pools the mines leave (Palette mode)
    "categorical": {"mode": "palette", "first": "#c1882e", "last": "#2ba798", "stops": 2, "direction": "short"},
}

SURFACE = {
    "background": "#0f1e19",  # canopy seen from above
    "panel": "#162a23",
    "grid": "#2c4238",        # recessive by design
    "text": "#f1e9d6",
    "text_muted": "#a9b6a8",
    "context": "#43594e",     # districts without data of interest: context marks, never identity
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
    mining, contrast = ramps.pop("categorical")
    return {
        "theme": "dark",
        "surface": SURFACE,
        "series": {"mining": mining, "contrast": contrast},
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
