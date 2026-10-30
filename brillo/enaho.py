"""ENAHO module 34 (Sumaria): household poverty, weights and the survey-design pieces the small-area model needs.

ENAHO is representative by department, not by district: a pooled district rate rests on a few dozen households, so
it is only an input to brillo.fay_herriot, never a result to publish.
"""
import io
import re
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

COLUMNS = ["ubigeo", "conglome", "estrato", "pobreza", "factor07", "mieperho", "gashog2d", "linea"]
NUMERIC = ["pobreza", "factor07", "mieperho", "gashog2d", "linea"]


def read_sumaria(path: Path, year: int) -> pd.DataFrame:
    """One row per household, from the annual Sumaria file of a module-34 zip.

    ``poor`` covers extreme and non-extreme poverty (POBREZA 1 and 2) and ``weight`` expands to people
    (FACTOR07 × MIEPERHO), because INEI's rate counts people. Rows without a poverty status or a weight are dropped.
    """
    pattern = re.compile(rf"(^|/)sumaria-{year}\.csv$", re.IGNORECASE)
    with zipfile.ZipFile(path) as archive:
        member = next(n for n in archive.namelist() if pattern.search(n))
        raw = archive.read(member)
    first_line = raw.split(b"\n", 1)[0]
    separator = ";" if first_line.count(b";") > first_line.count(b",") else ","
    table = pd.read_csv(io.BytesIO(raw), encoding="latin-1", sep=separator, dtype=str, low_memory=False)
    table.columns = [c.strip().lower() for c in table.columns]
    df = table[COLUMNS].copy()
    df["ubigeo"] = df["ubigeo"].str.strip().str.zfill(6)
    for column in NUMERIC:
        df[column] = pd.to_numeric(df[column].str.strip().str.replace(",", ".", regex=False), errors="coerce")
    df = df[df["pobreza"].notna() & df["factor07"].notna() & (df["mieperho"] > 0)].copy()
    df["poor"] = df["pobreza"] <= 2
    df["weight"] = df["factor07"] * df["mieperho"]
    df["department"] = df["ubigeo"].str[:2]
    df["year"] = year
    return df.reset_index(drop=True)


def weighted_poverty(df: pd.DataFrame, by: str | list[str] | None = None):
    """Share of people in poverty, overall or per group."""
    if by is None:
        return float(np.average(df["poor"], weights=df["weight"]))
    grouped = df.assign(_poor=df["poor"] * df["weight"]).groupby(by)
    return grouped["_poor"].sum() / grouped["weight"].sum()


def direct_estimates(df: pd.DataFrame) -> pd.DataFrame:
    """Per district: weighted rate, households sampled and Kish's effective sample size (Σw)²/Σw²."""
    work = df.assign(_poor=df["poor"] * df["weight"], _w2=df["weight"] ** 2)
    grouped = work.groupby("ubigeo")
    out = pd.DataFrame({"rate": grouped["_poor"].sum() / grouped["weight"].sum(),
                        "households": grouped.size(),
                        "n_eff": grouped["weight"].sum() ** 2 / grouped["_w2"].sum()})
    return out.reset_index()


def design_effects(df: pd.DataFrame) -> pd.Series:
    """Design effect of the poverty rate per department, from the clusters (conglome) within strata.

    It compares the linearized variance of the rate with what simple random sampling of the same effective size
    would give, and is floored at 1 so a department with a noisy estimate never looks better than random sampling.
    """
    effects = {}
    for department, d in df.groupby("department"):
        total = d["weight"].sum()
        rate = (d["poor"] * d["weight"]).sum() / total
        score = d["weight"] * (d["poor"] - rate) / total
        variance = 0.0
        for _, stratum in d.assign(_score=score).groupby("estrato"):
            clusters = stratum.groupby("conglome")["_score"].sum()
            if len(clusters) > 1:
                variance += len(clusters) / (len(clusters) - 1) * ((clusters - clusters.mean()) ** 2).sum()
        n_eff = total ** 2 / (d["weight"] ** 2).sum()
        simple = rate * (1 - rate) / n_eff
        effects[department] = max(variance / simple, 1.0) if simple > 0 else 1.0
    return pd.Series(effects, name="deff")


def sampling_variance(n_eff, deff):
    """Sampling variance of arcsin(√rate): about deff / (4·n), which stays defined when a rate is 0 or 1."""
    return deff / (4 * n_eff)
