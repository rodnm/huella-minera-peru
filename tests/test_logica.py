import json

import numpy as np
import pytest

from logica import (INDICATORS, Atlas, contrast_paragraphs, district_features, findings, fit_view, kpis, km2,
                    load_atlas, points_for_year, ranking, title_case)


def write_atlas(folder):
    panel = {"years": [2013, 2025], "districts": [
        {"u": "170101", "n": "INAMBARI", "p": "TAMBOPATA", "d": "MADRE DE DIOS", "pop": 1000.0, "area": 200.0,
         "m": [1.0, 5.0], "l": [10.0, 20.0], "pov": [40.0, 30.0, 50.0]},
        {"u": "170102", "n": "LABERINTO", "p": "TAMBOPATA", "d": "MADRE DE DIOS", "pop": 500.0, "area": 100.0,
         "m": [0.0, 1.0], "l": [1.0, 2.0], "pov": None},
        {"u": "010101", "n": "CHACHAPOYAS", "p": "CHACHAPOYAS", "d": "AMAZONAS", "pop": 2000.0, "area": 150.0,
         "m": [1.0, 2.0], "l": [3.0, 4.0], "pov": [9.0, 6.0, 12.0]},
        {"u": "010102", "n": "ASUNCION", "p": "CHACHAPOYAS", "d": "AMAZONAS", "pop": 300.0, "area": 50.0,
         "m": [0.0, 0.005], "l": [0.0, 0.0], "pov": [20.0, 10.0, 30.0]},
    ]}
    summary = {
        "first_year": 2013, "last_year": 2025, "national_km2": {"2013": 2.0, "2025": 8.005}, "ratio": 4.0025,
        "increase_km2": 6.005,
        "madre_de_dios": {"first_km2": 1.0, "last_km2": 6.0, "share_of_increase": 0.83, "share_of_last": 0.75},
        "top_districts": [{"ubigeo": "170101", "district": "INAMBARI", "department": "MADRE DE DIOS", "first_km2": 1.0,
                           "last_km2": 5.0, "gain_km2": 4.0}],
        "top_share_of_increase": 0.73, "districts_with_footprint": {"2013": 2, "2025": 3},
        "validation": {"official_km2": {}, "max_national_gap": 0.00254},
        "contrast": {
            "years": [2018, 2021, 2024], "share_of_increase_contrasted": 0.41,
            "madre_de_dios": {
                "last_confirmed_year": 2024, "mapbiomas_km2": {"2018": 507.0, "2021": 647.0, "2024": 1023.0},
                "amw_km2": {"2018": 769.0, "2021": 1166.0, "2024": 1520.0},
                "mapbiomas_on_amw": {"2018": 0.96, "2021": 0.98, "2024": 0.97}, "cells_with_scars_share": 0.0315,
                "periods": {"whole": {"mapbiomas": 2.02, "amw": 1.98}, "first_half": {"mapbiomas": 1.28, "amw": 1.52},
                            "second_half": {"mapbiomas": 1.58, "amw": 1.30}},
            },
            "other_departments": [{"department": "21", "name": "PUNO", "mapbiomas_ratio": 1.39, "amw_ratio": 3.6,
                                   "amw_first_km2": 5.9, "amw_last_km2": 21.4}],
        },
    }
    tokens = {
        "surface": {"background": "#0f1e19", "panel": "#162a23", "grid": "#2c4238", "text": "#f1e9d6",
                    "text_muted": "#a9b6a8", "context": "#43594e"},
        "series": {"mining": "#c1882e", "contrast": "#2ba798"},
        "ramps": {"footprint": ["#8a5413", "#9e6926", "#b18039", "#c5964d", "#d8ad61", "#ebc576", "#ffdd8b"],
                  "light": ["#2a6496", "#3e7ba8", "#5592b9", "#6daaca", "#87c2dc", "#a2daed", "#bff2ff"],
                  "poverty": ["#7a3a66", "#8f517e", "#a56897", "#bb80b0", "#d198ca", "#e8b2e4", "#ffcbff"]},
    }
    geo = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"ubigeo": d["u"]},
         "geometry": {"type": "Polygon", "coordinates": [[[-70, -13], [-69, -13], [-69, -12], [-70, -13]]]}}
        for d in panel["districts"]]}
    outlines = {"type": "FeatureCollection", "features": []}
    meta = {"count": 2, "years": [2013, 2025], "transform": [-70.0, 0.5, -10.0, -0.5], "min_fraction": 0.01}
    blob = np.array([0, 1], "<u2").tobytes() + np.array([0, 1], "<u2").tobytes() + bytes([255, 255, 0, 128])
    for name, content in (("panel", panel), ("atlas", summary), ("tokens", tokens), ("distritos", geo),
                          ("departamentos", outlines), ("huella", meta)):
        (folder / f"{name}.json").write_text(json.dumps(content), encoding="utf-8")
    (folder / "huella.bin").write_bytes(blob)


@pytest.fixture
def atlas(tmp_path) -> Atlas:
    write_atlas(tmp_path)
    return load_atlas(tmp_path)


def test_kpis_give_area_change_districts_and_concentration(atlas):
    result = kpis(atlas, "", 1)

    assert result["area"] == pytest.approx(8.005)
    assert result["ratio"] == pytest.approx(4.0025)
    assert result["change"] == pytest.approx(6.005)
    assert (result["districts"], result["districts_first"]) == (3, 2)
    assert result["gains"] == 4


def test_kpis_follow_the_department_filter(atlas):
    result = kpis(atlas, "MADRE DE DIOS", 1)

    assert result["area"] == pytest.approx(6.0)
    assert result["districts"] == 2


def test_kpis_do_not_claim_a_top_ten_when_few_districts_grew(atlas):
    assert kpis(atlas, "MADRE DE DIOS", 1)["top_share"] is None


def test_first_year_has_no_change_to_report(atlas):
    result = kpis(atlas, "", 0)

    assert result["ratio"] is None and result["top_share"] is None


def test_ranking_orders_the_chosen_indicator_inside_the_department(atlas):
    rows = ranking(atlas, "huella", "MADRE DE DIOS", 1, top=10)

    assert [row["name"] for row in rows] == ["Inambari", "Laberinto"]


def test_ranking_of_new_footprint_leaves_out_districts_without_a_gain(atlas):
    rows = ranking(atlas, "nueva", "", 0, top=10)

    assert rows == []


def test_ranking_of_poverty_carries_the_interval_and_skips_missing_values(atlas):
    rows = ranking(atlas, "pobreza", "", 1, top=10)

    assert [row["name"] for row in rows] == ["Inambari", "Asuncion", "Chachapoyas"]
    assert (rows[0]["low"], rows[0]["high"]) == (30.0, 50.0)


def test_every_indicator_has_a_note_a_label_and_a_unit():
    for spec in INDICATORS.values():
        assert spec.label and spec.unit and spec.note(2025) and spec.title("todo el Perú")


def test_points_drop_cells_without_footprint_that_year_and_mark_the_new_ones(atlas):
    first = points_for_year(atlas, 2013)
    last = points_for_year(atlas, 2025)

    assert len(first) == 1
    assert len(last) == 2
    assert first[0]["c"] != last[1]["c"]
    assert last[1]["r"] < last[0]["r"]


def test_district_features_paint_by_indicator_and_dim_other_departments(atlas):
    features = district_features(atlas, "pobreza", "MADRE DE DIOS", 1)["features"]

    painted = {f["properties"]["ubigeo"]: f["properties"] for f in features}
    assert painted["170101"]["fill"][3] == 255
    assert painted["010101"]["fill"][3] < 255
    assert "40.0 %" in painted["170101"]["valor"]
    assert painted["170102"]["valor"] == "sin dato"


def test_findings_quote_the_published_figures(atlas):
    text = " ".join(big + " " + small for big, small in findings(atlas))

    assert "de 2 a 8 km²" in text
    assert "Inambari" in text


def test_contrast_publishes_coverage_periods_and_disagreements(atlas):
    text = " ".join(contrast_paragraphs(atlas))

    for quote in ("41 %", "59 %", "×2.02", "×1.98", "×1.28", "×1.52", "×1.58", "×1.30", "Puno", "×3.6"):
        assert quote in text


def test_formats_and_names():
    assert km2(1984.9) == "1,985"
    assert km2(66.6) == "66.6"
    assert km2(0.5) == "0.50"
    assert title_case("MADRE DE DIOS") == "Madre de Dios"


def test_fit_view_zooms_in_on_a_smaller_area():
    peru = fit_view(((-81.4, -18.4), (-68.6, 0.1)))
    district = fit_view(((-70.6, -13.2), (-70.0, -12.8)))

    assert district["zoom"] > peru["zoom"]
    assert peru["longitude"] == pytest.approx(-75.0)
