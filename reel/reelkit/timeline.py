"""One timeline for audio, frames and subtitles: intro, scenes separated by pauses, outro, credits."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .text import Word

INTRO, PAUSE, OUTRO, CREDITS = 0.3, 0.35, 0.8, 4.0  # seconds


@dataclass(frozen=True)
class Timeline:
    scenes: list[tuple[float, float]]
    credits: tuple[float, float]

    @property
    def duration(self) -> float:
        return self.credits[1]

    def shift_words(self, scene: int, words: list[Word]) -> list[Word]:
        """Words timed from the start of a scene's own audio, moved onto the reel timeline."""
        offset = self.scenes[scene][0]
        return [Word(w.start + offset, w.end + offset, w.text) for w in words]

    def scene_at(self, t: float) -> int | None:
        """Index of the scene on screen at `t` (a scene stays until the next one starts); None on credits."""
        if t >= self.credits[0]:
            return None
        current = 0
        for i, (start, _) in enumerate(self.scenes):
            if t >= start - PAUSE:
                current = i
        return current


def build_timeline(durations: list[float], intro: float = INTRO, pause: float = PAUSE,
                   outro: float = OUTRO, credits: float = CREDITS) -> Timeline:
    scenes, t = [], intro
    for k, d in enumerate(durations):
        scenes.append((t, t + d))
        t += d + (pause if k + 1 < len(durations) else 0.0)
    credits_start = t + outro
    return Timeline(scenes, (credits_start, credits_start + credits))


def assemble_narration(clips: list[np.ndarray], sr: int, timeline: Timeline) -> np.ndarray:
    """Place each scene's audio at its start; silence everywhere else (including the credits card)."""
    out = np.zeros(round(timeline.duration * sr), np.float32)
    for clip, (start, _) in zip(clips, timeline.scenes):
        i = round(start * sr)
        clip = np.asarray(clip, np.float32)[: len(out) - i]
        out[i:i + len(clip)] += clip
    return out
