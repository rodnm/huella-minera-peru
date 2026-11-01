"""Scene timing: subtitles and audio share one timeline, so the SRT matches the narration."""
import numpy as np
import pytest

from reelkit.text import Word
from reelkit.timeline import assemble_narration, build_timeline


def test_scenes_are_laid_out_with_intro_pauses_outro_and_a_credits_card():
    tl = build_timeline([2.0, 3.0], intro=0.3, pause=0.35, outro=0.8, credits=4.0)
    assert tl.scenes == [pytest.approx((0.3, 2.3)), pytest.approx((2.65, 5.65))]
    assert tl.credits == pytest.approx((6.45, 10.45))
    assert tl.duration == pytest.approx(10.45)


def test_scene_words_are_shifted_to_the_scene_start():
    tl = build_timeline([2.0, 3.0], intro=0.3, pause=0.35, outro=0.8, credits=4.0)
    assert tl.shift_words(1, [Word(0.1, 0.5, "luz")]) == [Word(pytest.approx(2.75), pytest.approx(3.15), "luz")]


def test_assembled_narration_places_each_scene_at_its_timeline_start():
    sr = 1000
    a, b = np.zeros(2000, np.float32), np.zeros(3000, np.float32)
    a[0], b[0] = 0.5, 0.9  # a click at the first sample of each scene
    tl = build_timeline([2.0, 3.0], intro=0.3, pause=0.35, outro=0.8, credits=4.0)
    audio = assemble_narration([a, b], sr, tl)
    assert len(audio) == round(tl.duration * sr)
    assert audio[300] == pytest.approx(0.5) and audio[2650] == pytest.approx(0.9)
    assert np.count_nonzero(audio) == 2
