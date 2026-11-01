"""Descriptive figures of the mining footprint and the data files the public atlas reads.

Every number the dashboard, the reel and the post show comes from ``describe``, so none is typed by hand.
"""
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio

MADRE_DE_DIOS = "17"
MIN_DISTRICT_KM2 = 0.01  # one hectare: below it a district's footprint is a few isolated 30 m pixels


def describe(panel: pd.DataFrame, top: int = 10) -> dict:
    """National change, its share in Madre de Dios, the districts with the largest gains and how many have footprint."""
    years = sorted(panel["year"].unique())
    first, last = int(years[0]), int(years[-1])
    national = panel.groupby("year")["mining_km2"].sum()
    increase = national[last] - national[first]
    wide = panel.pivot(index="ubigeo", columns="year", values="mining_km2").fillna(0.0)
    gain = (wide[last] - wide[first]).sort_values(ascending=False)
    names = panel.drop_duplicates("ubigeo").set_index("ubigeo")
    madre = wide[wide.index.str[:2] == MADRE_DE_DIOS]
    leaders = gain.head(top)
    return {
        "first_year": first,
        "last_year": last,
        "national_km2": {str(int(year)): float(value) for year, value in national.items()},
        "ratio": float(national[last] / national[first]),
        "increase_km2": float(increase),
        "madre_de_dios": {
            "first_km2": float(madre[first].sum()),
            "last_km2": float(madre[last].sum()),
            "share_of_increase": float((madre[last].sum() - madre[first].sum()) / increase),
            "share_of_last": float(madre[last].sum() / national[last]),
        },
        "top_districts": [
            {"ubigeo": ubigeo, "district": names.loc[ubigeo, "district"], "department": names.loc[ubigeo, "department"],
             "first_km2": float(wide.loc[ubigeo, first]), "last_km2": float(wide.loc[ubigeo, last]),
             "gain_km2": float(value)}
            for ubigeo, value in leaders.items()
        ],
        "top_share_of_increase": float(leaders.sum() / increase),
        "districts_with_footprint": {str(int(year)): int((wide[year] >= MIN_DISTRICT_KM2).sum()) for year in years},
    }


def contrast_periods(table: pd.DataFrame, department: str, years: tuple[int, int, int]) -> dict:
    """Where two sources agree and where not: ratios over the whole period and its two halves, and yearly gains."""
    rows = table[table["department"] == department].set_index("year").sort_index()
    first, middle, last = years
    ratio = lambda column, a, b: float(rows.loc[b, column] / rows.loc[a, column])
    span = rows.loc[first:last]
    return {
        "whole": {source: ratio(f"{source}_km2", first, last) for source in ("mapbiomas", "amw")},
        "first_half": {source: ratio(f"{source}_km2", first, middle) for source in ("mapbiomas", "amw")},
        "second_half": {source: ratio(f"{source}_km2", middle, last) for source in ("mapbiomas", "amw")},
        "gain_km2": {source: float(rows.loc[last, f"{source}_km2"] - rows.loc[first, f"{source}_km2"])
                     for source in ("mapbiomas", "amw")},
        "yearly_gain_correlation": float(span["mapbiomas_km2"].diff().corr(span["amw_km2"].diff())),
    }


def other_departments(table: pd.DataFrame, excluded: str, first: int, last: int, min_km2: float) -> list[dict]:
    """Ratios of both sources in the other departments where the second source sees at least ``min_km2``."""
    wide = table.pivot(index="department", columns="year", values=["mapbiomas_km2", "amw_km2"])
    rows = []
    for department in wide.index:
        amw_first, amw_last = wide.loc[department, ("amw_km2", first)], wide.loc[department, ("amw_km2", last)]
        map_first, map_last = wide.loc[department, ("mapbiomas_km2", first)], wide.loc[department, ("mapbiomas_km2", last)]
        if department == excluded or amw_last < min_km2 or amw_first <= 0 or map_first <= 0:
            continue
        rows.append({"department": department, "mapbiomas_ratio": float(map_last / map_first),
                     "amw_ratio": float(amw_last / amw_first), "amw_first_km2": float(amw_first),
                     "amw_last_km2": float(amw_last)})
    return sorted(rows, key=lambda row: -row["amw_last_km2"])


def _number(value, digits: int) -> float | None:
    return None if pd.isna(value) else round(float(value), digits)


def panel_payload(panel: pd.DataFrame) -> dict:
    """One compact record per district with its yearly series; missing values are null so the file is valid JSON.

    Five decimals on the footprint keep every district on the same side of the one-hectare rule as ``describe``.
    """
    years = [int(year) for year in sorted(panel["year"].unique())]
    districts = []
    for ubigeo, group in panel.sort_values("year").groupby("ubigeo", sort=True):
        row = group.iloc[0]
        interval = [_number(row[column], 1) for column in ("poverty", "poverty_low", "poverty_high")]
        districts.append({
            "u": ubigeo, "n": row["district"], "p": row["province"], "d": row["department"],
            "pop": _number(row["population_2020"], 0), "area": _number(row["area_km2"], 1),
            "m": [_number(value, 5) for value in group["mining_km2"]],
            "l": [_number(value, 3) for value in group["light_per_km2"]],
            "pov": None if interval[0] is None else interval,
        })
    return {"years": years, "districts": districts}


def footprint_pixels(fractions: dict[int, Path], min_fraction: float) -> tuple[dict, bytes]:
    """Pixels with footprint in any year: little-endian uint16 rows, uint16 columns, then one uint8 share per year."""
    years = sorted(fractions)
    stack = []
    for year in years:
        with rasterio.open(fractions[year]) as src:
            stack.append(src.read(1))
            transform = src.transform
    stack = np.stack(stack, axis=-1)
    rows, cols = np.nonzero((stack >= min_fraction).any(axis=-1))
    shares = np.rint(np.clip(stack[rows, cols], 0, 1) * 255).astype("uint8")
    meta = {"count": int(rows.size), "years": [int(year) for year in years],
            "transform": [transform.c, transform.a, transform.f, transform.e], "min_fraction": min_fraction}
    return meta, rows.astype("<u2").tobytes() + cols.astype("<u2").tobytes() + shares.tobytes()
