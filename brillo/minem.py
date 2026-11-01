"""Read MINEM's "Producción Minera" spreadsheets into one tidy table: one row per unit, metal, district and year.

Two layouts exist:
- 2001-2019: one file per metal; the metal and its unit are only in the title ("... DE ORO (Grs.f) - 2016").
- 2020 onwards: one file with METAL/MINERAL and UNIDAD DE MEDIDA columns; column names change between years.
Both have a header row with TITULAR and DISTRITO and one column per month; the annual figure is the sum of the months.
"""
import datetime
import re
import unicodedata
from pathlib import Path

import pandas as pd

MAIN_METALS = {"COBRE", "ORO", "PLATA", "ZINC", "PLOMO", "HIERRO", "ESTANO", "MOLIBDENO"}
DOUBLE_COUNTED_STAGES = {"FUNDICION", "REFINACION", "REFINERIA"}
# From 2020 MINEM adds regional artisanal gold estimates with no district, labelled as general regime
ARTISANAL_AGGREGATES = {"DATA MINEROS ARTESANALES"}  # refining re-processes concentrates already counted upstream

# Fine-content units to metric tonnes (TLF: long tons, 1 016.0469088 kg)
TONNES_PER_UNIT = {"TMF": 1.0, "GRSF": 1e-6, "GRFINOS": 1e-6, "GFINOS": 1e-6, "KGF": 1e-3, "KGFINOS": 1e-3, "TLF": 1.0160469088}

COLUMN_ALIASES = {
    "metal": {"METAL", "MINERAL"},
    "unit_measure": {"UNIDAD DE MEDIDA"},
    "stage": {"ETAPA"},
    "process": {"PROCESO"},
    "stratum": {"ESTRATO", "CLASIFICACION"},
    "holder": {"TITULAR"},
    "unit_name": {"UNIDAD", "UNIDAD MINERA"},
    "region": {"REGION", "DEPARTAMENTO"},
    "province": {"PROVINCIA"},
    "district": {"DISTRITO"},
}
MONTH_NAMES = {
    **{m: i for i, m in enumerate(["ENE", "FEB", "MAR", "ABR", "MAY", "JUN", "JUL", "AGO", "SET", "OCT", "NOV",
                                   "DIC"], start=1)},
    **{m: i for i, m in enumerate(["ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO", "JULIO", "AGOSTO",
                                   "SETIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"], start=1)},
    "SEP": 9, "SEPTIEMBRE": 9,
}
NORMALIZED = ["metal", "stage", "process", "stratum", "holder", "unit_name", "region", "province", "district"]


def normalize_text(value) -> str:
    """Upper case without accents or repeated spaces, so names from different files compare equal."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(text.upper().split())


def to_tonnes(value: float, unit: str) -> float:
    key = re.sub(r"[^A-Z]", "", normalize_text(unit))
    return value * TONNES_PER_UNIT[key]


def _month(cell) -> int | None:
    if isinstance(cell, (datetime.datetime, pd.Timestamp)):
        return cell.month
    return MONTH_NAMES.get(normalize_text(cell))


def read_production(path: Path, year: int, sheet=0) -> pd.DataFrame:
    raw = pd.read_excel(path, sheet_name=sheet, header=None, dtype=object)
    header_row = next(i for i in range(min(15, len(raw)))
                      if {"TITULAR", "DISTRITO"} <= {normalize_text(v) for v in raw.iloc[i]})
    header = raw.iloc[header_row].tolist()
    columns, months = {}, []
    for j, cell in enumerate(header):
        name = normalize_text(cell)
        for canonical, aliases in COLUMN_ALIASES.items():
            if name in aliases and canonical not in columns:
                columns[canonical] = j
        if _month(cell):
            months.append(j)
    body = raw.iloc[header_row + 1:]
    df = pd.DataFrame({canonical: body.iloc[:, j].values for canonical, j in columns.items()})
    df["quantity"] = body.iloc[:, months].apply(pd.to_numeric, errors="coerce").sum(axis=1, min_count=1).values
    if "metal" not in df:  # per-metal layout: metal and unit come from the title above the header
        title = next(normalize_text(v) for i in range(header_row) for v in raw.iloc[i] if normalize_text(v))
        title_raw = next(str(v) for i in range(header_row) for v in raw.iloc[i] if normalize_text(v))
        df["metal"] = re.search(r" DE ([A-Z]+) \(", title).group(1)
        df["unit_measure"] = re.search(r"\(([^)]+)\)", title_raw).group(1).strip()
    df = df[df["holder"].map(normalize_text).ne("") & df["holder"].map(normalize_text).ne("TOTAL")]
    df = df[df["quantity"].notna()].copy()
    for column in NORMALIZED:
        df[column] = df[column].map(normalize_text)
    df["unit_measure"] = df["unit_measure"].map(lambda u: str(u).strip())
    df["tonnes"] = [to_tonnes(q, u) for q, u in zip(df["quantity"], df["unit_measure"])]
    df.insert(0, "year", year)
    df["source_file"] = Path(path).name
    return df.reset_index(drop=True)


def scale_mining(df: pd.DataFrame, log=None) -> pd.DataFrame:
    """Large and medium mining: general regime, the eight main metals, without smelting and refining.

    With a ``log`` (brillo.bitacora.Bitacora) every filter records how many rows it keeps.
    """
    filters = [
        ("solo régimen general (gran y mediana minería)", lambda d: d["stratum"].eq("REGIMEN GENERAL")),
        ("solo los 8 metales principales", lambda d: d["metal"].isin(MAIN_METALS)),
        ("sin fundición ni refinería (contarían dos veces el mismo metal)",
         lambda d: ~d["stage"].isin(DOUBLE_COUNTED_STAGES)),
        ("sin agregados regionales de mineros artesanales rotulados como régimen general",
         lambda d: ~d["holder"].isin(ARTISANAL_AGGREGATES)),
    ]
    for step, keep in filters:
        kept = df.loc[keep(df)]
        if log is not None:
            log.add("minem", step, len(df), len(kept))
        df = kept
    return df


def assign_ubigeo(df: pd.DataFrame, districts: pd.DataFrame, manual: pd.DataFrame) -> pd.DataFrame:
    """Add the UBIGEO of each (region, province, district) name, and how it was found: name, manual or unmatched.

    ``districts`` has ubigeo, department, province and district; ``manual`` lists the documented exceptions.
    """
    key = ["region", "province", "district"]
    by_name = {tuple(normalize_text(v) for v in row[1:]): row[0]
               for row in districts[["ubigeo", "department", "province", "district"]].itertuples(index=False)}
    by_hand = {tuple(normalize_text(v) for v in row[:3]): row[3]
               for row in manual[[*key, "ubigeo"]].itertuples(index=False)}
    out = df.copy()
    names = [tuple(normalize_text(v) for v in row) for row in out[key].itertuples(index=False)]
    out["ubigeo"] = [by_name.get(n, by_hand.get(n)) for n in names]
    out["match"] = ["name" if n in by_name else "manual" if n in by_hand else "unmatched" for n in names]
    return out


UNIT_COLUMNS = {
    "holder": {"TITULAR", "OPERADOR"},
    "unit_name": {"UNIDAD", "UNIDAD MINERA EN PRODUCCION"},
    "region": {"REGION", "DEPARTAMENTO"},
    "province": {"PROVINCIA"},
    "district": {"DISTRITO"},
    "product": {"METAL", "PRODUCTO", "PRODUCTO 1"},
    "lon": {"LONGITUD"},
    "lat": {"LATITUD"},
}


def read_units(path: Path, year: int) -> pd.DataFrame:
    """Read a "Principales Unidades Mineras en Producción" sheet: names plus the unit's coordinates."""
    raw = pd.read_excel(path, sheet_name=0, header=None, dtype=object)
    header_row = next(i for i in range(min(15, len(raw)))
                      if {"LONGITUD", "LATITUD"} <= {normalize_text(v) for v in raw.iloc[i]})
    header = [normalize_text(v) for v in raw.iloc[header_row]]
    body = raw.iloc[header_row + 1:]
    df = pd.DataFrame({canonical: body.iloc[:, header.index(next(a for a in aliases if a in header))].values
                       for canonical, aliases in UNIT_COLUMNS.items()})
    for column in ["holder", "unit_name", "region", "province", "district", "product"]:
        df[column] = df[column].map(normalize_text)
    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df = df[df["unit_name"].ne("") & df["lon"].notna() & df["lat"].notna()].copy()
    df.insert(0, "year", year)
    return df.reset_index(drop=True)


def coordinate_agreement(units: pd.DataFrame, districts, manual: pd.DataFrame) -> tuple[float, pd.DataFrame]:
    """Share of units whose named district (via assign_ubigeo) contains the unit's own point.

    ``agrees`` is None when the name does not match any district, so it does not count either way.
    ``distance_km`` is how far the point lies from the named district (0 inside it), which separates units on a
    district border from coordinates that are simply wrong.
    """
    import geopandas as gpd

    named = assign_ubigeo(units.reset_index(drop=True), districts, manual)
    points = gpd.GeoDataFrame(named, geometry=gpd.points_from_xy(named["lon"], named["lat"]), crs="EPSG:4326")
    located = gpd.sjoin(points, districts[["ubigeo", "geometry"]].rename(columns={"ubigeo": "ubigeo_point"}),
                        how="left", predicate="within")
    located = located[~located.index.duplicated()]
    table = pd.DataFrame(named)
    table["ubigeo_point"] = located["ubigeo_point"].values
    table["agrees"] = [None if u is None else u == p for u, p in zip(table["ubigeo"], table["ubigeo_point"])]
    metric = "EPSG:32718"  # UTM 18S: good enough for kilometres across Peru
    shapes = districts.set_index("ubigeo").geometry.to_crs(metric)
    where = points.geometry.to_crs(metric).reset_index(drop=True)
    table["distance_km"] = [None if u is None else round(shapes[u].distance(pt) / 1000, 1)
                            for u, pt in zip(table["ubigeo"], where)]
    judged = table["agrees"].dropna()
    return float(judged.mean()), table


def district_panel(units: pd.DataFrame) -> pd.DataFrame:
    """One row per district and year: units in production, tonnes of each metal and its main metal.

    The main metal is the one where the district holds the largest share of that year's national output, which
    compares gold and copper without needing prices.
    """
    tonnes = units.pivot_table(index=["ubigeo", "year"], columns="metal", values="tonnes", aggfunc="sum",
                               fill_value=0)
    share = tonnes / tonnes.groupby(level="year").transform("sum")
    panel = tonnes.add_prefix("tonnes_").rename(columns=str.lower)
    panel["main_metal"] = share.idxmax(axis=1)
    panel["units"] = units.groupby(["ubigeo", "year"])["unit_name"].nunique()
    return panel.reset_index().rename_axis(columns=None)
