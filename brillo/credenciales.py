"""Read the NASA Earthdata token without ever printing or committing it."""
from collections.abc import Mapping
from pathlib import Path

NAME = "BLACKMARBLE_TOKEN"
HELP = (f"Falta el token de NASA Earthdata. Créalo gratis en https://urs.earthdata.nasa.gov (Profile → Generate "
        f"Token) y ponlo en la variable de entorno {NAME} o en un archivo .env en la raíz del repo: {NAME}=...")


def load_token(environ: Mapping[str, str], dotenv: Path) -> str:
    """Return the token from the environment, or else from a .env file (ignored by git)."""
    if environ.get(NAME):
        return environ[NAME]
    if dotenv.exists():
        for line in dotenv.read_text(encoding="utf-8-sig").splitlines():  # utf-8-sig: PowerShell 5 adds a BOM
            key, sep, value = line.partition("=")
            if sep and key.strip() == NAME and value.strip():
                return value.strip().strip("'\"")
    raise SystemExit(HELP)
