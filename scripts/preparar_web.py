"""Copies datos/atlas to web/data, the folder published with the page. An Artifact doesn't serve .bin files, so the footprint goes as base64 text."""
import base64
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE, TARGET = ROOT / "datos" / "atlas", ROOT / "web" / "data"


def main() -> None:
    shutil.rmtree(TARGET, ignore_errors=True)
    TARGET.mkdir(parents=True)
    for path in SOURCE.glob("*.json"):
        shutil.copy2(path, TARGET / path.name)
    (TARGET / "huella.txt").write_text(base64.b64encode((SOURCE / "huella.bin").read_bytes()).decode("ascii"), encoding="ascii")
    print(f"{len(list(TARGET.iterdir()))} files in {TARGET.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
