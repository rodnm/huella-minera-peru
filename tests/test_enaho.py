import zipfile

import numpy as np
import pandas as pd
import pytest

from brillo.enaho import design_effects, direct_estimates, read_sumaria, sampling_variance, weighted_poverty


def write_zip(path, name, text, encoding="latin-1"):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(name, text.encode(encoding))
    return path


CSV = ('AÑO,UBIGEO,CONGLOME,ESTRATO,POBREZA,FACTOR07,MIEPERHO,GASHOG2D,LINEA\n'
       '2024,10101,1,1,1,10,2,100,500\n'
       '2024,010101,1,1,3,10,4,99999,500\n'
       '2024,150101,2,2,2,5,2,100,500\n'
       '2024,150101,2,2,3,,2,100,500\n')


def test_read_sumaria_picks_the_annual_file_and_builds_person_weights(tmp_path):
    path = tmp_path / "966-Modulo34.zip"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("966-Modulo34/ENAHO-TABLA-AGROPECUARIO.csv", "GRUPO,PRODUCTO\n1,x\n")
        z.writestr("966-Modulo34/Sumaria-2024-12g.csv", "wrong,file\n1,2\n")
        z.writestr("966-Modulo34/Sumaria-2024.csv", CSV.encode("latin-1"))
    df = read_sumaria(path, 2024)
    assert list(df["ubigeo"]) == ["010101", "010101", "150101"]       # padded; the row without a weight is dropped
    assert list(df["poor"]) == [True, False, True]                    # POBREZA 1 and 2 are poor
    assert list(df["weight"]) == [20, 40, 10]                         # FACTOR07 x MIEPERHO
    assert (df["year"] == 2024).all()


def test_read_sumaria_detects_a_semicolon_separator(tmp_path):
    path = write_zip(tmp_path / "x.zip", "SUMARIA-2013.csv", CSV.replace(",", ";"))
    assert len(read_sumaria(path, 2013)) == 3


def test_weighted_poverty_counts_people_not_households():
    df = pd.DataFrame({"poor": [True, False], "weight": [10.0, 30.0], "department": ["01", "01"]})
    assert weighted_poverty(df) == pytest.approx(0.25)
    assert weighted_poverty(df, by="department")["01"] == pytest.approx(0.25)


def test_direct_estimates_report_rate_households_and_effective_size():
    df = pd.DataFrame({"ubigeo": ["a", "a", "b"], "poor": [True, False, True], "weight": [1.0, 3.0, 2.0]})
    out = direct_estimates(df).set_index("ubigeo")
    assert out.loc["a", "rate"] == pytest.approx(0.25)
    assert out.loc["a", "households"] == 2
    assert out.loc["a", "n_eff"] == pytest.approx(16 / 10)            # (Σw)² / Σw²
    assert out.loc["b", "rate"] == 1


def test_design_effect_grows_when_households_in_a_cluster_are_alike():
    # 20 clusters of 10 households: half the clusters entirely poor, half entirely not
    clustered = pd.DataFrame({"department": "01", "estrato": 1, "conglome": np.repeat(range(20), 10),
                              "poor": np.repeat([True, False] * 10, 10), "weight": 1.0})
    assert 8 < design_effects(clustered)["01"] < 12
    # every cluster mixed half and half: no between-cluster variance, the effect is floored at 1
    mixed = clustered.assign(poor=np.tile([True, False], 100))
    assert design_effects(mixed)["01"] == 1


def test_sampling_variance_on_the_arcsine_scale():
    assert sampling_variance(n_eff=10, deff=2) == pytest.approx(2 / 40)
