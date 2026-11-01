"""Fonts from the design tokens, downloaded from the google/fonts repository (SIL Open Font License).

Fraunces (titles), IBM Plex Sans (subtitles and body) and IBM Plex Sans Condensed (big figures).
Files are pinned to one google/fonts commit and checked against their SHA-256; they land in
`recursos/fuentes/` (git-ignored) and are listed with their licence in `recursos/CREDITOS.md`.

    uv run python -m reelkit.fonts      # download them ahead of time (the renderer also does it)
"""
from __future__ import annotations

import hashlib
import sys
import urllib.request
from functools import lru_cache
from pathlib import Path

from PIL import ImageFont

from .config import FONTS_DIR, USER_AGENT

GOOGLE_FONTS_COMMIT = "9862abc066c9b83bf84c3e8ed1fc2d8d48f9bbf0"
RAW = f"https://raw.githubusercontent.com/google/fonts/{GOOGLE_FONTS_COMMIT}/ofl"

# local file name -> (path in google/fonts/ofl, sha256)
FILES = {
    "Fraunces[SOFT,WONK,opsz,wght].ttf": ("fraunces/Fraunces%5BSOFT,WONK,opsz,wght%5D.ttf",
        "177ff6c0f14e5550a3c624247cd1189611d4eb65d000b14944c63d967958abbb"),
    "IBMPlexSans[wdth,wght].ttf": ("ibmplexsans/IBMPlexSans%5Bwdth,wght%5D.ttf",
        "3b031aa4216174205bd8471f88a49b91f093169e9e87bd5262242bc5967fe2e3"),
    "IBMPlexSansCondensed-SemiBold.ttf": ("ibmplexsanscondensed/IBMPlexSansCondensed-SemiBold.ttf",
        "a081ca60548aea14100757a2d6fe71ca60fd90ebce779c9a8ae5a0c8fb4526d4"),
    "IBMPlexSansCondensed-Bold.ttf": ("ibmplexsanscondensed/IBMPlexSansCondensed-Bold.ttf",
        "b65492d86cdd5cd9d43d2671b55d5d36fec36859fc8b08bc6aba78e441d6c849"),
    "OFL-Fraunces.txt": ("fraunces/OFL.txt",
        "bdf4c22802eaf804f998195871c6b8938aac2ac14b2d78a8bd66a6f1eced833b"),
    "OFL-IBMPlexSans.txt": ("ibmplexsans/OFL.txt",
        "7e6b2818edbd8f6a01ae80641cc8f16a51080d08fb4e532be3a0b6f74adb07da"),
    "OFL-IBMPlexSansCondensed.txt": ("ibmplexsanscondensed/OFL.txt",
        "7e6b2818edbd8f6a01ae80641cc8f16a51080d08fb4e532be3a0b6f74adb07da"),
}

# role -> (file, weight); the families and weights come from design/tokens.json ("type")
ROLES = {
    "display": ("Fraunces[SOFT,WONK,opsz,wght].ttf", 600),
    "display_bold": ("Fraunces[SOFT,WONK,opsz,wght].ttf", 700),
    "text": ("IBMPlexSans[wdth,wght].ttf", 400),
    "text_medium": ("IBMPlexSans[wdth,wght].ttf", 500),
    "text_strong": ("IBMPlexSans[wdth,wght].ttf", 600),
    "figures_semibold": ("IBMPlexSansCondensed-SemiBold.ttf", 600),
    "figures": ("IBMPlexSansCondensed-Bold.ttf", 700),
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ensure_fonts(folder: Path = FONTS_DIR, quiet: bool = False) -> None:
    """Download any missing font file and verify every file's SHA-256 against the pinned value."""
    folder.mkdir(parents=True, exist_ok=True)
    for name, (remote, expected) in FILES.items():
        target = folder / name
        if not target.exists():
            url = f"{RAW}/{remote}"
            if not quiet:
                print(f"  descargando {name} ({url})", flush=True)
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=60) as response:
                data = response.read()
            tmp = target.with_suffix(target.suffix + ".part")
            tmp.write_bytes(data)
            tmp.replace(target)
        if expected and _sha256(target) != expected:
            raise RuntimeError(f"{target} no coincide con su SHA-256 fijado; bórrenlo y vuelvan a bajarlo.")


def _axis_values(font: ImageFont.FreeTypeFont, weight: int, size: int) -> list[float]:
    values = []
    for axis in font.get_variation_axes():
        name = axis["name"].decode() if isinstance(axis["name"], bytes) else str(axis["name"])
        name = name.lower()
        value = axis["default"]
        if "weight" in name:
            value = weight
        elif "optical" in name:
            value = size  # Fraunces' optical size follows the point size
        elif "wonky" in name:
            value = 0  # the file's default instance is "wonky"; keep the calmer editorial forms
        values.append(min(axis["maximum"], max(axis["minimum"], value)))
    return values


@lru_cache(maxsize=256)
def font(role: str, size: int) -> ImageFont.FreeTypeFont:
    """A font for a layout role ("display", "text", "text_strong", "figures", ...) at `size` px."""
    file, weight = ROLES[role]
    path = FONTS_DIR / file
    if not path.exists():
        ensure_fonts()
    f = ImageFont.truetype(str(path), size)
    try:
        axes = f.get_variation_axes()
    except OSError:  # static font
        axes = None
    if axes:
        f.set_variation_by_axes(_axis_values(f, weight, size))
    return f


if __name__ == "__main__":
    ensure_fonts()
    for name in FILES:
        p = FONTS_DIR / name
        print(f"{name}  {p.stat().st_size:>8} B  sha256 {_sha256(p)}")
    sys.exit(0)
