"""Catalog of primary sources. Every file the project uses comes from one of these entries.

The www.gob.pe landing pages answer HTTP 418 to automated clients, so the cdn.www.gob.pe file URLs are pinned here
(read from those pages on 2026-10-27/28). The ``page`` field is where a person can check them in a browser.
"""

MINEM_PRODUCTION_PAGE = "https://www.gob.pe/institucion/minem/informes-publicaciones/5472883-produccion-minera"
MINEM_UNITS_LICENSE = "Información pública del Estado peruano (Ley 27806); el portal no declara una licencia"
CDN = "https://cdn.www.gob.pe/uploads/document/file"
MAPBIOMAS_COVERAGE = ("https://storage.googleapis.com/mapbiomas-public/initiatives/peru/collection4/lulc/coverage/"
                      "peru_coverage")
MAPBIOMAS_PAGE = "https://peru.mapbiomas.org/descargas/mapas-de-las-colecciones/"
ENAHO_DOWNLOAD = "https://proyectos.inei.gob.pe/iinei/srienaho/descarga/CSV"
ENAHO_CODES = {2013: 404, 2014: 440, 2015: 498, 2016: 546, 2017: 603, 2018: 634, 2019: 687, 2020: 737, 2021: 759,
               2022: 784, 2023: 906, 2024: 966, 2025: 1031}
INEI_LICENSE = "Información pública del Estado peruano (Ley 27806); el portal no declara una licencia"

SOURCES = [
    {
        "name": "pobreza_inei_2018",
        "url": f"{CDN}/3340937/Anexo%20Estad%C3%ADstico.xlsx",
        "file": "inei/mapa_pobreza_2018_anexo_estadistico.xlsx",
        "page": "https://www.gob.pe/institucion/inei/informes-publicaciones/3204872-mapa-de-pobreza-provincial-y-distrital-2018",
        "license": "Información pública del Estado peruano (Ley 27806); el portal no declara una licencia",
        "description": "INEI, Mapa de Pobreza Monetaria Provincial y Distrital 2018: IC 95 % por distrito y población 2020",
    },
    {
        "name": "pobreza_inei_2013",
        "url": "https://www.inei.gob.pe/media/MenuRecursivo/publicaciones_digitales/Anexo_Estadistico_MapaPobreza2013.xlsx",
        "file": "inei/mapa_pobreza_2013_anexo_estadistico.xlsx",
        "page": "https://www.inei.gob.pe/cifras-de-pobreza/",
        "license": INEI_LICENSE,
        "description": "INEI, Mapa de Pobreza Monetaria Provincial y Distrital 2013: IC 95 % por distrito y población 2015",
    },
    *[
        {
            "name": f"enaho_sumaria_{year}",
            "url": f"{ENAHO_DOWNLOAD}/{code}-Modulo34.zip",
            "file": f"enaho/{code}-Modulo34.zip",
            "page": "https://proyectos.inei.gob.pe/microdatos/",
            "license": INEI_LICENSE,
            "description": f"INEI, ENAHO {year}, módulo 34 (Sumaria): pobreza, gasto y factor de expansión del hogar",
        }
        for year, code in ENAHO_CODES.items()
    ],
    {
        "name": "minas_maus_v2",
        "url": "https://download.pangaea.de/dataset/942325/files/global_mining_polygons_v2.gpkg",
        "file": "maus/global_mining_polygons_v2.gpkg",
        "page": "https://doi.org/10.1594/PANGAEA.942325",
        "license": "CC BY-SA 4.0",
        "description": "Maus et al. (2022), huella global de la minería v2: polígonos digitalizados sobre Sentinel-2 2019",
    },
    *[
        {
            "name": f"produccion_minem_{label}",
            "url": f"{CDN}/{path}",
            "file": f"minem/produccion/{path.rsplit('/', 1)[1]}",
            "page": MINEM_PRODUCTION_PAGE,
            "license": MINEM_UNITS_LICENSE,
            "description": f"MINEM, Producción Minera por unidad ({label.replace('_', ' ')}), declaraciones ESTAMIN",
        }
        for label, path in [
            ("2001_2020", "6209848/5472883-2001-2020.7z"),
            ("2021", "6209623/5472883-2021.zip"),
            ("2022", "6209624/5472883-2022.7z"),
            ("2023", "7768910/5472883-2023.7z"),
            ("2024", "7768911/5472883-2024.7z"),
            ("2025", "7850353/5472883-2025.zip"),
            ("2026_ene_ago", "9679417/5472883-ene-ago-2026.zip"),
        ]
    ],
    *[
        {
            "name": f"unidades_minem_{year}",
            "url": f"{CDN}/{path}",
            "file": f"minem/unidades/principales_unidades_{year}.xlsx",
            "page": "https://www.gob.pe/minem (Mapa de Principales Unidades Mineras en Producción)",
            "license": MINEM_UNITS_LICENSE,
            "description": f"MINEM, Principales Unidades Mineras en Producción {year}: titular, unidad, distrito y coordenadas",
        }
        for year, path in [
            (2016, "5220174/Database.xlsx"),
            (2017, "5220335/Database.xlsx"),
            (2023, "3447307/2023_%20MAPA%20DE%20PRODUCCION.xlsx"),
            (2024, "6711334/5724261-2024_mapa-principales-unidades-mineras-en-produccion.xlsx"),
            (2025, "8674918/6911615-principales-unidades-mineras-en-produccion-edicion-2025.xlsx"),
        ]
    ],
    *[
        {
            "name": f"mapbiomas_c4_{year}",
            "url": f"{MAPBIOMAS_COVERAGE}/peru_coverage-col4_{year}.tif",
            "file": f"mapbiomas/peru_coverage-col4_{year}.tif",
            "page": MAPBIOMAS_PAGE,
            "license": "CC BY 4.0 (MapBiomas Perú)",
            "description": f"MapBiomas Perú Colección 4, cobertura y uso del suelo {year} a 30 m; clase 30 = minería",
        }
        for year in range(2013, 2026)
    ],
    {
        "name": "mapbiomas_c4_estadisticas_departamento",
        "url": "https://peru.mapbiomas.org/wp-content/uploads/sites/6/2026/09/MAPBIOMAS-PERU-LULC-COL4-LIMITES-POLITICOS.xlsx",
        "file": "mapbiomas/MAPBIOMAS-PERU-LULC-COL4-LIMITES-POLITICOS.xlsx",
        "page": "https://peru.mapbiomas.org/descargas/estadisticas/",
        "license": "CC BY 4.0 (MapBiomas Perú)",
        "description": "MapBiomas Perú Colección 4, área por clase, departamento y año (para validar nuestro cálculo distrital)",
    },
    {
        "name": "amazon_mining_watch_cicatrices",
        "url": "https://data.source.coop/earthgenome/amazon-mining-watch/amazon_basin_mining_scar_masks.tif",
        "file": "amw/amazon_basin_mining_scar_masks.tif",
        "page": "https://source.coop/earthgenome/amazon-mining-watch",
        "license": "CC BY 4.0 (Earth Genome, Amazon Mining Watch)",
        "description": "Amazon Mining Watch: cicatrices mineras a 10 m con el año de confirmación, solo cuenca amazónica (contraste independiente)",
    },
]

# District polygons with their UBIGEO, served by INGEMMET from the INEI demarcation
DISTRICTS = {
    "name": "distritos_geocatmin",
    "url": "https://geocatmin.ingemmet.gob.pe/arcgis/rest/services/SERV_CARTOGRAFIA_DEMARCACION_WGS84/MapServer/2",
    "file": "limites/distritos_geocatmin.geojson",
    "page": "https://geocatmin.ingemmet.gob.pe/geocatmin/",
    "license": "Servicio público de INGEMMET (GEOCATMIN); el portal no declara una licencia",
    "description": "Límites distritales (CD_DIST = UBIGEO) de la demarcación del INEI, servidos por INGEMMET",
}
