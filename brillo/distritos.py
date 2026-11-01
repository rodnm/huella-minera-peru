"""District polygons with their UBIGEO, as every other step expects them."""
from pathlib import Path

import geopandas as gpd

EQUAL_AREA = "ESRI:102033"  # South America Albers Equal Area Conic: areas in km² without EPSG:4326 distortion


def load_districts(path: Path) -> gpd.GeoDataFrame:
    """GEOCATMIN districts renamed to ubigeo, department, province, district, plus their area in km²."""
    raw = gpd.read_file(path)
    districts = raw.rename(columns={"CD_DIST": "ubigeo", "NM_DEPA": "department", "NM_PROV": "province",
                                    "NM_DIST": "district"})[["ubigeo", "department", "province", "district",
                                                             "geometry"]]
    districts["area_km2"] = districts.geometry.to_crs(EQUAL_AREA).area / 1e6
    return districts.sort_values("ubigeo").reset_index(drop=True)
