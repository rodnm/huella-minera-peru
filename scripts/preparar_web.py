"""Copies datos/atlas to web/data, the folder published with the page. An Artifact doesn't serve .bin files, so the footprint goes as base64 text.

Also writes web/index.html, to open the page locally with the skeleton the Artifact adds when it is published.
"""
import base64
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE, TARGET = ROOT / "datos" / "atlas", ROOT / "web" / "data"
PAGE, INDEX = ROOT / "web" / "atlas.html", ROOT / "web" / "index.html"


def main() -> None:
    shutil.rmtree(TARGET, ignore_errors=True)
    TARGET.mkdir(parents=True)
    for path in SOURCE.glob("*.json"):
        shutil.copy2(path, TARGET / path.name)
    (TARGET / "huella.txt").write_text(base64.b64encode((SOURCE / "huella.bin").read_bytes()).decode("ascii"), encoding="ascii")
    INDEX.write_text(
        '<!doctype html><html lang="es"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1"></head>'
        f'<body style="margin:0">{PAGE.read_text(encoding="utf-8")}</body></html>', encoding="utf-8")
    print(f"{len(list(TARGET.iterdir()))} files in {TARGET.relative_to(ROOT)}, and {INDEX.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
