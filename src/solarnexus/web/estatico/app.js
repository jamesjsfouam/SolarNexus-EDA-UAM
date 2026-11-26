"use strict";

const $ = (sel) => document.querySelector(sel);
const fmt = (v, dec = 0) =>
  v === null || v === undefined || Number.isNaN(v)
    ? "—"
    : Number(v).toLocaleString("es-NI", { minimumFractionDigits: dec, maximumFractionDigits: dec });
const signo = (v, dec = 1) => (v > 0 ? "+" : v < 0 ? "−" : "") + fmt(Math.abs(v), dec);
const fmtP = (p) => (p < 0.001 ? "< 0,001" : fmt(p, 3));
const css = (nombre) => getComputedStyle(document.documentElement).getPropertyValue(nombre).trim();
const DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"];
const graficos = {};

async function api(url, opciones = {}) {
  const r = await fetch(url, opciones);
  const cuerpo = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(cuerpo.detail ? (typeof cuerpo.detail === "string" ? cuerpo.detail : JSON.stringify(cuerpo.detail)) : `Error ${r.status}`);
  return cuerpo;
}

function mostrarError(id, err) {
  const el = $(id);
  el.textContent = err ? err.message || String(err) : "";
  el.hidden = !err;
}

function dibujar(id, config) {
  if (typeof Chart === "undefined") return; // sin conexión al CDN: la página sigue funcionando sin gráficos
  graficos[id]?.destroy();
  Chart.defaults.color = css("--suave");
  Chart.defaults.borderColor = css("--borde");
  graficos[id] = new Chart($(id), config);
}

/* ---------- Indicadores institucionales ---------- */

let indicadores = null;

const DECIMALES = { pct_solar: 0, solar_implicita_pct: 1, intensidad_kwh_m2: 0, emisiones_brutas_kg: 0, co2_evitado_kg: 0,
  emisiones_netas_kg: 0, exportacion_kwh: 0, comunidad_personas: 0, per_capita_real_kg: 2, per_capita_uam_kg: 2,
  emisiones_sin_solar_kg: 0 };
const EDITABLES = [
  ["pct_solar", "% solar"], ["intensidad_kwh_m2", "kWh/m²/año"], ["emisiones_brutas_kg", "Emisiones brutas (kg)"],
  ["co2_evitado_kg", "CO₂ evitado (kg)"], ["exportacion_kwh", "Inyectado SIN (kWh)"], ["comunidad_personas", "Comunidad"],
];

function textoCambio(f) {
  if (f.cambio === null) {
    if (f.a === null && f.b !== null) return `nuevo en ${indicadores.b}`;
    return "sin dato en uno de los periodos";
  }
  if (f.porcentaje) return `${signo(f.cambio, 1)} puntos porcentuales`;
  const rel = f.cambio_relativo_pct === null ? "" : ` (${signo(f.cambio_relativo_pct, 2)} %)`;
  return `${signo(f.cambio, DECIMALES[f.clave] ?? 1)} ${f.unidad}${rel}`;
}

function pintarIndicadores(r) {
  indicadores = r;
  for (const id of ["#ind-a", "#ind-b"]) {
    $(id).innerHTML = r.periodos.map((p) => `<option>${p.periodo}</option>`).join("");
  }
  $("#ind-a").value = r.a;
  $("#ind-b").value = r.b;

  $("#tarjetas-indicadores").innerHTML = r.comparacion.map((f) => {
    const clase = f.mejora === true ? "mejora" : f.mejora === false ? "empeora" : "";
    const unidad = f.porcentaje ? "%" : f.unidad;
    return `<div class="indicador${f.derivado ? " derivado" : ""}">
      <div class="nombre">${f.nombre}${f.derivado ? ' <span class="chip">calculado</span>' : ""}</div>
      <div class="valores">
        <div><span class="periodo">${r.a}</span><span class="num a">${fmt(f.a, DECIMALES[f.clave])}</span><span class="unidad">${unidad}</span></div>
        <div><span class="periodo">${r.b}</span><span class="num b">${fmt(f.b, DECIMALES[f.clave])}</span><span class="unidad">${unidad}</span></div>
      </div>
      <span class="cambio ${clase}">${textoCambio(f)}</span>
      ${f.nota ? `<span class="unidad">${f.nota}</span>` : ""}
    </div>`;
  }).join("");

  const avisos = r.advertencias || [];
  $("#advertencias-indicadores").hidden = avisos.length === 0;
  $("#advertencias-indicadores").innerHTML = avisos.length
    ? `<strong>Inconsistencias en los datos oficiales</strong><ul>${avisos.map((a) => `<li>${a}</li>`).join("")}</ul>`
    : "";

  dibujar("#grafico-co2", {
    type: "bar",
    data: {
      labels: r.periodos.map((p) => p.periodo),
      datasets: [
        { label: "Emisiones brutas", data: r.periodos.map((p) => p.emisiones_brutas_kg), backgroundColor: "#94a3b8", borderRadius: 6 },
        { label: "CO₂ evitado", data: r.periodos.map((p) => p.co2_evitado_kg), backgroundColor: css("--b"), borderRadius: 6 },
        { label: "Emisiones netas", data: r.periodos.map((p) => p.emisiones_netas_kg), backgroundColor: css("--a"), borderRadius: 6 },
      ],
    },
    options: {
      maintainAspectRatio: false,
      plugins: { title: { display: true, text: "Emisiones de CO₂ por año (kg)" } },
      scales: { y: { beginAtZero: true, title: { display: true, text: "kg CO₂/año" } } },
    },
  });

  const t = $("#tabla-indicadores");
  t.innerHTML = `<tr><th>Periodo</th>${EDITABLES.map(([, n]) => `<th>${n}</th>`).join("")}<th></th></tr>` +
    r.periodos.map((p) => `<tr>
      <td><input name="periodo" value="${p.periodo}"></td>
      ${EDITABLES.map(([k]) => `<td><input name="${k}" type="number" step="any" min="0" value="${p[k] ?? ""}"></td>`).join("")}
      <td><button type="button" class="boton secundario quitar" title="Quitar periodo">✕</button></td>
    </tr>`).join("");
}

function leerTablaIndicadores() {
  return [...$("#tabla-indicadores").querySelectorAll("tr")].slice(1).map((fila) => {
    const p = {};
    fila.querySelectorAll("input").forEach((i) => { p[i.name] = i.name === "periodo" ? i.value : (i.value === "" ? null : Number(i.value)); });
    return p;
  });
}

async function cargarIndicadores(a, b) {
  try {
    const q = a && b ? `?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}` : "";
    pintarIndicadores(await api(`/api/indicadores${q}`));
    mostrarError("#error-indicadores", null);
  } catch (e) { mostrarError("#error-indicadores", e); }
}

$("#ind-a").addEventListener("change", () => cargarIndicadores($("#ind-a").value, $("#ind-b").value));
$("#ind-b").addEventListener("change", () => cargarIndicadores($("#ind-a").value, $("#ind-b").value));
$("#tabla-indicadores").addEventListener("click", (ev) => {
  if (ev.target.classList.contains("quitar")) ev.target.closest("tr").remove();
});
$("#ind-anadir").addEventListener("click", () => {
  const filas = $("#tabla-indicadores").querySelectorAll("tr");
  const ultima = filas[filas.length - 1];
  const nueva = ultima.cloneNode(true);
  nueva.querySelectorAll("input").forEach((i) => { i.value = ""; });
  ultima.after(nueva);
});
$("#ind-guardar").addEventListener("click", async () => {
  try {
    const periodos = leerTablaIndicadores();
    const nombres = periodos.map((p) => p.periodo);
    const a = nombres.includes($("#ind-a").value) ? $("#ind-a").value : nombres[nombres.length - 2];
    const b = nombres.includes($("#ind-b").value) ? $("#ind-b").value : nombres[nombres.length - 1];
    pintarIndicadores(await api("/api/indicadores", {
      method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ periodos, a, b }),
    }));
    mostrarError("#error-indicadores", null);
  } catch (e) { mostrarError("#error-indicadores", e); }
});
$("#ind-restablecer").addEventListener("click", async () => {
  try { pintarIndicadores(await api("/api/indicadores/restablecer", { method: "POST" })); mostrarError("#error-indicadores", null); }
  catch (e) { mostrarError("#error-indicadores", e); }
});

/* ---------- Datos horarios ---------- */

let datos = null;

function sumarDias(fecha, n) {
  const d = new Date(fecha + "T00:00:00Z");
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}

function fijarFechasPorDefecto() {
  const f = $("#form-periodos");
  const fechas = datos.consumo_diario.fechas;
  const demo = datos.origen === "demo";
  // Demo: antes y después de la mejora de eficiencia simulada (1 de agosto).
  const mitad = fechas[Math.floor(fechas.length / 2)];
  f.a_inicio.value = demo ? "2026-02-01" : datos.inicio;
  f.a_fin.value = demo ? "2026-05-31" : sumarDias(mitad, -1);
  f.b_inicio.value = demo ? "2026-08-01" : mitad;
  f.b_fin.value = demo ? "2026-11-30" : datos.fin;
  for (const nombre of ["a_inicio", "a_fin", "b_inicio", "b_fin"]) { f[nombre].min = datos.inicio; f[nombre].max = datos.fin; }

  const d = $("#form-despacho");
  d.fecha.min = sumarDias(datos.inicio, 7);
  d.fecha.max = datos.fin;
  d.fecha.value = demo ? "2026-09-15" : datos.fin;
}

function pintarDatos(r) {
  datos = r;
  const origen = r.origen === "demo" ? "Datos sintéticos de demostración" : "CSV cargado";
  $("#insignia-datos").textContent = `${origen} · ${r.inicio} → ${r.fin}`;
  $("#info-datos").textContent = `${origen}: ${fmt(r.horas)} horas (${fmt(r.dias)} días), del ${r.inicio} al ${r.fin}.` +
    (r.origen === "demo" ? " Incluye vacaciones y una mejora de eficiencia simulada del 8 % desde el 1 de agosto de 2026." : "");
  fijarFechasPorDefecto();
  $("#resultado-periodos").hidden = true;
  $("#resultado-despacho").hidden = true;
}

async function cargarDatos(promesa) {
  try { pintarDatos(await promesa); mostrarError("#error-periodos", null); }
  catch (e) { mostrarError("#error-periodos", e); }
}

$("#csv").addEventListener("change", async (ev) => {
  const archivo = ev.target.files[0];
  if (!archivo) return;
  await cargarDatos(api("/api/datos/csv", { method: "POST", headers: { "Content-Type": "text/csv" }, body: await archivo.text() }));
  ev.target.value = "";
});
$("#usar-demo").addEventListener("click", () => cargarDatos(api("/api/datos/demo", { method: "POST" })));

/* ---------- Análisis entre periodos ---------- */

const NOMBRES_COEF = {
  b0: "b0 · constante", b1_cdd: "b1 · CDD (clima)", b2_hum: "b2 · humedad",
  b3_ln_act: "b3 · ln actividad", b4_ln_area: "b4 · ln área",
};

const sombrearPeriodos = {
  id: "sombrear",
  beforeDatasetsDraw(chart, _args, opciones) {
    const { ctx, chartArea, scales: { x } } = chart;
    for (const p of opciones.periodos || []) {
      const i0 = x.getPixelForValue(p.inicio), i1 = x.getPixelForValue(p.fin);
      if (Number.isNaN(i0) || Number.isNaN(i1)) continue;
      ctx.save();
      ctx.fillStyle = p.color + "22";
      ctx.fillRect(i0, chartArea.top, Math.max(i1 - i0, 2), chartArea.bottom - chartArea.top);
      ctx.restore();
    }
  },
};

function kpi(etiqueta, valor, detalle = "", clase = "") {
  return `<div class="kpi"><div class="etiqueta">${etiqueta}</div><div class="valor ${clase}">${valor}</div><div class="detalle">${detalle}</div></div>`;
}

function pintarPeriodos(r) {
  const ahorro = r.ahorro_normalizado_pct;
  const v = $("#veredicto");
  v.className = "veredicto" + (r.chow.significativo ? " cambio" : "");
  v.innerHTML = r.chow.significativo
    ? `<strong>Hay un cambio estructural significativo entre A y B.</strong>
       Test de Chow: F(${r.chow.gl[0]}, ${r.chow.gl[1]}) = ${fmt(r.chow.f, 2)}, p ${fmtP(r.chow.p_valor)}.
       Descontando clima y actividad, B consume un ${fmt(Math.abs(ahorro), 1)} % ${ahorro >= 0 ? "menos" : "más"} de lo que predice el modelo de A.`
    : `<strong>No hay evidencia de cambio estructural entre A y B.</strong>
       Test de Chow: F(${r.chow.gl[0]}, ${r.chow.gl[1]}) = ${fmt(r.chow.f, 2)}, p = ${fmtP(r.chow.p_valor)} (α = ${r.chow.alpha}).
       Las diferencias de consumo se explican por el clima y la actividad académica.`;

  $("#kpis-periodos").innerHTML = [
    kpi("Consumo medio A", `${fmt(r.a.consumo_medio_kwh, 0)} kWh/h`, `${r.a.inicio} → ${r.a.fin}`),
    kpi("Consumo medio B", `${fmt(r.b.consumo_medio_kwh, 0)} kWh/h`, `${r.b.inicio} → ${r.b.fin}`),
    kpi("Variación bruta", `${signo(r.variacion_consumo_medio_pct)} %`, "sin ajustar por clima ni actividad"),
    kpi("Ahorro normalizado", `${signo(ahorro)} %`, `${fmt(r.ahorro_normalizado_kwh, 0)} kWh frente a la línea base de A`,
      ahorro > 0 ? "positivo" : ahorro < 0 ? "negativo" : ""),
    kpi("Temperatura base", `${fmt(r.tb, 0)} °C`, r.tb_automatica ? "elegida por mínimo AIC" : "fijada a mano"),
  ].join("");

  $("#tabla-coef").innerHTML = `<tr><th>Coeficiente</th><th>A</th><th>e.e. A</th><th>B</th><th>e.e. B</th><th>Diferencia</th><th>z</th><th>p-valor</th></tr>` +
    r.coeficientes.map((c) => `<tr class="${c.p_valor < 0.05 ? "signif" : ""}">
      <td>${NOMBRES_COEF[c.nombre] || c.nombre}</td><td>${fmt(c.a, 4)}</td><td>${fmt(c.ee_a, 4)}</td>
      <td>${fmt(c.b, 4)}</td><td>${fmt(c.ee_b, 4)}</td><td>${signo(c.diferencia, 4)}</td>
      <td>${fmt(c.z, 2)}</td><td>${fmtP(c.p_valor)}${c.p_valor < 0.05 ? ' <span class="chip">signif.</span>' : ""}</td></tr>`).join("");

  const fila = (n, fa, fb) => `<tr><td>${n}</td><td>${fa}</td><td>${fb}</td></tr>`;
  $("#tabla-resumen").innerHTML = `<tr><th></th><th>Periodo A</th><th>Periodo B</th></tr>` +
    fila("Horas de datos", fmt(r.a.horas), fmt(r.b.horas)) +
    fila("Consumo total (kWh)", fmt(r.a.consumo_total_kwh), fmt(r.b.consumo_total_kwh)) +
    fila("Temperatura media (°C)", fmt(r.a.temperatura_media, 1), fmt(r.b.temperatura_media, 1)) +
    fila("Humedad media", fmt(r.a.humedad_media * 100, 0) + " %", fmt(r.b.humedad_media * 100, 0) + " %") +
    fila("Actividad media", fmt(r.a.actividad_media, 2), fmt(r.b.actividad_media, 2)) +
    fila("R²", fmt(r.a.r2, 3), fmt(r.b.r2, 3)) +
    fila("σ residual (ln)", fmt(r.a.sigma, 4), fmt(r.b.sigma, 4)) +
    fila("AIC (escala EViews)", fmt(r.a.aic_eviews, 3), fmt(r.b.aic_eviews, 3)) +
    `<tr><td>AIC: modelo único vs. separados</td><td colspan="2">${fmt(r.aic.conjunto, 0)} vs. ${fmt(r.aic.separados, 0)} →
      ${r.aic.separados < r.aic.conjunto ? "conviene un modelo por periodo" : "basta un modelo común"}</td></tr>` +
    fila("Consumo de B esperado con el modelo de A (kWh)", "—", fmt(r.consumo_b_esperado_kwh));

  const cd = datos.consumo_diario;
  dibujar("#grafico-diario", {
    type: "line",
    data: { labels: cd.fechas, datasets: [{ label: "Consumo diario (kWh)", data: cd.kwh, borderColor: css("--acento"), borderWidth: 1.5, pointRadius: 0 }] },
    options: {
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { display: false },
        title: { display: true, text: "Consumo diario · zona azul = periodo A, zona verde = periodo B" },
        sombrear: { periodos: [{ inicio: r.a.inicio, fin: r.a.fin, color: css("--a") }, { inicio: r.b.inicio, fin: r.b.fin, color: css("--b") }] },
      },
      scales: { x: { ticks: { maxTicksLimit: 12 } }, y: { title: { display: true, text: "kWh/día" } } },
    },
    plugins: [sombrearPeriodos],
  });
  $("#resultado-periodos").hidden = false;
}

$("#form-periodos").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const boton = ev.submitter || ev.target.querySelector('button[type="submit"]');
  boton.disabled = true;
  try {
    const q = new URLSearchParams(new FormData(ev.target));
    if (!q.get("tb")) q.delete("tb");
    pintarPeriodos(await api(`/api/periodos?${q}`));
    mostrarError("#error-periodos", null);
  } catch (e) {
    mostrarError("#error-periodos", e);
    $("#resultado-periodos").hidden = true;
  } finally { boton.disabled = false; }
});

/* ---------- Despacho ---------- */

const REGIMEN = {
  carga: "Carga", peak_shaving: "Peak shaving", descarga_tras_pico: "Descarga tras pico",
  exportacion: "Exportación", autoconsumo: "Autoconsumo",
};

function pintarDespacho(r) {
  const t = r.totales;
  $("#kpis-despacho").innerHTML = [
    kpi("Día", `${DIAS[r.dia_semana]}`, r.fecha),
    kpi("Pico vespertino", r.pico_previsto ? "Previsto" : "No previsto", `ventana ${r.ventana_pico[0]}:00–${r.ventana_pico[1]}:00`),
    kpi("Compra a red", `${fmt(t.red)} kWh`),
    kpi("Batería", `${fmt(t.b_carga)} / ${fmt(t.b_descarga)} kWh`, "carga / descarga"),
    kpi("Exportación al SIN", `${fmt(t.exportacion)} kWh`),
  ].join("");

  const h = r.horas;
  dibujar("#grafico-despacho", {
    data: {
      labels: h.map((f) => `${f.hora}h`),
      datasets: [
        { type: "line", label: "Consumo previsto", data: h.map((f) => f.consumo_previsto), borderColor: css("--texto"), pointRadius: 0, borderWidth: 2 },
        { type: "line", label: "PV Solar Jaguar", data: h.map((f) => f.pv), borderColor: "#f59e0b", backgroundColor: "#f59e0b33", fill: true, pointRadius: 0 },
        { type: "bar", label: "Red (G)", data: h.map((f) => f.red), backgroundColor: "#94a3b8", stack: "s" },
        { type: "bar", label: "Descarga batería", data: h.map((f) => f.b_descarga), backgroundColor: css("--b"), stack: "s" },
        { type: "bar", label: "Carga batería", data: h.map((f) => -f.b_carga), backgroundColor: css("--a"), stack: "s" },
        { type: "bar", label: "Exportación", data: h.map((f) => -f.exportacion), backgroundColor: "#0ea5e9", stack: "s" },
      ],
    },
    options: {
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      scales: { y: { title: { display: true, text: "kWh (negativo = sale de la red interna)" } } },
    },
  });

  $("#tabla-despacho").innerHTML = `<tr><th>Hora</th><th>Consumo prev.</th><th>Consumo real</th><th>PV</th><th>P(margen)</th>
    <th>Red</th><th>Carga</th><th>Descarga</th><th>Export.</th><th>SOC</th><th>Régimen</th></tr>` +
    h.map((f) => `<tr><td>${f.hora}:00</td><td>${fmt(f.consumo_previsto)}</td><td>${fmt(f.consumo_real)}</td><td>${fmt(f.pv)}</td>
      <td>${fmt(f.prob_en_margen, 2)}</td><td>${fmt(f.red)}</td><td>${fmt(f.b_carga)}</td><td>${fmt(f.b_descarga)}</td>
      <td>${fmt(f.exportacion)}</td><td>${fmt(f.soc)}</td><td>${REGIMEN[f.regimen] || f.regimen}</td></tr>`).join("");
  $("#resultado-despacho").hidden = false;
}

$("#form-despacho").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const boton = ev.submitter || ev.target.querySelector('button[type="submit"]');
  boton.disabled = true;
  try {
    const f = ev.target;
    const q = new URLSearchParams({
      fecha: f.fecha.value, capacidad_kwh: f.capacidad_kwh.value, potencia_kw: f.potencia_kw.value,
      reserva_kwh: f.reserva_kwh.value, descarga_tras_pico: f.descarga_tras_pico.checked,
    });
    pintarDespacho(await api(`/api/despacho?${q}`));
    mostrarError("#error-despacho", null);
  } catch (e) {
    mostrarError("#error-despacho", e);
    $("#resultado-despacho").hidden = true;
  } finally { boton.disabled = false; }
});

/* ---------- Inicio ---------- */

(function iniciar() {
  const sel = $("#form-periodos").tb;
  for (let t = 22; t <= 30; t++) sel.insertAdjacentHTML("beforeend", `<option value="${t}">${t} °C</option>`);
  cargarIndicadores();
  cargarDatos(api("/api/datos")).then(() => $("#form-periodos").requestSubmit());
})();
