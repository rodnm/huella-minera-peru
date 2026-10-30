"""Compute the findings, the KPIs and the named cases from the clean panel; write datos/procesados/hallazgos.json.

Run from the repository root, after scripts.procesar_datos: uv run python -m scripts.analizar_datos
Every number the dashboard, the reel and the README show comes from this file.
"""
import json
from pathlib import Path

import pandas as pd

from brillo.analisis import cross_section, gaps, mine_openings, paradox_districts

ROOT = Path(__file__).resolve().parent.parent
PROCESADOS = ROOT / "datos" / "procesados"
REFERENCIAS = ROOT / "datos" / "referencias"
PER_THOUSAND = 1000  # light per capita is shown per 1,000 inhabitants (sum of nW·cm⁻²·sr⁻¹)


def main_unit(units: pd.DataFrame, years: tuple[int, int]) -> pd.Series:
    """Name of the unit with most tonnes in each district over ``years``."""
    window = units[units.year.between(*years)]
    totals = window.groupby(["ubigeo", "unit_name"])["tonnes"].sum().reset_index()
    return totals.sort_values("tonnes").groupby("ubigeo")["unit_name"].last()


def summary(cs: pd.DataFrame) -> dict:
    mine, rest = cs[cs.mining], cs[~cs.mining]
    lpc = lambda d: float(d.light_per_capita.median() * PER_THOUSAND)
    out = lambda d: float(d.light_outside_per_capita.median() * PER_THOUSAND)
    return {
        "districts": int(len(cs)), "mining_districts": int(len(mine)),
        "light_per_1000_mining": lpc(mine), "light_per_1000_rest": lpc(rest), "light_ratio": lpc(mine) / lpc(rest),
        "light_outside_per_1000_mining": out(mine), "light_outside_per_1000_rest": out(rest),
        "light_outside_ratio": out(mine) / out(rest),
        "poverty_median_mining": float(mine.poverty.median()), "poverty_median_rest": float(rest.poverty.median()),
        "share_of_mining_light_on_mines": float(mine.light_inside_mines.sum() / mine.light_sum.sum()),
        "gaps": gaps(cs),
    }


def main() -> None:
    panel = pd.read_csv(PROCESADOS / "panel_distrito_anio.csv", dtype={"ubigeo": str})
    units = pd.read_csv(PROCESADOS / "produccion_unidad_anio.csv", dtype={"ubigeo": str})
    flares = pd.read_csv(REFERENCIAS / "hidrocarburos.csv", dtype={"ubigeo": str})
    names = panel.drop_duplicates("ubigeo").set_index("ubigeo")[["district", "province", "department",
                                                                   "poverty", "population_2020"]]

    cs = cross_section(panel)
    robust = cross_section(panel, exclude=set(flares.ubigeo))
    unit_1618 = main_unit(units, (2016, 2018))

    paradox = paradox_districts(cs).copy()
    paradox["mine"] = paradox.ubigeo.map(unit_1618)
    paradox["light_per_1000"] = paradox.light_per_capita * PER_THOUSAND
    paradox["share_on_mine"] = paradox.light_inside_mines / paradox.light_sum
    paradox = paradox.sort_values("poverty", ascending=False)

    openings = mine_openings(panel, first=2015, last=2022)
    openings["mine"] = openings.ubigeo.map(main_unit(units, (2013, 2025)))
    openings = openings.join(names, on="ubigeo").sort_values("ratio", ascending=False)

    national = panel.groupby("year")["light_sum"].sum()
    latest = int(panel.year.max())
    first = int(panel.year.min())
    footprint_light = panel[panel.year == latest]
    mining_km2 = panel.groupby("year")["mining_km2"].sum()
    by_year = panel.pivot(index="ubigeo", columns="year", values="mining_km2")
    growth = (by_year[latest] - by_year[first]).sort_values(ascending=False).head(10).rename("km2_nuevos").reset_index()
    growth = growth.join(names, on="ubigeo")
    is_mdd = panel.department.eq("MADRE DE DIOS")
    mdd_share = panel[is_mdd].groupby("year")["mining_km2"].sum() / mining_km2
    gap = pd.read_csv(PROCESADOS / "validacion_huella.csv", dtype={"department": str})
    gap_by_year = gap.groupby("year")[["mining_km2", "official_km2"]].sum()

    def records(df, columns):
        return json.loads(df[columns].round(3).to_json(orient="records", force_ascii=False))

    findings = {
        "corte": {"pobreza": "INEI, Mapa de Pobreza 2018", "luz": "NASA Black Marble VNP46A4, 2018",
                  "mineria": "MINEM, producción en régimen general 2016-2018"},
        "resumen": summary(cs),
        "robustez_sin_hidrocarburos": {"excluidos": flares.district.tolist(), **summary(robust)},
        "paradoja": {
            "regla": "distrito minero con luz por habitante en el 25 % más alto del país y pobreza mayor que la mediana"
                     " de su departamento; confirmada si el límite inferior del IC 95 % también la supera",
            "n_confirmados": int(paradox.confirmed.sum()),
            "n_posibles": int((~paradox.confirmed).sum()),
            "distritos": records(paradox.sort_values(["confirmed", "poverty"], ascending=False),
                                 ["ubigeo", "district", "province", "department", "mine", "confirmed", "poverty",
                                  "poverty_low", "poverty_high", "light_per_1000", "share_on_mine", "mining_km2",
                                  "population_2020"]),
        },
        "aperturas": records(openings.dropna(subset=["ratio"]),
                             ["ubigeo", "district", "department", "mine", "start", "light_before", "light_after",
                              "ratio", "poverty"]),
        "luz_nacional": {"por_anio": {int(y): float(v) for y, v in national.items()},
                         "cambio_2013_ultimo": float(national.iloc[-1] / national.iloc[0] - 1), "ultimo_anio": latest},
        "huella": {
            "fuente": "MapBiomas Perú C4, clase 30 (no distingue minería industrial, artesanal o ilegal)",
            "km2_por_anio": {int(y): float(v) for y, v in mining_km2.items()},
            "multiplicador_primero_ultimo": float(mining_km2[latest] / mining_km2[first]),
            "km2_nuevos": float(mining_km2[latest] - mining_km2[first]),
            "participacion_madre_de_dios_por_anio": {int(y): float(v) for y, v in mdd_share.items()},
            "mayor_crecimiento": records(growth, ["ubigeo", "district", "province", "department", "km2_nuevos",
                                                  "poverty"]),
            "luz_sobre_huella_ultimo_anio": float(footprint_light.light_inside_mines.sum()
                                                  / footprint_light.light_sum.sum()),
            "luz_madre_de_dios_ultimo_anio": float(footprint_light[footprint_light.department == "MADRE DE DIOS"]
                                                   .light_sum.sum() / footprint_light.light_sum.sum()),
            "validacion_nacional_vs_oficial": {int(y): float(r.mining_km2 / r.official_km2 - 1)
                                               for y, r in gap_by_year.iterrows()},
        },
    }
    path = PROCESADOS / "hallazgos.json"
    path.write_text(json.dumps(findings, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"hallazgos -> {path}")


if __name__ == "__main__":
    main()
