import geopandas as gpd
import pytest
from shapely.geometry import box

from brillo.huella import footprint_by_district


def test_a_mine_straddling_two_districts_splits_its_area_between_them():
    districts = gpd.GeoDataFrame({"ubigeo": ["000001", "000002", "000003"]},
                                 geometry=[box(-75, -10, -74.9, -9.9), box(-74.9, -10, -74.8, -9.9),
                                           box(-74.8, -10, -74.7, -9.9)], crs="EPSG:4326")
    mines = gpd.GeoDataFrame(geometry=[box(-74.95, -10, -74.85, -9.95)], crs="EPSG:4326")
    area = footprint_by_district(mines, districts).set_index("ubigeo")["footprint_km2"]
    assert area["000001"] == pytest.approx(area["000002"], rel=0.01)
    assert area["000003"] == 0
    total = mines.to_crs("ESRI:102033").area.iloc[0] / 1e6
    assert area.sum() == pytest.approx(total, rel=0.001)
