"""The palette functions replicate the LearnUI data color picker (learnui.design/tools/js/data-color-picker.js)."""
from coloraide import Color

from brillo.paleta import divergent_scale, palette_scale, single_scale

# Real output of the picker's Palette mode with its default ends and 8 stops (copied from the site for Tarea 2)
PICKER_DEFAULT_8 = ["#003d5c", "#31497e", "#674f95", "#a14e9a", "#d44c8d", "#f9596f", "#ff7a47", "#ffa600"]


def test_palette_mode_reproduces_picker_output():
    assert palette_scale("#003d5c", "#ffa600", 8) == PICKER_DEFAULT_8


def test_palette_mode_long_hue_path_differs_from_short():
    short = palette_scale("#003d5c", "#ffa600", 5)
    long = palette_scale("#003d5c", "#ffa600", 5, direction="long")
    assert short[0] == long[0] and short[-1] == long[-1]
    assert short[1:-1] != long[1:-1]


def test_single_hue_mode_ends_at_requested_lightness_and_chroma():
    scale = single_scale("#004c6d", chroma=0, lightness=100, stops=5)
    assert scale[0] == "#004c6d"
    assert scale[-1] == "#ffffff"
    lightness = [Color(c).convert("lch-d65")["lightness"] for c in scale]
    assert lightness == sorted(lightness)


def test_divergent_mode_has_a_gray_midpoint_with_zero_chroma():
    scale = divergent_scale("#00876c", "#d43d51", mid_chroma=0, mid_lightness=50, stops=7)
    assert len(scale) == 7
    assert scale[0] == "#00876c" and scale[-1] == "#d43d51"
    mid = Color(scale[3]).convert("lch-d65")
    assert mid["chroma"] < 1
    assert abs(mid["lightness"] - 50) < 1


def test_divergent_arms_keep_their_end_hue_when_the_middle_is_gray():
    # chroma.js stores colors as RGB, so a gray middle has no hue and each arm keeps the hue of its end
    scale = divergent_scale("#00876c", "#d43d51", mid_chroma=0, mid_lightness=50, stops=7)
    hue = [Color(c).convert("lch-d65")["hue"] for c in scale]
    assert abs(hue[1] - hue[0]) < 5
    assert abs(hue[5] - hue[6]) < 5
