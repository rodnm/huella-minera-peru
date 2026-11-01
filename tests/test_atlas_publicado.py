"""The published files must match the committed panel: this is what stops a wrong figure from being deployed."""
import json
from pathlib import Path

import pandas as pd
import pytest

from brillo.atlas import MIN_DISTRICT_KM2, describe

ROOT = Path(__file__).resolve().parent.parent
PROCESADOS = ROOT / "datos" / "procesados"
WEB_DATA = ROOT / "datos" / "atlas"


@pytest.fixture(scope="module")
def panel():
    return pd.read_csv(PROCESADOS / "panel_distrito_anio.csv", dtype={"ubigeo": str}, low_memory=False)


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_published_figures_are_the_ones_the_panel_gives(panel):
    expected = describe(panel)
    for path in (PROCESADOS / "atlas.json", WEB_DATA / "atlas.json"):
        published = load(path)
        for key in ("national_km2", "ratio", "increase_km2", "madre_de_dios", "top_share_of_increase",
                    "districts_with_footprint"):
            assert published[key] == pytest.approx(expected[key]), f"{path.name}: {key}"


def test_the_browser_counts_the_same_districts_as_the_findings(panel):
    payload = load(WEB_DATA / "panel.json")
    expected = describe(panel)["districts_with_footprint"]
    for i, year in enumerate(payload["years"]):
        assert sum((d["m"][i] or 0) >= MIN_DISTRICT_KM2 for d in payload["districts"]) == expected[str(year)]


def test_published_contrast_is_the_one_computed_from_the_table():
    table = pd.read_csv(PROCESADOS / "contraste_huella.csv", dtype={"department": str})
    rows = table[table["department"] == "17"].set_index("year")
    contrast = load(WEB_DATA / "atlas.json")["contrast"]["madre_de_dios"]
    last = contrast["last_confirmed_year"]
    for source in ("mapbiomas", "amw"):
        assert contrast["periods"]["whole"][source] == pytest.approx(rows.loc[last, f"{source}_km2"] / rows.loc[2018, f"{source}_km2"])


@pytest.mark.parametrize("text", ["727", "1,985", "63 %", "73 %", "×2.02", "×1.98", "41 %", "59 %"])
def test_the_readme_quotes_the_figures_of_the_data(text):
    assert text in (ROOT / "README.md").read_text(encoding="utf-8")
