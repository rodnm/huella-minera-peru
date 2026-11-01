"""INEI district poverty map 2018 (sheet Anexo1 of its statistical annex)."""
from pathlib import Path

import pandas as pd

COLUMNS = ["ubigeo", "department", "province", "district", "population_2020", "poverty_low", "poverty_high",
           "robust_group", "rank"]


def read_poverty(path: Path) -> pd.DataFrame:
    """One row per district. INEI publishes only the 95 % interval, so ``poverty`` is its midpoint (in %)."""
    raw = pd.read_excel(path, sheet_name="Anexo1", header=None, dtype=str)
    body = raw.iloc[:, :len(COLUMNS)]
    body.columns = COLUMNS
    df = body[body["ubigeo"].str.strip().str.fullmatch(r"\d{6}", na=False)].copy()
    for column in ["ubigeo", "department", "province", "district"]:
        df[column] = df[column].str.strip()
    for column in ["population_2020", "poverty_low", "poverty_high", "robust_group", "rank"]:
        df[column] = pd.to_numeric(df[column])
    df["poverty"] = (df["poverty_low"] + df["poverty_high"]) / 2
    return df.reset_index(drop=True)


def read_poverty_2013(path: Path) -> pd.DataFrame:
    """INEI district poverty map 2013 (sheet Cdr01), one row per district.

    Large districts come split into up to three "Grupo" rows, collapsed here with population weights. Districts that
    share one interval with another of their province were estimated as a group and are flagged. ``poverty_2013`` is
    the midpoint of the 95 % interval, as in the 2018 map; a negative lower bound is taken as 0.
    """
    raw = pd.read_excel(path, sheet_name="Cdr01", header=None, dtype=str)
    body = raw.iloc[:, 1:9].copy()
    body.columns = ["ubigeo", "department", "province", "district", "population", "low", "high", "rank"]
    rows = body[body["ubigeo"].str.strip().str.fullmatch(r"\d{6}", na=False)].copy()
    rows["ubigeo"] = rows["ubigeo"].str.strip()
    for column in ["population", "low", "high"]:
        rows[column] = pd.to_numeric(rows[column])
    rows["low"] = rows["low"].clip(lower=0)
    rows["mid"] = (rows["low"] + rows["high"]) / 2
    rows["split"] = rows["ubigeo"].duplicated(keep=False)
    whole = rows[~rows["split"]]
    shared = whole[whole.duplicated(["province", "low", "high"], keep=False)]["ubigeo"]

    def collapse(d):
        weights = d["population"]
        return pd.Series({"population_2015": weights.sum(), "poverty_2013": (d["mid"] * weights).sum() / weights.sum(),
                          "poverty_low_2013": (d["low"] * weights).sum() / weights.sum(),
                          "poverty_high_2013": (d["high"] * weights).sum() / weights.sum(),
                          "split_2013": len(d) > 1})

    out = rows.groupby("ubigeo")[["population", "low", "high", "mid"]].apply(collapse).reset_index()
    out["split_2013"] = out["split_2013"].astype(bool)
    out["grouped_2013"] = out["ubigeo"].isin(set(shared))
    return out
