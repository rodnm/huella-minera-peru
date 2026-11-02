"""Text fitting never overflows its box, and scene text never covers the visual."""
from PIL import Image, ImageDraw, ImageFont

from reelkit import layout
from reelkit.layout import FRAME, VISUAL_BOX, ZONES, fit_text, scene_text_layer


def default_fonts(role, size):
    return ImageFont.load_default(size)


def _inside(inner, outer):
    return (inner[0] >= outer[0] and inner[1] >= outer[1]
            and inner[2] <= outer[2] and inner[3] <= outer[3])


def _overlap(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _draw():
    return ImageDraw.Draw(Image.new("RGB", FRAME))


def test_short_text_stays_on_one_line_at_the_largest_size():
    box = (90, 1300, 990, 1500)
    fitted = fit_text(_draw(), "12 %", lambda s: default_fonts("figures", s), box, max_size=150, min_size=40)
    assert fitted.lines == ["12 %"] and fitted.size == 150
    assert all(_inside(b, box) for b in fitted.line_boxes)


def test_long_text_wraps_and_every_measured_line_stays_inside_the_box():
    box = (90, 1300, 600, 1500)
    text = "Distritos con mucha luz y pobreza por encima de la mediana departamental"
    fitted = fit_text(_draw(), text, lambda s: default_fonts("text", s), box, max_size=80, min_size=24, max_lines=3)
    assert 1 < len(fitted.lines) <= 3
    assert all(_inside(b, box) for b in fitted.line_boxes)


def test_text_that_cannot_fit_is_truncated_with_an_ellipsis_and_still_fits():
    box = (90, 1300, 300, 1340)
    text = "Supercalifragilisticoespialidoso " * 6
    fitted = fit_text(_draw(), text, lambda s: default_fonts("text", s), box, max_size=60, min_size=30, max_lines=1)
    assert len(fitted.lines) == 1 and fitted.lines[0].endswith("…")
    assert all(_inside(b, box) for b in fitted.line_boxes)


def test_layout_zones_do_not_overlap_the_visual_or_each_other():
    names = list(ZONES)
    for i, a in enumerate(names):
        assert not _overlap(ZONES[a], VISUAL_BOX), a
        assert _inside(ZONES[a], (0, 0, *FRAME)), a
        for b in names[i + 1:]:
            assert not _overlap(ZONES[a], ZONES[b]), (a, b)
    visual_area = (VISUAL_BOX[2] - VISUAL_BOX[0]) * (VISUAL_BOX[3] - VISUAL_BOX[1])
    assert visual_area >= 0.45 * FRAME[0] * FRAME[1]  # the visual is a large part of the frame


def test_scene_text_layer_never_draws_over_the_visual_box():
    colors = {"text": "#f3efe6", "text_muted": "#a9b0c4", "accent": "#c18414"}
    scenes = [
        {"cifra": "+38 %", "etiqueta": "Más luz en los distritos mineros entre 2013 y 2024"},
        {"cifra": "", "etiqueta": "¿La luz es de la mina o del pueblo que vive a su lado?"},
        {"cifra": "1 234 567 890 123", "etiqueta": "Una etiqueta exageradamente larga " * 4},
    ]
    for scene in scenes:
        layer = scene_text_layer(scene, default_fonts, colors)
        assert layer.size == FRAME and layer.mode == "RGBA"
        bbox = layer.getchannel("A").getbbox()
        assert bbox is not None
        assert not _overlap(bbox, VISUAL_BOX), scene
        assert _inside(bbox, ZONES["figure"]), (scene, bbox)


def test_a_line_break_in_the_text_is_kept():
    box = (60, 0, 1020, 200)
    fitted = fit_text(_draw(), "Fuente: datos\nNombre Apellido", lambda s: default_fonts("text", s), box, max_size=28, min_size=20)
    assert fitted.lines == ["Fuente: datos", "Nombre Apellido"]


def test_the_author_goes_on_a_line_of_their_own_in_the_footer(monkeypatch):
    seen = []
    real = layout.fit_text

    def spy(draw, text, *args, **kwargs):
        fitted = real(draw, text, *args, **kwargs)
        seen.append(fitted.lines)
        return fitted

    monkeypatch.setattr(layout, "fit_text", spy)
    colors = {"background": "#000000", "text": "#ffffff", "text_muted": "#cccccc", "panel": "#111111", "accent": "#ff0000"}
    layout.base_layer("Título", "Fuente: MapBiomas Perú (Col. 4) y Amazon Mining Watch", "Rodrigo Norabuena", default_fonts, colors)

    assert seen[-1] == ["Fuente: MapBiomas Perú (Col. 4) y Amazon Mining Watch", "Rodrigo Norabuena"]
