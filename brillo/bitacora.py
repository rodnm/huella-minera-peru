"""Cleaning log: how many rows enter and leave each step, saved as datos/procesados/bitacora_limpieza.json."""
import json
from pathlib import Path


class Bitacora:
    def __init__(self):
        self.steps = []

    def add(self, source: str, step: str, rows_in: int, rows_out: int, note: str = "") -> None:
        self.steps.append({"source": source, "step": step, "rows_in": int(rows_in), "rows_out": int(rows_out),
                           "dropped": int(rows_in) - int(rows_out), "note": note})

    def save(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"steps": self.steps}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return path
