"""Atlas of Peru's mining footprint, 2013-2025. Run from the repository root: streamlit run dashboard/app.py"""
import time

import altair as alt
import pandas as pd
import pydeck
import streamlit as st

from logica import (INDICATORS, MADRE_DE_DIOS, PERU_BOUNDS, bounds_of, contrast_paragraphs, csv_rows, department_rows,
                    district_features, findings, fit_view, km2, kpis, load_atlas, percent, points_for_year, ranking, rgb,
                    scope_mask, thresholds_for, title_case)

PLAY_PAUSE_SECONDS = 0.7
MAP_HEIGHT = 720
PIXELS, METERS = pydeck.types.String("pixels"), pydeck.types.String("meters")  # pydeck reads bare strings as expressions
BLANK_MAP = {"version": 8, "sources": {}, "layers": [{"id": "fondo", "type": "background", "paint": {"background-color": "#0b1713"}}]}

st.set_page_config(page_title="La huella de la minería en el Perú, 2013–2025", page_icon="⛏️", layout="wide")


@st.cache_resource(show_spinner="Cargando el atlas…")
def get_atlas():
    return load_atlas()


atlas = get_atlas()


@st.cache_data(show_spinner=False)
def cached_points(year: int) -> list[dict]:
    return points_for_year(atlas, year)


@st.cache_data(show_spinner=False)
def cached_features(indicator: str, department: str, i: int) -> dict:
    return district_features(atlas, indicator, department, i)


SURFACE, SERIES, RAMPS = atlas.tokens["surface"], atlas.tokens["series"], atlas.tokens["ramps"]

st.html(f"""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600;9..144,700&family=IBM+Plex+Sans+Condensed:wght@600;700&family=IBM+Plex+Sans:wght@400;500;600&display=swap">
<style>
html, body, [data-testid="stAppViewContainer"], [data-testid="stMarkdownContainer"], label, input, button {{ font-family: "IBM Plex Sans", system-ui, sans-serif; font-variant-numeric: tabular-nums; }}
[data-testid="stHeader"] {{ display: none; }}
.block-container {{ padding: 0 1.25rem 3rem; max-width: 100%; }}
h1, h2 {{ font-family: Fraunces, Georgia, serif !important; font-weight: 600 !important; letter-spacing: -0.01em; }}
h1 {{ font-size: clamp(2rem, 2.7vw, 2.8rem) !important; line-height: 1.1 !important; padding: 0.75rem 0 0 !important; }}
h2 {{ font-size: clamp(1.45rem, 2.1vw, 1.95rem) !important; line-height: 1.15 !important; padding-bottom: 0.5rem !important; }}
h3 {{ font-size: 1.05rem !important; font-weight: 600 !important; line-height: 1.3 !important; padding: 0 !important; font-family: "IBM Plex Sans", sans-serif !important; }}
.st-key-controles {{ position: sticky; top: 0; z-index: 50; background: {SURFACE["background"]}; padding: 0.6rem 0 0.35rem; border-bottom: 1px solid {SURFACE["grid"]}; }}
.question {{ font: 600 1.15rem/1.35 Fraunces, Georgia, serif; color: {RAMPS["footprint"][6]}; margin-bottom: 0.75rem; }}
.lead, .coverage, .note {{ color: {SURFACE["text_muted"]}; font-size: 0.93rem; }}
.coverage {{ font-size: 0.82rem; }}
.scope {{ font-weight: 600; font-size: 0.95rem; padding-top: 0.75rem; border-top: 1px solid {SURFACE["grid"]}; margin: 0.5rem 0 0.9rem; }}
.kpis {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1rem 1.25rem; margin: 0 0 1rem; padding: 0; }}
.kpis div {{ display: flex; flex-direction: column-reverse; justify-content: flex-end; gap: 0.15rem; }}
.kpis dt {{ color: {SURFACE["text_muted"]}; font-size: 0.82rem; line-height: 1.3; }}
.kpis dd {{ margin: 0 !important; font: 700 2.1rem/1.05 "IBM Plex Sans Condensed", sans-serif; }}
.kpis small {{ display: block; font: 400 0.8rem/1.3 "IBM Plex Sans", sans-serif; color: {SURFACE["text_muted"]}; margin-top: 0.15rem; }}
.st-key-mapa {{ position: relative; background: #0b1713; gap: 0; }}
.st-key-mapa [data-testid="stElementContainer"]:has(.legend), .st-key-mapa [data-testid="stElementContainer"]:has(.big-year), .st-key-mapa [data-testid="stHtml"] {{ position: static; height: 0; min-height: 0; margin: 0; padding: 0; }}
.big-year {{ position: absolute; left: 1.25rem; bottom: 0.75rem; z-index: 5; pointer-events: none; font: 700 clamp(4rem, 8vw, 7.5rem)/0.9 Fraunces, Georgia, serif; letter-spacing: -0.03em; color: {SURFACE["text"]}; }}
.legend {{ position: absolute; left: 1rem; top: 1rem; z-index: 5; max-width: 21rem; padding: 0.5rem 0.7rem; background: {SURFACE["background"]}; border: 1px solid {SURFACE["grid"]}; border-radius: 3px; font-size: 0.8rem; line-height: 1.35; color: {SURFACE["text_muted"]}; }}
.legend strong {{ display: block; color: {SURFACE["text"]}; font-weight: 600; margin-bottom: 0.25rem; }}
.legend-row {{ display: flex; align-items: center; gap: 0.4rem; color: {SURFACE["text"]}; }}
.legend-dot {{ width: 0.65rem; height: 0.65rem; border-radius: 50%; flex: none; }}
.legend-steps {{ display: flex; gap: 2px; margin: 0.25rem 0 0.1rem; }}
.legend-steps span {{ flex: 1; height: 0.6rem; min-width: 1.9rem; }}
.legend-ticks {{ display: flex; justify-content: space-between; color: {SURFACE["text"]}; }}
.legend p {{ margin: 0.3rem 0 0; }}
.finding {{ font: 600 1.25rem/1.32 Fraunces, Georgia, serif; }}
.finding small {{ display: block; font: 400 0.88rem/1.45 "IBM Plex Sans", sans-serif; color: {SURFACE["text_muted"]}; margin-top: 0.5rem; }}
.card dl {{ margin: 0.5rem 0 0; padding: 0; display: grid; grid-template-columns: 1fr auto; gap: 0.25rem 0.75rem; font-size: 0.88rem; }}
.card dt {{ color: {SURFACE["text_muted"]}; }}
.card dd {{ margin: 0 !important; text-align: right; font-weight: 500; }}
.card h3 {{ font: 600 1.3rem/1.15 Fraunces, Georgia, serif !important; }}
.card p {{ color: {SURFACE["text_muted"]}; font-size: 0.85rem; margin: 0; }}
@media (max-width: 640px) {{ .st-key-controles {{ position: static; }} .legend p {{ display: none; }} .block-container {{ padding: 0 1rem 2.5rem; }} }}
</style>
""")



@alt.theme.register("atlas", enable=True)
def atlas_theme() -> dict:
    return {"config": {
        "background": "transparent", "view": {"stroke": None},
        "font": "IBM Plex Sans",
        "axis": {"labelColor": SURFACE["text_muted"], "titleColor": SURFACE["text_muted"], "gridColor": SURFACE["grid"],
                 "domain": False, "tickColor": SURFACE["grid"], "labelFontSize": 12, "titleFontSize": 12, "tickSize": 0},
        "legend": {"labelColor": SURFACE["text"], "titleColor": SURFACE["text_muted"], "labelFontSize": 12},
        "text": {"color": SURFACE["text"], "fontSize": 12},
    }}


# ---------- state ----------

last_year = atlas.years[-1]
if "year" not in st.session_state:
    st.session_state.update(year=atlas.years[0], playing=True, department="", indicator="huella", district=None, search=None)


def stop_playing() -> None:
    st.session_state.playing = False


def choose_year() -> None:
    # Any click also reports the slider as the browser has it, which during the animation can be the previous year:
    # only a value other than the one last sent to the browser is the user moving it
    if st.session_state.year_slider != st.session_state.get("slider_sent"):
        st.session_state.year = st.session_state.year_slider
        stop_playing()


def toggle_play() -> None:
    if st.session_state.playing:
        st.session_state.playing = False
        return
    if st.session_state.year == last_year:
        st.session_state.year = atlas.years[0]
    st.session_state.playing = True


def choose_department() -> None:
    stop_playing()
    current = st.session_state.district
    if current and st.session_state.department:
        row = atlas.districts[atlas.districts["ubigeo"] == current]
        if not row.empty and row["department"].iat[0] != st.session_state.department:
            st.session_state.district = None
            st.session_state.search = None


LABELS = {f"{title_case(r.name)}, {title_case(r.province)}, {title_case(r.department)}": r.ubigeo
          for r in atlas.districts.itertuples(name="Row", index=False)}


def choose_search() -> None:
    stop_playing()
    picked = st.session_state.search
    st.session_state.district = LABELS.get(picked) if picked else None


def close_card() -> None:
    st.session_state.district = None
    st.session_state.search = None


# A year chosen by the previous frame of the animation; it only counts if the animation is still playing
pending = st.session_state.pop("next_year", None)
if pending is not None and st.session_state.playing:
    st.session_state.year = pending

# ---------- filters ----------

with st.container(key="controles"):
    play_col, year_col, department_col, indicator_col, search_col = st.columns([1, 4, 2, 2.4, 2.6], vertical_alignment="bottom")
    with play_col:
        st.button("Pausar" if st.session_state.playing else "Reproducir", on_click=toggle_play, width="stretch")
    with year_col:
        year_slot = st.container()  # filled after the map: it takes seconds to arrive, and the slider must not run ahead of it
    with department_col:
        names = sorted(atlas.districts["department"].unique())
        st.selectbox("Departamento", [""] + names, key="department", on_change=choose_department,
                     format_func=lambda v: title_case(v) if v else "Todo el Perú")
    with indicator_col:
        st.selectbox("Mostrar en el mapa", list(INDICATORS), key="indicator", format_func=lambda k: {
            "huella": "Huella minera", "nueva": "Huella nueva desde 2013", "luz": "Luz nocturna por km²",
            "pobreza": "Pobreza monetaria 2018 (INEI)"}[k])
    with search_col:
        st.selectbox("Buscar distrito", list(LABELS), key="search", index=None, on_change=choose_search,
                     placeholder="Por ejemplo, Inambari")

year, department, indicator, district = (st.session_state.year, st.session_state.department, st.session_state.indicator,
                                         st.session_state.district)
i = atlas.years.index(year)
scope_title = title_case(department) if department else "Todo el Perú"
scope_inline = title_case(department) if department else "todo el Perú"


def kpi_html() -> str:
    k = kpis(atlas, department, i)
    change = ("– <small>es el año de partida</small>" if i == 0 else "– <small>sin huella en 2013</small>"
              ) if k["ratio"] is None else f"×{k['ratio']:.1f} <small>{'+' if k['change'] >= 0 else '−'}{km2(abs(k['change']))} km²</small>"
    if i == 0 or k["change"] <= 0:
        top = "– <small>sin aumento que repartir</small>"
    elif k["top_share"] is None:
        top = f"– <small>solo {k['gains']} distritos con aumento</small>"
    else:
        top = f"{percent(k['top_share'])} <small>de {km2(k['change'])} km²</small>"
    return f"""<div class="scope">{scope_title}</div><dl class="kpis">
      <div><dt>Huella en {year}</dt><dd>{km2(k['area'])} <small>km²</small></dd></div>
      <div><dt>Frente a 2013</dt><dd>{change}</dd></div>
      <div><dt>Distritos con huella</dt><dd>{k['districts']:,} <small>{k['districts_first']:,} en 2013</small></dd></div>
      <div><dt>Del aumento, en sus 10 distritos que más crecieron</dt><dd>{top}</dd></div></dl>"""


def legend_html() -> str:
    footprint = RAMPS["footprint"]
    if indicator == "huella":
        return f"""<div class="legend"><strong>Suelo minero visto desde satélite</strong>
          <div class="legend-row"><span class="legend-dot" style="background:{footprint[2]}"></span>Celda con huella en 2013</div>
          <div class="legend-row"><span class="legend-dot" style="background:{footprint[6]}"></span>Celda con huella después de 2013</div>
          <p>Cada círculo es una celda de 500 m y su área equivale a la superficie minera. De lejos, los más chicos se agrandan para que se vean.</p></div>"""
    spec = INDICATORS[indicator]
    ticks = thresholds_for(atlas, indicator)
    shown = [ticks[0], ticks[2], ticks[4], ticks[5]]
    text = [spec.format(v) for v in shown]
    extra = {"pobreza": "<p>Es de 2018: no cambia con el año elegido.</p>", "luz": "<p>Es contexto: no mide minería.</p>"}.get(indicator, "")
    steps = "".join(f'<span style="background:{c}"></span>' for c in RAMPS[spec.ramp])
    labels = "".join(f"<span>{t}</span>" for t in text)
    return f"""<div class="legend"><strong>{spec.label} ({spec.unit})</strong><div class="legend-steps">{steps}</div>
      <div class="legend-ticks">{labels}</div>{extra}</div>"""


def build_deck() -> pydeck.Deck:
    layers = [
        pydeck.Layer("GeoJsonLayer", cached_features(indicator, department, i), id="distritos", pickable=True, stroked=True,
                     filled=True, get_fill_color="properties.fill", get_line_color=rgb(SURFACE["grid"], 150),
                     line_width_units=PIXELS, get_line_width=0.4, auto_highlight=True, highlight_color=[241, 233, 214, 50]),
        pydeck.Layer("GeoJsonLayer", atlas.outlines, id="departamentos", stroked=True, filled=False,
                     get_line_color=rgb(SURFACE["text_muted"], 120), line_width_units=PIXELS, get_line_width=0.8),
    ]
    if indicator == "huella":
        layers.append(pydeck.Layer("ScatterplotLayer", cached_points(year), id="huella", get_position="p", get_radius="r",
                                   get_fill_color="c", radius_units=METERS, radius_min_pixels=0.8, radius_max_pixels=60))
    if district:
        selected = [f for f in atlas.geo["features"] if f["properties"]["ubigeo"] == district]
        layers.append(pydeck.Layer("GeoJsonLayer", {"type": "FeatureCollection", "features": selected}, id="seleccion",
                                   stroked=True, filled=False, get_line_color=rgb(SURFACE["text"]),
                                   line_width_units=PIXELS, get_line_width=2))
    if district:
        bounds = bounds_of(atlas, {district})
    elif department:
        bounds = bounds_of(atlas, set(atlas.districts.loc[scope_mask(atlas, department), "ubigeo"]))
    else:
        bounds = PERU_BOUNDS
    tooltip = {"html": "<b>{nombre}</b><br>{departamento}<br>" + f"{INDICATORS[indicator].label}: " + "{valor}",
               "style": {"backgroundColor": SURFACE["panel"], "color": SURFACE["text"], "fontSize": "13px",
                         "border": f"1px solid {SURFACE['grid']}"}}
    deck = pydeck.Deck(layers=layers, initial_view_state=pydeck.ViewState(**fit_view(bounds, height=MAP_HEIGHT)),
                       map_provider=None, tooltip=tooltip)
    deck.map_style = [BLANK_MAP]  # Streamlit reads the first item of a list: this keeps its default street map out
    return deck


# ---------- first screen: rail and map ----------

rail, map_col = st.columns([1, 2.6], gap="medium")

with map_col:
    with st.container(key="mapa"):
        st.pydeck_chart(build_deck(), height=MAP_HEIGHT, key="mapa_deck")
        # The year lives apart from the slider: a click that interrupts this run before the slider is drawn makes Streamlit
        # forget the slider's state, and with it the year
        with year_slot:
            st.session_state.year_slider = year
            st.slider("Año", atlas.years[0], last_year, key="year_slider", on_change=choose_year)
            st.session_state.slider_sent = year
        st.html(legend_html())
        st.html(f'<div class="big-year" aria-hidden="true">{year}</div>')

with rail:
    st.title("La huella de la minería en el Perú, 2013–2025")
    st.html('<p class="question">¿Dónde apareció y cuánto creció el suelo minero que se ve desde el satélite?</p>')
    st.html('<p class="lead">La minería deja suelo expuesto, y eso se ve desde el espacio. Este atlas suma, distrito por distrito y año por año, lo que MapBiomas clasifica como minería. Una segunda fuente independiente la contrasta donde hay datos, y aquí también se ve en qué discrepan.</p>')
    st.html(kpi_html())
    if district:
        row = atlas.districts.index[atlas.districts["ubigeo"] == district]
        if len(row):
            k = row[0]
            d = atlas.districts.loc[k]
            poverty = "sin dato" if pd.isna(d["poverty"]) else f"{d['poverty']:.1f} % ({d['poverty_low']:.1f} a {d['poverty_high']:.1f})"
            light = atlas.light[k, i]
            with st.container(border=True):
                st.html(f"""<div class="card"><h3>{title_case(d['name'])}</h3><p>{title_case(d['province'])}, {title_case(d['department'])}</p><dl>
                  <dt>Huella en {year}</dt><dd>{km2(atlas.mining[k, i])} km²</dd>
                  <dt>Huella en 2013</dt><dd>{km2(atlas.mining[k, 0])} km²</dd>
                  <dt>Luz por km² en {year}</dt><dd>{'sin dato' if pd.isna(light) else f'{light:.2f}'}</dd>
                  <dt>Pobreza 2018 (INEI)</dt><dd>{poverty}</dd>
                  <dt>Población 2020</dt><dd>{'sin dato' if pd.isna(d['population']) else f"{d['population']:,.0f}"}</dd></dl></div>""")
                st.button("Cerrar la ficha", on_click=close_card)
    st.html('<p class="coverage">Cubre 13 años y todos los distritos del país. Fuente: MapBiomas Perú, Colección 4, clase 30, con imágenes Landsat de 30 m.</p>')

# ---------- findings ----------

st.header("Lo que muestran los datos")
for column, (big, small) in zip(st.columns(3, gap="large"), findings(atlas)):
    column.html(f'<div class="finding">{big}<small>{small}</small></div>')


# ---------- charts ----------

def line_chart(series: list[tuple[str, list[float], str]], years: list[int], marker: int | None, height: int = 300) -> alt.LayerChart:
    table = pd.DataFrame([{"año": y, "serie": name, "km²": value} for name, values, _ in series
                          for y, value in zip(years, values)])
    table["texto"] = table["km²"].map(km2)
    colors = alt.Scale(domain=[s[0] for s in series], range=[s[2] for s in series])
    x = alt.X("año:Q", title=None, scale=alt.Scale(domain=[years[0], years[-1]]), axis=alt.Axis(format="d", tickCount=min(len(years), 13), grid=False))
    y = alt.Y("km²:Q", title="km²", axis=alt.Axis(format=",.0f", tickCount=5))
    base = alt.Chart(table).encode(x=x, y=y, color=alt.Color("serie:N", scale=colors, legend=alt.Legend(orient="top", title=None)))
    lines = base.mark_line(strokeWidth=2)
    hover = alt.selection_point(fields=["año"], nearest=True, on="pointerover", empty=False, clear="pointerout")
    points = base.mark_point(filled=True, size=70).encode(
        opacity=alt.condition(hover, alt.value(1), alt.value(0)),
        tooltip=[alt.Tooltip("año:Q", format="d", title="Año"), alt.Tooltip("serie:N", title="Serie"), alt.Tooltip("texto:N", title="km²")],
    ).add_params(hover)
    ends = base.transform_filter(alt.datum["año"] == years[-1]).mark_text(align="left", dx=8, fontWeight=500, color=SURFACE["text"]).encode(
        text="texto:N", color=alt.value(SURFACE["text"]))
    layers = [lines, points, ends]
    if marker is not None and marker in years:
        rule = alt.Chart(pd.DataFrame({"año": [marker]})).mark_rule(strokeDash=[2, 3], color=SURFACE["text_muted"]).encode(x=x)
        layers.insert(0, rule)
    return alt.layer(*layers).properties(height=height, padding={"right": 56, "top": 4, "left": 0, "bottom": 0})


years = atlas.years
total = lambda mask: [float(atlas.mining[mask, j].sum()) for j in range(len(years))]
if department:
    values = total(scope_mask(atlas, department))
    series = [(title_case(department), values, SERIES["mining"])]
    trend_title = f"{series[0][0]}: de {km2(values[0])} a {km2(values[-1])} km² entre {years[0]} y {years[-1]}"
else:
    madre = scope_mask(atlas, MADRE_DE_DIOS)
    md_values, rest_values = total(madre), total(~madre)
    series = [("Madre de Dios", md_values, SERIES["mining"]), ("Resto del Perú", rest_values, SURFACE["text_muted"])]
    trend_title = f"Madre de Dios se multiplicó por {md_values[-1] / md_values[0]:.1f} y el resto del Perú, por {rest_values[-1] / rest_values[0]:.1f}"
if district and len(atlas.districts.index[atlas.districts["ubigeo"] == district]):
    k = atlas.districts.index[atlas.districts["ubigeo"] == district][0]
    series.append((title_case(atlas.districts["name"].iat[k]), [float(v) for v in atlas.mining[k]], SURFACE["text"]))

st.subheader(trend_title)
st.html('<p class="note">Kilómetros cuadrados clasificados como minería cada año. Fuente: MapBiomas Perú.</p>')
st.altair_chart(line_chart(series, years, year), width="stretch", theme=None)

rank_col, department_col_chart = st.columns(2, gap="large")
spec = INDICATORS[indicator]
with rank_col:
    st.subheader(spec.title(scope_inline))
    st.html(f'<p class="note">{spec.note(year)}</p>')
    rows = ranking(atlas, indicator, department, i)
    if rows:
        table = pd.DataFrame(rows)
        table["orden"] = table["name"] + "|" + table["ubigeo"]
        y_axis = alt.Y("orden:N", sort=None, title=None, axis=alt.Axis(labelExpr="split(datum.label, '|')[0]", labelLimit=170, labelFontSize=13, labelColor=SURFACE["text"]))
        x_max = 100 if indicator == "pobreza" else float(table["value"].max()) * 1.18
        color = {"huella": RAMPS["footprint"][4], "nueva": RAMPS["footprint"][4], "luz": RAMPS["light"][3], "pobreza": RAMPS["poverty"][3]}[indicator]
        tip = [alt.Tooltip("name:N", title="Distrito"), alt.Tooltip("department:N", title="Departamento"), alt.Tooltip("label:N", title=spec.label)]
        x = alt.X("value:Q", title=None, scale=alt.Scale(domain=[0, x_max]), axis=None)
        bars = alt.Chart(table).mark_bar(size=9, cornerRadiusEnd=3, color=color).encode(x=x, y=y_axis, tooltip=tip)
        labels = alt.Chart(table).mark_text(align="left", dx=6, fontWeight=500, color=SURFACE["text"]).encode(x=x, y=y_axis, text="label:N")
        layers = [bars, labels]
        if indicator == "pobreza":
            whisker = alt.Chart(table).mark_rule(color=SURFACE["text_muted"], strokeWidth=2).encode(x=alt.X("low:Q", scale=alt.Scale(domain=[0, x_max]), axis=None), x2="high:Q", y=y_axis)
            layers = [bars, whisker, labels.encode(x=alt.X("high:Q", scale=alt.Scale(domain=[0, x_max]), axis=None))]
        st.altair_chart(alt.layer(*layers).properties(height=36 * len(table) + 8), width="stretch", theme=None)
    else:
        st.info(f"{scope_title} no tiene distritos con este dato en {year}. Prueba otro año o departamento.")
    with st.expander("Ver todos los distritos en una tabla"):
        all_rows = csv_rows(atlas, department, i)
        visible = all_rows[all_rows["huella_km2"] >= 0.01].sort_values("huella_km2", ascending=False)
        st.dataframe(visible[["distrito", "departamento", "huella_km2", "huella_2013_km2"]], hide_index=True, width="stretch",
                     column_config={"distrito": "Distrito", "departamento": "Departamento",
                                    "huella_km2": st.column_config.NumberColumn(f"Huella {year} (km²)", format="%.2f"),
                                    "huella_2013_km2": st.column_config.NumberColumn("Huella 2013 (km²)", format="%.2f")})
    slug = department.lower().replace(" ", "_") if department else "peru"
    st.download_button("Descargar estos distritos en CSV", csv_rows(atlas, department, i).to_csv(index=False).encode("utf-8"),
                       file_name=f"huella_minera_{slug}_{year}.csv", mime="text/csv")

with department_col_chart:
    st.subheader("Huella por departamento")
    st.html('<p class="note">El círculo vacío marca 2013 y el lleno, el año elegido.</p>')
    table = department_rows(atlas, i)
    y_axis = alt.Y("name:N", sort=None, title=None, axis=alt.Axis(labelLimit=170, labelFontSize=13, labelColor=SURFACE["text"]))
    x_scale = alt.Scale(domain=[0, float(table[["now", "first"]].max().max()) * 1.18])
    x = alt.X("now:Q", title=None, scale=x_scale, axis=None)
    tip = [alt.Tooltip("name:N", title="Departamento"), alt.Tooltip("first:Q", format=",.1f", title="2013 (km²)"), alt.Tooltip("now:Q", format=",.1f", title=f"{year} (km²)")]
    link = alt.Chart(table).mark_rule(color=RAMPS["footprint"][2], strokeWidth=2).encode(x=x, x2="first:Q", y=y_axis)
    start = alt.Chart(table).mark_point(size=70, filled=True, color=SURFACE["background"], stroke=RAMPS["footprint"][3], strokeWidth=2).encode(x=alt.X("first:Q", axis=None, scale=x_scale), y=y_axis, tooltip=tip)
    end = alt.Chart(table).mark_point(size=90, filled=True, color=RAMPS["footprint"][5]).encode(x=x, y=y_axis, tooltip=tip)
    labels = alt.Chart(table).mark_text(align="left", dx=10, fontWeight=500, color=SURFACE["text"]).encode(x=x, y=y_axis, text=alt.Text("label:N"))
    st.altair_chart(alt.layer(link, start, end, labels).properties(height=34 * len(table) + 8), width="stretch", theme=None)

# ---------- contrast ----------

st.write("")
text_col, chart_col = st.columns([5, 7], gap="large")
contrast = atlas.summary["contrast"]["madre_de_dios"]
with text_col:
    st.header("¿Se puede confiar en esta tendencia?")
    for paragraph in contrast_paragraphs(atlas):
        st.markdown(paragraph)
with chart_col:
    st.subheader("Madre de Dios: las dos fuentes suben, con distinto nivel y calendario")
    st.html('<p class="note">Kilómetros cuadrados, 2018 a 2024, último año con cicatrices confirmadas.</p>')
    confirmed = [y for y in atlas.summary["contrast"]["years"] if y <= contrast["last_confirmed_year"]]
    st.altair_chart(line_chart([
        ("MapBiomas", [contrast["mapbiomas_km2"][str(y)] for y in confirmed], SERIES["mining"]),
        ("Amazon Mining Watch", [contrast["amw_km2"][str(y)] for y in confirmed], SERIES["contrast"]),
    ], confirmed, None, height=280), width="stretch", theme=None)

# ---------- method, limits and sources ----------

gap = atlas.summary["validation"]["max_national_gap"] * 100
method, limits, sources = st.columns([1, 1.25, 1], gap="large")
with method:
    st.header("Cómo se hizo")
    st.markdown(f"""
1. Se descargan los 13 mapas anuales de MapBiomas Perú y se conservan sus huellas digitales para comprobar que son los mismos archivos.
2. Cada mapa de 30 m se promedia sobre una grilla de 500 m, y esa fracción se multiplica por el área real de cada celda.
3. La superficie se suma por distrito con los límites oficiales de GEOCATMIN.
4. Las sumas se comparan con la tabla oficial de MapBiomas y con Amazon Mining Watch.

La suma nacional difiere de la tabla oficial de MapBiomas en {gap:.2f} % como máximo. Eso muestra que la suma reproduce esa tabla, no que el satélite acierte: por eso existe el contraste.
""")
with limits:
    st.header("Lo que estos datos no dicen")
    st.markdown("""
- **No distinguen minería legal, informal o ilegal.** La clase incluye además la extracción no metálica, como los fosfatos de Sechura.
- **El área exacta está en discusión.** En 2019, los polígonos de Maus y su equipo suman unas tres veces más que MapBiomas en el país, y el grupo de clases sin vegetación de MapBiomas, donde está la minería, tiene 74 % de exactitud de productor.
- **Más de la mitad del aumento no tiene contraste.** Amazon Mining Watch solo cubre la cuenca amazónica, y aquí se compara en Madre de Dios entre 2018 y 2024. El resto se apoya sobre todo en MapBiomas.
- **Las fuentes no coinciden año a año.** Tampoco coinciden fuera de Madre de Dios. Mejor no usar este atlas para fechar un salto.
- **La luz y la pobreza son contexto.** Verlas junto a la huella no significa que una cause la otra, y este atlas no lo afirma. La pobreza es la estimación del INEI para 2018, con su intervalo. La luz nacional tiene saltos que aún no están explicados.
""")
with sources:
    st.header("Fuentes")
    st.markdown("""
- [MapBiomas Perú, Colección 4](https://peru.mapbiomas.org/descargas/mapas-de-las-colecciones/): cobertura anual, CC BY 4.0.
- [Amazon Mining Watch](https://source.coop/earthgenome/amazon-mining-watch), de Earth Genome: cicatrices mineras a 10 m, CC BY 4.0.
- [Maus y otros, polígonos mineros v2](https://doi.org/10.1594/PANGAEA.942325): CC BY-SA.
- [NASA Black Marble, VNP46A4](https://doi.org/10.5067/VIIRS/VNP46A4.002): luz nocturna anual.
- [INEI, Mapa de Pobreza 2018](https://www.gob.pe/institucion/inei/informes-publicaciones/3204872-mapa-de-pobreza-provincial-y-distrital-2018): estimación distrital con intervalo de 95 %.
- [GEOCATMIN, INGEMMET](https://geocatmin.ingemmet.gob.pe/geocatmin/): límites distritales.

[Código, datos y metodología completa en GitHub](https://github.com/rodnm/huella-minera-peru).
""")

# ---------- animation: each year starts when the previous page has been drawn, so slow connections never skip one ----------

if st.session_state.playing:
    time.sleep(PLAY_PAUSE_SECONDS)
    if st.session_state.year >= last_year:
        st.session_state.playing = False
    else:
        st.session_state.next_year = st.session_state.year + 1
    st.rerun()
