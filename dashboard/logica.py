"""Figures and texts of the atlas, apart from Streamlit so they can be tested.

Everything is computed from datos/atlas, which scripts/construir_atlas.py writes from datos/procesados, so no number
in the app is typed by hand.
"""
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

ATLAS_DIR = Path(__file__).resolve().parent.parent / "datos" / "atlas"
PERU_BOUNDS = ((-81.4, -18.4), (-68.6, 0.1))
MADRE_DE_DIOS = "MADRE DE DIOS"
VISIBLE_KM2 = 0.01
TOP_DISTRICTS = 10
OUTSIDE_ALPHA = 60
SMALL_WORDS = {"de", "del", "la", "las", "los", "y", "el", "en"}


def title_case(text: str) -> str:
    words = text.lower().split(" ")
    return " ".join(word if i and word in SMALL_WORDS else word[:1].upper() + word[1:] for i, word in enumerate(words))


def km2(value: float) -> str:
    if value >= 100:
        return f"{value:,.0f}"
    return f"{value:,.1f}" if value >= 1 else f"{value:,.2f}"


def percent(share: float) -> str:
    return f"{share * 100:,.0f} %"


def rgb(color: str, alpha: int = 255) -> list[int]:
    return [int(color[i:i + 2], 16) for i in (1, 3, 5)] + [alpha]


@dataclass(frozen=True)
class Atlas:
    years: list[int]
    districts: pd.DataFrame
    mining: np.ndarray
    light: np.ndarray
    summary: dict
    tokens: dict
    geo: dict
    outlines: dict
    pixel_lon: np.ndarray
    pixel_lat: np.ndarray
    pixel_area: np.ndarray
    pixel_shares: np.ndarray
    pixel_years: list[int]
    min_fraction: float
    light_thresholds: list[float]


def load_atlas(folder: Path = ATLAS_DIR) -> Atlas:
    read = lambda name: json.loads((folder / f"{name}.json").read_text(encoding="utf-8"))
    panel, meta = read("panel"), read("huella")
    rows = panel["districts"]
    districts = pd.DataFrame({
        "ubigeo": [d["u"] for d in rows], "name": [d["n"] for d in rows], "province": [d["p"] for d in rows],
        "department": [d["d"] for d in rows], "population": [d["pop"] for d in rows],
        "poverty": [d["pov"][0] if d["pov"] else np.nan for d in rows],
        "poverty_low": [d["pov"][1] if d["pov"] else np.nan for d in rows],
        "poverty_high": [d["pov"][2] if d["pov"] else np.nan for d in rows],
    })
    mining = np.array([d["m"] for d in rows], dtype="float64")
    light = np.array([d["l"] for d in rows], dtype="float64")

    blob = (folder / "huella.bin").read_bytes()
    n, years = meta["count"], len(meta["years"])
    pixel_rows = np.frombuffer(blob, "<u2", n, 0)
    pixel_cols = np.frombuffer(blob, "<u2", n, 2 * n)
    shares = np.frombuffer(blob, "u1", n * years, 4 * n).reshape(n, years)
    left, dx, top, dy = meta["transform"]
    lat = top + (pixel_rows + 0.5) * dy
    area = dx * 111320 * np.cos(np.radians(lat)) * abs(dy) * 110574

    positive = light[np.nan_to_num(light) > 0]
    thresholds = [float(q) for q in np.quantile(positive, [0.15, 0.3, 0.45, 0.6, 0.75, 0.9])] if positive.size else []
    return Atlas(panel["years"], districts, np.nan_to_num(mining), light, read("atlas"), read("tokens"), read("distritos"),
                 read("departamentos"), left + (pixel_cols + 0.5) * dx, lat, area, shares, meta["years"],
                 meta["min_fraction"], thresholds)


def scope_mask(atlas: Atlas, department: str) -> np.ndarray:
    return (atlas.districts["department"] == department).to_numpy() if department else np.ones(len(atlas.districts), bool)


def kpis(atlas: Atlas, department: str, i: int) -> dict:
    """The four headline figures for the filtered area and year; None where a figure would say nothing true."""
    mask = scope_mask(atlas, department)
    now, first = atlas.mining[mask, i], atlas.mining[mask, 0]
    area, base = float(now.sum()), float(first.sum())
    gains = np.sort((now - first)[now > first])[::-1]
    change = area - base
    has_top = i > 0 and change > 0 and gains.size > TOP_DISTRICTS
    return {
        "area": area, "base": base, "change": change,
        "ratio": area / base if i > 0 and base > 0 else None,
        "districts": int((now >= VISIBLE_KM2).sum()), "districts_first": int((first >= VISIBLE_KM2).sum()),
        "gains": int(gains.size),
        "top_share": min(float(gains[:TOP_DISTRICTS].sum() / change), 1.0) if has_top else None,
    }


@dataclass(frozen=True)
class Indicator:
    label: str
    unit: str
    title: Callable[[str], str]
    note: Callable[[int], str]
    format: Callable[[float], str]
    ramp: str


INDICATORS = {
    "huella": Indicator("Huella minera", "km²", lambda s: f"Distritos con mayor huella, {s}",
                        lambda y: f"Superficie clasificada como minería en {y}.", km2, "footprint"),
    "nueva": Indicator("Huella nueva desde 2013", "km²", lambda s: f"Distritos donde más creció la huella, {s}",
                       lambda y: f"Diferencia entre {y} y 2013. Solo aparecen los distritos donde aumentó.", km2, "footprint"),
    "luz": Indicator("Luz nocturna por km²", "nW/cm²/sr", lambda s: f"Distritos con más luz por km², {s}",
                     lambda y: f"Radiancia sumada por km² en {y}, NASA Black Marble. Es contexto: no mide minería.",
                     lambda v: f"{v:,.2f}", "light"),
    "pobreza": Indicator("Pobreza monetaria 2018", "%", lambda s: f"Distritos con mayor pobreza estimada, {s}",
                         lambda _: "Punto medio e intervalo de 95 % del Mapa de Pobreza 2018 del INEI. No cambia con el año "
                                   "elegido y es contexto: no prueba una relación con la minería.",
                         lambda v: f"{v:,.1f} %", "poverty"),
}
NEW_THRESHOLDS = [0.1, 0.5, 1, 5, 20, 100]
POVERTY_THRESHOLDS = [10, 20, 30, 40, 50, 60]


def indicator_values(atlas: Atlas, indicator: str, i: int) -> np.ndarray:
    if indicator == "huella":
        return atlas.mining[:, i]
    if indicator == "nueva":
        return atlas.mining[:, i] - atlas.mining[:, 0]
    if indicator == "luz":
        return atlas.light[:, i]
    return atlas.districts["poverty"].to_numpy()


def thresholds_for(atlas: Atlas, indicator: str) -> list[float]:
    return {"nueva": NEW_THRESHOLDS, "luz": atlas.light_thresholds, "pobreza": POVERTY_THRESHOLDS}.get(indicator, [])


def ranking(atlas: Atlas, indicator: str, department: str, i: int, top: int = TOP_DISTRICTS) -> list[dict]:
    values = indicator_values(atlas, indicator, i)
    table = atlas.districts.assign(value=values)[scope_mask(atlas, department)].dropna(subset=["value"])
    if indicator != "pobreza":
        table = table[table["value"] > 0]
    spec = INDICATORS[indicator]
    return [{"ubigeo": row.ubigeo, "name": title_case(row.name), "department": title_case(row.department),
             "value": float(row.value), "label": spec.format(float(row.value)),
             "low": None if math.isnan(row.poverty_low) else float(row.poverty_low),
             "high": None if math.isnan(row.poverty_high) else float(row.poverty_high)}
            for row in table.sort_values("value", ascending=False).head(top).itertuples(name="Row", index=False)
            ] if len(table) else []


def department_rows(atlas: Atlas, i: int, top: int = 12) -> pd.DataFrame:
    table = pd.DataFrame({"department": atlas.districts["department"], "now": atlas.mining[:, i], "first": atlas.mining[:, 0]})
    table = table.groupby("department", as_index=False).sum()
    table = table[(table["now"] >= 1) | (table["first"] >= 1)].sort_values("now", ascending=False).head(top)
    return table.assign(name=table["department"].map(title_case), label=table["now"].map(km2))


def points_for_year(atlas: Atlas, year: int) -> list[dict]:
    """One circle per 500 m cell with footprint that year; its area equals the mining land in the cell."""
    i = atlas.pixel_years.index(year)
    footprint = atlas.tokens["ramps"]["footprint"]
    old, new = rgb(footprint[2]), rgb(footprint[6])
    first_min = math.ceil(atlas.min_fraction * 255)
    shares = atlas.pixel_shares[:, i]
    keep = np.nonzero(shares > 0)[0]
    radius = np.sqrt(shares[keep] / 255 * atlas.pixel_area[keep] / math.pi)
    existed = atlas.pixel_shares[keep, 0] >= first_min
    return [{"p": [round(float(x), 4), round(float(y), 4)], "r": round(float(r), 1), "c": old if e else new}
            for x, y, r, e in zip(atlas.pixel_lon[keep], atlas.pixel_lat[keep], radius, existed)]


def district_features(atlas: Atlas, indicator: str, department: str, i: int) -> dict:
    """Districts painted by the indicator, with the text of their tooltip. Other departments stay dim."""
    surface = atlas.tokens["surface"]
    spec = INDICATORS[indicator]
    values = indicator_values(atlas, indicator, i)
    thresholds = thresholds_for(atlas, indicator)
    ramp = atlas.tokens["ramps"][spec.ramp]
    in_scope = scope_mask(atlas, department)
    by_ubigeo = {u: k for k, u in enumerate(atlas.districts["ubigeo"])}
    features = []
    for feature in atlas.geo["features"]:
        k = by_ubigeo.get(feature["properties"]["ubigeo"])
        if k is None:
            continue
        value = float(values[k])
        alpha = 255 if in_scope[k] else OUTSIDE_ALPHA
        empty = math.isnan(value) or indicator == "huella" or (indicator == "nueva" and value < VISIBLE_KM2)
        color = surface["panel"] if empty else ramp[int(np.searchsorted(thresholds, value, side="right"))]
        shown = "sin dato" if math.isnan(value) else spec.format(value) + ("" if spec.unit == "%" else f" {spec.unit}")
        features.append({"type": "Feature", "geometry": feature["geometry"], "properties": {
            "ubigeo": feature["properties"]["ubigeo"], "fill": rgb(color, alpha),
            "nombre": title_case(atlas.districts["name"].iat[k]),
            "departamento": title_case(atlas.districts["department"].iat[k]), "valor": shown}})
    return {"type": "FeatureCollection", "features": features}


def fit_view(bounds, width: int = 860, height: int = 720, padding: int = 36) -> dict:
    """Center and zoom that show the bounds on a Web Mercator map of that size."""
    (west, south), (east, north) = bounds
    project = lambda lat: math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))
    x_span = max(east - west, 1e-6) / 360
    y_span = max(project(north) - project(south), 1e-6) / (2 * math.pi)
    zoom = min(math.log2((width - 2 * padding) / (512 * x_span)), math.log2((height - 2 * padding) / (512 * y_span)))
    middle = (project(north) + project(south)) / 2
    return {"longitude": (west + east) / 2, "latitude": math.degrees(2 * math.atan(math.exp(middle)) - math.pi / 2),
            "zoom": round(zoom, 2)}


def bounds_of(atlas: Atlas, ubigeos: set[str]) -> tuple:
    west, south, east, north = math.inf, math.inf, -math.inf, -math.inf

    def walk(coordinates):
        nonlocal west, south, east, north
        if isinstance(coordinates[0], (int, float)):
            west, east = min(west, coordinates[0]), max(east, coordinates[0])
            south, north = min(south, coordinates[1]), max(north, coordinates[1])
        else:
            for part in coordinates:
                walk(part)

    for feature in atlas.geo["features"]:
        if feature["properties"]["ubigeo"] in ubigeos:
            walk(feature["geometry"]["coordinates"])
    return ((west, south), (east, north)) if west != math.inf else PERU_BOUNDS


def findings(atlas: Atlas) -> list[tuple[str, str]]:
    a = atlas.summary
    y0, y1 = a["first_year"], a["last_year"]
    first, last = a["national_km2"][str(y0)], a["national_km2"][str(y1)]
    md, leader = a["madre_de_dios"], a["top_districts"][0]
    return [
        (f"La superficie clasificada como minera pasó de {first:,.0f} a {last:,.0f} km²: se multiplicó por {a['ratio']:.1f} en {y1 - y0} años.",
         f"Según MapBiomas Perú, {y0} a {y1}. El área exacta está en discusión y gran parte del aumento se apoya en esta fuente."),
        (f"Madre de Dios explica el {percent(md['share_of_increase'])} del aumento y ya reúne el {percent(md['share_of_last'])} de la huella del país.",
         f"Pasó de {md['first_km2']:,.0f} a {md['last_km2']:,.0f} km². El tramo de 2018 a 2024 tiene una segunda fuente."),
        (f"Diez distritos explican el {percent(a['top_share_of_increase'])} del aumento. {title_case(leader['district'])} pasó de {leader['first_km2']:,.0f} a {leader['last_km2']:,.0f} km².",
         f"Los distritos con huella visible pasaron de {a['districts_with_footprint'][str(y0)]:,} a {a['districts_with_footprint'][str(y1)]:,}: se concentra mucho y también se extiende."),
    ]


def contrast_paragraphs(atlas: Atlas) -> list[str]:
    contrast = atlas.summary["contrast"]
    c, y, y0 = contrast["madre_de_dios"], contrast["madre_de_dios"]["last_confirmed_year"], contrast["years"][0]
    on = [v for year, v in c["mapbiomas_on_amw"].items() if int(year) <= y]
    whole, a, b = c["periods"]["whole"], c["periods"]["first_half"], c["periods"]["second_half"]
    covered = contrast["share_of_increase_contrasted"]
    others = ", ".join(f"{title_case(d['name'])} (×{d['mapbiomas_ratio']:.1f} y ×{d['amw_ratio']:.1f})"
                       for d in contrast["other_departments"])
    return [
        f"Amazon Mining Watch usa otro satélite (Sentinel-2) y otro modelo, así que sirve como comprobación independiente. Solo cubre la cuenca amazónica. Aquí se compara en Madre de Dios entre {y0} y {y}, un tramo que equivale al **{percent(covered)} del aumento nacional**. El {percent(1 - covered)} restante se apoya sobre todo en MapBiomas.",
        f"**Coinciden en la dirección y el lugar.** Ambas se duplican en el periodo (×{whole['mapbiomas']:.2f} y ×{whole['amw']:.2f}). Además, entre {percent(min(on))} y {percent(max(on))} de la superficie de MapBiomas cae en celdas de 500 m con cicatrices, que son solo el {c['cells_with_scars_share'] * 100:.1f} % de las celdas del departamento.",
        f"**No coinciden en el nivel ni en el calendario.** En {y} suman {c['amw_km2'][str(y)]:,.0f} y {c['mapbiomas_km2'][str(y)]:,.0f} km². De {y0} a 2021, MapBiomas crece ×{a['mapbiomas']:.2f} y la otra fuente ×{a['amw']:.2f}; de 2021 a {y}, ×{b['mapbiomas']:.2f} y ×{b['amw']:.2f}. La coincidencia del periodo completo no sirve para fechar los saltos. Amazon Mining Watch acumula cicatrices e indica que su máscara acumulada mide cerca de 1.7 veces lo anotado a mano; MapBiomas clasifica el suelo de cada año.",
        f"**Fuera de Madre de Dios discrepan más:** {others}, en ese orden, de {y0} a {y}. Amazon Mining Watch cubre solo la parte amazónica de varios de ellos y parte de áreas pequeñas, así que estas razones no se comparan directamente.",
    ]


def csv_rows(atlas: Atlas, department: str, i: int) -> pd.DataFrame:
    mask = scope_mask(atlas, department)
    d = atlas.districts[mask]
    return pd.DataFrame({
        "ubigeo": d["ubigeo"], "distrito": d["name"], "provincia": d["province"], "departamento": d["department"],
        "anio": atlas.years[i], "huella_km2": atlas.mining[mask, i], "huella_2013_km2": atlas.mining[mask, 0],
        "luz_por_km2": atlas.light[mask, i], "pobreza_inei_2018": d["poverty"], "pobreza_ic95_inf": d["poverty_low"],
        "pobreza_ic95_sup": d["poverty_high"],
    })
