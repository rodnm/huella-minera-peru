import pytest
from openpyxl import Workbook

from brillo.pobreza import read_poverty, read_poverty_2013


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


def test_read_poverty_2013_collapses_split_districts_and_flags_grouped_ones(tmp_path):
    wb = Workbook()
    ws = wb.active
    ws.title = "Cdr01"
    for row in [[None, "ANEXO N° 01"], [None, "PERÚ"], [],
                [None, "Ubigeo", "Departamento", "Provincia", "Distrito", "Población", "Intervalo", None, "Ubicación", "Grupos"],
                [None, None, None, None, None, None, "Inferior", "Superior"],
                [None, "021801", "Áncash", "Santa", "Chimbote - Grupo 1", 300, 10, 20, 1, 1],
                [None, "021801", "Áncash", "Santa", "Chimbote - Grupo 2", 100, 30, 50, 2, 2],
                [None, "060101", "Cajamarca", "Cajamarca", "Cajamarca", 200, -1, 5, 3, 3],
                [None, "060102", "Cajamarca", "Cajamarca", "Asunción", 50, 40, 60, 4, 4],
                [None, "060103", "Cajamarca", "Cajamarca", "Chetilla", 60, 40, 60, 5, 4],
                [None, "Nota: los distritos"]]:
        ws.append(row)
    path = tmp_path / "anexo2013.xlsx"
    wb.save(path)
    out = read_poverty_2013(path).set_index("ubigeo")
    assert list(out.index) == ["021801", "060101", "060102", "060103"]
    chimbote = out.loc["021801"]
    assert chimbote["population_2015"] == 400
    assert chimbote["poverty_2013"] == pytest.approx((300 * 15 + 100 * 40) / 400)
    assert chimbote["poverty_low_2013"] == pytest.approx((300 * 10 + 100 * 30) / 400)
    assert bool(chimbote["split_2013"]) is True
    assert out.loc["060101", "poverty_low_2013"] == 0      # a negative lower bound is not a rate
    assert out.loc["060101", "poverty_2013"] == pytest.approx(2.5)
    assert bool(out.loc["060102", "grouped_2013"]) is True  # same interval as a neighbour: estimated as a group
    assert bool(out.loc["060101", "grouped_2013"]) is False
