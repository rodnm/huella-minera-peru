/* Atlas of Peru's mining footprint. Every figure is computed in the browser from web/data, which scripts/construir_web.py
   writes from datos/procesados, so no number in the page is typed by hand. */
const $ = (id) => document.getElementById(id);
const REDUCED_MOTION = matchMedia("(prefers-reduced-motion: reduce)").matches;
const PERU_BOUNDS = [[-81.4, -18.4], [-68.6, 0.1]];
const MADRE_DE_DIOS = "MADRE DE DIOS";
const VISIBLE_KM2 = 0.01;
const PLAY_MS = 620;

const fmt0 = new Intl.NumberFormat("es-PE", { maximumFractionDigits: 0 });
const fmt1 = new Intl.NumberFormat("es-PE", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const fmt2 = new Intl.NumberFormat("es-PE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const km2 = (value) => (value >= 100 ? fmt0.format(value) : value >= 1 ? fmt1.format(value) : fmt2.format(value));
const pct = (share) => `${fmt0.format(share * 100)} %`;
const rgb = (hex, alpha = 255) => { const c = d3.rgb(hex); return [c.r, c.g, c.b, alpha]; };

const SMALL_WORDS = new Set(["de", "del", "la", "las", "los", "y", "el", "en"]);
const titleCase = (text) => text.toLowerCase().split(" ")
  .map((word, i) => (i && SMALL_WORDS.has(word) ? word : word.charAt(0).toUpperCase() + word.slice(1))).join(" ");

const state = { year: 2013, department: "", indicator: "huella", district: null, playing: false };
const data = {};
let deckgl, viewState, timer;

const INDICATORS = {
  huella: {
    label: "Huella minera", unit: "km²", title: (s) => `Distritos con mayor huella, ${s}`,
    note: (y) => `Superficie clasificada como minería en ${y}.`,
    value: (d, i) => d.m[i], format: km2,
  },
  nueva: {
    label: "Huella nueva desde 2013", unit: "km²", title: (s) => `Distritos donde más creció la huella, ${s}`,
    note: (y) => `Diferencia entre ${y} y 2013. Solo aparecen los distritos donde aumentó.`,
    value: (d, i) => d.m[i] - d.m[0], format: km2,
  },
  luz: {
    label: "Luz nocturna por km²", unit: "nW/cm²/sr", title: (s) => `Distritos con más luz por km², ${s}`,
    note: (y) => `Radiancia sumada por km² en ${y}, NASA Black Marble. Es contexto: no mide minería.`,
    value: (d, i) => d.l[i], format: (v) => fmt2.format(v),
  },
  pobreza: {
    label: "Pobreza monetaria 2018", unit: "%", title: (s) => `Distritos con mayor pobreza estimada, ${s}`,
    note: () => "Punto medio e intervalo de 95 % del Mapa de Pobreza 2018 del INEI. No cambia con el año elegido y es contexto: no prueba una relación con la minería.",
    value: (d) => (d.pov ? d.pov[0] : null), format: (v) => `${fmt1.format(v)} %`,
  },
};

const yearIndex = () => data.panel.years.indexOf(state.year);
const inScope = (d) => !state.department || d.d === state.department;
const scopeDistricts = () => data.panel.districts.filter(inScope);
const scopeName = () => (state.department ? titleCase(state.department) : "todo el Perú");
const sum = (rows, i) => d3.sum(rows, (d) => d.m[i] || 0);

async function load() {
  const json = (name) => fetch(`data/${name}.json`).then((r) => { if (!r.ok) throw new Error(name); return r.json(); });
  const [panel, atlas, geo, outlines, meta, tokens, blob] = await Promise.all([
    json("panel"), json("atlas"), json("distritos"), json("departamentos"), json("huella"), json("tokens"),
    fetch("data/huella.bin").then((r) => { if (!r.ok) throw new Error("huella"); return r.arrayBuffer(); }),
  ]);
  Object.assign(data, { panel, atlas, geo, outlines, tokens });
  data.byUbigeo = new Map(panel.districts.map((d) => [d.u, d]));
  data.pixels = decodePixels(meta, blob);
  data.pixelYears = meta.years;
  data.scales = buildScales();
}

function decodePixels(meta, buffer) {
  const n = meta.count, years = meta.years.length;
  const rows = new Uint16Array(buffer, 0, n);
  const cols = new Uint16Array(buffer.slice(2 * n, 4 * n));
  const shares = new Uint8Array(buffer, 4 * n);
  const [left, dx, top, dy] = meta.transform;
  const firstYearMin = Math.ceil(meta.min_fraction * 255);
  return Array.from({ length: n }, (_, p) => {
    const lat = top + (rows[p] + 0.5) * dy;
    return {
      position: [left + (cols[p] + 0.5) * dx, lat],
      shares: shares.subarray(p * years, (p + 1) * years),
      area: dx * 111320 * Math.cos(lat * Math.PI / 180) * Math.abs(dy) * 110574,
      existed: shares[p * years] >= firstYearMin,
    };
  });
}

function buildScales() {
  const { footprint, light, poverty } = data.tokens.ramps;
  const lightValues = data.panel.districts.flatMap((d) => d.l).filter((v) => v > 0);
  const quantiles = [0.15, 0.3, 0.45, 0.6, 0.75, 0.9].map((q) => d3.quantile(lightValues.sort(d3.ascending), q));
  return {
    nueva: { thresholds: [0.1, 0.5, 1, 5, 20, 100], ramp: footprint, ticks: ["0.1", "1", "20", "100"] },
    luz: { thresholds: quantiles, ramp: light, ticks: quantiles.filter((_, i) => i % 2 === 0).map((v) => fmt2.format(v)) },
    pobreza: { thresholds: [10, 20, 30, 40, 50, 60], ramp: poverty, ticks: ["10 %", "30 %", "50 %", "60 %"] },
  };
}

/* ---------- map ---------- */

function districtFill(feature) {
  const d = data.byUbigeo.get(feature.properties.ubigeo);
  const { surface } = data.tokens;
  if (!d) return rgb(surface.background, 0);
  const alpha = inScope(d) ? 255 : 60;
  if (state.indicator === "huella") return rgb(surface.panel, inScope(d) ? 255 : 90);
  const value = INDICATORS[state.indicator].value(d, yearIndex());
  if (value == null || (state.indicator === "nueva" && value < VISIBLE_KM2)) return rgb(surface.panel, inScope(d) ? 255 : 90);
  const scale = data.scales[state.indicator];
  return rgb(scale.ramp[d3.bisectRight(scale.thresholds, value)], alpha);
}

function layers() {
  const i = yearIndex(), { footprint } = data.tokens.ramps, { surface } = data.tokens;
  const line = rgb(surface.grid, 150);
  const out = [
    new deck.GeoJsonLayer({
      id: "districts", data: data.geo, pickable: true, stroked: true, filled: true,
      getFillColor: districtFill, getLineColor: line, lineWidthUnits: "pixels", getLineWidth: 0.4,
      autoHighlight: true, highlightColor: [241, 233, 214, 50],
      updateTriggers: { getFillColor: [state.indicator, state.year, state.department] },
    }),
    new deck.GeoJsonLayer({
      id: "departments", data: data.outlines, stroked: true, filled: false, pickable: false,
      getLineColor: rgb(data.tokens.surface.text_muted, 120), lineWidthUnits: "pixels", getLineWidth: 0.8,
    }),
  ];
  if (state.indicator === "huella") {
    const pi = data.pixelYears.indexOf(state.year);
    out.push(new deck.ScatterplotLayer({
      id: "footprint", data: data.pixels, pickable: false, radiusUnits: "meters", radiusMinPixels: 0.8, radiusMaxPixels: 60,
      getPosition: (p) => p.position,
      getRadius: (p) => Math.sqrt((p.shares[pi] / 255) * p.area / Math.PI),
      getFillColor: (p) => (p.shares[pi] === 0 ? [0, 0, 0, 0] : rgb(p.existed ? footprint[2] : footprint[6])),
      updateTriggers: { getRadius: state.year, getFillColor: state.year },
    }));
  }
  if (state.district) {
    const feature = data.geo.features.find((f) => f.properties.ubigeo === state.district);
    if (feature) out.push(new deck.GeoJsonLayer({
      id: "selected", data: [feature], filled: false, stroked: true,
      getLineColor: rgb(surface.text), lineWidthUnits: "pixels", getLineWidth: 2,
    }));
  }
  return out;
}

function tooltip({ object }) {
  if (!object) return null;
  const d = data.byUbigeo.get(object.properties.ubigeo);
  if (!d) return null;
  const spec = INDICATORS[state.indicator], value = spec.value(d, yearIndex());
  const shown = value == null ? "sin dato" : `${spec.format(value)}${spec.unit === "%" ? "" : ` ${spec.unit}`}`;
  return {
    html: `<b>${titleCase(d.n)}</b><br>${titleCase(d.d)}<br>${spec.label}: ${shown}`,
    style: { background: data.tokens.surface.panel, color: data.tokens.surface.text, border: `1px solid ${data.tokens.surface.grid}`, borderRadius: "3px", font: '400 13px/1.4 "IBM Plex Sans", sans-serif', padding: "6px 9px" },
  };
}

function fit(bounds, padding = 36) {
  const el = $("map");
  const width = el.clientWidth, height = el.clientHeight;
  const safe = Math.min(padding, Math.floor(Math.min(width, height) / 4));
  const top = width < 576 ? Math.max(safe, 96) : safe;  // on phones the legend sits over the top of the map
  return new deck.WebMercatorViewport({ width, height }).fitBounds(bounds, { padding: { top, bottom: safe, left: safe, right: safe } });
}

function flyTo(bounds) {
  const { longitude, latitude, zoom } = fit(bounds);
  viewState = { longitude, latitude, zoom, transitionDuration: REDUCED_MOTION ? 0 : 700, transitionInterpolator: new deck.LinearInterpolator(["longitude", "latitude", "zoom"]) };
  deckgl.setProps({ initialViewState: { ...viewState } });
}

function boundsOf(features) {
  let west = Infinity, south = Infinity, east = -Infinity, north = -Infinity;
  const walk = (c) => {
    if (typeof c[0] === "number") { west = Math.min(west, c[0]); east = Math.max(east, c[0]); south = Math.min(south, c[1]); north = Math.max(north, c[1]); } else c.forEach(walk);
  };
  features.forEach((f) => walk(f.geometry.coordinates));
  return [[west, south], [east, north]];
}

function initMap() {
  const { longitude, latitude, zoom } = fit(PERU_BOUNDS);
  viewState = { longitude, latitude, zoom };
  deckgl = new deck.Deck({
    parent: $("map"),
    initialViewState: viewState,
    controller: { scrollZoom: false, dragRotate: false, touchRotate: false, keyboard: false },
    layers: layers(),
    getTooltip: tooltip,
    onViewStateChange: ({ viewState: next }) => { viewState = next; },
    onClick: ({ object }) => { if (object) selectDistrict(object.properties.ubigeo); },
    getCursor: ({ isHovering, isDragging }) => (isDragging ? "grabbing" : isHovering ? "pointer" : "grab"),
  });
  const zoomBy = (delta) => {
    const next = { ...viewState, zoom: viewState.zoom + delta, transitionDuration: REDUCED_MOTION ? 0 : 200, transitionInterpolator: new deck.LinearInterpolator(["zoom"]) };
    viewState = next;
    deckgl.setProps({ initialViewState: next });
  };
  $("zoom-in").addEventListener("click", () => zoomBy(1));
  $("zoom-out").addEventListener("click", () => zoomBy(-1));
}

function renderLegend() {
  const { footprint } = data.tokens.ramps;
  const el = $("legend");
  if (state.indicator === "huella") {
    el.innerHTML = `<strong>Suelo minero visto desde satélite</strong>
      <div class="legend-row"><span class="legend-dot" style="background:${footprint[2]}"></span>Celda con huella en 2013</div>
      <div class="legend-row"><span class="legend-dot" style="background:${footprint[6]}"></span>Celda con huella después de 2013</div>
      <p>Cada círculo es una celda de 500 m y su área equivale a la superficie minera. De lejos, los más chicos se agrandan para que se vean.</p>`;
    return;
  }
  const scale = data.scales[state.indicator], spec = INDICATORS[state.indicator];
  el.innerHTML = `<strong>${spec.label} (${spec.unit})</strong>
    <div class="legend-steps">${scale.ramp.map((c) => `<span style="background:${c}"></span>`).join("")}</div>
    <div class="legend-ticks">${scale.ticks.map((t) => `<span>${t}</span>`).join("")}</div>
    ${state.indicator === "pobreza" ? "<p>Es de 2018: no cambia con el año elegido.</p>" : ""}
    ${state.indicator === "luz" ? "<p>Es contexto: no mide minería.</p>" : ""}`;
}

function renderCard() {
  const el = $("card"), d = state.district && data.byUbigeo.get(state.district);
  el.hidden = !d;
  if (!d) { el.textContent = ""; return; }
  const i = yearIndex();
  const pov = d.pov ? `${fmt1.format(d.pov[0])} % (${fmt1.format(d.pov[1])} a ${fmt1.format(d.pov[2])})` : "sin dato";
  const rows = [
    [`Huella en ${state.year}`, `${km2(d.m[i] || 0)} km²`],
    ["Huella en 2013", `${km2(d.m[0] || 0)} km²`],
    [`Luz por km² en ${state.year}`, d.l[i] == null ? "sin dato" : fmt2.format(d.l[i])],
    ["Pobreza 2018 (INEI)", pov],
    ["Población 2020", d.pop == null ? "sin dato" : fmt0.format(d.pop)],
  ];
  el.innerHTML = `<button type="button" class="card-close" aria-label="Cerrar la ficha del distrito">×</button>
    <h3>${titleCase(d.n)}</h3><p>${titleCase(d.p)}, ${titleCase(d.d)}</p>
    <dl>${rows.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join("")}</dl>`;
  el.querySelector("button").addEventListener("click", () => selectDistrict(null));
}

/* ---------- figures ---------- */

function renderKpis() {
  const rows = scopeDistricts(), i = yearIndex();
  const area = sum(rows, i), base = sum(rows, 0);
  const count = (idx) => rows.filter((d) => (d.m[idx] || 0) >= VISIBLE_KM2).length;
  $("scope-name").textContent = state.department ? titleCase(state.department) : "Todo el Perú";
  $("kpi-area-label").textContent = `Huella en ${state.year}`;
  $("kpi-area").innerHTML = `${km2(area)} <small>km²</small>`;
  const change = area - base;
  $("kpi-change").innerHTML = i === 0 || base === 0
    ? `– <small>${i === 0 ? "es el año de partida" : "sin huella en 2013"}</small>`
    : `×${fmt1.format(area / base)} <small>${change >= 0 ? "+" : "−"}${km2(Math.abs(change))} km²</small>`;
  $("kpi-districts").innerHTML = `${fmt0.format(count(i))} <small>${fmt0.format(count(0))} en 2013</small>`;
  const gains = rows.map((d) => (d.m[i] || 0) - (d.m[0] || 0)).filter((g) => g > 0).sort(d3.descending);
  const total = change, top = d3.sum(gains.slice(0, 10));
  $("kpi-top").innerHTML = i === 0 || total <= 0
    ? "– <small>sin aumento que repartir</small>"
    : gains.length <= 10
    ? `– <small>solo ${fmt0.format(gains.length)} distritos con aumento</small>`
    : `${pct(Math.min(top / total, 1))} <small>de ${km2(total)} km²</small>`;
}

function renderFindings() {
  const a = data.atlas, first = a.national_km2[a.first_year], last = a.national_km2[a.last_year];
  const leader = a.top_districts[0], md = a.madre_de_dios, y0 = a.first_year, y1 = a.last_year;
  const items = [
    [`La superficie clasificada como minera pasó de ${fmt0.format(first)} a ${fmt0.format(last)} km²: se multiplicó por ${fmt1.format(a.ratio)} en ${y1 - y0} años.`,
      `Según MapBiomas Perú, ${y0} a ${y1}. El área exacta está en discusión, por eso conviene mirar la tendencia.`],
    [`Madre de Dios explica el ${pct(md.share_of_increase)} del aumento y ya reúne el ${pct(md.share_of_last)} de la huella del país.`,
      `Pasó de ${fmt0.format(md.first_km2)} a ${fmt0.format(md.last_km2)} km². Es la parte contrastada con una segunda fuente.`],
    [`Diez distritos explican el ${pct(a.top_share_of_increase)} del aumento. ${titleCase(leader.district)} pasó de ${fmt0.format(leader.first_km2)} a ${fmt0.format(leader.last_km2)} km².`,
      `Los distritos con huella visible pasaron de ${fmt0.format(a.districts_with_footprint[y0])} a ${fmt0.format(a.districts_with_footprint[y1])}: se concentra mucho y también se extiende.`],
  ];
  $("findings").innerHTML = items.map(([big, small]) => `<li>${big}<small>${small}</small></li>`).join("");
}

function renderContrastText() {
  const c = data.atlas.contrast.madre_de_dios, y = c.last_confirmed_year, y0 = data.atlas.contrast.years[0];
  const on = Object.values(c.mapbiomas_on_amw).filter((_, i) => data.atlas.contrast.years[i] <= y);
  const ratio = c.ratio_to_last_confirmed;
  const rest = 1 - data.atlas.madre_de_dios.share_of_increase;
  const step = (series) => series[2023] - series[2022];
  const v = data.atlas.validation;
  $("contrast-text").innerHTML = `
    <p>Amazon Mining Watch usa otro satélite (Sentinel-2) y otro modelo, así que sirve como comprobación independiente. En Madre de Dios, entre ${y0} y ${y}, <strong>MapBiomas se multiplica por ${fmt2.format(ratio.mapbiomas)} y Amazon Mining Watch por ${fmt2.format(ratio.amw)}</strong>.</p>
    <p>También coinciden en el lugar: entre ${pct(d3.min(on))} y ${pct(d3.max(on))} de la superficie de MapBiomas cae en celdas de 500 m donde la otra fuente detecta cicatrices.</p>
    <p>No coinciden en el nivel: en ${y} una suma ${fmt0.format(c.amw_km2[y])} km² y la otra ${fmt0.format(c.mapbiomas_km2[y])} km². Amazon Mining Watch acumula cicatrices desde 2018 e indica que su máscara acumulada mide cerca de 1.7 veces lo anotado a mano. MapBiomas clasifica el suelo de cada año.</p>
    <p>Tampoco coinciden en cada salto: de 2022 a 2023, MapBiomas sube ${fmt0.format(step(c.mapbiomas_km2))} km² y la otra fuente, ${fmt0.format(step(c.amw_km2))} km².</p>
    <p>El ${pct(rest)} restante del aumento, fuera de Madre de Dios, se apoya sobre todo en MapBiomas.</p>`;
  $("method-check").textContent = `La suma nacional difiere de la tabla oficial de MapBiomas en ${fmt2.format(v.max_national_gap * 100)} % como máximo. Eso prueba que el cálculo es correcto, no que el satélite acierte: por eso existe el contraste.`;
}

function tip(host) {
  let el = host.querySelector(".chart-tip");
  if (!el) { el = document.createElement("div"); el.className = "chart-tip"; el.hidden = true; host.append(el); }
  return el;
}

function lineChart(host, series, { years, marker, height = 300, right = 150 }) {
  const width = Math.max(host.clientWidth, 280);
  const compact = width < 520;
  const m = { top: 12, right: compact ? 12 : right, bottom: compact ? 58 : 26, left: 46 };
  const x = d3.scalePoint(years, [m.left, width - m.right]);
  const top = d3.max(series, (s) => d3.max(s.values)) || 1;
  const y = d3.scaleLinear([0, top], [height - m.bottom, m.top]).nice();
  const svg = d3.create("svg").attr("viewBox", [0, 0, width, height]).attr("role", "img")
    .attr("aria-label", series.map((s) => `${s.name}: de ${km2(s.values[0])} a ${km2(s.values[s.values.length - 1])} km²`).join(". "));
  svg.append("g").attr("transform", `translate(${m.left},0)`)
    .call(d3.axisLeft(y).ticks(5).tickSize(-(width - m.left - m.right)).tickFormat((v) => fmt0.format(v)))
    .call((g) => g.selectAll("line").attr("stroke-width", 1));
  const every = width < 640 ? 3 : 1;
  svg.append("g").attr("transform", `translate(0,${height - m.bottom})`)
    .call(d3.axisBottom(x).tickValues(years.filter((_, i) => i % every === 0)).tickSize(0).tickPadding(8).tickFormat(String));
  if (marker != null && years.includes(marker)) {
    svg.append("line").attr("x1", x(marker)).attr("x2", x(marker)).attr("y1", m.top).attr("y2", height - m.bottom)
      .attr("stroke", data.tokens.surface.text_muted).attr("stroke-dasharray", "2 3");
  }
  const line = d3.line().x((_, i) => x(years[i])).y((v) => y(v));
  series.forEach((s) => {
    svg.append("path").attr("d", line(s.values)).attr("fill", "none").attr("stroke", s.color).attr("stroke-width", 2).attr("stroke-linejoin", "round");
    const last = s.values.length - 1;
    svg.append("circle").attr("cx", x(years[last])).attr("cy", y(s.values[last])).attr("r", 4).attr("fill", s.color).attr("stroke", data.tokens.surface.background).attr("stroke-width", 2);
  });
  const labelled = series.map((s) => ({ s, y: y(s.values[s.values.length - 1]) })).sort((a, b) => a.y - b.y);
  labelled.forEach((row, i) => { if (i && row.y - labelled[i - 1].y < 16) row.y = labelled[i - 1].y + 16; });
  if (compact) {
    const legend = svg.append("g").attr("transform", `translate(${m.left},${height - 26})`);
    let cursor = 0;
    series.forEach((s) => {
      legend.append("circle").attr("cx", cursor + 4).attr("cy", 0).attr("r", 4).attr("fill", s.color);
      legend.append("text").attr("class", "direct").attr("x", cursor + 12).attr("y", 4).text(s.name);
      cursor += 12 + s.name.length * 6.6 + 12;
    });
  } else {
    labelled.forEach(({ s, y: ly }) => {
      svg.append("text").attr("class", "direct").attr("x", width - m.right + 10).attr("y", ly + 4).text(s.name);
    });
  }
  const guide = svg.append("line").attr("y1", m.top).attr("y2", height - m.bottom).attr("stroke", data.tokens.surface.text).attr("opacity", 0);
  host.replaceChildren(svg.node());
  const box = tip(host);
  const ratio = () => host.clientWidth / width;
  const show = (event) => {
    const [px] = d3.pointer(event, svg.node());
    const i = d3.bisectCenter(years.map((yr) => x(yr)), px), year = years[i];
    guide.attr("x1", x(year)).attr("x2", x(year)).attr("opacity", 0.5);
    box.hidden = false;
    box.innerHTML = `<b>${year}</b>${series.map((s) => `<br>${s.name}: ${km2(s.values[i])} km²`).join("")}`;
    const left = x(year) * ratio();
    box.style.left = `${Math.min(left + 10, host.clientWidth - box.offsetWidth - 2)}px`;
    box.style.top = "8px";
  };
  const hide = () => { guide.attr("opacity", 0); box.hidden = true; };
  svg.append("rect").attr("x", m.left).attr("y", m.top).attr("width", width - m.left - m.right).attr("height", height - m.top - m.bottom)
    .attr("fill", "transparent").on("pointermove", show).on("pointerleave", hide);
}

function renderTrend() {
  const { mining } = data.tokens.series, { text, text_muted: muted } = data.tokens.surface;
  const years = data.panel.years;
  const total = (filter) => years.map((_, i) => d3.sum(data.panel.districts.filter(filter), (d) => d.m[i] || 0));
  let series, title;
  if (state.department) {
    series = [{ name: titleCase(state.department), values: total(inScope), color: mining }];
    const v = series[0].values;
    title = `${series[0].name}: de ${km2(v[0])} a ${km2(v[v.length - 1])} km² entre ${years[0]} y ${years[years.length - 1]}`;
  } else {
    const md = total((d) => d.d === MADRE_DE_DIOS), rest = total((d) => d.d !== MADRE_DE_DIOS);
    series = [{ name: "Madre de Dios", values: md, color: mining }, { name: "Resto del Perú", values: rest, color: muted }];
    title = `Madre de Dios se multiplicó por ${fmt1.format(md[md.length - 1] / md[0])} y el resto del Perú, por ${fmt1.format(rest[rest.length - 1] / rest[0])}`;
  }
  const d = state.district && data.byUbigeo.get(state.district);
  if (d) series.push({ name: titleCase(d.n), values: d.m.map((v) => v || 0), color: text });
  $("trend-title").textContent = title;
  lineChart($("trend"), series, { years, marker: state.year });
}

function renderContrastChart() {
  const c = data.atlas.contrast.madre_de_dios, y = c.last_confirmed_year;
  const years = data.atlas.contrast.years.filter((year) => year <= y);
  const { mining, contrast } = data.tokens.series;
  lineChart($("contrast"), [
    { name: "MapBiomas", values: years.map((year) => c.mapbiomas_km2[year]), color: mining },
    { name: "Amazon Mining Watch", values: years.map((year) => c.amw_km2[year]), color: contrast },
  ], { years, height: 280, right: 165 });
}

function rankedRows() {
  const spec = INDICATORS[state.indicator], i = yearIndex();
  return scopeDistricts().map((d) => ({ d, value: spec.value(d, i) }))
    .filter((row) => row.value != null && row.value > (state.indicator === "pobreza" ? -1 : 0))
    .sort((a, b) => b.value - a.value);
}

function renderRank() {
  const spec = INDICATORS[state.indicator], rows = rankedRows(), top = rows.slice(0, 10);
  $("rank-title").textContent = spec.title(scopeName());
  $("rank-note").textContent = spec.note(state.year);
  const host = $("rank");
  host.replaceChildren();
  if (!top.length) { host.innerHTML = `<p class="empty">${scopeName()} no tiene distritos con este dato en ${state.year}. Prueba otro año o departamento.</p>`; return; }
  const color = { huella: data.tokens.ramps.footprint[4], nueva: data.tokens.ramps.footprint[4], luz: data.tokens.ramps.light[3], pobreza: data.tokens.ramps.poverty[3] }[state.indicator];
  const max = state.indicator === "pobreza" ? 100 : d3.max(top, (r) => r.value);
  top.forEach(({ d, value }) => {
    const whisker = state.indicator === "pobreza" && d.pov
      ? `<span class="bar-whisker" style="left:${d.pov[1] / max * 100}%;width:${(d.pov[2] - d.pov[1]) / max * 100}%"></span>` : "";
    const button = document.createElement("button");
    button.type = "button"; button.className = "bar";
    button.setAttribute("aria-pressed", String(state.district === d.u));
    button.innerHTML = `<span class="bar-name">${titleCase(d.n)}${state.department ? "" : `<small>${titleCase(d.d)}</small>`}</span>
      <span class="bar-track"><span class="bar-fill" style="width:${value / max * 100}%;background:${color}"></span>${whisker}</span>
      <span class="bar-value">${spec.format(value)}${spec.unit === "%" ? "" : ` ${state.indicator === "luz" ? "" : spec.unit}`}</span>`;
    button.addEventListener("click", () => selectDistrict(d.u));
    host.append(button);
  });
  const table = $("table"), i = yearIndex();
  table.innerHTML = `<thead><tr><th scope="col">Distrito</th><th scope="col">Departamento</th><th scope="col">Huella ${state.year} (km²)</th><th scope="col">Huella 2013 (km²)</th></tr></thead>
    <tbody>${scopeDistricts().filter((d) => (d.m[i] || 0) >= VISIBLE_KM2).sort((a, b) => b.m[i] - a.m[i])
    .map((d) => `<tr><td>${titleCase(d.n)}</td><td style="text-align:left">${titleCase(d.d)}</td><td>${km2(d.m[i] || 0)}</td><td>${km2(d.m[0] || 0)}</td></tr>`).join("")}</tbody>`;
}

function renderDepartments() {
  const i = yearIndex(), host = $("departments");
  const rows = d3.rollups(data.panel.districts, (v) => ({ now: sum(v, i), base: sum(v, 0) }), (d) => d.d)
    .map(([name, v]) => ({ name, ...v })).filter((r) => r.now >= 1 || r.base >= 1)
    .sort((a, b) => b.now - a.now).slice(0, 12);
  const max = d3.max(rows, (r) => Math.max(r.now, r.base));
  host.replaceChildren(...rows.map((r) => {
    const button = document.createElement("button");
    button.type = "button"; button.className = "bar";
    button.setAttribute("aria-pressed", String(state.department === r.name));
    const a = r.base / max * 100, b = r.now / max * 100;
    button.innerHTML = `<span class="bar-name">${titleCase(r.name)}</span>
      <span class="bar-track"><span class="bar-link" style="left:${Math.min(a, b)}%;width:${Math.abs(b - a)}%"></span>
      <span class="bar-dot from" style="left:${a}%"></span><span class="bar-dot to" style="left:${b}%"></span></span>
      <span class="bar-value">${km2(r.now)} km²</span>`;
    button.setAttribute("aria-label", `${titleCase(r.name)}: ${km2(r.base)} km² en 2013 y ${km2(r.now)} km² en ${state.year}`);
    button.addEventListener("click", () => selectDepartment(state.department === r.name ? "" : r.name));
    return button;
  }));
}

function downloadCsv() {
  const i = yearIndex();
  const header = ["ubigeo", "distrito", "provincia", "departamento", "anio", "huella_km2", "huella_2013_km2", "luz_por_km2", "pobreza_inei_2018", "pobreza_ic95_inf", "pobreza_ic95_sup"];
  const quote = (v) => (v == null ? "" : /[",\n]/.test(v) ? `"${String(v).replace(/"/g, '""')}"` : v);
  const lines = scopeDistricts().map((d) => [d.u, d.n, d.p, d.d, state.year, d.m[i], d.m[0], d.l[i], ...(d.pov || [null, null, null])].map(quote).join(","));
  const link = document.createElement("a");
  link.href = URL.createObjectURL(new Blob([`${header.join(",")}\n${lines.join("\n")}\n`], { type: "text/csv;charset=utf-8" }));
  link.download = `huella_minera_${state.department ? state.department.toLowerCase().replace(/ /g, "_") : "peru"}_${state.year}.csv`;
  link.click();
  URL.revokeObjectURL(link.href);
}

/* ---------- state ---------- */

function refresh() {
  $("year").value = state.year;
  $("year-output").textContent = state.year;
  $("big-year").textContent = state.year;
  deckgl.setProps({ layers: layers() });
  renderLegend(); renderCard(); renderKpis(); renderTrend(); renderRank(); renderDepartments();
}

function stop() {
  clearInterval(timer);
  state.playing = false;
  $("play").textContent = "Reproducir";
}

function play() {
  const { years } = data.panel;
  if (state.year === years[years.length - 1]) { state.year = years[0]; refresh(); }
  state.playing = true;
  $("play").textContent = "Pausar";
  timer = setInterval(() => {
    if (state.year >= years[years.length - 1]) { stop(); return; }
    state.year += 1;
    refresh();
  }, PLAY_MS);
}

function selectDepartment(name) {
  state.department = name;
  $("department").value = name;
  const current = state.district && data.byUbigeo.get(state.district);
  if (current && name && current.d !== name) state.district = null;
  const features = data.geo.features.filter((f) => { const d = data.byUbigeo.get(f.properties.ubigeo); return d && d.d === name; });
  flyTo(name && features.length ? boundsOf(features) : PERU_BOUNDS);
  refresh();
}

function selectDistrict(ubigeo) {
  state.district = ubigeo;
  if (ubigeo) {
    const feature = data.geo.features.find((f) => f.properties.ubigeo === ubigeo);
    if (feature) flyTo(boundsOf([feature]));
  }
  refresh();
}

function initControls() {
  const names = [...new Set(data.panel.districts.map((d) => d.d))].sort();
  $("department").append(...names.map((name) => new Option(titleCase(name), name)));
  const label = (d) => `${titleCase(d.n)}, ${titleCase(d.p)}, ${titleCase(d.d)}`;
  const lookup = new Map(data.panel.districts.map((d) => [label(d).toLowerCase(), d.u]));
  $("district-list").append(...data.panel.districts.map((d) => { const o = document.createElement("option"); o.value = label(d); return o; }));
  $("controls").addEventListener("submit", (event) => event.preventDefault());
  $("year").addEventListener("input", (event) => { stop(); state.year = Number(event.target.value); refresh(); });
  $("department").addEventListener("change", (event) => { stop(); selectDepartment(event.target.value); });
  $("indicator").addEventListener("change", (event) => { state.indicator = event.target.value; refresh(); });
  $("search").addEventListener("change", (event) => {
    const ubigeo = lookup.get(event.target.value.trim().toLowerCase());
    if (ubigeo) { stop(); selectDistrict(ubigeo); }
  });
  $("play").addEventListener("click", () => (state.playing ? stop() : play()));
  $("download").addEventListener("click", downloadCsv);
  let resize;
  addEventListener("resize", () => { clearTimeout(resize); resize = setTimeout(() => { renderTrend(); renderContrastChart(); }, 150); });
}

load().then(() => {
  initMap();
  initControls();
  renderFindings();
  renderContrastText();
  renderContrastChart();
  if (REDUCED_MOTION) {
    state.year = data.panel.years[data.panel.years.length - 1];
    stop();
    refresh();
  } else {
    refresh();
    play();
  }
}).catch((error) => {
  console.error(error);
  $("load-error").hidden = false;
});
