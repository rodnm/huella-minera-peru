"""Physical footprint of mining (Maus et al. 2022, v2): polygons digitised over 2019 Sentinel-2 imagery."""
from pathlib import Path

import geopandas as gpd
import pandas as pd

from brillo.distritos import EQUAL_AREA


def peru_mines(gpkg: Path) -> gpd.GeoDataFrame:
    """Mining polygons in Peru, read with a filter so the global file never loads whole."""
    return gpd.read_file(gpkg, where="ISO3_CODE = 'PER'").to_crs("EPSG:4326")


def footprint_by_district(mines: gpd.GeoDataFrame, districts: gpd.GeoDataFrame) -> pd.DataFrame:
    """Mining area (km²) inside each district; a mine on a border is split between its districts."""
    pieces = gpd.overlay(districts[["ubigeo", "geometry"]].to_crs(EQUAL_AREA),
                         mines[["geometry"]].to_crs(EQUAL_AREA), how="intersection", keep_geom_type=True)
    area = (pieces.area / 1e6).groupby(pieces["ubigeo"]).sum()
    out = districts[["ubigeo"]].copy()
    out["footprint_km2"] = out["ubigeo"].map(area).fillna(0.0)
    return out.reset_index(drop=True)
