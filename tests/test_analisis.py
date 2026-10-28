import pandas as pd
import pytest

from brillo.analisis import mine_openings, paradox_districts


def test_paradox_is_a_mining_district_bright_nationally_but_poorer_than_its_department():
    cs = pd.DataFrame({
        "ubigeo": ["a", "b", "c", "d", "e"],
        "department": ["X", "X", "X", "Y", "Y"],
        "mining": [True, True, False, True, False],
        "light_per_capita": [9.0, 8.0, 1.0, 0.5, 2.0],
        "poverty": [60.0, 10.0, 40.0, 70.0, 20.0],
    })
    # national q75 of light per capita = 8.0; department X median poverty = 40, Y = 45
    assert list(paradox_districts(cs, quantile=0.75)["ubigeo"]) == ["a"]


def test_mine_opening_compares_light_two_years_before_and_three_after_the_first_production():
    years = list(range(2013, 2021))
    panel = pd.DataFrame({
        "ubigeo": ["m"] * 8 + ["o"] * 8,
        "year": years * 2,
        "mining": [False, False, False, True, True, True, True, True] + [True] * 8,
        "light_sum": [10, 10, 10, 40, 60, 60, 60, 60] + [5] * 8,
    })
    openings = mine_openings(panel, first=2015, last=2018).set_index("ubigeo")
    assert list(openings.index) == ["m"]               # "o" produced from the start of the series
    row = openings.loc["m"]
    assert row["start"] == 2016
    assert row["light_before"] == 10                   # mean of 2014-2015
    assert row["light_after"] == 60                    # mean of 2017-2019
    assert row["ratio"] == pytest.approx(6)
