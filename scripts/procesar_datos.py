"""Clean and join the primary sources into the tables the analysis and the dashboard read.

Run from the repository root, after scripts.obtener_datos: uv run python -m scripts.procesar_datos
Every filter is recorded in datos/procesados/bitacora_limpieza.json with the rows it keeps.
"""
import glob
import warnings
import zipfile
from pathlib import Path

import pandas as pd
import py7zr

from brillo.bitacora import Bitacora
from brillo.distritos import load_districts
from brillo.huella import footprint_by_district, peru_mines
from brillo.luz import light_by_district
from brillo.minem import (DOUBLE_COUNTED_STAGES, assign_ubigeo, coordinate_agreement, district_panel,
                          read_production, read_units, scale_mining)
from brillo.pobreza import read_poverty

ROOT = Path(__file__).resolve().parent.parent
ORIGINALES = ROOT / "datos" / "originales"
INTERMEDIOS = ROOT / "datos" / "intermedios"
PROCESADOS = ROOT / "datos" / "procesados"
REFERENCIAS = ROOT / "datos" / "referencias"
YEARS = range(2013, 2026)
# Official national copper output (MINEM, TMF), used to check that no stage is counted twice
COPPER_CHECK = {2013: 1_375_641, 2019: 2_455_440}

warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")


def extract_minem() -> Path:
    """Unpack the MINEM archives (zip and 7z, with zips nested inside the 2001-2020 file)."""
    out = INTERMEDIOS / "minem" / "produccion"
    for archive in sorted((ORIGINALES / "minem" / "produccion").iterdir()):
        target = out / archive.stem
        if target.exists():
            continue
        target.mkdir(parents=True)
        if archive.suffix == ".zip":
            with zipfile.ZipFile(archive) as z:
                z.extractall(target)
        else:
            with py7zr.SevenZipFile(archive) as z:
                z.extractall(target)
        for nested in target.rglob("*.zip"):
            with zipfile.ZipFile(nested) as z:
                z.extractall(nested.with_suffix(""))
    return out


def production_files(base: Path) -> list[tuple[int, Path]]:
    """2013-2019: one file per metal. 2020 onwards: one metallic-production file per year."""
    skip = ("METALES", "NO-MET", "CARBON", "CONCENT", "OTROS")
    files = []
    for year in YEARS:
        if year <= 2019:
            files += [(year, Path(f)) for f in sorted(glob.glob(str(base / "5472883-2001-2020" / str(year) / "*.xls*")))
                      if not any(k in Path(f).name.upper() for k in skip)]
        else:
            folder = base / ("5472883-2001-2020/2020" if year == 2020 else f"5472883-{year}")
            metallic = [f for f in folder.glob("Producci*") if "met" in f.name.lower() or "minera" in f.name.lower()]
            files.append((year, metallic[0]))
    return files


def process_minem(log: Bitacora, districts) -> pd.DataFrame:
    files = production_files(extract_minem())
    raw = pd.concat([read_production(path, year) for year, path in files], ignore_index=True)
    log.add("minem", f"filas de producción leídas de {len(files)} archivos ({YEARS.start}-{YEARS.stop - 1})",
            len(raw), len(raw), "dos formatos: un archivo por metal hasta 2019, uno consolidado desde 2020")
    for year, expected in COPPER_CHECK.items():
        copper = raw[(raw.year == year) & (raw.metal == "COBRE") & ~raw.stage.isin(DOUBLE_COUNTED_STAGES)]
        assert abs(copper.tonnes.sum() - expected) < 1_000, f"copper {year}: {copper.tonnes.sum():,.0f} t"
    scale = scale_mining(raw, log)
    manual = pd.read_csv(REFERENCIAS / "crosswalk_manual.csv", dtype=str)
    matched = assign_ubigeo(scale, districts, manual)
    unmatched = matched[matched.match.eq("unmatched")]
    unmatched.to_csv(PROCESADOS / "minem_sin_ubigeo.csv", index=False)
    log.add("minem", "con UBIGEO por nombre o por el crosswalk manual", len(matched), len(matched) - len(unmatched),
            f"{(matched.match == 'manual').sum()} filas por crosswalk manual")
    units = matched[matched.match.ne("unmatched")]
    assert len(units) / len(matched) >= 0.98, "less than 98 % of rows found their UBIGEO"
    units.to_csv(PROCESADOS / "produccion_unidad_anio.csv", index=False)
    panel = district_panel(units)
    panel.to_csv(PROCESADOS / "produccion_distrito_anio.csv", index=False)
    log.add("minem", "panel distrito × año", len(units), len(panel),
            f"{panel.ubigeo.nunique()} distritos con minería en algún año")
    return panel


def validate_coordinates(log: Bitacora, districts) -> None:
    """Check the name→UBIGEO match against the coordinates MINEM publishes for its main units."""
    files = sorted((ORIGINALES / "minem" / "unidades").glob("principales_unidades_*.xlsx"))
    units = pd.concat([read_units(f, int(f.stem[-4:])) for f in files], ignore_index=True)
    manual = pd.read_csv(REFERENCIAS / "crosswalk_manual.csv", dtype=str)
    rate, table = coordinate_agreement(units, districts, manual)
    table.drop(columns="geometry", errors="ignore").to_csv(PROCESADOS / "validacion_coordenadas.csv", index=False)
    judged = table[table.agrees.notna()]
    near = (judged.distance_km <= 5).mean()
    far = judged[judged.distance_km > 25]
    log.add("minem", "validación: punto de la unidad dentro del distrito nombrado", len(table), len(judged),
            f"coincide exacto {rate:.1%}; a 5 km o menos {near:.1%} (minas en el borde entre distritos); "
            f"{len(far)} puntos a más de 25 km son coordenadas erróneas de MINEM")


def process_districts(log: Bitacora, districts) -> pd.DataFrame:
    """One row per district: area, INEI 2018 poverty and population, and the mining footprint inside it."""
    poverty = read_poverty(ORIGINALES / "inei" / "mapa_pobreza_2018_anexo_estadistico.xlsx")
    log.add("pobreza", "distritos del Mapa de Pobreza 2018 (INEI)", len(poverty), poverty.ubigeo.nunique(),
            "sin filas en blanco de salto de página ni notas al pie; pobreza = punto medio del IC 95 %")
    table = districts.drop(columns="geometry").merge(
        poverty[["ubigeo", "population_2020", "poverty", "poverty_low", "poverty_high"]], on="ubigeo", how="left")
    missing = table[table.poverty.isna()]
    log.add("pobreza", "distritos de GEOCATMIN con pobreza 2018", len(table), len(table) - len(missing),
            f"{len(missing)} distritos creados después del censo 2017 quedan sin pobreza: "
            + ", ".join(missing.district.str.title().head(8)) + ("…" if len(missing) > 8 else ""))
    mines = peru_mines(ORIGINALES / "maus" / "global_mining_polygons_v2.gpkg")
    footprint = footprint_by_district(mines, districts)
    table = table.merge(footprint, on="ubigeo")
    log.add("huella", "polígonos mineros de Maus v2 en el Perú → área por distrito", len(mines),
            int((table.footprint_km2 > 0).sum()),
            f"{table.footprint_km2.sum():,.0f} km² en total; una mina en el borde se reparte entre distritos")
    table.to_csv(PROCESADOS / "distritos.csv", index=False)
    return table


def process_light(log: Bitacora, districts, table: pd.DataFrame, production: pd.DataFrame) -> pd.DataFrame | None:
    """District × year panel: radiance (total, inside and outside mine footprints) joined to production."""
    rasters = sorted((INTERMEDIOS / "luz").glob("vnp46a4_*.tif"))
    if not rasters:
        print("Sin rasters de luz: corre primero `uv run python -m scripts.obtener_luz` (necesita el token).")
        return None
    mines = peru_mines(ORIGINALES / "maus" / "global_mining_polygons_v2.gpkg")
    years = []
    for raster in rasters:
        light = light_by_district(raster, districts, mines)
        light.insert(1, "year", int(raster.stem[-4:]))
        years.append(light)
    light = pd.concat(years, ignore_index=True)
    log.add("luz", f"radiancia anual VNP46A4 por distrito ({len(rasters)} años)", len(rasters), len(light),
            "píxeles sin dato no suman; valores negativos (ruido del sensor) pasan a 0")
    panel = light.merge(table, on="ubigeo", how="left").merge(production, on=["ubigeo", "year"], how="left")
    tonnes = [c for c in panel.columns if c.startswith("tonnes_")]
    panel[tonnes] = panel[tonnes].fillna(0)
    panel["units"] = panel["units"].fillna(0).astype(int)
    panel["mining"] = panel["units"] > 0
    panel["light_per_km2"] = panel["light_sum"] / panel["area_km2"]
    panel["light_per_capita"] = panel["light_sum"] / panel["population_2020"]
    panel.to_csv(PROCESADOS / "panel_distrito_anio.csv", index=False)
    log.add("panel", "panel distrito × año con luz, pobreza, huella y producción", len(light), len(panel),
            f"{panel.ubigeo.nunique()} distritos × {panel.year.nunique()} años")
    return panel


def main() -> None:
    PROCESADOS.mkdir(parents=True, exist_ok=True)
    log = Bitacora()
    districts = load_districts(ORIGINALES / "limites" / "distritos_geocatmin.geojson")
    log.add("limites", "distritos de GEOCATMIN con UBIGEO único", len(districts), districts.ubigeo.nunique())
    production = process_minem(log, districts)
    validate_coordinates(log, districts)
    table = process_districts(log, districts)
    process_light(log, districts, table, production)
    log.save(PROCESADOS / "bitacora_limpieza.json")
    for step in log.steps:
        print(f"[{step['source']}] {step['step']}: {step['rows_in']:,} -> {step['rows_out']:,}  {step['note']}")


if __name__ == "__main__":
    main()
