"""Contrast the MapBiomas footprint with Amazon Mining Watch, a source built independently from other satellites.

Run from the repository root: uv run python -m scripts.contrastar_huella
The two do not measure the same thing: MapBiomas says what the ground is each year, so mined land that regrows leaves
the class; Amazon Mining Watch accumulates scars since 2018 and only covers the Amazon basin. The comparison is about
where the land is and which way it moves, and the difference in level is reported as it is.
"""
import json
from pathlib import Path

import pandas as pd

from brillo.distritos import load_districts
from brillo.mapbiomas import mining_km2_by_district, overlap_share, scar_fractions

ROOT = Path(__file__).resolve().parent.parent
ORIGINALES = ROOT / "datos" / "originales"
INTERMEDIOS = ROOT / "datos" / "intermedios"
PROCESADOS = ROOT / "datos" / "procesados"
YEARS = list(range(2018, 2026))
LAST_CONFIRMED = 2024  # a scar is confirmed when seen again the next year, so 2025 onsets cannot be annual yet
MADRE_DE_DIOS = "17"


def main() -> None:
    districts = load_districts(ORIGINALES / "limites" / "distritos_geocatmin.geojson")
    panel = pd.read_csv(PROCESADOS / "panel_distrito_anio.csv", dtype={"ubigeo": str},
                        usecols=["ubigeo", "year", "mining_km2"])
    fractions = scar_fractions(ORIGINALES / "amw" / "amazon_basin_mining_scar_masks.tif",
                               INTERMEDIOS / "luz" / "vnp46a4_2018.tif", INTERMEDIOS / "huella_amw", YEARS)
    scars = pd.concat([mining_km2_by_district(path, districts).rename(columns={"mining_km2": "amw_km2"}).assign(year=year)
                       for year, path in fractions.items()])
    both = panel[panel["year"].isin(YEARS)].merge(scars, on=["ubigeo", "year"], how="left").rename(
        columns={"mining_km2": "mapbiomas_km2"})
    both["department"] = both["ubigeo"].str[:2]
    by_department = both.groupby(["department", "year"], as_index=False)[["mapbiomas_km2", "amw_km2"]].sum()
    by_department.round(3).to_csv(PROCESADOS / "contraste_huella.csv", index=False)

    region = districts[districts["ubigeo"].str[:2] == MADRE_DE_DIOS].to_crs("EPSG:4326").geometry.union_all()
    mapbiomas = {year: INTERMEDIOS / "huella" / f"mineria_frac_{year}.tif" for year in YEARS}
    madre = by_department[by_department["department"] == MADRE_DE_DIOS].set_index("year")
    first = both[both["year"] == YEARS[0]].set_index("ubigeo")
    last = both[both["year"] == LAST_CONFIRMED].set_index("ubigeo")
    gain = pd.DataFrame({"mapbiomas": last["mapbiomas_km2"] - first["mapbiomas_km2"],
                         "amw": last["amw_km2"] - first["amw_km2"]})
    summary = {
        "years": YEARS,
        "madre_de_dios": {
            "mapbiomas_km2": madre["mapbiomas_km2"].round(1).to_dict(),
            "amw_km2": madre["amw_km2"].round(1).to_dict(),
            "mapbiomas_on_amw": {y: round(overlap_share(mapbiomas[y], fractions[y], region), 3) for y in YEARS},
            "amw_on_mapbiomas": {y: round(overlap_share(fractions[y], mapbiomas[y], region), 3) for y in YEARS},
            "last_confirmed_year": LAST_CONFIRMED,
            "ratio_to_last_confirmed": {
                column: round(madre.loc[LAST_CONFIRMED, f"{column}_km2"] / madre.loc[YEARS[0], f"{column}_km2"], 2)
                for column in ("mapbiomas", "amw")},
        },
        "district_gain_spearman": {
            "madre_de_dios": round(gain[gain.index.str[:2] == MADRE_DE_DIOS].corr(method="spearman").iloc[0, 1], 3),
            "districts_with_scars": round(gain[last["amw_km2"] > 0.1].corr(method="spearman").iloc[0, 1], 3),
            "n_districts_with_scars": int((last["amw_km2"] > 0.1).sum()),
        },
    }
    (PROCESADOS / "contraste_huella.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(by_department[by_department["year"].isin([2018, 2025]) & (by_department["amw_km2"] > 1)].round(1).to_string(index=False))


if __name__ == "__main__":
    main()
