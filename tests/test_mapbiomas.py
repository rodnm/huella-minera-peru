import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import box

from brillo.mapbiomas import (maus_agreement, mining_fraction, mining_km2_by_district, official_gap, overlap_share,
                             pixel_area_km2, read_official_mining, scar_fractions)


def write(path, values, transform, dtype):
    with rasterio.open(path, "w", driver="GTiff", height=values.shape[0], width=values.shape[1], count=1,
                       dtype=dtype, crs="EPSG:4326", transform=transform) as dst:
        dst.write(values.astype(dtype), 1)
    return path


def test_pixel_area_of_one_degree_at_the_equator():
    area = pixel_area_km2(from_origin(0, 1, 1, 1), (1, 1))
    assert area[0, 0] == pytest.approx(12_363.6, rel=1e-3)


def test_mining_fraction_averages_class_30_onto_the_coarse_light_grid_strip_by_strip(tmp_path):
    fine = np.full((30, 30), 22, dtype="uint8")       # 0.001° pixels, 3 x 3 per coarse pixel
    fine[0:3, 0:3] = 30                               # a whole coarse pixel is mining
    fine[4, 4] = 30                                   # one ninth of another one
    fine_path = write(tmp_path / "coverage.tif", fine, from_origin(-75, -10, 0.001, 0.001), "uint8")
    like_path = write(tmp_path / "light.tif", np.zeros((10, 10)), from_origin(-75, -10, 0.003, 0.003), "float32")
    out = mining_fraction(fine_path, like_path, tmp_path / "frac.tif", strip=4)
    with rasterio.open(out) as src:
        frac = src.read(1)
        assert src.transform == from_origin(-75, -10, 0.003, 0.003)
    assert frac[0, 0] == pytest.approx(1)
    assert frac[1, 1] == pytest.approx(1 / 9)
    assert frac.sum() == pytest.approx(1 + 1 / 9)


def test_mining_km2_sums_fraction_times_pixel_area_per_district(tmp_path):
    frac = np.zeros((4, 4), dtype="float32")
    frac[0, 3] = 0.5
    transform = from_origin(-75, -9.96, 0.01, 0.01)
    path = write(tmp_path / "frac.tif", frac, transform, "float32")
    districts = gpd.GeoDataFrame({"ubigeo": ["000001", "000002"]},
                                 geometry=[box(-75, -10, -74.98, -9.96), box(-74.98, -10, -74.96, -9.96)],
                                 crs="EPSG:4326")
    km2 = mining_km2_by_district(path, districts).set_index("ubigeo")["mining_km2"]
    assert km2["000001"] == 0
    assert km2["000002"] == pytest.approx(0.5 * pixel_area_km2(transform, (4, 4))[0, 3])


def test_official_table_sums_biomes_per_department_and_converts_hectares_to_km2(tmp_path):
    table = pd.DataFrame({"class": [30, 30, 3, 30], "geocode_2": [15, 15, 15, 8],
                          "y2013": [100.0, 50.0, 999.0, 200.0], "y2014": [300.0, 0.0, 999.0, 400.0]})
    path = tmp_path / "stats.xlsx"
    table.to_excel(path, sheet_name="COVERAGE_4", index=False)
    official = read_official_mining(path).set_index(["department", "year"])["official_km2"]
    assert official["15", 2013] == pytest.approx(1.5)      # two biomes of Lima, class 3 ignored
    assert official["15", 2014] == pytest.approx(3.0)
    assert official["08", 2013] == pytest.approx(2.0)


def test_official_gap_compares_our_district_sums_with_the_official_department_table():
    ours = pd.DataFrame({"ubigeo": ["150101", "150102", "080101"], "year": [2018] * 3, "mining_km2": [1.0, 1.0, 5.5]})
    official = pd.DataFrame({"department": ["15", "08"], "year": [2018, 2018], "official_km2": [2.0, 5.0]})
    gap = official_gap(ours, official).set_index("department")
    assert gap.loc["15", "gap"] == pytest.approx(0)
    assert gap.loc["08", "gap"] == pytest.approx(0.1)


def test_maus_agreement_reports_the_share_of_mapbiomas_mining_on_maus_pixels(tmp_path):
    frac = np.zeros((4, 4), dtype="float32")
    frac[0, 0] = frac[3, 3] = 0.5                     # same pixel area in both rows only approximately
    transform = from_origin(-75, -9.96, 0.01, 0.01)
    path = write(tmp_path / "frac.tif", frac, transform, "float32")
    mines = gpd.GeoDataFrame(geometry=[box(-74.998, -9.968, -74.992, -9.962)], crs="EPSG:4326")   # inside pixel (0, 0)
    assert maus_agreement(mines, path) == pytest.approx(0.5, abs=0.01)


def test_scar_fractions_accumulate_annual_onsets_and_leave_out_quarterly_codes(tmp_path):
    like = write(tmp_path / "like.tif", np.zeros((2, 2)), from_origin(0, 2, 1, 1), "float32")
    onset = np.zeros((4, 4))
    onset[0, 0] = 2018  # coarse pixel (0, 0)
    onset[0, 1] = 2020  # coarse pixel (0, 0)
    onset[3, 3] = 20251  # quarterly and provisional: not an annual onset
    onset[2, 2] = 2020  # coarse pixel (1, 1)
    mask = write(tmp_path / "mask.tif", onset, from_origin(0, 2, 0.5, 0.5), "uint16")

    paths = scar_fractions(mask, like, tmp_path / "amw", years=[2018, 2020])

    with rasterio.open(paths[2018]) as src:
        first = src.read(1)
    with rasterio.open(paths[2020]) as src:
        second = src.read(1)
    assert first.tolist() == [[0.25, 0], [0, 0]]
    assert second.tolist() == [[0.5, 0], [0, 0.25]]


def test_scar_fractions_ignore_pixels_outside_the_grid(tmp_path):
    like = write(tmp_path / "like.tif", np.zeros((1, 1)), from_origin(0, 1, 1, 1), "float32")
    mask = write(tmp_path / "mask.tif", np.full((2, 4), 2018), from_origin(-1, 1, 0.5, 0.5), "uint16")

    paths = scar_fractions(mask, like, tmp_path / "amw", years=[2018])

    with rasterio.open(paths[2018]) as src:
        assert src.read(1).tolist() == [[1.0]]


def test_overlap_share_weights_by_area_and_counts_any_touched_pixel(tmp_path):
    transform = from_origin(0, 2, 1, 1)
    a = write(tmp_path / "a.tif", np.array([[0.6, 0.0], [0.2, 0.2]]), transform, "float32")
    b = write(tmp_path / "b.tif", np.array([[0.1, 0.9], [0.0, 0.3]]), transform, "float32")
    assert overlap_share(a, b) == pytest.approx(0.8, rel=1e-2)


def test_overlap_share_can_be_limited_to_a_region(tmp_path):
    transform = from_origin(0, 1, 1, 1)
    a = write(tmp_path / "a.tif", np.array([[0.5, 0.5]]), transform, "float32")
    b = write(tmp_path / "b.tif", np.array([[0.1, 0.0]]), transform, "float32")
    assert overlap_share(a, b, within=box(1, 0, 2, 1)) == 0
