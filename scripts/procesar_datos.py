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
from brillo.minem import (DOUBLE_COUNTED_STAGES, assign_ubigeo, coordinate_agreement, district_panel,
                          read_production, read_units, scale_mining)

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


def main() -> None:
    PROCESADOS.mkdir(parents=True, exist_ok=True)
    log = Bitacora()
    districts = load_districts(ORIGINALES / "limites" / "distritos_geocatmin.geojson")
    log.add("limites", "distritos de GEOCATMIN con UBIGEO único", len(districts), districts.ubigeo.nunique())
    process_minem(log, districts)
    validate_coordinates(log, districts)
    log.save(PROCESADOS / "bitacora_limpieza.json")
    for step in log.steps:
        print(f"[{step['source']}] {step['step']}: {step['rows_in']:,} -> {step['rows_out']:,}  {step['note']}")


if __name__ == "__main__":
    main()
