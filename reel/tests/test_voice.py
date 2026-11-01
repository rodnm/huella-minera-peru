"""Choosing the 15-25 s voice reference window that ends on a sentence boundary."""
from reelkit.voice import Segment, choose_reference_window


def _seg(start, end, text, logprob=-0.2):
    return Segment(start=start, end=end, text=text, avg_logprob=logprob, no_speech_prob=0.0)


def test_window_lasts_15_to_25_seconds_and_ends_on_a_sentence_end():
    segs = [
        _seg(0.0, 6.0, "Hola, soy estudiante del curso,"),
        _seg(6.2, 12.0, "y esta grabación sirve de referencia."),
        _seg(12.3, 19.0, "Hablo con calma y con buena dicción,"),
        _seg(19.2, 26.0, "como lo haría en un reel."),
        _seg(26.3, 33.0, "Gracias por escuchar"),
    ]
    w = choose_reference_window(segs)
    assert w is not None
    assert 15.0 <= w.end - w.start <= 25.0
    assert w.text.rstrip().endswith((".", "?", "!", "…"))
    last = [s for s in segs if s.start < w.end][-1]
    assert last.text.endswith(".")
    assert w.end >= last.end  # never cuts the last sentence short


def test_window_rejects_spans_that_end_mid_sentence():
    segs = [
        _seg(0.0, 8.0, "Esto es una prueba,"),
        _seg(8.1, 16.0, "que sigue con una coma,"),
        _seg(16.1, 22.0, "y termina aquí."),
    ]
    w = choose_reference_window(segs)
    assert w is not None
    assert w.text.endswith("termina aquí.")
    assert 15.0 <= w.end - w.start <= 25.0


def test_window_is_none_when_no_sentence_end_falls_in_range():
    # the only sentence end makes windows of 2 s, 13.9 s or 25.9 s: none fits 15-25 s
    segs = [_seg(0.0, 12.0, "Una frase larga,"), _seg(12.1, 24.0, "sin final,"),
            _seg(24.1, 36.0, "que nunca termina,"), _seg(36.1, 38.0, "fin.")]
    assert choose_reference_window(segs) is None


def test_window_does_not_bridge_a_long_pause():
    segs = [_seg(0.0, 9.0, "Primera parte."), _seg(12.0, 20.0, "Segunda parte.")]
    assert choose_reference_window(segs) is None


def test_window_prefers_the_clearest_speech():
    segs = [
        _seg(0.0, 8.0, "Primera frase dudosa.", logprob=-0.9),
        _seg(8.2, 17.0, "Segunda frase dudosa.", logprob=-0.9),
        _seg(20.0, 28.0, "Tercera frase clara.", logprob=-0.1),
        _seg(28.2, 37.0, "Cuarta frase clara.", logprob=-0.1),
    ]
    w = choose_reference_window(segs)
    assert w is not None and w.start >= 19.0
