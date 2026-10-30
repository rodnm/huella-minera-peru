"""Night-light radiance per district from a NASA Black Marble VNP46A4 yearly raster (nW·cm⁻²·sr⁻¹ per pixel)."""
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import rioxarray  # noqa: F401  (registers the .rio accessor that exactextract reads)
import xarray as xr
from exactextract import exact_extract
from rasterio.transform import Affine


def zonal_sum(values: np.ndarray, transform: Affine, crs, districts: gpd.GeoDataFrame) -> pd.Series:
    """Sum of a grid inside each district, with partial weights for pixels cut by the border (exactextract)."""
    rows, cols = values.shape
    layer = (xr.DataArray(values, dims=("y", "x"),
                          coords={"x": transform.c + transform.a * (np.arange(cols) + 0.5),
                                  "y": transform.f + transform.e * (np.arange(rows) + 0.5)})
             .rio.write_transform(transform).rio.write_crs(crs))
    stats = exact_extract(layer, districts[["ubigeo", "geometry"]].to_crs(crs), ["sum"], include_cols=["ubigeo"],
                          output="pandas")
    return stats.set_index("ubigeo")["sum"]


def light_by_district(raster: Path, districts: gpd.GeoDataFrame, mine_fraction: np.ndarray | None) -> pd.DataFrame:
    """Sum of radiance per district, split into pixels with any mining that year and the rest.

    ``mine_fraction`` is the share of each light pixel that MapBiomas classifies as mining (same grid as
    ``raster``). Missing pixels (fill, cloud) are gaps and add nothing; small negative values are sensor noise and
    become 0. ``light_outside_mines`` is the light of the town and the rest of the district.
    """
    with rasterio.open(raster) as src:
        values = src.read(1, masked=True).filled(np.nan).astype("float64")
        transform, crs = src.transform, src.crs
    values = np.where(np.isnan(values), 0.0, np.clip(values, 0, None))
    on_mine = np.zeros(values.shape, bool) if mine_fraction is None else mine_fraction > 0
    out = pd.DataFrame({"light_sum": zonal_sum(values, transform, crs, districts),
                        "light_outside_mines": zonal_sum(np.where(on_mine, 0.0, values), transform, crs, districts)})
    out["light_inside_mines"] = out["light_sum"] - out["light_outside_mines"]
    return out.reset_index()


def write_yearly_raster(grid: xr.DataArray, path: Path) -> Path:
    """Save one year of radiance as a GeoTIFF in WGS84 with NaN as nodata.

    blackmarblepy returns lon/lat grids without a CRS, so the file would otherwise be unreferenced.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    grid.rio.write_crs("EPSG:4326").rio.write_nodata(np.nan).rio.to_raster(path, compress="deflate")
    return path
