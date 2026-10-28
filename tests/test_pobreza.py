import pytest
from openpyxl import Workbook

from brillo.pobreza import read_poverty


def test_read_poverty_keeps_districts_and_takes_the_interval_midpoint(tmp_path):
    wb = Workbook()
    ws = wb.active
    ws.title = "Anexo1"
    for row in [["Anexo N° 1"], ["PERÚ: POBREZA MONETARIA"], [],
                ["Ubigeo", "Departamento", "Provincia", "Distrito", "Población proyectada 2020 1/",
                 "Intervalo de confianza al 95%", None, "Grupos robustos 2/", "Ubicación"],
                [], [None, None, None, None, None, "Inferior", "Superior"], [],
                ["050410", "AYACUCHO", "HUANTA", "UCHURACCAY   ", 3672, 73.25, 89.27, 1, 1],
                [],
                ["150131", "LIMA ", "LIMA", "SAN ISIDRO", 67703, 0, 0.11, 28, 1874],
                ["1/ Población proyectada a junio del 2020."]]:
        ws.append(row)
    path = tmp_path / "anexo.xlsx"
    wb.save(path)
    poverty = read_poverty(path)
    assert list(poverty["ubigeo"]) == ["050410", "150131"]
    assert list(poverty["district"]) == ["UCHURACCAY", "SAN ISIDRO"]
    assert poverty.iloc[0]["poverty"] == pytest.approx((73.25 + 89.27) / 2)
    assert (poverty.iloc[1]["poverty_low"], poverty.iloc[1]["poverty_high"]) == (0, 0.11)
    assert poverty.iloc[1]["population_2020"] == 67703
