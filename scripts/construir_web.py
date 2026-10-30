"""Write the files the public atlas reads into web/data and web/assets/tokens.css.

Run from the repository root, after the contrast step: uv run python -m scripts.construir_web
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
WEB = ROOT / "web"
DATA = WEB / "data"
SIMPLIFY_DEGREES = 0.004  # about 400 m: invisible at national zoom, and it divides the file size by ten
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


def tokens_css(tokens: dict) -> str:
    lines = [f"  --{name.replace('_', '-')}: {value};" for name, value in tokens["surface"].items()]
    lines += [f"  --{name}: {value};" for name, value in tokens["series"].items()]
    for name, ramp in tokens["ramps"].items():
        lines += [f"  --{name}-{step}: {value};" for step, value in enumerate(ramp)]
    return ":root {\n" + "\n".join(lines) + "\n}\n"


def official_totals(path: Path) -> dict:
    table = pd.read_csv(path)
    totals = table.groupby("year")[["mining_km2", "official_km2"]].sum()
    gap = totals["mining_km2"] / totals["official_km2"] - 1
    return {"official_km2": {str(y): round(float(v), 1) for y, v in totals["official_km2"].items()},
            "max_national_gap": round(float(gap.abs().max()), 4)}


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    panel = pd.read_csv(PROCESADOS / "panel_distrito_anio.csv", dtype={"ubigeo": str}, low_memory=False)

    atlas = describe(panel)
    atlas["validation"] = official_totals(PROCESADOS / "validacion_huella.csv")
    atlas["contrast"] = json.loads((PROCESADOS / "contraste_huella.json").read_text(encoding="utf-8"))
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
    (WEB / "assets").mkdir(exist_ok=True)
    (WEB / "assets" / "tokens.css").write_text(tokens_css(tokens), encoding="utf-8")

    for path in sorted(DATA.iterdir()):
        print(f"{path.name:<22} {path.stat().st_size / 1e6:6.2f} MB")


if __name__ == "__main__":
    main()
