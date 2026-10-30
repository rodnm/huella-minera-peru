"""Yearly mining footprint from MapBiomas Perú Collection 4 (class 30 "Minería", 30 m Landsat pixels).

MapBiomas publishes area per class only by department, so the district figures are computed here: the 30 m mining
mask is averaged onto the 500 m Black Marble grid (the share of each light pixel that is mining), and that share
times the pixel's geodesic area is summed per district.
"""
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import geometry_mask
from rasterio.transform import Affine
from rasterio.warp import Resampling, reproject
from rasterio.windows import Window, from_bounds

from brillo.luz import zonal_sum

MINING = 30
EARTH_RADIUS_KM = 6371.0072  # authalic radius: a sphere with the same surface as the WGS84 ellipsoid


def pixel_area_km2(transform: Affine, shape: tuple[int, int]) -> np.ndarray:
    """Area of every pixel of a north-up longitude/latitude grid (km²): R²·Δλ·|sin φ₁ − sin φ₂|."""
    top = transform.f + transform.e * np.arange(shape[0])
    bottom = top + transform.e
    band = EARTH_RADIUS_KM ** 2 * np.radians(abs(transform.a)) * np.abs(np.sin(np.radians(top))
                                                                       - np.sin(np.radians(bottom)))
    return np.repeat(band[:, None], shape[1], axis=1)


def mining_fraction(coverage: Path, like: Path, out: Path, code: int = MINING, strip: int = 128) -> Path:
    """Write the share of each pixel of the ``like`` grid covered by ``code`` in the 30 m ``coverage`` raster.

    The national raster has about 3,200 million pixels, so it is read in strips that match ``strip`` rows of the
    coarse grid, and each strip's 0/1 mask is averaged onto the coarse grid.
    """
    with rasterio.open(like) as ref:
        grid, (rows, cols), crs = ref.transform, (ref.height, ref.width), ref.crs
    fraction = np.zeros((rows, cols), dtype="float32")
    with rasterio.open(coverage) as src:
        for r0 in range(0, rows, strip):
            n = min(strip, rows - r0)
            strip_grid = Affine(grid.a, grid.b, grid.c, grid.d, grid.e, grid.f + grid.e * r0)
            left, top = strip_grid.c, strip_grid.f
            right, bottom = left + strip_grid.a * cols, top + strip_grid.e * n
            window = (from_bounds(left, bottom, right, top, src.transform)
                      .round_offsets(op="floor").round_lengths(op="ceil"))
            window = Window(window.col_off - 1, window.row_off - 1, window.width + 2, window.height + 2)
            mask = (src.read(1, window=window, boundless=True, fill_value=0) == code).astype("float32")
            reproject(mask, fraction[r0:r0 + n], src_transform=src.window_transform(window), src_crs=src.crs,
                      dst_transform=strip_grid, dst_crs=crs, resampling=Resampling.average)
    out.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(out, "w", driver="GTiff", height=rows, width=cols, count=1, dtype="float32", crs=crs,
                       transform=grid, compress="deflate") as dst:
        dst.write(fraction, 1)
    return out


def mining_km2_by_district(fraction_path: Path, districts: gpd.GeoDataFrame) -> pd.DataFrame:
    """Mining area per district (km²): share of each pixel that is mining times the pixel's area."""
    with rasterio.open(fraction_path) as src:
        fraction, transform, crs = src.read(1).astype("float64"), src.transform, src.crs
    km2 = zonal_sum(fraction * pixel_area_km2(transform, fraction.shape), transform, crs, districts)
    out = districts[["ubigeo"]].copy()
    out["mining_km2"] = out["ubigeo"].map(km2).fillna(0.0)
    return out.reset_index(drop=True)


def read_official_mining(xlsx: Path) -> pd.DataFrame:
    """MapBiomas' own mining area per department and year (km²), to check the district sums against.

    Sheet COVERAGE_4 has one row per biome × department × class, in hectares; ``geocode_2`` is the INEI department.
    """
    table = pd.read_excel(xlsx, sheet_name="COVERAGE_4")
    mining = table[table["class"] == MINING]
    years = [c for c in table.columns if str(c).startswith("y") and str(c)[1:].isdigit()]
    long = mining.melt(id_vars="geocode_2", value_vars=years, var_name="year", value_name="hectares")
    long["department"] = long["geocode_2"].astype(int).astype(str).str.zfill(2)
    long["year"] = long["year"].str[1:].astype(int)
    out = long.groupby(["department", "year"], as_index=False)["hectares"].sum()
    out["official_km2"] = out.pop("hectares") / 100
    return out


def official_gap(ours: pd.DataFrame, official: pd.DataFrame) -> pd.DataFrame:
    """Our district figures summed per department against the official table: ``gap`` = ours / official − 1."""
    summed = ours.assign(department=ours["ubigeo"].str[:2]).groupby(["department", "year"], as_index=False)[
        "mining_km2"].sum()
    out = summed.merge(official, on=["department", "year"])
    out["gap"] = out["mining_km2"] / out["official_km2"] - 1
    return out


def maus_agreement(mines: gpd.GeoDataFrame, fraction_path: Path) -> float:
    """Share of MapBiomas' mining area that falls on pixels touched by a Maus et al. polygon."""
    with rasterio.open(fraction_path) as src:
        fraction, transform, crs = src.read(1).astype("float64"), src.transform, src.crs
    on_maus = geometry_mask(mines.to_crs(crs).geometry, out_shape=fraction.shape, transform=transform, invert=True,
                            all_touched=True)
    area = fraction * pixel_area_km2(transform, fraction.shape)
    return float(area[on_maus].sum() / area.sum())
