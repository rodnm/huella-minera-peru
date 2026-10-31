"""Write the files the Streamlit app reads into datos/atlas, and its theme into .streamlit/config.toml.

Run from the repository root, after the contrast step: uv run python -m scripts.construir_atlas
"""
import json
from pathlib import Path

import pandas as pd
import shapely

from brillo.atlas import MIN_DISTRICT_KM2, describe, footprint_pixels, panel_payload
from brillo.distritos import load_districts

ROOT = Path(__file__).resolve().parent.parent
ORIGINALES = ROOT / "datos" / "originales"
INTERMEDIOS = ROOT / "datos" / "intermedios"
PROCESADOS = ROOT / "datos" / "procesados"
DATA = ROOT / "datos" / "atlas"
SIMPLIFY_DEGREES = 0.01  # about 1 km: light enough to resend on every year change, and every district keeps its shape
MIN_PIXEL_SHARE = 0.01  # about 0.2 ha of a 21 ha pixel: fewer than three 30 m pixels are classification specks


def write_json(path: Path, content) -> None:
    path.write_text(json.dumps(content, ensure_ascii=False, allow_nan=False, separators=(",", ":")), encoding="utf-8")


def district_geometries(path: Path) -> tuple[dict, dict]:
    """Simplified districts and department outlines; shared borders stay shared thanks to the coverage simplifier."""
    districts = load_districts(path).to_crs("EPSG:4326")
    simple = shapely.coverage_simplify(districts.geometry.values, SIMPLIFY_DEGREES)
    districts = districts.assign(geometry=shapely.set_precision(simple, 0.001)).loc[lambda d: ~d.geometry.is_empty]
    features = json.loads(districts[["ubigeo", "geometry"]].to_json(drop_id=True))
    outlines = districts.assign(code=districts["ubigeo"].str[:2]).dissolve("code", as_index=False)[["code", "geometry"]]
    return features, json.loads(outlines.boundary.to_frame("geometry").to_json(drop_id=True))


def streamlit_config(tokens: dict) -> str:
    """App theme from the design tokens, so that the app, the charts and the reel share one palette."""
    surface = tokens["surface"]
    return f"""[theme]
base = "dark"
primaryColor = "{tokens['ramps']['footprint'][4]}"
backgroundColor = "{surface['background']}"
secondaryBackgroundColor = "{surface['panel']}"
textColor = "{surface['text']}"
borderColor = "{surface['grid']}"

[client]
toolbarMode = "minimal"

[browser]
gatherUsageStats = false
"""


def official_totals(path: Path) -> dict:
    table = pd.read_csv(path)
    totals = table.groupby("year")[["mining_km2", "official_km2"]].sum()
    gap = totals["mining_km2"] / totals["official_km2"] - 1
    return {"official_km2": {str(y): round(float(v), 1) for y, v in totals["official_km2"].items()},
            "max_national_gap": float(gap.abs().max())}


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    panel = pd.read_csv(PROCESADOS / "panel_distrito_anio.csv", dtype={"ubigeo": str}, low_memory=False)

    atlas = describe(panel)
    atlas["validation"] = official_totals(PROCESADOS / "validacion_huella.csv")
    atlas["contrast"] = json.loads((PROCESADOS / "contraste_huella.json").read_text(encoding="utf-8"))
    madre = atlas["contrast"]["madre_de_dios"]
    covered = madre["periods"]["gain_km2"]["mapbiomas"] / atlas["increase_km2"]
    atlas["contrast"]["share_of_increase_contrasted"] = covered
    names = panel.assign(code=panel["ubigeo"].str[:2]).drop_duplicates("code").set_index("code")["department"]
    for row in atlas["contrast"]["other_departments"]:
        row["name"] = names[row["department"]]
    (PROCESADOS / "atlas.json").write_text(json.dumps(atlas, ensure_ascii=False, indent=2), encoding="utf-8")
    write_json(DATA / "atlas.json", atlas)
    payload = panel_payload(panel)
    for i, year in enumerate(payload["years"]):
        counted = sum((d["m"][i] or 0) >= MIN_DISTRICT_KM2 for d in payload["districts"])
        assert counted == atlas["districts_with_footprint"][str(year)], f"rounding changes the district count in {year}"
    write_json(DATA / "panel.json", payload)

    features, outlines = district_geometries(ORIGINALES / "limites" / "distritos_geocatmin.geojson")
    write_json(DATA / "distritos.json", features)
    write_json(DATA / "departamentos.json", outlines)

    years = sorted(panel["year"].unique())
    meta, blob = footprint_pixels({int(y): INTERMEDIOS / "huella" / f"mineria_frac_{y}.tif" for y in years},
                                  MIN_PIXEL_SHARE)
    write_json(DATA / "huella.json", meta)
    (DATA / "huella.bin").write_bytes(blob)

    tokens = json.loads((ROOT / "design" / "tokens.json").read_text(encoding="utf-8"))
    write_json(DATA / "tokens.json", {key: tokens[key] for key in ("surface", "series", "ramps")})
    config = ROOT / ".streamlit" / "config.toml"
    config.parent.mkdir(exist_ok=True)
    config.write_text(streamlit_config(tokens), encoding="utf-8")

    for path in sorted(DATA.iterdir()):
        print(f"{path.name:<22} {path.stat().st_size / 1e6:6.2f} MB")


if __name__ == "__main__":
    main()
