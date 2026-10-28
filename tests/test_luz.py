import geopandas as gpd
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import box

from brillo.luz import light_by_district

# 4x4 grid of 0.01° pixels whose top-left corner is (-75, -9.96)
LEFT, TOP, PIXEL = -75.0, -9.96, 0.01


def pixel(row, col, inset=0.0):
    x0, y1 = LEFT + col * PIXEL, TOP - row * PIXEL
    return box(x0 + inset, y1 - PIXEL + inset, x0 + PIXEL - inset, y1 - inset)


@pytest.fixture
def raster(tmp_path):
    values = np.array([[1, 1, 2, 2],
                       [1, 1, 2, 2],
                       [1, np.nan, 2, 2],
                       [1, -0.5, 2, 2]], dtype="float32")
    path = tmp_path / "vnp46a4_2020.tif"
    with rasterio.open(path, "w", driver="GTiff", height=4, width=4, count=1, dtype="float32", crs="EPSG:4326",
                       transform=from_origin(LEFT, TOP, PIXEL, PIXEL), nodata=np.nan) as dst:
        dst.write(values, 1)
    return path


def test_light_sums_radiance_per_district_ignoring_gaps_and_negative_noise(raster):
    districts = gpd.GeoDataFrame({"ubigeo": ["000001", "000002"]},
                                 geometry=[box(LEFT, TOP - 4 * PIXEL, LEFT + 2 * PIXEL, TOP),
                                           box(LEFT + 2 * PIXEL, TOP - 4 * PIXEL, LEFT + 4 * PIXEL, TOP)],
                                 crs="EPSG:4326")
    mines = gpd.GeoDataFrame(geometry=[pixel(0, 3, inset=0.002)], crs="EPSG:4326")
    light = light_by_district(raster, districts, mines).set_index("ubigeo")
    assert light.loc["000001", "light_sum"] == pytest.approx(6)        # NaN is a gap, -0.5 is noise -> 0
    assert light.loc["000002", "light_sum"] == pytest.approx(16)
    assert light.loc["000002", "light_inside_mines"] == pytest.approx(2)
    assert light.loc["000002", "light_outside_mines"] == pytest.approx(14)
    assert light.loc["000001", "light_inside_mines"] == pytest.approx(0)
