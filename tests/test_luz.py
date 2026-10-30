import geopandas as gpd
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import box

from brillo.luz import light_by_district

# 4x4 grid of 0.01° pixels whose top-left corner is (-75, -9.96)
LEFT, TOP, PIXEL = -75.0, -9.96, 0.01


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


def test_light_sums_radiance_per_district_and_splits_pixels_with_any_mining(raster):
    districts = gpd.GeoDataFrame({"ubigeo": ["000001", "000002"]},
                                 geometry=[box(LEFT, TOP - 4 * PIXEL, LEFT + 2 * PIXEL, TOP),
                                           box(LEFT + 2 * PIXEL, TOP - 4 * PIXEL, LEFT + 4 * PIXEL, TOP)],
                                 crs="EPSG:4326")
    mine_fraction = np.zeros((4, 4), dtype="float32")
    mine_fraction[0, 3] = 0.4   # MapBiomas says 40 % of this light pixel is mining that year
    light = light_by_district(raster, districts, mine_fraction).set_index("ubigeo")
    assert light.loc["000001", "light_sum"] == pytest.approx(6)        # NaN is a gap, -0.5 is noise -> 0
    assert light.loc["000002", "light_sum"] == pytest.approx(16)
    assert light.loc["000002", "light_inside_mines"] == pytest.approx(2)
    assert light.loc["000002", "light_outside_mines"] == pytest.approx(14)
    assert light.loc["000001", "light_inside_mines"] == pytest.approx(0)


def test_yearly_raster_is_written_in_wgs84_with_nan_as_nodata(tmp_path):
    import xarray as xr

    from brillo.luz import write_yearly_raster

    grid = xr.DataArray(np.array([[1.0, np.nan], [0.5, 2.0]], dtype="float32"), dims=("y", "x"),
                        coords={"y": [-9.995, -10.005], "x": [-75.005, -74.995]})
    path = write_yearly_raster(grid, tmp_path / "vnp46a4_2020.tif")
    with rasterio.open(path) as src:
        assert src.crs.to_epsg() == 4326
        assert np.isnan(src.nodata)
        assert src.read(1, masked=True).count() == 3
