"""Python replica of the three modes of the LearnUI data color picker.

Source: https://www.learnui.design/tools/js/data-color-picker.js (read on 2026-10-28).

- Palette mode interpolates the two ends in CIE LCh with culori (D50 white point), along the short or long hue path.
- Single-hue and Divergent modes use chroma.js ``scale(...).mode("lch")``, whose LCh uses the D65 white point.
- Both libraries clamp out-of-gamut channels when they format hex, so the replica clips instead of gamut mapping.
- chroma.js stores every color as clipped RGB. A gray built from LCh therefore loses its hue, and interpolation
  takes the hue of the other end, so the replica converts the colors it builds to clipped sRGB too.
"""
from coloraide import Color


def _to_hex(color: Color) -> str:
    return color.convert("srgb").to_string(hex=True, fit="clip")


def _as_rgb(color: Color) -> Color:
    """Store a built color as clipped sRGB, like chroma.js does."""
    return color.convert("srgb").fit(method="clip")


def _sample(colors: list, stops: int, space: str, hue: str = "shorter") -> list[str]:
    interpolate = Color.interpolate(colors, space=space, hue=hue)
    return [_to_hex(interpolate(i / (stops - 1))) for i in range(stops)]


def palette_scale(first: str, last: str, stops: int, direction: str = "short") -> list[str]:
    """Palette mode: evenly spaced colors between two ends, through the short or the long side of the hue wheel."""
    hue = {"short": "shorter", "long": "longer"}[direction]
    return _sample([first, last], stops, space="lch", hue=hue)


def single_scale(first: str, chroma: float, lightness: float, stops: int) -> list[str]:
    """Single-hue mode: from ``first`` to a color with the same hue and the chosen chroma and lightness."""
    hue = Color(first).convert("lch-d65")["hue"]
    last = _as_rgb(Color("lch-d65", [lightness, chroma, hue]))
    return _sample([first, last], stops, space="lch-d65")


def divergent_midpoint(first: str, last: str, chroma: float, lightness: float) -> Color:
    """The picker's neutral middle: halfway along the shorter arc between the two hues."""
    h1 = Color(first).convert("lch-d65")["hue"]
    h3 = Color(last).convert("lch-d65")["hue"]
    arc = abs(h1 - h3)
    distance = min(arc, 360 - arc)
    hue = (min(h1, h3) if arc < 360 - arc else max(h1, h3)) + distance / 2
    return _as_rgb(Color("lch-d65", [lightness, chroma, hue % 360]))


def divergent_scale(first: str, last: str, mid_chroma: float, mid_lightness: float, stops: int) -> list[str]:
    """Divergent mode: two ends joined through the computed middle color."""
    mid = divergent_midpoint(first, last, mid_chroma, mid_lightness)
    return _sample([first, mid, last], stops, space="lch-d65")
