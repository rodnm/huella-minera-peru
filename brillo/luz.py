"""Night-light radiance per district from a NASA Black Marble VNP46A4 yearly raster (nW·cm⁻²·sr⁻¹ per pixel)."""
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import rioxarray  # noqa: F401  (registers the .rio accessor that exactextract reads)
import xarray as xr
from exactextract import exact_extract
from rasterio.features import geometry_mask


def _zonal_sum(values: np.ndarray, like: xr.DataArray, districts: gpd.GeoDataFrame) -> pd.Series:
    layer = like.copy(data=values)
    stats = exact_extract(layer, districts[["ubigeo", "geometry"]], ["sum"], include_cols=["ubigeo"],
                          output="pandas")
    return stats.set_index("ubigeo")["sum"]


def light_by_district(raster: Path, districts: gpd.GeoDataFrame, mines: gpd.GeoDataFrame) -> pd.DataFrame:
    """Sum of radiance per district, split into pixels touching a mine footprint and the rest.

    Missing pixels (fill, cloud) are gaps and add nothing; small negative values are sensor noise and become 0.
    A pixel touched by any mine polygon counts as mine light, so ``light_outside_mines`` is the light of the
    town and the rest of the district.
    """
    with rasterio.open(raster) as src:
        values = src.read(1, masked=True).filled(np.nan).astype("float64")
        transform, shape, crs = src.transform, (src.height, src.width), src.crs
    values = np.where(np.isnan(values), 0.0, np.clip(values, 0, None))
    like = xr.DataArray(values, dims=("y", "x")).rio.write_transform(transform).rio.write_crs(crs)
    like = like.assign_coords(x=transform.c + transform.a * (np.arange(shape[1]) + 0.5),
                              y=transform.f + transform.e * (np.arange(shape[0]) + 0.5))
    on_mine = geometry_mask(mines.to_crs(crs).geometry, out_shape=shape, transform=transform, invert=True,
                            all_touched=True) if len(mines) else np.zeros(shape, bool)
    total = _zonal_sum(values, like, districts.to_crs(crs))
    outside = _zonal_sum(np.where(on_mine, 0.0, values), like, districts.to_crs(crs))
    out = pd.DataFrame({"light_sum": total, "light_outside_mines": outside})
    out["light_inside_mines"] = out["light_sum"] - out["light_outside_mines"]
    return out.reset_index()
