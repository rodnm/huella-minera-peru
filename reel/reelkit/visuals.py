"""Scene visuals: a still image (with a slow zoom) or a folder of numbered PNG frames (an animation)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg"}


@dataclass(frozen=True)
class VisualSource:
    """Where a scene's visual comes from: `image` (one file) or `frames` (ordered PNG files)."""

    kind: str
    paths: list[Path]


def _natural_key(path: Path) -> list:
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", path.stem)]


def resolve_visual(base: Path, rel: str) -> VisualSource:
    """Resolve a script's `visual` (relative to `base`, the reel folder) to an image or frame list."""
    path = (Path(base) / rel).resolve()
    if not path.exists():
        raise ValueError(f"El visual '{rel}' no existe (se buscó en {path}).")
    if path.is_dir():
        frames = sorted((p for p in path.iterdir() if p.suffix.lower() == ".png"), key=_natural_key)
        if not frames:
            raise ValueError(f"La carpeta '{rel}' no tiene cuadros PNG numerados.")
        return VisualSource("frames", frames)
    if path.suffix.lower() not in IMAGE_SUFFIXES:
        raise ValueError(f"El visual '{rel}' tiene un formato no admitido; usen PNG, JPG o una carpeta de PNG.")
    return VisualSource("image", [path])


def fit_into(img: Image.Image, size: tuple[int, int], mode: str, background: str) -> Image.Image:
    """Scale `img` to `size`: `cover` fills and crops the centre, `contain` letterboxes on `background`."""
    w, h = size
    img = img.convert("RGB")
    scale = (max if mode == "cover" else min)(w / img.width, h / img.height)
    resized = img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))),
                         Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", size, background)
    canvas.paste(resized, ((w - resized.width) // 2, (h - resized.height) // 2))
    return canvas


class VisualClip:
    """A scene visual ready to draw: `frame(progress)` for progress in [0, 1] of the scene."""

    def __init__(self, source: VisualSource, size: tuple[int, int], mode: str = "contain",
                 zoom: float = 0.04, background: str = "#000000", hold: float = 0.2):
        self.kind = source.kind
        self.size = size
        self.zoom = zoom if source.kind == "image" else 0.0
        self.hold = hold  # last share of the scene that keeps the final animation frame on screen
        self.frames = []
        for p in source.paths:
            with Image.open(p) as im:
                self.frames.append(fit_into(im, size, mode, background))

    def frame(self, progress: float) -> Image.Image:
        progress = min(1.0, max(0.0, progress))
        if self.kind == "frames":
            playing = min(1.0, progress / max(1e-6, 1.0 - self.hold))
            return self.frames[min(len(self.frames) - 1, int(playing * len(self.frames)))]
        base = self.frames[0]
        if self.zoom <= 0:
            return base
        # slow centred zoom ("Ken Burns"), so a still never sits frozen on screen
        k = 1.0 + self.zoom * progress
        w, h = self.size
        cw, ch = w / k, h / k
        box = ((w - cw) / 2, (h - ch) / 2, (w + cw) / 2, (h + ch) / 2)
        return base.resize(self.size, Image.Resampling.BILINEAR, box=box)
