"""Frames with Pillow, encoded by ffmpeg (H.264 + AAC 48 kHz, -14 LUFS).

Every frame is: the static base (title, AI notice, footer), the scene visual in its box (crossfading
between scenes), the figure and label (fading in), a progress bar and the karaoke subtitle block with
the current word highlighted. After the last scene a credits card replaces the visual.

Adapted from the course pipeline (d2cml-ai/Data-Science-Python, sessions/15-texto-a-reel/reel.py:
`_base`, `_escena`, `_cuadro`, `video`), with full-bleed visuals, token colours and fonts added here.
"""
from __future__ import annotations

import math
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw

from .layout import (ELLIPSIS, FRAME, VISUAL_BOX, ZONES, base_layer, credits_layer, fit_text,
                     scene_text_layer)
from .media import FFMPEG
from .script import Script
from .text import Word, group_words
from .timeline import PAUSE, Timeline
from .visuals import VisualClip

FPS = 30
CROSSFADE = 0.45   # seconds between two scene visuals
TEXT_IN = 0.35     # fade and rise of the figure and label
TARGET_LUFS = -14.0


@dataclass
class SubtitleBlock:
    words: list[Word]
    font: object
    positions: list[tuple[float, float]]   # left-baseline origin of each word
    panel: tuple[float, float, float, float]
    plain: object = None                     # FittedText fallback when the block had to be truncated

    @property
    def start(self) -> float:
        return self.words[0].start

    @property
    def end(self) -> float:
        return self.words[-1].end


def _edge_mask(size: tuple[int, int], fade: int = 56) -> Image.Image:
    """Opaque in the middle, fading at the top and bottom so the visual melts into the background."""
    w, h = size
    column = [min(255, int(255 * min(y, h - 1 - y) / fade)) for y in range(h)]
    return Image.frombytes("L", (1, h), bytes(column)).resize((w, h))


class Renderer:
    def __init__(self, script: Script, timeline: Timeline, words: list[Word], author: str,
                 colors: dict, fonts, fps: int = FPS):
        self.timeline, self.colors, self.fps = timeline, colors, fps
        self.base = base_layer(script.titulo, script.fuente, author, fonts, colors)
        self.text_layers = [scene_text_layer(s.as_dict(), fonts, colors) for s in script.escenas]
        size = (VISUAL_BOX[2] - VISUAL_BOX[0], VISUAL_BOX[3] - VISUAL_BOX[1])
        self.clips = [VisualClip(s.source, size, s.fit, s.zoom, colors["background"]) for s in script.escenas]
        self.mask = _edge_mask(size)
        self.credits = credits_layer(script.creditos, author, fonts, colors)
        self.subtitles = self._layout_subtitles(words, fonts)
        # when each scene appears on screen: its audio start minus the pause before it
        self.shows = [0.0] + [max(0.0, a - PAUSE) for a, _ in timeline.scenes[1:]] + [timeline.credits[0]]

    # --- subtitles ------------------------------------------------------------

    def _layout_subtitles(self, words: list[Word], fonts) -> list[SubtitleBlock]:
        draw = ImageDraw.Draw(Image.new("RGB", FRAME))
        x0, y0, x1, y1 = ZONES["subtitle"]
        box = (x0 + 36, y0 + 22, x1 - 36, y1 - 22)
        blocks = []
        for group in group_words(words):
            text = " ".join(w.text for w in group)
            fitted = fit_text(draw, text, lambda s: fonts("text_strong", s), box, max_size=62, min_size=34,
                              max_lines=2, align="center", valign="center")
            bx0, by0, bx1, by1 = fitted.bbox
            panel = (max(x0, bx0 - 30), max(y0, by0 - 18), min(x1, bx1 + 30), min(y1, by1 + 22))
            if any(l.endswith(ELLIPSIS) for l in fitted.lines):
                blocks.append(SubtitleBlock(group, fitted.font, [], panel, plain=fitted))
                continue
            positions, k = [], 0
            for line, (ox, oy) in zip(fitted.lines, fitted.origins):
                tokens = line.split(" ")
                for j in range(len(tokens)):
                    prefix = " ".join(tokens[:j])
                    dx = draw.textlength(prefix + " ", font=fitted.font) if prefix else 0.0
                    positions.append((ox + dx, oy))
                k += len(tokens)
            if k != len(group):  # a word with inner spaces: fall back to plain text
                blocks.append(SubtitleBlock(group, fitted.font, [], panel, plain=fitted))
            else:
                blocks.append(SubtitleBlock(group, fitted.font, positions, panel))
        return blocks

    def _subtitle_at(self, t: float) -> SubtitleBlock | None:
        for k, block in enumerate(self.subtitles):
            nxt = self.subtitles[k + 1].start if k + 1 < len(self.subtitles) else math.inf
            if block.start - 0.1 <= t <= min(block.end + 0.25, nxt - 0.02):
                return block
        return None

    def _draw_subtitle(self, draw: ImageDraw.ImageDraw, block: SubtitleBlock, t: float) -> None:
        draw.rounded_rectangle(block.panel, radius=26, fill=self.colors["panel"])
        if block.plain is not None:
            block.plain.draw(draw, self.colors["text"])
            return
        for word, origin in zip(block.words, block.positions):
            current = word.start <= t <= word.end + 0.05
            draw.text(origin, word.text, font=block.font, anchor="ls",
                      fill=self.colors["highlight"] if current else self.colors["text"])

    # --- frames ---------------------------------------------------------------

    def _visual(self, scene: int, t: float) -> Image.Image:
        start, end = self.shows[scene], self.shows[scene + 1]
        return self.clips[scene].frame((t - start) / max(1e-6, end - start))

    def frame(self, t: float, subtitles: bool = True) -> Image.Image:
        img = self.base.copy()
        scene = self.timeline.scene_at(t)
        x0, y0 = VISUAL_BOX[:2]
        if scene is None:  # credits card, fading in over the last visual
            last = len(self.clips) - 1
            img.paste(self.clips[last].frame(1.0), (x0, y0), self.mask)
            a = min(1.0, (t - self.timeline.credits[0]) / 0.5)
            layer = self.credits if a >= 1 else _faded(self.credits, a)
            img.paste(layer, (0, 0), layer)
        else:
            visual = self._visual(scene, t)
            since = t - self.shows[scene]
            if scene > 0 and since < CROSSFADE:
                previous = self.clips[scene - 1].frame(1.0)
                visual = Image.blend(previous, visual, max(0.0, since / CROSSFADE))
            img.paste(visual, (x0, y0), self.mask)
            a = min(1.0, max(0.0, since / TEXT_IN))
            layer = self.text_layers[scene] if a >= 1 else _faded(self.text_layers[scene], a)
            img.paste(layer, (0, int(30 * (1 - a))), layer)

        draw = ImageDraw.Draw(img)
        px0, py0, px1, py1 = ZONES["progress"]
        draw.rounded_rectangle((px0, py0, px1, py1), radius=4, fill=self.colors["grid"])
        done = px0 + (px1 - px0) * min(1.0, t / self.timeline.duration)
        if done > px0 + 8:
            draw.rounded_rectangle((px0, py0, done, py1), radius=4, fill=self.colors["accent"])
        if subtitles and (block := self._subtitle_at(t)):
            self._draw_subtitle(draw, block, t)
        return img

    @property
    def frame_count(self) -> int:
        return math.ceil(self.timeline.duration * self.fps)


def _faded(layer: Image.Image, alpha: float) -> Image.Image:
    out = layer.copy()
    out.putalpha(layer.getchannel("A").point(lambda v: int(v * alpha)))
    return out


def encode(renderer: Renderer, out: Path, audio: Path | None = None, gain_db: float = 0.0,
           log=print) -> float:
    """Pipe every frame to ffmpeg; with `audio`, apply `gain_db` and a -1.5 dBFS peak limiter."""
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [FFMPEG, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{FRAME[0]}x{FRAME[1]}", "-r", str(renderer.fps), "-i", "-"]
    if audio is not None:
        cmd += ["-i", str(audio)]
    cmd += ["-map", "0:v"] + (["-map", "1:a"] if audio is not None else [])
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p"]
    if audio is not None:
        cmd += ["-af", f"volume={gain_db:.2f}dB,alimiter=limit=0.84:level=false",
                "-c:a", "aac", "-b:a", "192k", "-ar", "48000"]
    # Encode to a side file and swap it in only on success, so a failed run keeps the previous reel
    partial = out.with_name(f"{out.stem}.part{out.suffix}")
    cmd += ["-movflags", "+faststart", str(partial)]
    t0 = time.time()
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    total = renderer.frame_count
    try:
        for k in range(total):
            try:
                proc.stdin.write(renderer.frame(k / renderer.fps).tobytes())
            except BrokenPipeError:
                break  # ffmpeg stopped early; its stderr below says why
            if k and k % (renderer.fps * 10) == 0:
                log(f"  {k}/{total} cuadros ({time.time() - t0:.0f} s)")
    finally:
        try:
            proc.stdin.close()
        except BrokenPipeError:
            pass
        err = proc.stderr.read().decode("utf-8", "replace")
        proc.wait()
    if proc.returncode != 0:
        partial.unlink(missing_ok=True)
        raise RuntimeError(f"ffmpeg falló ({proc.returncode}): {err.strip()}")
    partial.replace(out)
    return time.time() - t0
