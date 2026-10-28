"""Download NASA Black Marble VNP46A4 (annual night lights, Collection 2) for Peru and save one GeoTIFF per year.

Run from the repository root: uv run python -m scripts.obtener_luz
Needs a free NASA Earthdata token (see brillo/credenciales.py). The HDF5 tiles are cached in
datos/originales/blackmarble/ and pinned in the manifest; the yearly rasters go to datos/intermedios/luz/.
"""
import datetime
import os
from pathlib import Path

import geopandas as gpd
from blackmarble import BlackMarble, Product

from brillo.credenciales import load_token
from brillo.descarga import record

ROOT = Path(__file__).resolve().parent.parent
ORIGINALES = ROOT / "datos" / "originales"
TILES = ORIGINALES / "blackmarble"
YEARLY = ROOT / "datos" / "intermedios" / "luz"
DISTRICTS = ORIGINALES / "limites" / "distritos_geocatmin.geojson"
YEARS = range(2013, 2026)  # 2012 starts in April, so the first full year is 2013
PAGE = "https://doi.org/10.5067/VIIRS/VNP46A4.002"
LICENSE = "NASA Earth Science data: open, no restrictions on use (cite the DOI)"


def main() -> None:
    token = load_token(os.environ, ROOT / ".env")
    peru = gpd.read_file(DISTRICTS)[["geometry"]].dissolve()
    bm = BlackMarble(token=token, output_directory=TILES, drop_values_by_quality_flag=[255])
    # One raster() call for every year: a second call in the same session fails (blackmarblepy issue #158)
    stack = bm.raster(peru, Product.VNP46A4, [datetime.date(year, 1, 1) for year in YEARS])
    variable = list(stack.data_vars)[0]
    YEARLY.mkdir(parents=True, exist_ok=True)
    for when in stack["time"].values:
        year = str(when)[:4]
        stack[variable].sel(time=when).rio.to_raster(YEARLY / f"vnp46a4_{year}.tif", compress="deflate")
        print(f"vnp46a4_{year}.tif")
    for tile in sorted(TILES.glob("*.h5")):
        record(ORIGINALES / "MANIFEST.json", f"blackmarble_{tile.stem}", PAGE, tile, PAGE, LICENSE)
    print(f"{len(list(TILES.glob('*.h5')))} tiles pinned in the manifest")


if __name__ == "__main__":
    main()
