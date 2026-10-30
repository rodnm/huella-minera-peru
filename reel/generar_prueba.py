"""Placeholder visuals for guion_prueba.json (no real data): a gradient still and a 10-frame animation.

    uv run python generar_prueba.py

Writes escenas/prueba/gradiente.jpg and escenas/prueba/encendido/0001..0010.png at the visual box
size (1080x960), using the token colours. They only exist to prove the pipeline; the real scenes
(map time-lapse, charts) are rendered from the data in T8.
"""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from reelkit.config import REEL_DIR, load_colors
from reelkit.layout import VISUAL_BOX

OUT = REEL_DIR / "escenas" / "prueba"
W, H = VISUAL_BOX[2] - VISUAL_BOX[0], VISUAL_BOX[3] - VISUAL_BOX[1]


def _rgb(hex_color: str) -> np.ndarray:
    return np.array([int(hex_color[i:i + 2], 16) for i in (1, 3, 5)], np.float32)


def gradient(colors: dict) -> Image.Image:
    """Night background with a warm glow, like a city seen from space."""
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    bg, panel, glow = _rgb(colors["background"]), _rgb(colors["panel"]), _rgb(colors["footprint"][4])
    vertical = (y / H)[..., None]
    img = bg * (1 - vertical) + panel * vertical
    r = np.hypot((x - 0.62 * W) / W, (y - 0.45 * H) / H)
    img += np.exp(-(r / 0.16) ** 2)[..., None] * (glow - bg) * 0.85
    img += np.random.default_rng(3).normal(0, 1.2, img.shape)  # light grain: avoids H.264 banding
    return Image.fromarray(np.clip(np.round(img), 0, 255).astype(np.uint8))


def lighting_frames(colors: dict, n: int = 10) -> list[Image.Image]:
    """A grid of 'districts' that light up a few at a time, ramp colours from dark to bright."""
    rng = np.random.default_rng(7)
    cols, rows = 18, 16
    order = rng.permutation(cols * rows)
    ramp = colors["footprint"]
    frames = []
    for k in range(1, n + 1):
        img = Image.new("RGB", (W, H), colors["background"])
        glow = Image.new("RGB", (W, H), (0, 0, 0))
        d, g = ImageDraw.Draw(img), ImageDraw.Draw(glow)
        lit = set(order[: int(len(order) * k / n * 0.7)].tolist())
        for idx in range(cols * rows):
            cx = 90 + (idx % cols) * (W - 180) / (cols - 1)
            cy = 80 + (idx // cols) * (H - 160) / (rows - 1)
            if idx in lit:
                level = ramp[min(len(ramp) - 1, 2 + (idx * 7 + k) % (len(ramp) - 2))]
                g.ellipse((cx - 16, cy - 16, cx + 16, cy + 16), fill=level)
                d.ellipse((cx - 7, cy - 7, cx + 7, cy + 7), fill=level)
            else:
                d.ellipse((cx - 4, cy - 4, cx + 4, cy + 4), fill=colors["grid"])
        frames.append(ImageChops.screen(img, glow.filter(ImageFilter.GaussianBlur(10))))
    return frames


def main() -> None:
    colors = load_colors()
    (OUT / "encendido").mkdir(parents=True, exist_ok=True)
    gradient(colors).save(OUT / "gradiente.jpg", quality=92)  # JPG keeps the grain small; a palette PNG bands
    for k, frame in enumerate(lighting_frames(colors), 1):
        frame.quantize(colors=96).save(OUT / "encendido" / f"{k:04}.png", optimize=True)
    print(f"Visuales de prueba en {OUT}")


if __name__ == "__main__":
    main()
