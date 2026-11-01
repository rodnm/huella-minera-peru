"""Rebuild everything from the primary sources, in order.

Run from the repository root: uv run python -m scripts.run_all
Files already downloaded are kept. Night lights need a NASA Earthdata token (see brillo/credenciales.py).
"""
from scripts import (analizar_datos, auditar_datos, construir_atlas, contrastar_huella, estimar_pobreza, obtener_datos,
                     obtener_luz, procesar_datos)

STAGES = [obtener_datos, obtener_luz, procesar_datos, contrastar_huella, estimar_pobreza, analizar_datos,
          auditar_datos, construir_atlas]


def main() -> None:
    for stage in STAGES:
        print(f"\n== {stage.__name__}")
        stage.main()


if __name__ == "__main__":
    main()
