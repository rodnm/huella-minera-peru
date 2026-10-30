"""Estimate monetary poverty by district: official maps, department series and a Fay-Herriot model by period.

Run from the repository root, after scripts.procesar_datos: uv run python -m scripts.estimar_pobreza
Night light, mining production and mining footprint are never predictors here: the analysis compares poverty with
them, and using them to build poverty would manufacture that relationship.

Window 2017-19 is the test: its model uses the 2013 map and is scored against the 2018 map. Window 2023-25 is the
update INEI does not publish; it uses the 2018 map. Figures from this script are project estimates, not INEI data.
"""
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

from brillo.bitacora import Bitacora
from brillo.enaho import design_effects, direct_estimates, read_sumaria, sampling_variance, weighted_poverty
from brillo.fay_herriot import benchmark, fit, predict, to_rate, to_theta
from brillo.fuentes import ENAHO_CODES
from brillo.pobreza import read_poverty_2013

ROOT = Path(__file__).resolve().parent.parent
ORIGINALES = ROOT / "datos" / "originales"
PROCESADOS = ROOT / "datos" / "procesados"
OFFICIAL_2024 = 0.2758  # national rate this pipeline must reproduce from Sumaria 2024 (checked by hand against INEI)
WINDOWS = {"2017-19": ((2017, 2018, 2019), "poverty_2013"), "2023-25": ((2023, 2024, 2025), "poverty")}


def covariates(table: pd.DataFrame, anchor: str) -> tuple[np.ndarray, list[str]]:
    """Predictors: earlier official map, log density, natural region and department."""
    parts = [pd.Series(1.0, index=table.index, name="intercept"),
             pd.Series(to_theta(table[anchor] / 100), index=table.index, name="anchor"),
             np.log(table["population_2020"] / table["area_km2"]).rename("log_density"),
             pd.get_dummies(table["region"], prefix="region", drop_first=True, dtype=float),
             pd.get_dummies(table["department_code"], prefix="dep", drop_first=True, dtype=float)]
    X = pd.concat(parts, axis=1)
    return X.to_numpy(dtype=float), list(X.columns)


def estimate_window(table: pd.DataFrame, households: pd.DataFrame, anchor: str) -> pd.DataFrame:
    """Fit one window on its sampled districts and estimate every district that has the anchor map."""
    base = table[table[anchor].notna() & table["population_2020"].notna()].copy()
    direct = direct_estimates(households)
    deff = design_effects(households)
    base = base.merge(direct, on="ubigeo", how="left")
    y = to_theta(base["rate"].to_numpy(dtype=float))
    D = sampling_variance(base["n_eff"].to_numpy(dtype=float), base["department_code"].map(deff).to_numpy(dtype=float))
    X, _ = covariates(base, anchor)
    sampled = ~np.isnan(y)
    model = fit(y[sampled], X[sampled], D[sampled])
    prediction = predict(model, X, y, D)
    targets = weighted_poverty(households, by="department").to_dict()
    raw = to_rate(prediction.theta)
    rate = benchmark(raw, base["population_2020"], base["department_code"], targets)
    ratio = np.divide(rate, raw, out=np.ones_like(rate), where=raw > 0)
    half = 1.96 * np.sqrt(prediction.mse)
    out = base[["ubigeo", "department", "province", "district", "population_2020", "households"]].copy()
    out["households"] = out["households"].fillna(0).astype(int)
    out["direct_rate_pct"] = base["rate"] * 100
    out["gamma"] = prediction.gamma
    out["rate_before_benchmark_pct"] = raw * 100
    out["rate_pct"] = rate * 100
    out["low_pct"] = np.clip(to_rate(prediction.theta - half) * ratio, 0, 1) * 100
    out["high_pct"] = np.clip(to_rate(prediction.theta + half) * ratio, 0, 1) * 100
    out.attrs["sigma2"] = model.sigma2
    return out


def score(pred: np.ndarray, truth: np.ndarray, low: np.ndarray, high: np.ndarray, weight: np.ndarray) -> dict:
    return {"mae": float(np.abs(pred - truth).mean()),
            "mae_population_weighted": float(np.average(np.abs(pred - truth), weights=weight)),
            "correlation": float(np.corrcoef(pred, truth)[0, 1]),
            "inside_inei_interval": float(((pred >= low) & (pred <= high)).mean()),
            "n": int(len(pred))}


def validate(estimate: pd.DataFrame, table: pd.DataFrame, households: pd.DataFrame, enaho_2013: pd.DataFrame) -> dict:
    """Score the 2017-19 model and two simple baselines against the 2018 map."""
    d = estimate.merge(table[["ubigeo", "department_code", "poverty", "poverty_low", "poverty_high", "poverty_2013"]],
                       on="ubigeo").dropna(subset=["poverty", "poverty_2013"])
    window_rate = weighted_poverty(households, by="department")
    change = (window_rate - weighted_poverty(enaho_2013, by="department")) * 100
    baseline = (d["poverty_2013"] + d["department_code"].map(change)).clip(0, 100) / 100
    baseline = benchmark(baseline, d["population_2020"], d["department_code"], window_rate.to_dict()) * 100
    truth, low, high, weight = (d[c].to_numpy(dtype=float) for c in ["poverty", "poverty_low", "poverty_high", "population_2020"])
    model = d["rate_pct"].to_numpy()
    sampled = d["households"].to_numpy() > 0
    results = {
        "modelo": score(model, truth, low, high, weight),
        "linea_base_mapa_2013_mas_cambio_departamental": score(baseline, truth, low, high, weight),
        "mapa_2013_sin_cambios": score(d["poverty_2013"].to_numpy(), truth, low, high, weight),
        "modelo_distritos_con_muestra": score(model[sampled], truth[sampled], low[sampled], high[sampled], weight[sampled]),
        "linea_base_distritos_con_muestra": score(baseline[sampled], truth[sampled], low[sampled], high[sampled], weight[sampled]),
        "modelo_distritos_sin_muestra": score(model[~sampled], truth[~sampled], low[~sampled], high[~sampled], weight[~sampled]),
        "linea_base_distritos_sin_muestra": score(baseline[~sampled], truth[~sampled], low[~sampled], high[~sampled], weight[~sampled]),
    }
    results["acepta_modelo"] = results["modelo"]["mae"] < results["linea_base_mapa_2013_mas_cambio_departamental"]["mae"]
    return results


def main() -> None:
    log = Bitacora()
    panel_districts = pd.read_csv(PROCESADOS / "distritos.csv", dtype={"ubigeo": str})
    regions = gpd.read_file(ORIGINALES / "limites" / "distritos_geocatmin.geojson", ignore_geometry=True)[
        ["CD_DIST", "REG_NAT"]].rename(columns={"CD_DIST": "ubigeo", "REG_NAT": "region"})
    map_2013 = read_poverty_2013(ORIGINALES / "inei" / "mapa_pobreza_2013_anexo_estadistico.xlsx")
    log.add("pobreza_2013", "distritos del Mapa de Pobreza 2013 (INEI)", len(map_2013), int(map_2013.ubigeo.isin(panel_districts.ubigeo).sum()),
            f"{int(map_2013.split_2013.sum())} distritos partidos en grupos, colapsados por población; "
            f"{int(map_2013.grouped_2013.sum())} estimados en conjunto con otro distrito")
    table = panel_districts.merge(map_2013, on="ubigeo", how="left").merge(regions, on="ubigeo", how="left")
    table["department_code"] = table["ubigeo"].str[:2]
    table["region"] = table["region"].fillna("SIN DATO")
    table[["ubigeo", "population_2015", "poverty_2013", "poverty_low_2013", "poverty_high_2013", "split_2013",
           "grouped_2013"]].dropna(subset=["poverty_2013"]).to_csv(PROCESADOS / "pobreza_mapa_2013.csv", index=False)

    frames, series, national = {}, [], {}
    rule = {}
    for year, code in ENAHO_CODES.items():
        df = read_sumaria(ORIGINALES / "enaho" / f"{code}-Modulo34.zip", year)
        frames[year] = df
        national[year] = weighted_poverty(df)
        rule[year] = float(((df.gashog2d / (12 * df.mieperho) < df.linea) == df.poor).mean())
        series.append(weighted_poverty(df, by="department").rename("rate").reset_index().assign(year=year))
        log.add("enaho", f"hogares de Sumaria {year}", len(df), len(df),
                f"{df.ubigeo.nunique()} distritos en la muestra; {int(df.ubigeo.isin(panel_districts.ubigeo).sum())} hogares en distritos del panel")
    assert abs(national[2024] - OFFICIAL_2024) < 5e-4, f"national poverty 2024 is {national[2024]:.4f}"
    assert min(rule.values()) > 0.99, f"poverty does not follow spending vs line: {rule}"
    department = pd.concat(series, ignore_index=True)
    department["rate_pct"] = department.pop("rate") * 100
    department.to_csv(PROCESADOS / "pobreza_departamental.csv", index=False)

    estimates, summary = [], {}
    for name, (years, anchor) in WINDOWS.items():
        households = pd.concat([frames[y] for y in years], ignore_index=True)
        estimate = estimate_window(table, households, anchor)
        gamma = estimate.gamma[estimate.households > 0]
        summary[name] = {"anios": list(years), "predictor_oficial": anchor, "sigma2": estimate.attrs["sigma2"],
                         "distritos_estimados": int(len(estimate)), "distritos_con_muestra": int((estimate.households > 0).sum()),
                         "hogares_por_distrito_mediana": float(estimate.households[estimate.households > 0].median()),
                         "gamma_mediana": float(gamma.median()), "gamma_p10": float(gamma.quantile(.1)), "gamma_p90": float(gamma.quantile(.9)),
                         "ancho_intervalo_mediano_pp": float((estimate.high_pct - estimate.low_pct).median())}
        if name == "2017-19":
            summary["validacion_contra_mapa_2018"] = validate(estimate, table, households, frames[2013])
        estimate.insert(0, "window", name)
        estimates.append(estimate)
        log.add("pobreza_estimada", f"Fay-Herriot {name}", len(households), len(estimate),
                f"{summary[name]['distritos_con_muestra']} distritos con muestra; γ mediana {summary[name]['gamma_mediana']:.2f}")
    pd.concat(estimates, ignore_index=True).to_csv(PROCESADOS / "pobreza_estimada.csv", index=False)
    summary["pobreza_nacional_por_anio"] = {int(y): float(v) for y, v in national.items()}
    summary["regla_gasto_contra_linea"] = rule
    (PROCESADOS / "validacion_pobreza.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    path = PROCESADOS / "bitacora_limpieza.json"
    previous = json.loads(path.read_text(encoding="utf-8"))["steps"]
    kept = [s for s in previous if s["source"] not in {"enaho", "pobreza_2013", "pobreza_estimada"}]
    log.steps = kept + log.steps
    log.save(path)
    print(json.dumps(summary, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
