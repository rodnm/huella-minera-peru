# Metodología y hallazgos: minería, luz nocturna y pobreza en los distritos del Perú

Este documento reúne todos los hallazgos del proyecto, incluidos los que debilitan su hipótesis inicial, con el método que produjo cada uno, su incertidumbre y lo que no permite afirmar. Toda cifra sale de `datos/procesados/hallazgos.json`, `datos/procesados/auditoria.json` o `datos/procesados/validacion_pobreza.json`, y se regenera con `uv run python -m scripts.run_all`.

## Síntesis

**Pregunta:** ¿los distritos con minería formal a escala brillan más de noche y son menos pobres que distritos comparables de su departamento?

| # | Hallazgo | Confianza |
|---|---|---|
| 1 | Los distritos mineros brillan entre 2 y 4 veces más por habitante | Sólido |
| 2 | Son menos pobres, y la brecha crece con la escala: de −3 a −6 puntos | Sólido como asociación |
| 3 | **Abrir una mina no se asocia con más caída de la pobreza entre 2013 y 2018**; el placebo también falla | Sólido como ausencia de evidencia |
| 4 | Detrás del promedio hay destinos opuestos: Challhuahuacho pasa de 77 % a 39 %, y Cachachi de 84 % a 77 % | Sólido para los mapas oficiales; la causa es desconocida |
| 5 | La huella minera creció ×2.7 entre 2013 y 2025, y más de la mitad está en Madre de Dios | Sólido en la tendencia; el nivel está en disputa |
| 6 | Entre 21 % y 43 % de la luz de los distritos mineros cae sobre píxeles con minería | Depende de la medición |
| 7 | 8 distritos muy luminosos son, con certeza estadística, más pobres que su departamento | Débil como patrón minero |
| 8 | La apertura típica casi no cambia la luz; Cachachi (×19.6) es el caso extremo | Sólido |
| 9 | La luz nacional creció 93 % entre 2013 y 2025 | Medición estable; significado sin explicar |
| 10 | Estimación propia de pobreza distrital 2023–25, validada contra el mapa 2018 | Útil con intervalos anchos |

**Lo que los datos no permiten decir:** que la mina reduzca o no reduzca la pobreza. Son asociaciones entre mapas estimados.

---

## 1. Hallazgos

### H1. Los distritos mineros brillan más

| | Valor |
|---|---|
| **Cifra** | Mediana 3.07 veces por habitante; promedio 4.15; agregada 1.90 |
| **Controlando** | +1.02 log-puntos de luz total (t = 7.8), con área, población y departamento |
| **Datos** | Luz 2018; 126 distritos con producción en régimen general 2016–18, de 1,873 con pobreza |
| **Robustez** | Sin distritos de hidrocarburos: +1.04 log-puntos. Con solo píxeles de 1 nW o más, la razón de medianas sube a 4.1 |
| **No permite afirmar** | Que más luz sea más bienestar: incluye la iluminación de la operación minera (H6) |

### H2. Son menos pobres, y más cuanto mayor es la operación

| Definición o especificación | Brecha (pp) | IC 95 % | Distritos mineros |
|---|---|---|---|
| Base: departamento, población y área | **−2.95** | −5.27 a −0.62 | 126 |
| Errores agrupados por provincia | −2.95 | −5.41 a −0.49 | 126 |
| Errores agrupados por departamento | −2.95 | −5.57 a −0.33 | 126 |
| Con región natural | −3.90 | −6.11 a −1.69 | 126 |
| Sin Lima ni Callao | −2.91 | −5.36 a −0.45 | 119 |
| Sin provincias con distritos nuevos | −3.24 | −5.55 a −0.93 | 122 |
| Con al menos 1 km² de huella | −4.10 | −7.87 a −0.33 | 50 |
| **Los 30 mayores productores** | **−6.00** | −10.31 a −1.69 | 30 |
| Ponderado por población | −3.50 | −9.35 a +2.35 | 126 |
| Con la misma luz por habitante | +1.63 | −0.66 a +3.92 | 126 |

- **Lectura:** el signo se sostiene en casi todas las especificaciones y la brecha crece con la escala. Solo cruza el cero al ponderar por población.
- **Última fila:** no prueba que "no haya diferencia". Es un resultado no significativo, y la luz es en parte efecto de la mina, así que controlar por ella es discutible.
- **No permite afirmar:** causalidad. Una sola foto no dice cuán pobres eran antes (ver H3).

### H3. Abrir una mina no se asocia con más caída de la pobreza

Cambio del mapa 2013 al de 2018, contra distritos sin mina en toda la serie, con pobreza inicial, población, área, región natural y departamento, y errores agrupados por provincia.

| Grupo | Efecto (pp) | IC 95 % | n | Sin distritos partidos o agrupados | Sin Lima |
|---|---|---|---|---|---|
| Establecida (produce desde 2013–14) | −2.00 | −3.65 a −0.35 | 120 | −2.08 | −2.53 |
| **Abre entre los mapas (2015–18)** | **−0.71** | **−4.72 a +3.30** | 31 | −0.51 | −0.80 |
| **Placebo: abre después de 2018** | **−2.68** | **−5.00 a −0.36** | 28 | −2.60 | −3.64 |

- **Cambio mediano sin controles:** sin mina −8.49, abre entre mapas −8.19, establecida −6.71, abre después −5.99.
- **Lectura:** el placebo debería dar cero y no da. Los distritos donde la mina abriría *después* ya bajaban más, lo que apunta a diferencias previas entre zonas. Por eso tampoco se atribuye el −2.00 de las establecidas a la minería.
- **Precisión:** con 31 aperturas, el intervalo no descarta efectos de hasta ±4 puntos. Esto es ausencia de evidencia, no evidencia de que no haya efecto.
- **Límites:** los mapas usan bases distintas (SISFOH y censo), el de 2018 usa el de 2013 como insumo, y ambos son estimaciones.

### H4. Destinos opuestos con aperturas parecidas

| Distrito | Mina (inicio) | Mapa 2013 | Mapa 2018 | Estimación propia 2023–25 |
|---|---|---|---|---|
| Huaquirca | Valeria (2015) | 75.2 (62.9–87.5) | 25.5 (14.7–36.3) | 18.7 (9.2–30.6) |
| Challhuahuacho | Las Bambas (2015) | 77.4 (71.1–83.8) | 39.0 (28.6–49.4) | 21.7 (12.3–32.9) |
| Oyolo | Inmaculada (2015) | 71.8 (59.3–84.3) | 39.7 (24.3–55.1) | 41.5 (28.6–55.1) |
| **Cachachi** | Shahuindo (2016) | **83.7 (79.6–87.9)** | **76.9 (70.3–83.4)** | **63.5 (50.7–75.5)** |

- De las 31 aperturas, **6 tienen una caída confirmada** (el intervalo de 2018 queda completamente por debajo del de 2013): Huaquirca, Challhuahuacho, Oyolo, Ocoyo, Laramarca y Marmot. En 5 la pobreza subió.
- **No permite afirmar por qué.** Son hipótesis sin verificar: el tamaño de la operación, el canon, la migración de trabajadores, que cambia quién vive en el distrito, y el cambio de base entre mapas.

### H5. La huella minera casi se triplicó

| | Valor |
|---|---|
| **Cifra** | 727 km² en 2013 → 1,985 km² en 2025 (×2.73; 1,258 km² nuevos) |
| **Madre de Dios** | De 46 % a 57 % de la huella, con 1.1 % de la luz nacional |
| **Mayor crecimiento** | Inambari (+329 km²), Madre de Dios (+205), Laberinto (+115), Huepetuhe (+114), todos en Madre de Dios; luego Marcona (+41) |
| **Validación** | Contra la tabla oficial de MapBiomas: 0.25 % de diferencia nacional máxima, 4.8 % departamental |

- **Nivel en disputa:** Maus et al. da 3,526 km² (2019) y MapBiomas 1,109 km² (2019). En Madre de Dios, 2,538 km² contra unos 507 km² (2018). El 85.8 % del área de MapBiomas 2019 cae en píxeles que tocan un polígono de Maus. MapBiomas informa 74 % de exactitud de productor para su grupo "sin vegetación", lo que sugiere subestimación.
- **No distingue** minería industrial, artesanal o ilegal, e incluye la no metálica.
- **Dos mediciones distintas:** 43 de los 126 distritos mineros de MINEM no tienen huella visible (subterránea, plantas o atribución), y 164 de los 1,041 km² de 2018 están fuera de esos distritos.

### H6. Cuánta de la luz es de la mina

| Un píxel de luz cuenta como "mina" si su fracción minera supera | Agregado | Distrito mediano | Cachachi |
|---|---|---|---|
| 0 | 43.1 % | 13.0 % | 86.8 % |
| 5 % | 38.4 % | 7.1 % | 73.9 % |
| 10 % | 35.7 % | 3.8 % | 67.2 % |
| 25 % | 29.2 % | 1.3 % | 58 % |
| 50 % | 20.9 % | 0.0 % | 39 % |

- **Lectura:** el 43 % es un techo. Con la regla más amplia, los píxeles marcados suman 3,131 km² para 1,043 km² de minería real. El agregado lo dominan pocas operaciones grandes.
- Con esa misma regla amplia, fuera de los píxeles mineros la ventaja por habitante baja de 3.07 a 1.65 veces.

### H7. Los distritos-paradoja no son exclusivos de la minería

**Regla:** distrito con luz por habitante en el 25 % más alto del país y pobreza mayor que la mediana de su departamento. Se **confirma** solo si el límite inferior del IC 95 % también la supera.

- **Resultado:** 8 confirmados (Cachachi, Encañada, Tapay, Cayarani, Caylloma, Palca, Chavín, Carumas) y 12 posibles.

| Umbral de luz | Mineros confirmados | No mineros confirmados | p (Fisher) |
|---|---|---|---|
| 50 % más alto | 11 de 95 | 64 de 841 | 0.167 |
| 30 % más alto | 8 de 72 | 27 de 490 | 0.111 |
| **25 % más alto** | **8 de 67 (11.9 %)** | **23 de 401 (5.7 %)** | **0.066** |
| 20 % más alto | 7 de 61 | 18 de 314 | 0.154 |
| 10 % más alto | 5 de 43 | 8 de 145 | 0.178 |

- **Sobre todos los distritos es un empate:** 16.7 % de los mineros y 16.3 % de los no mineros están confirmados como más pobres que su departamento.
- **Lectura:** el patrón existe y es cerca del doble entre los mineros muy luminosos, pero no alcanza significancia convencional y no es exclusivo de la minería.
- **Cachachi está cerca del umbral:** 20.1 de luz por mil habitantes, con corte en 17.3; sale con el umbral de 20 % (20.4).

### H8. La apertura típica casi no cambia la luz

| | Valor |
|---|---|
| **Aperturas 2015–22** | 49 |
| **Razón mediana de luz (después/antes)** | 1.14, contra 1.08 en distritos sin mina del mismo departamento |
| **Con exceso sobre su control** | 57 % |
| **Cachachi** | ×19.6, el mayor de los 49, partiendo de casi cero (28 → 556) |

Cachachi es real: su serie va de 5 (2013) a 914 (2025), y la huella de 0.8 a 9.4 km². Pero es **el caso extremo, no el patrón**. Muchas aperturas son unidades pequeñas.

### H9. La luz nacional creció 93 %

- **Medición estable:** el crecimiento no cambia al filtrar el ruido (93.3 % total; 93.1 % con píxeles de 1 nW o más). Dentro del Perú no hay píxeles sin dato ni negativos.
- **Sin explicar:** +12.7 % en 2020, en plena pandemia, y +12.4 % en 2022, con un salto de píxeles iluminados.
- **Sin segunda fuente** de luz que lo confirme. No se presenta como crecimiento económico.

### H10. Pobreza nacional, departamental y distrital estimada

**Nacional, de Sumaria:**

| 2013 | 2014 | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 23.9 | 22.7 | 21.8 | 20.7 | 21.7 | 20.5 | 20.2 | 30.1 | 25.9 | 27.5 | 29.0 | 27.6 | 25.7 |

De 2016 a 2025 coincide en los 10 años con el [informe técnico del INEI](https://cdn.www.gob.pe/uploads/document/file/9911234/8087825-informe-tecnico-de-pobreza-monetaria-2016-2025.pdf). 2013–2015 están pendientes de cruce.

**Distrital estimada (estimación del proyecto, no dato del INEI):** `datos/procesados/pobreza_estimada.csv`.

| Ventana | Distritos estimados | Con muestra | Hogares por distrito (mediana) | γ mediana | Ancho del intervalo (mediana) |
|---|---|---|---|---|---|
| 2017–19 | 1,853 | 1,320 | 42 | 0.14 | 22.5 pp |
| 2023–25 | 1,873 | 1,308 | 39 | 0.19 | 25.2 pp |

**Validación de 2017–19 contra el mapa 2018:**

| Método | Error absoluto medio | Ponderado por población | Correlación | Dentro del intervalo del INEI |
|---|---|---|---|---|
| **Modelo** | **7.06 pp** | 3.16 | 0.839 | 73.0 % |
| Línea base (mapa 2013 + cambio departamental) | 8.40 pp | 4.29 | 0.820 | 63.5 % |
| Mapa 2013 sin cambios | 11.82 pp | 5.75 | 0.828 | 46.7 % |

- **Distritos sin muestra:** el modelo apenas mejora (9.71 contra 10.33) y su correlación es algo menor (0.667 contra 0.689). Es la parte más débil.
- **Optimista:** el mapa 2018 usó el de 2013 como insumo, y el modelo también.
- **Uso correcto:** γ mediana de 0.19 significa que **el modelo pesa más que la encuesta**. La mayoría de los distritos queda cerca de lo que predice el mapa 2018. Sirve para ver patrones y rangos, no para ordenar distritos parecidos ni para seguir cambios finos.

---

## 2. Metodologías

### M1. Descarga y trazabilidad

`scripts/obtener_datos.py` y `scripts/obtener_luz.py` bajan cada fuente y fijan URL, fecha y SHA-256 en `datos/originales/MANIFEST.json`. Los crudos no se versionan. Se usa un User-Agent que identifica al proyecto, sin hacerse pasar por un navegador, y TLS verificado contra el almacén del sistema.

### M2. Producción minera (MINEM) y cruce a UBIGEO

1. Se unifican 86 archivos de 2013–2025 en dos formatos; el año es la suma de los meses.
2. Unidades a toneladas finas (TMF, g y kg finos, TLF).
3. Filtros, con filas que entran y salen: lectura 10,580 → régimen general 6,601 → 8 metales principales 6,445 → sin fundición ni refinería 6,289 → sin agregados artesanales regionales 6,261.
4. Nombre a UBIGEO: 6,261 de 6,261, 2 por el crosswalk manual `datos/referencias/crosswalk_manual.csv` (Nazca/Nasca).
5. Panel distrito × año: 1,164 filas, 179 distritos. El metal principal es aquel donde el distrito tiene mayor participación nacional, para comparar oro y cobre sin precios.

**Definición de "distrito minero":** producción en régimen general (gran y mediana minería). Los productores pequeños y los informales cuentan como no mineros, lo que contamina la comparación, sobre todo en Madre de Dios.

### M3. Luz nocturna

NASA Black Marble VNP46A4, Colección 2, 500 m, variable `NearNadir_Composite_Snow_Free`, sin el flag 255. Suma de radiancia por distrito con exactextract, que pondera los píxeles cortados por el borde. Los negativos pasan a 0. La luz por habitante usa la población proyectada a 2020 sobre la luz de 2018.

### M4. Huella minera

MapBiomas publica el área solo por departamento, así que el cálculo distrital es propio. La máscara de clase 30 a 30 m se promedia sobre la grilla de luz (`rasterio.warp.reproject`, promedio), por franjas. El área de cada píxel es `R²·Δλ·|sin φ₁ − sin φ₂|`, con el radio authálico, y se suma fracción × área por distrito.

### M5. Pobreza oficial

INEI, mapas 2013 y 2018, método Elbers-Lanjouw-Lanjouw. El INEI publica un **intervalo**, no un valor puntual: se usa el punto medio y se conserva el intervalo. El dato `Poverty.csv` del curso coincide exactamente con ese punto medio en los 1,873 distritos. En 2013, los distritos partidos en grupos se colapsan por población y los límites negativos pasan a 0. 25 distritos creados después de 2017 no tienen dato en 2018.

### M6. Comparaciones

Corte en 2018: luz 2018, pobreza 2018, producción 2016–18. Regresión con efectos fijos de departamento y errores robustos o agrupados: `pobreza ~ minero + log(población) + log(área) + C(departamento)`. Para el cambio 2013→2018 se agrega la pobreza inicial, porque los distritos más pobres tienden a bajar más. El grupo placebo son los distritos cuya primera producción es posterior a 2018.

### M7. Estimación de pobreza distrital (Fay-Herriot)

La ENAHO no representa a los distritos: en 2024 cubre 1,271, con mediana de 14 hogares. Por eso una tasa directa no se publica, y se usa un modelo de área (`brillo/fay_herriot.py`).

1. **Tasa directa:** ventana de 3 años, peso de personas `FACTOR07 × MIEPERHO`.
2. **Escala y error:** `y = arcsin(√p)` y `D = deff / (4·n_ef)`, con n efectivo de Kish y efecto de diseño por departamento (conglomerados dentro de estratos).
3. **Modelo:** `y_i = x_i'β + u_i + e_i`, con `σ²` por REML.
4. **Estimador:** `θ_i = γ_i·y_i + (1 − γ_i)·x_i'β`, con `γ_i = σ²/(σ² + D_i)`. Un distrito sin muestra recibe `x_i'β`.
5. **Predictores:** mapa oficial previo, log de densidad, región natural y departamento.
6. **Ajuste:** las tasas se escalan para sumar la tasa directa de cada departamento.
7. **Error:** Prasad-Rao con corrección REML; el intervalo se construye en escala arcoseno.

**Regla central:** luz, producción y huella **no** son predictores. Usarlas fabricaría la relación que después se compara. Aun así, los mapas del INEI no son independientes de todo: usan consumo eléctrico, entre otros registros.

**Criterio de aceptación:** en 2017–19, el modelo debía ganarle a la línea base contra el mapa 2018. Lo cumplió (ver H10).

### M8. Auditoría

`scripts/auditar_datos.py` intenta romper los resultados: hashes, totales de MINEM, vacíos en la luz, umbrales de H6, especificaciones de H2, comparación minero/no minero en H7 y control en H8. Escribe `datos/procesados/auditoria.json`.

---

## 3. Qué se verificó y qué no

| Comprobación | Resultado |
|---|---|
| Hashes del `MANIFEST` | 108 de 108 |
| Panel | 24,674 filas, claves únicas, sin nulos en luz ni huella |
| Suma de MINEM contra sus totales (8 metales, 2013–2019) | Diferencia prácticamente nula en 56 comparaciones |
| Huella contra la tabla oficial de MapBiomas | 0.25 % nacional, 4.8 % departamental |
| Pobreza nacional contra el INEI, 2016–2025 | Coincide en los 10 años |
| Regla gasto contra línea, 2013–2025 | 100 % en los 13 años |
| Referencia con Stata 17 (`docs/referencia_stata.do`, 2024) | Tasas departamentales idénticas; razón de errores estándar de 0.92 a 1.01 |
| Benchmark de la sesión 7 (2021) | San Borja primero por km²; brecha +1.84 log-puntos, mismo signo |
| **Coordenadas de MINEM contra el distrito nombrado** | **No llega a la meta del 95 %: 84 % exacto, 93 % a 5 km o menos**; 33 puntos a más de 25 km son errores de MINEM (Las Bambas a 475 km en 2016–17; Iscaycruz y Yauliyacu intercambiadas en 2024). Por eso la producción va por nombre y la huella por geometría |

**Sin verificar:**

- MINEM 2020–2025 contra totales propios, y pobreza 2013–2015 contra el informe del INEI que las publica.
- La validación de MapBiomas prueba nuestro cálculo, no que su clasificación sea correcta en terreno.
- La luz no tiene una segunda fuente.
- La lista `datos/referencias/hidrocarburos.csv` identifica los casos atípicos en los datos, pero su atribución a instalaciones de gas y petróleo es conocimiento general, **sin fuente citada**. Excluirlos no cambia las brechas.
- Las Sumarias de años distintos pueden repetir hogares de la parte panel de la ENAHO, lo que hace que el n efectivo de la ventana sea algo optimista.

---

## 4. Afirmaciones corregidas durante el trabajo

| Se dijo | Se corrige | Por qué |
|---|---|---|
| "72 % de la huella está en Madre de Dios" | 46–57 % según el año | Era la cifra de Maus; con MapBiomas cambia |
| "La pobreza casi no se mueve" | Son menos pobres, y la brecha llega a −6 pp en los mayores productores | H2 |
| "Con la misma luz, la minería no marca diferencia" | No significativo no es igual a sin diferencia | Y la luz es en parte efecto de la mina |
| "El 43 % de la luz es la mina" | Entre 21 % y 43 %, y 13 % en el distrito mediano | H6 |
| "87 % de la luz de Cachachi es la mina" | Entre 39 % y 87 % | H6 |
| "20 distritos-paradoja" | 8 confirmados y 12 posibles | El intervalo cruza la mediana en 12 |
| "Tapay ya no se puede afirmar" | Tapay sí se confirma | Error propio al leer la tabla |
| "El Perú minero se encendió" | No se sostiene como afirmación general | H8 |

---

## 5. Fuentes

| Fuente | Uso | Licencia |
|---|---|---|
| NASA Black Marble VNP46A4 v2 ([DOI](https://doi.org/10.5067/VIIRS/VNP46A4.002)); Román et al. (2018), *Remote Sensing of Environment* 210 | Luz | Datos abiertos de NASA |
| MapBiomas Perú, [Colección 4](https://peru.mapbiomas.org/descargas/mapas-de-las-colecciones/) | Huella anual | CC BY 4.0 |
| Maus et al. (2022), *Scientific Data* 9, 433 ([PANGAEA](https://doi.org/10.1594/PANGAEA.942325)) | Validación de la huella | CC BY-SA 4.0 |
| MINEM, [Producción Minera](https://www.gob.pe/institucion/minem/informes-publicaciones/5472883-produccion-minera) y Principales Unidades | Producción | Información pública |
| INEI, [Mapa de Pobreza 2018](https://www.gob.pe/institucion/inei/informes-publicaciones/3204872-mapa-de-pobreza-provincial-y-distrital-2018) y [2013](https://www.inei.gob.pe/media/MenuRecursivo/publicaciones_digitales/Anexo_Estadistico_MapaPobreza2013.xlsx) | Pobreza oficial | Información pública |
| INEI, [ENAHO módulo 34](https://proyectos.inei.gob.pe/microdatos/), 2013–2025 | Pobreza y estimación | Información pública |
| INGEMMET, GEOCATMIN | Límites distritales | Servicio público |

**Métodos:** Fay y Herriot (1979), *JASA* 74(366). Prasad y Rao (1990), *JASA* 85(409). Datta y Lahiri (2000), *Statistica Sinica* 10(2). Elbers, Lanjouw y Lanjouw (2003), *Econometrica* 71(1).

## 6. Cómo reproducir

```bash
uv sync
# Token gratuito de NASA Earthdata en .env: BLACKMARBLE_TOKEN=...
uv run python -m scripts.run_all
uv run pytest
```

Unos 9 GB de descargas. Stata no forma parte del pipeline: `docs/referencia_stata.do` es solo un contraste.
