"""Draw the reel's scene visuals from the project data: every map and chart comes from the same files as the dashboard.

Run from the repository root, after scripts.construir_web and reel's fonts (cd reel && uv run python -m reelkit.fonts):
    uv run python -m scripts.construir_escenas
Frames go to reel/escenas/atlas/<scene>/, 1080 x 960, the reel's visual box. The MapBiomas scenes read the 30 m rasters,
so they show more detail than the 500 m grid of the dashboard.
"""
import json
from pathlib import Path

import numpy as np
import rasterio
import shapely
from PIL import Image, ImageDraw, ImageFont
from rasterio.features import geometry_mask
from rasterio.transform import from_bounds as transform_from_bounds
from rasterio.windows import from_bounds

ROOT = Path(__file__).resolve().parent.parent
WEB_DATA = ROOT / "web" / "data"
OUT = ROOT / "reel" / "escenas" / "atlas"
FONTS = ROOT / "reel" / "recursos" / "fuentes"
MAPBIOMAS = ROOT / "datos" / "originales" / "mapbiomas"
AMW_2024 = ROOT / "datos" / "intermedios" / "huella_amw" / "amw_frac_2024.tif"
PROCESADOS = ROOT / "datos" / "procesados"
SIZE = (1080, 960)
MINING = 30
MADRE_DE_DIOS = "17"
INAMBARI = "170102"

tokens = json.loads((WEB_DATA / "tokens.json").read_text(encoding="utf-8"))
SURFACE, SERIES, FOOTPRINT = tokens["surface"], tokens["series"], tokens["ramps"]["footprint"]
OLD, NEW = FOOTPRINT[2], FOOTPRINT[6]


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    if bold:
        return ImageFont.truetype(FONTS / "IBMPlexSansCondensed-Bold.ttf", size)
    return ImageFont.truetype(FONTS / "IBMPlexSans[wdth,wght].ttf", size)


def rgb(color: str) -> tuple[int, int, int]:
    return tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))


def number(value: float) -> str:
    return f"{value:,.0f}"


def save(image: Image.Image, scene: str, index: int) -> None:
    folder = OUT / scene
    folder.mkdir(parents=True, exist_ok=True)
    image.save(folder / f"{index:03d}.png", optimize=False, compress_level=3)


class Projection:
    """Longitude and latitude to pixels, with longitudes scaled by the cosine of the middle latitude."""

    def __init__(self, bounds, size=SIZE, margin=40):
        west, south, east, north = bounds
        self.kx = np.cos(np.radians((south + north) / 2))
        scale = min((size[0] - 2 * margin) / ((east - west) * self.kx), (size[1] - 2 * margin) / (north - south))
        self.scale, self.west, self.north = scale, west, north
        self.dx = (size[0] - (east - west) * self.kx * scale) / 2
        self.dy = (size[1] - (north - south) * scale) / 2

    def __call__(self, lon, lat):
        return (np.asarray(lon) - self.west) * self.kx * self.scale + self.dx, (self.north - np.asarray(lat)) * self.scale + self.dy

    def bounds(self, size=SIZE):
        west = self.west - self.dx / (self.kx * self.scale)
        north = self.north + self.dy / self.scale
        return west, north - size[1] / self.scale, west + size[0] / (self.kx * self.scale), north


def line_coordinates(geometry):
    if geometry["type"] == "LineString":
        return [geometry["coordinates"]]
    if geometry["type"] == "MultiLineString":
        return geometry["coordinates"]
    if geometry["type"] == "Polygon":
        return geometry["coordinates"]
    return [ring for polygon in geometry["coordinates"] for ring in polygon]


def draw_lines(draw, geometries, project, color, width, factor=1):
    for geometry in geometries:
        for line in line_coordinates(geometry):
            xs, ys = project(*zip(*[point[:2] for point in line]))
            draw.line(list(zip((xs * factor).tolist(), (ys * factor).tolist())), fill=color, width=width)


def legend(draw, y=28, x=28):
    draw.rectangle((x - 14, y - 10, x + 300, y + 76), fill=rgb(SURFACE["background"]))
    for color, text in ((OLD, "Ya estaba en 2013"), (NEW, "Apareció después")):
        draw.ellipse((x, y + 6, x + 20, y + 26), fill=rgb(color))
        draw.text((x + 30, y), text, font=font(26), fill=rgb(SURFACE["text"]))
        y += 38


def year_label(draw, year, value, place="", position=(28, 790)):
    text = f"{place}: {number(value)} km²" if place else f"{number(value)} km²"
    width = max(draw.textlength(str(year), font=font(112, True)), draw.textlength(text, font=font(30)))
    draw.rectangle((position[0] - 14, position[1] + 8, position[0] + width + 14, SIZE[1]), fill=rgb(SURFACE["background"]))
    draw.text(position, str(year), font=font(112, True), fill=rgb(SURFACE["text"]))
    draw.text((position[0], position[1] + 116), text, font=font(30), fill=rgb(SURFACE["text"]))


def load_pixels():
    meta = json.loads((WEB_DATA / "huella.json").read_text(encoding="utf-8"))
    blob = (WEB_DATA / "huella.bin").read_bytes()
    n, years = meta["count"], len(meta["years"])
    rows = np.frombuffer(blob, "<u2", n, 0)
    cols = np.frombuffer(blob, "<u2", n, 2 * n)
    shares = np.frombuffer(blob, "u1", n * years, 4 * n).reshape(n, years) / 255
    left, dx, top, dy = meta["transform"]
    return meta["years"], left + (cols + 0.5) * dx, top + (rows + 0.5) * dy, shares, abs(dx)


def national_scene():
    """Peru year by year: each circle is a 500 m cell, its area proportional to the mining land in it."""
    years, lon, lat, shares, cell = load_pixels()
    outlines = [f["geometry"] for f in json.loads((WEB_DATA / "departamentos.json").read_text(encoding="utf-8"))["features"]]
    project = Projection((-81.4, -18.4, -68.6, 0.1))
    x, y = project(lon, lat)
    radius_full = cell * project.scale * 0.56 * 2
    atlas = json.loads((PROCESADOS / "atlas.json").read_text(encoding="utf-8"))
    existed = shares[:, 0] >= 0.01
    base = Image.new("RGB", (SIZE[0] * 2, SIZE[1] * 2), rgb(SURFACE["background"]))
    draw_lines(ImageDraw.Draw(base), outlines, project, rgb(SURFACE["context"]), 2, factor=2)
    for i, year in enumerate(years):
        image = base.copy()
        draw = ImageDraw.Draw(image)
        for px, py, share, old in zip(x * 2, y * 2, shares[:, i], existed):
            if share <= 0:
                continue
            r = max(2.2, radius_full * np.sqrt(share))
            draw.ellipse((px - r, py - r, px + r, py + r), fill=rgb(OLD if old else NEW))
        image = image.resize(SIZE, Image.Resampling.LANCZOS)
        draw = ImageDraw.Draw(image)
        legend(draw)
        year_label(draw, year, atlas["national_km2"][str(year)])
        save(image, "peru", i)


def corridor_bounds(features, ubigeo_prefix, lon, lat, share_last):
    region = shapely.union_all([shapely.geometry.shape(f["geometry"]) for f in features
                                if f["properties"]["ubigeo"].startswith(ubigeo_prefix)])
    inside = shapely.contains_xy(region, lon, lat) & (share_last > 0.02)
    west, east = np.percentile(lon[inside], [1, 99])
    south, north = np.percentile(lat[inside], [1, 99])
    return float(west), float(south), float(east), float(north), region


def detail_scene(name, ubigeo_prefix, place, km2_by_year, outline_width=2):
    """Real 30 m MapBiomas mining pixels, year by year. Land outside the place is dimmed, so the label matches the view."""
    features = json.loads((WEB_DATA / "distritos.json").read_text(encoding="utf-8"))["features"]
    years, lon, lat, shares, _ = load_pixels()
    west, south, east, north, region = corridor_bounds(features, ubigeo_prefix, lon, lat, shares[:, -1])
    project = Projection((west, south, east, north), margin=70)
    window_bounds = project.bounds()
    outlines = [f["geometry"] for f in features if f["properties"]["ubigeo"].startswith(ubigeo_prefix[:2])]
    background = Image.new("RGB", SIZE, rgb(SURFACE["background"]))
    draw_lines(ImageDraw.Draw(background), outlines, project, rgb(SURFACE["context"]), outline_width)
    inside = geometry_mask([region], out_shape=SIZE[::-1], transform=transform_from_bounds(*window_bounds, *SIZE), invert=True)
    focus = np.where(inside, 1.0, 0.22)[..., None]
    base_mask = None
    for i, year in enumerate(years):
        with rasterio.open(MAPBIOMAS / f"peru_coverage-col4_{year}.tif") as src:
            mask = src.read(1, window=from_bounds(*window_bounds, src.transform), boundless=True, fill_value=0) == MINING
        if base_mask is None:
            base_mask = mask
        def layer(array):
            return np.asarray(Image.fromarray(array.astype("uint8") * 255).resize(SIZE, Image.Resampling.BOX), dtype="float32") / 255
        old, new = layer(mask & base_mask), layer(mask & ~base_mask)
        pixels = np.asarray(background, dtype="float32")
        for coverage, color in ((old, OLD), (new, NEW)):
            weight = np.clip(coverage * 2.2, 0, 1)[..., None] * focus
            pixels = pixels * (1 - weight) + np.asarray(rgb(color), dtype="float32") * weight
        image = Image.fromarray(pixels.astype("uint8"))
        draw = ImageDraw.Draw(image)
        legend(draw)
        year_label(draw, year, km2_by_year(i), place)
        save(image, name, i)


def bars_scene():
    panel = json.loads((WEB_DATA / "panel.json").read_text(encoding="utf-8"))
    names = sorted({d["d"] for d in panel["districts"]})
    totals = {name: np.sum([d["m"] for d in panel["districts"] if d["d"] == name], axis=0) for name in names}
    top = sorted(names, key=lambda name: -totals[name][-1])[:8]
    limit = totals[top[0]][-1]
    for i, year in enumerate(panel["years"]):
        image = Image.new("RGB", SIZE, rgb(SURFACE["background"]))
        draw = ImageDraw.Draw(image)
        draw.text((40, 26), str(year), font=font(92, True), fill=rgb(SURFACE["text"]))
        draw.text((270, 72), "km² de huella por departamento", font=font(30), fill=rgb(SURFACE["text_muted"]))
        for row, name in enumerate(top):
            y = 170 + row * 96
            value = totals[name][i]
            color = NEW if name == "MADRE DE DIOS" else OLD
            draw.text((40, y), name.title().replace(" De ", " de "), font=font(30), fill=rgb(SURFACE["text"]))
            length = 880 * value / limit
            draw.rounded_rectangle((40, y + 44, 40 + max(length, 6), y + 72), radius=5, fill=rgb(color))
            draw.text((40 + max(length, 6) + 14, y + 38), number(value), font=font(32, True), fill=rgb(SURFACE["text"]))
        save(image, "departamentos", i)


def contrast_scene():
    summary = json.loads((PROCESADOS / "contraste_huella.json").read_text(encoding="utf-8"))
    contrast = summary["madre_de_dios"]
    last = contrast["last_confirmed_year"]
    years = [y for y in summary["years"] if y <= last]
    series = [("MapBiomas", [contrast["mapbiomas_km2"][str(y)] for y in years], SERIES["mining"], contrast["ratio_to_last_confirmed"]["mapbiomas"]),
              ("Amazon Mining Watch", [contrast["amw_km2"][str(y)] for y in years], SERIES["contrast"], contrast["ratio_to_last_confirmed"]["amw"])]
    left, right, top, bottom, ymax = 110, 860, 150, 860, 1600
    px = lambda t: left + (right - left) * t / (len(years) - 1)
    py = lambda v: bottom - (bottom - top) * v / ymax
    steps = np.linspace(0, len(years) - 1, 25)
    for frame, t in enumerate(steps):
        image = Image.new("RGB", (SIZE[0] * 2, SIZE[1] * 2), rgb(SURFACE["background"]))
        draw = ImageDraw.Draw(image)
        for tick in (0, 500, 1000, 1500):
            draw.line((left * 2, py(tick) * 2, right * 2, py(tick) * 2), fill=rgb(SURFACE["grid"]), width=2)
            draw.text((26 * 2, (py(tick) - 18) * 2), number(tick), font=font(52), fill=rgb(SURFACE["text_muted"]))
        for year_index in (0, len(years) - 1):
            draw.text(((px(year_index) - 40) * 2, (bottom + 14) * 2), str(years[year_index]), font=font(56), fill=rgb(SURFACE["text_muted"]))
        for name, values, color, ratio in series:
            shown = [(px(j) * 2, py(v) * 2) for j, v in enumerate(values) if j <= t]
            whole = int(np.floor(t))
            if whole < len(values) - 1:
                value = values[whole] + (values[whole + 1] - values[whole]) * (t - whole)
                shown.append((px(t) * 2, py(value) * 2))
            else:
                value = values[-1]
            if len(shown) > 1:
                draw.line(shown, fill=rgb(color), width=12, joint="curve")
            x, y = shown[-1]
            draw.ellipse((x - 16, y - 16, x + 16, y + 16), fill=rgb(color))
            draw.text((x + 26, y - 40), f"×{ratio:.2f}" if whole == len(values) - 1 else number(value), font=font(64, True), fill=rgb(SURFACE["text"]))
        draw.text((40 * 2, 28 * 2), "Madre de Dios, km²", font=font(64), fill=rgb(SURFACE["text_muted"]))
        x = 40
        for name, _, color, _ in series:
            draw.ellipse((x * 2, 92 * 2, (x + 22) * 2, 114 * 2), fill=rgb(color))
            draw.text(((x + 32) * 2, 84 * 2), name, font=font(60), fill=rgb(SURFACE["text"]))
            x += 32 + len(name) * 17 + 40
        save(image.resize(SIZE, Image.Resampling.LANCZOS), "contraste", frame)


def coverage_scene():
    """Where a second source exists: all of MapBiomas first, then the cells where Amazon Mining Watch also sees scars."""
    years, lon, lat, shares, cell = load_pixels()
    outlines = [f["geometry"] for f in json.loads((WEB_DATA / "departamentos.json").read_text(encoding="utf-8"))["features"]]
    project = Projection((-81.4, -18.4, -68.6, 0.1))
    x, y = project(lon, lat)
    with rasterio.open(AMW_2024) as src:
        scars, transform = src.read(1), src.transform
    rows, cols = rasterio.transform.rowcol(transform, lon, lat)
    seen = scars[np.asarray(rows), np.asarray(cols)] > 0
    i = years.index(2024)
    for frame, show_second in enumerate((False, True)):
        image = Image.new("RGB", (SIZE[0] * 2, SIZE[1] * 2), rgb(SURFACE["background"]))
        draw = ImageDraw.Draw(image)
        draw_lines(draw, outlines, project, rgb(SURFACE["context"]), 2, factor=2)
        order = np.argsort(seen) if show_second else np.arange(len(x))
        for j in order:
            if shares[j, i] <= 0:
                continue
            r = max(2.6, cell * project.scale * 1.12 * np.sqrt(shares[j, i]))
            color = SERIES["contrast"] if show_second and seen[j] else OLD
            draw.ellipse((x[j] * 2 - r, y[j] * 2 - r, x[j] * 2 + r, y[j] * 2 + r), fill=rgb(color))
        image = image.resize(SIZE, Image.Resampling.LANCZOS)
        draw = ImageDraw.Draw(image)
        rows_of_legend = [(OLD, "Solo MapBiomas" if show_second else "MapBiomas, 2024")]
        if show_second:
            rows_of_legend.append((SERIES["contrast"], "También Amazon Mining Watch"))
        for k, (color, text) in enumerate(rows_of_legend):
            draw.ellipse((28, 34 + k * 38, 48, 54 + k * 38), fill=rgb(color))
            draw.text((58, 28 + k * 38), text, font=font(26), fill=rgb(SURFACE["text"]))
        save(image, "cobertura", frame)


def main() -> None:
    panel = json.loads((WEB_DATA / "panel.json").read_text(encoding="utf-8"))
    def total(prefix):
        rows = [d["m"] for d in panel["districts"] if d["u"].startswith(prefix)]
        return lambda i: float(np.sum([row[i] for row in rows]))
    national_scene()
    print("peru")
    detail_scene("madre_de_dios", MADRE_DE_DIOS, "Madre de Dios", total(MADRE_DE_DIOS))
    print("madre_de_dios")
    detail_scene("inambari", INAMBARI, "Inambari", total(INAMBARI))
    print("inambari")
    bars_scene()
    contrast_scene()
    coverage_scene()
    print("listo ->", OUT)


if __name__ == "__main__":
    main()
