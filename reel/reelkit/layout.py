"""Frame layout for a 1080x1920 (9:16) reel: fixed zones, measured text fitting and static layers.

Zones (pixels, x0, y0, x1, y1). The visual gets half of the frame and no text is ever drawn on it,
so the key area of a map or chart is never covered:

    progress  thin bar at the top           title  reel title (Fraunces)
    badge     "VOZ GENERADA CON IA"         VISUAL_BOX  the scene visual, full width
    figure    big figure + label            subtitle  karaoke subtitles
    footer    data source and author

Every text is measured with `ImageDraw.textbbox` and shrunk, wrapped or truncated until it fits its
box (the course pipeline learned that Pillow draws from the box corner, not the baseline).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from PIL import Image, ImageDraw, ImageFont

FRAME = (1080, 1920)
MARGIN = 72
VISUAL_BOX = (0, 272, 1080, 1232)
ZONES = {
    "progress": (MARGIN, 92, FRAME[0] - MARGIN, 100),
    "title": (MARGIN, 116, FRAME[0] - MARGIN, 186),
    "badge": (MARGIN, 200, FRAME[0] - MARGIN, 252),
    "figure": (MARGIN, 1256, FRAME[0] - MARGIN, 1508),
    "subtitle": (48, 1528, FRAME[0] - 48, 1690),
    "footer": (MARGIN, 1706, FRAME[0] - MARGIN, 1800),
}
AI_NOTICE = "VOZ GENERADA CON IA"
ELLIPSIS = "…"

FontFor = Callable[[int], ImageFont.FreeTypeFont]
Fonts = Callable[[str, int], ImageFont.FreeTypeFont]


@dataclass
class FittedText:
    """Lines placed inside a box: `origins` are left-baseline anchors, `line_boxes` measured bboxes."""

    font: ImageFont.FreeTypeFont
    size: int
    lines: list[str]
    origins: list[tuple[float, float]] = field(default_factory=list)
    line_boxes: list[tuple[float, float, float, float]] = field(default_factory=list)

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        xs0, ys0, xs1, ys1 = zip(*self.line_boxes)
        return min(xs0), min(ys0), max(xs1), max(ys1)

    def draw(self, draw: ImageDraw.ImageDraw, fill) -> None:
        for line, origin in zip(self.lines, self.origins):
            draw.text(origin, line, font=self.font, fill=fill, anchor="ls")


def _inside(inner, outer) -> bool:
    return (inner[0] >= outer[0] and inner[1] >= outer[1]
            and inner[2] <= outer[2] and inner[3] <= outer[3])


def wrap(draw: ImageDraw.ImageDraw, text: str, font, width: float) -> list[str]:
    """Greedy word wrap measured with the real font; a line break in the text always starts a new line."""
    lines = []
    for paragraph in text.split("\n"):
        current = ""
        for word in paragraph.split():
            candidate = f"{current} {word}".strip()
            if not current or draw.textlength(candidate, font=font) <= width:
                current = candidate
            else:
                lines.append(current)
                current = word
        if current:
            lines.append(current)
    return lines


def _truncate(draw, line: str, font, width: float) -> str:
    """Cut a line (by characters) and end it with an ellipsis so it fits `width`."""
    while line and draw.textlength(line + ELLIPSIS, font=font) > width:
        line = line[:-1].rstrip()
    return line + ELLIPSIS


def _place(draw, lines, font, size, box, line_gap, align, valign) -> FittedText:
    x0, y0, x1, y1 = box
    ascent, _ = font.getmetrics()
    pitch = size * (1 + line_gap)
    origins, boxes = [], []
    for k, line in enumerate(lines):
        w = draw.textlength(line, font=font)
        x = x0 + ((x1 - x0) - w) / 2 if align == "center" else x0
        origins.append((x, y0 + ascent + k * pitch))
        boxes.append(draw.textbbox(origins[-1], line, font=font, anchor="ls"))
    fitted = FittedText(font, size, lines, origins, boxes)
    top, bottom = fitted.bbox[1], fitted.bbox[3]
    free = (y1 - y0) - (bottom - top)
    shift = y0 - top + (free / 2 if valign == "center" else free if valign == "bottom" else 0)
    fitted.origins = [(x, y + shift) for x, y in origins]
    fitted.line_boxes = [(a, b + shift, c, d + shift) for a, b, c, d in boxes]
    return fitted


def fit_text(draw: ImageDraw.ImageDraw, text: str, font_for: FontFor, box, max_size: int,
             min_size: int, max_lines: int = 2, line_gap: float = 0.15, step: int = 2,
             align: str = "left", valign: str = "top") -> FittedText:
    """Largest size (from `max_size` down to `min_size`) whose measured lines all fit inside `box`.

    If even `min_size` does not fit, the text is cut to `max_lines` and the last line ends in an
    ellipsis, so the result never overflows the box.
    """
    width = box[2] - box[0]
    for size in range(max_size, min_size - 1, -step):
        font = font_for(size)
        lines = wrap(draw, text, font, width)
        if len(lines) > max_lines:
            continue
        fitted = _place(draw, lines, font, size, box, line_gap, align, valign)
        if all(_inside(b, box) for b in fitted.line_boxes):
            return fitted
    font = font_for(min_size)
    lines = wrap(draw, text, font, width)
    kept = lines[:max_lines]
    if len(lines) > max_lines or any(draw.textlength(l, font=font) > width for l in kept):
        kept = [l if draw.textlength(l, font=font) <= width else _truncate(draw, l, font, width) for l in kept]
        if len(lines) > max_lines and not kept[-1].endswith(ELLIPSIS):
            kept[-1] = _truncate(draw, kept[-1], font, width)
    while kept:
        fitted = _place(draw, kept, font, min_size, box, line_gap, align, valign)
        if all(_inside(b, box) for b in fitted.line_boxes):
            return fitted
        kept = kept[:-1]
        if kept:
            kept[-1] = _truncate(draw, kept[-1], font, width)
    raise ValueError(f"El cuadro {box} es demasiado chico para cualquier texto a {min_size} px.")


# --- static layers ------------------------------------------------------------

def scene_text_layer(scene: dict, fonts: Fonts, colors: dict) -> Image.Image:
    """Transparent layer with the scene's big figure (`cifra`) and its label (`etiqueta`)."""
    layer = Image.new("RGBA", FRAME, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    x0, y0, x1, y1 = ZONES["figure"]
    figure, label = (scene.get("cifra") or "").strip(), (scene.get("etiqueta") or "").strip()
    top = y0
    if figure:
        fitted = fit_text(draw, figure, lambda s: fonts("figures", s), (x0, y0, x1, y0 + 150),
                          max_size=150, min_size=56, max_lines=1)
        fitted.draw(draw, colors["accent"])
        top = fitted.bbox[3] + 28
    if label and top < y1 - 30:
        if figure:
            fitted = fit_text(draw, label, lambda s: fonts("text_strong", s), (x0, top, x1, y1),
                              max_size=46, min_size=26, max_lines=3)
        else:
            fitted = fit_text(draw, label, lambda s: fonts("display", s), (x0, top, x1, y1),
                              max_size=76, min_size=34, max_lines=3, valign="center")
        fitted.draw(draw, colors["text"])
    return layer


def base_layer(title: str, source: str, author: str, fonts: Fonts, colors: dict) -> Image.Image:
    """What stays on screen for the whole video: background, title, AI notice and footer."""
    img = Image.new("RGB", FRAME, colors["background"])
    draw = ImageDraw.Draw(img)
    fit_text(draw, title, lambda s: fonts("display", s), ZONES["title"],
             max_size=50, min_size=28, max_lines=1, valign="center").draw(draw, colors["text"])

    # AI notice: a solid pill so it reads on any frame
    bx0, by0, _, by1 = ZONES["badge"]
    font = fonts("text_strong", 28)
    w = draw.textlength(AI_NOTICE, font=font)
    pill = (bx0, by0 + 4, bx0 + w + 76, by1 - 4)
    draw.rounded_rectangle(pill, radius=(pill[3] - pill[1]) // 2, fill=colors["panel"],
                           outline=colors["text_muted"], width=2)
    cy = (pill[1] + pill[3]) / 2
    draw.ellipse((bx0 + 22, cy - 7, bx0 + 36, cy + 7), fill=colors["accent"])
    draw.text((bx0 + 52, cy), AI_NOTICE, font=font, fill=colors["text"], anchor="lm")

    footer = f"{source}\n{author}" if author else source
    fit_text(draw, footer, lambda s: fonts("text", s), ZONES["footer"],
             max_size=28, min_size=20, max_lines=2).draw(draw, colors["text_muted"])
    return img


def credits_layer(credits: list[str], author: str, fonts: Fonts, colors: dict) -> Image.Image:
    """Closing card drawn over the visual box: sources, music, image credits and the AI-voice note."""
    layer = Image.new("RGBA", FRAME, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    x0, y0, x1, y1 = VISUAL_BOX
    draw.rectangle(VISUAL_BOX, fill=colors["panel"])
    inner = (x0 + MARGIN, y0 + 70, x1 - MARGIN, y1 - 60)
    heading = fit_text(draw, "Créditos y fuentes", lambda s: fonts("display", s),
                       (inner[0], inner[1], inner[2], inner[1] + 90), max_size=64, min_size=36, max_lines=1)
    heading.draw(draw, colors["accent"])
    lines = list(credits) + ([f"Reel: {author}"] if author else [])
    top = heading.bbox[3] + 40
    for size in range(40, 19, -2):
        blocks, y, ok = [], top, True
        for line in lines:
            box = (inner[0], y, inner[2], inner[3])
            if y >= inner[3] - size:
                ok = False
                break
            fitted = fit_text(draw, line, lambda s: fonts("text", s), box, max_size=size, min_size=size, max_lines=4)
            if any(l.endswith(ELLIPSIS) for l in fitted.lines) and size > 20:
                ok = False
                break
            blocks.append(fitted)
            y = fitted.bbox[3] + int(size * 0.7)
        if ok:
            break
    for fitted in blocks:
        fitted.draw(draw, colors["text"])
    return layer
