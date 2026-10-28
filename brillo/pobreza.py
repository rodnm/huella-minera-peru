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
