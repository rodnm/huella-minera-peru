"""Try to break the data and the findings; write the results to datos/procesados/auditoria.json.

Run from the repository root, after scripts.analizar_datos: uv run python -m scripts.auditar_datos
It changes nothing else. It checks the downloaded files against the manifest, MINEM's sums against its own totals,
the light for gaps and unexplained jumps, and how much each finding moves when its definitions change.
"""
import glob
import json
import warnings
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import statsmodels.formula.api as smf
from rasterio.features import geometry_mask
from scipy.stats import fisher_exact

from brillo.analisis import cross_section, mine_openings
from brillo.descarga import sha256
from brillo.distritos import load_districts
from brillo.luz import zonal_sum
from brillo.mapbiomas import pixel_area_km2
from brillo.minem import DOUBLE_COUNTED_STAGES, MAIN_METALS, normalize_text, read_production

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
ORI, INT, PRO = ROOT / "datos" / "originales", ROOT / "datos" / "intermedios", ROOT / "datos" / "procesados"
BASELINE = "poverty ~ mining + log_pop + log_area + C(department)"


def audit_manifest() -> dict:
    manifest = json.loads((ORI / "MANIFEST.json").read_text(encoding="utf-8"))
    missing = [n for n, e in manifest.items() if not (ORI / e["file"]).exists()]
    changed = [n for n, e in manifest.items() if n not in missing and sha256(ORI / e["file"]) != e["sha256"]]
    return {"archivos": len(manifest), "faltantes": missing, "hash_distinto": changed}


def audit_panel(p: pd.DataFrame) -> dict:
    return {"filas": len(p), "claves_unicas": int(p[["ubigeo", "year"]].drop_duplicates().shape[0]),
            "distritos": int(p.ubigeo.nunique()), "anios": [int(p.year.min()), int(p.year.max())],
            "nulos": {c: int(p[c].isna().sum()) for c in ["light_sum", "mining_km2", "poverty", "population_2020"]},
            "poblacion_2020": int(p[p.year == 2018].population_2020.sum()), "area_km2": round(float(p[p.year == 2018].area_km2.sum()))}


def audit_minem() -> dict:
    """Our sum of every unit against the national total MINEM publishes in METALES.xlsx, 2013-2019."""
    base = INT / "minem" / "produccion" / "5472883-2001-2020"
    gaps = {}
    for year in range(2013, 2020):
        frames = [read_production(f, year) for f in sorted(glob.glob(str(base / str(year) / "*.xls*")))
                  if not any(k in Path(f).name.upper() for k in ["METALES", "NO-MET", "CARBON", "CONCENT", "OTROS"])]
        d = pd.concat(frames)
        ours = d[~d.stage.isin(DOUBLE_COUNTED_STAGES)].groupby("metal").quantity.sum()
        sheet = pd.read_excel(base / str(year) / "METALES.xlsx", sheet_name=0, header=None)
        metal = None
        for i in range(len(sheet)):
            label = normalize_text(sheet.iloc[i, 0])
            if " (" in label and label.split(" (")[0] in MAIN_METALS:
                metal = label.split(" (")[0]
            elif metal and label.startswith("CONCENTRACION"):
                values = [v for v in sheet.iloc[i, 1:].tolist() if isinstance(v, (int, float)) and pd.notna(v)]
                gaps[f"{metal}_{year}"] = float(ours.get(metal, np.nan) / values[-1] - 1)
                metal = None
    return {"comparaciones": len(gaps), "diferencia_maxima_abs": max(abs(v) for v in gaps.values()),
            "alcance": "2013-2019; 2020-2025 no se cruzaron con totales de MINEM"}


def audit_light(districts: gpd.GeoDataFrame) -> tuple[dict, tuple]:
    with rasterio.open(INT / "luz" / "vnp46a4_2018.tif") as src:
        grid, shape, crs = src.transform, (src.height, src.width), src.crs
    inside = geometry_mask(districts.geometry, out_shape=shape, transform=grid, invert=True)
    rows = {}
    for year in range(2013, 2026):
        with rasterio.open(INT / "luz" / f"vnp46a4_{year}.tif") as src:
            v = src.read(1, masked=True).filled(np.nan).astype("float64")[inside]
        clean = np.clip(np.nan_to_num(v), 0, None)
        rows[year] = {"sin_dato_pct": float(np.isnan(v).mean() * 100), "suma": float(clean.sum()),
                      "suma_1nW_o_mas": float(clean[clean >= 1].sum()), "pixeles_1nW_o_mas": int((clean >= 1).sum()),
                      "pct_bajo_1nW": float(clean[clean < 1].sum() / clean.sum() * 100)}
    total = pd.Series({y: r["suma"] for y, r in rows.items()})
    lit = pd.Series({y: r["pixeles_1nW_o_mas"] for y, r in rows.items()})
    return {"por_anio": rows, "cambio_primero_ultimo": float(total.iloc[-1] / total.iloc[0] - 1),
            "cambio_anual_pct": (total.pct_change() * 100).round(1).dropna().to_dict(),
            "cambio_anual_pixeles_iluminados_pct": (lit.pct_change() * 100).round(1).dropna().to_dict(),
            "aviso": "Sin segunda fuente de luz que lo confirme; los saltos de 2020 y 2022 no están explicados."}, (grid, crs)


def audit_light_gap(cs: pd.DataFrame, districts, grid, crs) -> dict:
    mine, rest = cs[cs.mining], cs[~cs.mining]
    with rasterio.open(INT / "luz" / "vnp46a4_2018.tif") as src:
        light = np.clip(np.nan_to_num(src.read(1, masked=True).filled(np.nan).astype("float64")), 0, None)
    with rasterio.open(INT / "huella" / "mineria_frac_2018.tif") as src:
        fraction = src.read(1)
    area = pixel_area_km2(grid, fraction.shape)
    sub = districts[districts.ubigeo.isin(cs.ubigeo)]
    total = zonal_sum(light, grid, crs, sub)
    ids = [u for u in total.index if u in set(mine.ubigeo)]
    cachachi = districts[districts.district == "CACHACHI"].ubigeo.iloc[0]
    share = {}
    for threshold in [0, 0.05, 0.1, 0.25, 0.5]:
        on = total - zonal_sum(np.where(fraction > threshold, 0.0, light), grid, crs, sub)
        share[str(threshold)] = {"agregado": float(on[ids].sum() / total[ids].sum()), "distrito_mediano": float((on[ids] / total[ids]).median()),
                                 "cachachi": float(on[cachachi] / total[cachachi])}
    return {"razon_por_habitante": {"mediana": float(mine.light_per_capita.median() / rest.light_per_capita.median()),
                                    "promedio": float(mine.light_per_capita.mean() / rest.light_per_capita.mean()),
                                    "agregada": float((mine.light_sum.sum() / mine.population_2020.sum()) / (rest.light_sum.sum() / rest.population_2020.sum()))},
            "area_pixeles_con_mina_km2": float(area[fraction > 0].sum()), "area_minera_km2": float((fraction * area).sum()),
            "luz_sobre_mina_segun_umbral_de_fraccion": share}


def audit_poverty_gap(cs: pd.DataFrame, p: pd.DataFrame) -> dict:
    regions = gpd.read_file(ORI / "limites" / "distritos_geocatmin.geojson", ignore_geometry=True)[["CD_DIST", "REG_NAT"]].rename(columns={"CD_DIST": "ubigeo"})
    d = cs.merge(regions, on="ubigeo", how="left")
    d = d.assign(log_pop=np.log(d.population_2020), log_area=np.log(d.area_km2), log_density=np.log(d.population_2020 / d.area_km2),
                 log_lpc=np.log1p(d.light_per_capita * 1000), province_id=d.ubigeo.str[:4])
    output = pd.read_csv(PRO / "produccion_distrito_anio.csv", dtype={"ubigeo": str})
    output = output[output.year.between(2016, 2018)].groupby("ubigeo")[[c for c in output.columns if c.startswith("tonnes_")]].sum()
    top = (output / output.sum()).sum(axis=1).sort_values(ascending=False).head(30).index

    def run(data, formula=BASELINE, cluster=None, weights=None):
        model = smf.wls(formula, data, weights=weights if weights is not None else np.ones(len(data)))
        fitted = model.fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(data[cluster])[0]}) if cluster else model.fit(cov_type="HC1")
        low, high = fitted.conf_int().loc["mining[T.True]"]
        return {"coef": float(fitted.params["mining[T.True]"]), "low": float(low), "high": float(high), "mineros": int(data.mining.sum())}

    new_provinces = set(p[p.poverty.isna()].ubigeo.str[:4])
    return {"base": run(d), "agrupado_por_provincia": run(d, cluster="province_id"), "agrupado_por_departamento": run(d, cluster="department"),
            "ponderado_por_poblacion": run(d, weights=d.population_2020), "con_region_natural": run(d, BASELINE + " + C(REG_NAT)"),
            "sin_lima": run(d[~d.department.isin(["LIMA", "CALLAO"])]), "sin_provincias_con_distritos_nuevos": run(d[~d.province_id.isin(new_provinces)]),
            "huella_de_1_km2_o_mas": run(d.assign(mining=d.mining & (d.mining_km2 >= 1))), "top_30_productores": run(d.assign(mining=d.ubigeo.isin(top))),
            "misma_luz_por_habitante": run(d, "poverty ~ mining + log_lpc + log_pop + log_area + C(department)")}


def audit_paradox(cs: pd.DataFrame) -> dict:
    median = cs.groupby("department").poverty.transform("median")
    confirmed = cs.poverty_low > median
    out = {}
    for q in [0.5, 0.7, 0.75, 0.8, 0.9]:
        bright = cs.light_per_capita > cs.light_per_capita.quantile(q)
        a, b = int((bright & cs.mining & confirmed).sum()), int((bright & cs.mining).sum())
        c, e = int((bright & ~cs.mining & confirmed).sum()), int((bright & ~cs.mining).sum())
        out[str(q)] = {"mineros": [a, b], "no_mineros": [c, e], "p_fisher": float(fisher_exact([[a, b - a], [c, e - c]])[1])}
    return {"por_umbral_de_luz": out, "confirmados_todos_los_distritos": {"mineros": float(confirmed[cs.mining].mean()), "no_mineros": float(confirmed[~cs.mining].mean())}}


def audit_openings(p: pd.DataFrame) -> dict:
    ever = set(p[p.mining].ubigeo)
    rows = []
    for r in mine_openings(p, first=2015, last=2022).itertuples():
        department = p[p.ubigeo == r.ubigeo].department.iloc[0]
        control = p[(p.department == department) & ~p.ubigeo.isin(ever)]
        before = control[control.year.between(r.start - 2, r.start - 1)].groupby("ubigeo").light_sum.mean()
        after = control[control.year.between(r.start + 1, r.start + 3)].groupby("ubigeo").light_sum.mean()
        rows.append({"ratio": r.ratio, "control": (after / before.replace(0, np.nan)).median()})
    o = pd.DataFrame(rows)
    excess = o.ratio / o.control
    return {"aperturas": len(o), "razon_mediana": float(o.ratio.median()), "control_mediano": float(o.control.median()),
            "exceso_mediano": float(excess.median()), "share_exceso_mayor_1": float((excess > 1).mean())}


def main() -> None:
    p = pd.read_csv(PRO / "panel_distrito_anio.csv", dtype={"ubigeo": str})
    districts = load_districts(ORI / "limites" / "distritos_geocatmin.geojson")
    cs = cross_section(p)
    light, (grid, crs) = audit_light(districts)
    f18 = p[p.year == 2018].set_index("ubigeo").mining_km2
    mining_ids = set(cs[cs.mining].ubigeo)
    result = {
        "manifest": audit_manifest(), "panel": audit_panel(p), "minem_contra_sus_totales": audit_minem(), "luz": light,
        "brecha_de_luz": audit_light_gap(cs, districts, grid, crs), "brecha_de_pobreza": audit_poverty_gap(cs, p),
        "paradoja": audit_paradox(cs), "aperturas_contra_control": audit_openings(p),
        "huella": {"km2_2018_en_distritos_mineros_minem": float(f18[f18.index.isin(mining_ids)].sum()), "km2_2018_total": float(f18.sum()),
                   "distritos_mineros_sin_huella_visible": int((f18[f18.index.isin(mining_ids)] < 0.01).sum()), "distritos_mineros": len(mining_ids)},
    }
    (PRO / "auditoria.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("auditoria ->", PRO / "auditoria.json")


if __name__ == "__main__":
    main()
