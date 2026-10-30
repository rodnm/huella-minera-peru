import numpy as np
import pandas as pd
import pytest

from brillo.analisis import mine_openings, mining_groups, paradox_districts, poverty_change_effects


def test_paradox_is_confirmed_only_when_the_whole_poverty_interval_is_above_the_department_median():
    cs = pd.DataFrame({
        "ubigeo": ["a", "b", "c", "d", "e", "f"],
        "department": ["X", "X", "X", "X", "Y", "Y"],
        "mining": [True, True, True, False, True, False],
        "light_per_capita": [9.0, 9.5, 8.0, 1.0, 0.5, 2.0],
        "poverty": [60.0, 50.0, 10.0, 40.0, 70.0, 20.0],
        "poverty_low": [55.0, 35.0, 5.0, 30.0, 60.0, 10.0],
    })
    # national q75 of light per capita = 8.75; department X median poverty = 45, Y = 45
    paradox = paradox_districts(cs, quantile=0.75).set_index("ubigeo")
    assert list(paradox.index) == ["a", "b"]           # "c" is less poor, "e" is not bright, "d" and "f" have no mine
    assert bool(paradox.loc["a", "confirmed"]) is True    # 55 > 45: poorer even at the low end
    assert bool(paradox.loc["b", "confirmed"]) is False   # 35 < 45 < 50: only the midpoint is above


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


def test_mining_groups_separate_established_opened_and_later_mines():
    panel = pd.DataFrame({
        "ubigeo": ["old"] * 3 + ["new"] * 3 + ["late"] * 3 + ["none"] * 3,
        "year": [2013, 2016, 2021] * 4,
        "mining": [True, True, True, False, True, True, False, False, True, False, False, False],
    })
    groups = mining_groups(panel, before=2014, after=2018)
    assert groups.to_dict() == {"late": "abre_despues", "new": "abre_entre_mapas", "none": "sin_mina", "old": "establecida"}


def test_poverty_change_recovers_a_planted_effect_against_districts_without_mine():
    rng = np.random.default_rng(3)
    n = 400
    d = pd.DataFrame({"group": np.repeat(["sin_mina", "abre_entre_mapas"], [300, 100]),
                      "department": rng.choice(["A", "B", "C"], n), "province": rng.choice(list("abcdefghij"), n),
                      "start": rng.uniform(10, 80, n), "log_pop": rng.normal(8, 1, n), "log_area": rng.normal(5, 1, n),
                      "region": rng.choice(["COSTA", "SIERRA"], n)})
    d["change"] = -0.2 * d["start"] + np.where(d["group"] == "abre_entre_mapas", -5.0, 0.0) + rng.normal(0, 2, n)
    effects = poverty_change_effects(d)
    assert effects["abre_entre_mapas"]["coef"] == pytest.approx(-5, abs=1)
    assert effects["abre_entre_mapas"]["low"] < effects["abre_entre_mapas"]["coef"] < effects["abre_entre_mapas"]["high"]
    assert effects["abre_entre_mapas"]["n"] == 100
