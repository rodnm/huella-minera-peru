"""The app as a user sees it: it must run on the committed data, and every control must change the figures."""
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "dashboard" / "app.py")


@pytest.fixture
def app():
    test = AppTest.from_file(APP, default_timeout=60)
    test.session_state["year"] = 2025
    test.session_state["playing"] = False
    test.session_state["department"] = ""
    test.session_state["indicator"] = "huella"
    test.session_state["district"] = None
    test.session_state["search"] = None
    return test.run()


def page_text(app) -> str:
    parts = []
    for name in ("markdown", "subheader", "header", "title"):
        parts += [element.value for element in getattr(app, name)]
    html = [element.proto.body for element in app.get("html")]
    return " ".join(parts + html)


def test_the_app_runs_and_shows_the_national_figures(app):
    assert not app.exception
    text = page_text(app)
    assert "1,985" in text and "×2.7" in text and "310" in text and "73 %" in text


def test_the_year_changes_the_figures(app):
    app.session_state["year"] = 2018
    app.run()

    assert not app.exception
    text = page_text(app)
    assert "1,041" in text and "Huella en 2018" in text


def test_the_department_filter_changes_figures_and_trend(app):
    app.selectbox(key="department").select("MADRE DE DIOS").run()

    assert not app.exception
    text = page_text(app)
    assert "1,130" in text and "solo 6 distritos con aumento" in text
    assert "Madre de Dios: de 336 a 1,130 km²" in text


@pytest.mark.parametrize("indicator,title", [("nueva", "Distritos donde más creció la huella"),
                                             ("luz", "Distritos con más luz por km²"),
                                             ("pobreza", "Distritos con mayor pobreza estimada")])
def test_the_indicator_changes_ranking_and_legend(app, indicator, title):
    app.selectbox(key="indicator").select(indicator).run()

    assert not app.exception
    assert title in page_text(app)


def test_the_search_opens_the_district_card_and_it_closes(app):
    app.selectbox(key="search").select("Inambari, Tambopata, Madre de Dios").run()

    assert not app.exception
    assert "Pobreza 2018 (INEI)" in page_text(app)

    next(b for b in app.button if b.label == "Cerrar la ficha").click().run()
    assert "Pobreza 2018 (INEI)" not in page_text(app)


def test_a_department_without_the_selected_district_closes_the_card(app):
    app.selectbox(key="search").select("Inambari, Tambopata, Madre de Dios").run()
    app.selectbox(key="department").select("PUNO").run()

    assert not app.exception
    assert app.session_state["district"] is None


def test_the_public_text_states_the_limits_of_the_contrast(app):
    text = page_text(app)

    for quote in ("41 %", "59 %", "×1.28", "×1.52", "Fuera de Madre de Dios discrepan más", "Más de la mitad del aumento no tiene contraste"):
        assert quote in text


def test_play_goes_through_every_year_and_stops_at_the_last(app):
    next(b for b in app.button if b.label == "Reproducir").click().run()

    assert not app.exception
    assert app.session_state["playing"] is False
    assert app.session_state["year"] == 2025
    assert "Reproducir" in [b.label for b in app.button]


def test_the_slider_is_sent_after_the_map(monkeypatch):
    """The map takes seconds to arrive, so a slider sent before it runs a year ahead of the year on the map."""
    sent = []
    for name in ("pydeck_chart", "slider"):
        def record(*args, _name=name, _original=getattr(st, name), **kwargs):
            sent.append(_name)
            return _original(*args, **kwargs)
        monkeypatch.setattr(st, name, record)

    test = AppTest.from_file(APP, default_timeout=60)
    test.session_state["year"] = 2018
    test.session_state["playing"] = False
    test.session_state["department"] = ""
    test.session_state["indicator"] = "huella"
    test.session_state["district"] = None
    test.session_state["search"] = None
    test.run()

    assert not test.exception
    assert sent == ["pydeck_chart", "slider"]


def test_moving_the_slider_changes_the_year_and_stops_the_animation(app):
    app.slider[0].set_value(2018).run()

    assert not app.exception
    assert app.session_state["year"] == 2018
    assert app.session_state["playing"] is False
    assert "1,041" in page_text(app)


def test_a_slider_value_that_is_a_year_behind_is_not_the_user_moving_it(app):
    """A click elsewhere reports the slider as the browser has it, which during the animation can be the previous year."""
    app.slider[0].set_value(2023).run()
    app.session_state["year"] = 2024
    app.session_state["year_slider"] = 2024
    app.session_state["playing"] = True
    app.slider[0].set_value(2023).run()

    assert not app.exception
    assert app.session_state["year"] == 2025
