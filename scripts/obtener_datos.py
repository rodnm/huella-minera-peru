"""Download every primary source into datos/originales/ and pin it in datos/originales/MANIFEST.json.

Run from the repository root: uv run python -m scripts.obtener_datos
Files that already exist are kept; delete one to download it again. Night lights have their own script
(scripts/obtener_luz.py) because they need a NASA Earthdata token and take much longer.
"""
from pathlib import Path

from brillo.descarga import download, fetch_arcgis_layer, new_session, record
from brillo.fuentes import DISTRICTS, SOURCES

ORIGINALES = Path(__file__).resolve().parent.parent / "datos" / "originales"
MANIFEST = ORIGINALES / "MANIFEST.json"


def main() -> None:
    session = new_session()
    for source in SOURCES:
        path = download(source["url"], ORIGINALES / source["file"], session=session)
        entry = record(MANIFEST, source["name"], source["url"], path, source["page"], source["license"])
        print(f"{source['name']:<28} {entry['bytes']:>12,} B  {entry['sha256'][:12]}")
    path = fetch_arcgis_layer(DISTRICTS["url"], ORIGINALES / DISTRICTS["file"], session=session)
    entry = record(MANIFEST, DISTRICTS["name"], DISTRICTS["url"], path, DISTRICTS["page"], DISTRICTS["license"])
    print(f"{DISTRICTS['name']:<28} {entry['bytes']:>12,} B  {entry['sha256'][:12]}")


if __name__ == "__main__":
    main()
