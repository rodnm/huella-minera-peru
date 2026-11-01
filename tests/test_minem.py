import datetime

import pandas as pd
import pytest
from openpyxl import Workbook

from brillo.minem import (assign_ubigeo, coordinate_agreement, district_panel, normalize_text, read_production, read_units,
                          scale_mining, to_tonnes)

MONTHS = list(range(1, 13))


def write_rows(path, rows):
    wb = Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    wb.save(path)
    return path


def test_normalize_text_drops_accents_case_and_extra_spaces():
    assert normalize_text("  Áncash ") == "ANCASH"
    assert normalize_text("Estaño") == "ESTANO"
    assert normalize_text("San  Miguel De Aco") == "SAN MIGUEL DE ACO"


@pytest.mark.parametrize("unit, value, tonnes", [("TMF", 2, 2), ("Grs.f", 1e6, 1), ("GR. FINOS", 1e6, 1),
                                                 ("G FINOS", 1e6, 1),
                                                 ("Kg.f", 1e3, 1), ("KG. FINOS", 1e3, 1), ("TLF", 1, 1.0160469088)])
def test_to_tonnes_converts_fine_content_units(unit, value, tonnes):
    assert to_tonnes(value, unit) == pytest.approx(tonnes)


def test_reads_per_metal_layout_2013_2019(tmp_path):
    header = ["LEY", "ETAPA", "PROCESO", "CLASIFICACIÓN", "TITULAR", "UNIDAD", "REGION", "PROVINCIA", "DISTRITO",
              *[datetime.datetime(2016, m, 1) for m in MONTHS], "TOTAL GENERAL"]
    path = write_rows(tmp_path / "ORO.xlsx", [
        ["PRODUCCIÓN MINERA METÁLICA DE ORO (Grs.f) - 2016"], [], header,
        ["TOTAL"] * 9 + [999] * 13, [],
        ["%Oro", "Concentración", "Flotación", "Régimen General", "MINERA X S.A.", "MINA X", "Apurimac", "Cotabambas",
         "Challhuahuacho", *MONTHS, 78],
    ])
    df = read_production(path, year=2016)
    assert len(df) == 1
    row = df.iloc[0]
    assert (row["metal"], row["unit_measure"], row["stratum"], row["district"]) == ("ORO", "Grs.f", "REGIMEN GENERAL",
                                                                                     "CHALLHUAHUACHO")
    assert row["quantity"] == 78
    assert row["tonnes"] == pytest.approx(78e-6)


def test_reads_consolidated_layout_2020_onwards(tmp_path):
    months = ["ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO", "JULIO", "AGOSTO", "SETIEMBRE", "OCTUBRE",
              "NOVIEMBRE", "DICIEMBRE"]
    header = ["MINERAL", "UNIDAD DE MEDIDA", "ETAPA", "PROCESO", "ESTRATO", "TITULAR", "UNIDAD MINERA",
              "DEPARTAMENTO", "PROVINCIA", "DISTRITO", *months, "TOTAL"]
    path = write_rows(tmp_path / "produccion.xlsx", [
        [], ["PRODUCCIÓN METÁLICA - ENERO A DICIEMBRE DE 2025"], [], header,
        ["PLATA", "KG. FINOS", "CONCENTRACIÓN", "FLOTACIÓN", "RÉGIMEN GENERAL", "MINERA Y", "MINA Y", "PASCO", "PASCO",
         "YANACANCHA", *[100] * 12, 1200],
        ["COBRE", "TMF", "REFINACIÓN", "ELECTROLÍTICO", "RÉGIMEN GENERAL", "REFINERÍA Z", "ILO", "MOQUEGUA", "ILO",
         "PACOCHA", *[None] * 11, 5, 5],
    ])
    df = read_production(path, year=2025)
    assert list(df["metal"]) == ["PLATA", "COBRE"]
    assert list(df["quantity"]) == [1200, 5]
    assert df.iloc[0]["tonnes"] == pytest.approx(1.2)
    assert df.iloc[1]["stage"] == "REFINACION"


def test_scale_mining_keeps_general_regime_extraction_of_main_metals():
    df = pd.DataFrame({
        "metal": ["COBRE", "COBRE", "ORO", "ARSENICO", "ZINC", "COBRE"],
        "stratum": ["REGIMEN GENERAL", "PEQUENO PRODUCTOR MINERO", "REGIMEN GENERAL", "REGIMEN GENERAL",
                    "REGIMEN GENERAL", "REGIMEN GENERAL"],
        "stage": ["CONCENTRACION", "CONCENTRACION", "BENEFICIO", "CONCENTRACION", "REFINACION", "REFINERIA"],
        "holder": ["MINERA A", "MINERA B", "MINERA C", "MINERA D", "REFINERIA E", "REFINERIA F"],
    })
    kept = scale_mining(df)
    assert list(kept.index) == [0, 2]


def test_scale_mining_drops_regional_artisanal_aggregates_labelled_as_general_regime():
    df = pd.DataFrame({"metal": ["ORO", "ORO"], "stratum": ["REGIMEN GENERAL"] * 2, "stage": ["CONCENTRACION"] * 2,
                       "holder": ["DATA MINEROS ARTESANALES", "MINERA A"]})
    assert list(scale_mining(df)["holder"]) == ["MINERA A"]


def test_assign_ubigeo_matches_names_and_applies_manual_crosswalk():
    districts = pd.DataFrame({"ubigeo": ["110301", "110302", "030705"],
                              "department": ["ICA", "ICA", "APURIMAC"], "province": ["NASCA", "NASCA", "COTABAMBAS"],
                              "district": ["NASCA", "MARCONA", "CHALLHUAHUACHO"]})
    manual = pd.DataFrame({"region": ["ICA"], "province": ["NAZCA"], "district": ["MARCONA"], "ubigeo": ["110302"],
                           "reason": ["MINEM writes Nazca, INEI writes Nasca"]})
    df = pd.DataFrame({"region": ["APURIMAC", "ICA", "ICA"], "province": ["COTABAMBAS", "NAZCA", "NAZCA"],
                       "district": ["CHALLHUAHUACHO", "MARCONA", "NAZCA"]})
    out = assign_ubigeo(df, districts, manual)
    assert list(out["ubigeo"]) == ["030705", "110302", None]
    assert list(out["match"]) == ["name", "manual", "unmatched"]


def test_read_units_finds_coordinates_under_any_header_spelling(tmp_path):
    path = write_rows(tmp_path / "unidades.xlsx", [
        ["MAPA DE PRINCIPALES UNIDADES MINERAS EN PRODUCCIÓN"], [],
        ["OPERADOR", "UNIDAD MINERA EN PRODUCCIÓN", "PRODUCTO 1", "TIPO DE SUSTANCIA", "DEPARTAMENTO", "PROVINCIA",
         "DISTRITO", "LONGITUD", "LATITUD", "LABEL"],
        ["MINERA X", "LAS BAMBAS", "CU, MO", "MINERÍA METÁLICA", "Apurímac", "Cotabambas", "Challhuahuacho",
         "-72.29", "-14.07", "TAJO ABIERTO"],
    ])
    units = read_units(path, year=2025)
    row = units.iloc[0]
    assert (row["holder"], row["unit_name"], row["region"], row["district"]) == ("MINERA X", "LAS BAMBAS", "APURIMAC",
                                                                                 "CHALLHUAHUACHO")
    assert (row["lon"], row["lat"]) == (-72.29, -14.07)


def test_coordinate_agreement_compares_the_named_district_with_the_point():
    import geopandas as gpd
    from shapely.geometry import box

    districts = gpd.GeoDataFrame({"ubigeo": ["000001", "000002"], "department": ["A", "A"], "province": ["P", "P"],
                                  "district": ["UNO", "DOS"]},
                                 geometry=[box(-75, -10, -74, -9), box(-74, -10, -73, -9)], crs="EPSG:4326")
    units = pd.DataFrame({"region": ["A", "A", "A"], "province": ["P", "P", "P"], "district": ["UNO", "DOS", "TRES"],
                          "lon": [-74.5, -74.5, -73.5], "lat": [-9.5, -9.5, -9.5]})
    rate, table = coordinate_agreement(units, districts, manual=pd.DataFrame(columns=["region", "province",
                                                                                      "district", "ubigeo"]))
    assert rate == 0.5
    assert list(table["agrees"]) == [True, False, None]
    # the misplaced point sits 0.5° (about 55 km) from the district its name points to
    assert table["distance_km"].iloc[0] == 0
    assert 50 < table["distance_km"].iloc[1] < 60


def test_coordinate_agreement_survives_a_repeated_index_from_concatenated_years():
    import geopandas as gpd
    from shapely.geometry import box

    districts = gpd.GeoDataFrame({"ubigeo": ["000001"], "department": ["A"], "province": ["P"], "district": ["UNO"]},
                                 geometry=[box(0, 0, 1, 1)], crs="EPSG:4326")
    one_year = pd.DataFrame({"region": ["A"], "province": ["P"], "district": ["UNO"], "lon": [0.5], "lat": [0.5]})
    units = pd.concat([one_year, one_year])  # both rows have index 0
    rate, table = coordinate_agreement(units, districts, manual=pd.DataFrame(columns=["region", "province",
                                                                                      "district", "ubigeo"]))
    assert len(table) == 2 and rate == 1.0


def test_district_panel_sums_units_and_picks_the_metal_with_the_largest_national_share():
    units = pd.DataFrame({
        "ubigeo": ["030506", "030506", "030506", "130808"],
        "year": [2020] * 4,
        "metal": ["COBRE", "ORO", "COBRE", "ORO"],
        "unit_name": ["LAS BAMBAS", "LAS BAMBAS", "OTRA", "PARCOY"],
        "tonnes": [300.0, 1.0, 100.0, 9.0],
    })
    panel = district_panel(units).set_index("ubigeo")
    assert panel.loc["030506", "units"] == 2
    assert panel.loc["030506", "tonnes_cobre"] == 400
    assert panel.loc["030506", "main_metal"] == "COBRE"   # 100 % of copper vs 10 % of gold
    assert panel.loc["130808", "main_metal"] == "ORO"
    assert panel.loc["130808", "tonnes_cobre"] == 0
