import json
import struct

import numpy as np
import pandas as pd
import pytest
import rasterio
from rasterio.transform import from_origin

from brillo.atlas import MADRE_DE_DIOS, describe, footprint_pixels, panel_payload


def panel():
    rows = [
        ("170101", "MADRE DE DIOS", "TAMBOPATA", "INAMBARI", 2013, 1.0, 10.0, 40.0, 30.0, 50.0, 1000.0, 200.0),
        ("170101", "MADRE DE DIOS", "TAMBOPATA", "INAMBARI", 2025, 5.0, 20.0, 40.0, 30.0, 50.0, 1000.0, 200.0),
        ("170102", "MADRE DE DIOS", "TAMBOPATA", "LABERINTO", 2013, 0.0, 1.0, np.nan, np.nan, np.nan, 500.0, 100.0),
        ("170102", "MADRE DE DIOS", "TAMBOPATA", "LABERINTO", 2025, 1.0, 2.0, np.nan, np.nan, np.nan, 500.0, 100.0),
        ("010101", "AMAZONAS", "CHACHAPOYAS", "CHACHAPOYAS", 2013, 1.0, 3.0, 9.0, 6.0, 12.0, 2000.0, 150.0),
        ("010101", "AMAZONAS", "CHACHAPOYAS", "CHACHAPOYAS", 2025, 2.0, 4.0, 9.0, 6.0, 12.0, 2000.0, 150.0),
        ("010102", "AMAZONAS", "CHACHAPOYAS", "ASUNCION", 2013, 0.0, 0.0, 20.0, 10.0, 30.0, 300.0, 50.0),
        ("010102", "AMAZONAS", "CHACHAPOYAS", "ASUNCION", 2025, 0.005, 0.0, 20.0, 10.0, 30.0, 300.0, 50.0),
    ]
    return pd.DataFrame(rows, columns=["ubigeo", "department", "province", "district", "year", "mining_km2",
                                       "light_per_km2", "poverty", "poverty_low", "poverty_high", "population_2020",
                                       "area_km2"])


def test_describe_gives_the_national_change_and_where_it_happened():
    result = describe(panel(), top=2)

    assert result["first_year"] == 2013 and result["last_year"] == 2025
    assert result["national_km2"] == {"2013": 2.0, "2025": pytest.approx(8.005)}
    assert result["ratio"] == pytest.approx(4.0025)
    assert result["increase_km2"] == pytest.approx(6.005)
    assert result["madre_de_dios"]["share_of_increase"] == pytest.approx(5 / 6.005)
    assert result["madre_de_dios"]["share_of_last"] == pytest.approx(6 / 8.005)


def test_describe_ranks_the_largest_gains_and_measures_their_concentration():
    result = describe(panel(), top=2)

    assert [row["ubigeo"] for row in result["top_districts"]] == ["170101", "010101"]
    assert result["top_districts"][0]["gain_km2"] == pytest.approx(4)
    assert result["top_share_of_increase"] == pytest.approx(5 / 6.005)


def test_describe_counts_a_district_only_from_one_hectare():
    result = describe(panel(), top=2)

    assert result["districts_with_footprint"] == {"2013": 2, "2025": 3}


def test_panel_payload_keeps_years_in_order_and_writes_missing_values_as_null():
    shuffled = panel().sample(frac=1, random_state=1)

    payload = panel_payload(shuffled)
    text = json.dumps(payload, allow_nan=False)  # a NaN would break JSON.parse in the browser

    assert payload["years"] == [2013, 2025]
    laberinto = next(row for row in payload["districts"] if row["u"] == "170102")
    assert laberinto["n"] == "LABERINTO" and laberinto["d"] == "MADRE DE DIOS" and laberinto["p"] == "TAMBOPATA"
    assert laberinto["m"] == [0.0, 1.0] and laberinto["l"] == [1.0, 2.0]
    assert laberinto["pov"] is None
    assert "NaN" not in text
    inambari = next(row for row in payload["districts"] if row["u"] == "170101")
    assert inambari["pov"] == [40.0, 30.0, 50.0]


def test_panel_payload_rounding_keeps_districts_on_the_same_side_of_the_hectare_rule():
    table = panel()
    table.loc[(table["ubigeo"] == "010102") & (table["year"] == 2025), "mining_km2"] = 0.009994

    laberinto_like = next(row for row in panel_payload(table)["districts"] if row["u"] == "010102")

    assert laberinto_like["m"][1] < 0.01


def write(path, values, transform):
    with rasterio.open(path, "w", driver="GTiff", height=values.shape[0], width=values.shape[1], count=1,
                       dtype="float32", crs="EPSG:4326", transform=transform) as dst:
        dst.write(values.astype("float32"), 1)
    return path


def test_footprint_pixels_keep_pixels_seen_in_any_year_and_store_each_year(tmp_path):
    transform = from_origin(-70, -10, 0.5, 0.5)
    first = write(tmp_path / "a.tif", np.array([[0.0, 0.002], [0.5, 0.0]]), transform)
    second = write(tmp_path / "b.tif", np.array([[1.0, 0.002], [0.5, 0.0]]), transform)

    meta, blob = footprint_pixels({2013: first, 2025: second}, min_fraction=0.01)

    assert meta["count"] == 2
    assert meta["years"] == [2013, 2025]
    assert meta["transform"] == [-70.0, 0.5, -10.0, -0.5]
    count = meta["count"]
    rows = struct.unpack(f"<{count}H", blob[:2 * count])
    cols = struct.unpack(f"<{count}H", blob[2 * count:4 * count])
    assert sorted(zip(rows, cols)) == [(0, 0), (1, 0)]
    fractions = np.frombuffer(blob[4 * count:], dtype="uint8").reshape(count, 2)
    by_pixel = dict(zip(zip(rows, cols), map(tuple, fractions.tolist())))
    assert by_pixel[(0, 0)] == (0, 255)
    assert by_pixel[(1, 0)] == (128, 128)


def test_madre_de_dios_is_the_inei_department_code():
    assert MADRE_DE_DIOS == "17"
