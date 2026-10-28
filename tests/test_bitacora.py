import json

from brillo.bitacora import Bitacora


def test_bitacora_saves_steps_in_order_with_rows_in_and_out(tmp_path):
    log = Bitacora()
    log.add("minem", "leer archivos 2013-2025", rows_in=13, rows_out=10580, note="13 años, 2 formatos")
    log.add("minem", "régimen general", rows_in=10580, rows_out=6289)
    path = log.save(tmp_path / "bitacora.json")
    steps = json.loads(path.read_text(encoding="utf-8"))["steps"]
    assert [s["step"] for s in steps] == ["leer archivos 2013-2025", "régimen general"]
    assert steps[1] == {"source": "minem", "step": "régimen general", "rows_in": 10580, "rows_out": 6289,
                        "dropped": 4291, "note": ""}
