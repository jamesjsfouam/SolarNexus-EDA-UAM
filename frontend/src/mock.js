// Datos de ejemplo con el mismo formato que la API (docs/API_CONTRACT.md).
// Se usan cuando la API no está levantada. El despacho replica las reglas de
// src/solarnexus/despacho.py para que el dashboard se vea igual que con el back real.

const OFFSET = '-06:00' // Managua

function manana() {
  const d = new Date()
  d.setDate(d.getDate() + 1)
  return d.toISOString().slice(0, 10)
}

function marca(fecha, hora) {
  return `${fecha}T${String(hora).padStart(2, '0')}:00:00${OFFSET}`
}

// Curvas suaves de un día laborable: demanda con pico vespertino y PV con campana solar.
function serieDia() {
  const fecha = manana()
  return Array.from({ length: 24 }, (_, h) => {
    const clases = h >= 7 && h < 20 ? 1 : 0.35
    const calor = Math.max(0, Math.sin(((h - 9) / 12) * Math.PI))
    const demanda = 180 + 260 * clases + 260 * calor
    const pv = h >= 6 && h <= 18 ? 900 * Math.sin(((h - 6) / 12) * Math.PI) : 0
    const prob = 0.9 + 0.08 * Math.cos((h / 24) * 2 * Math.PI)
    return {
      interval_start: marca(fecha, h),
      demand_kwh: Math.round(demanda * 10) / 10,
      pv_generation_kwh: Math.round(pv * 10) / 10,
      probability_within_margin: Math.round(prob * 1000) / 1000,
    }
  })
}

export function pronosticoParaSubir() {
  return {
    model_name: 'ASHRAE-3P-log-linear',
    model_version: '0.1.0',
    source: 'frontend-demo',
    notes: 'Pronóstico sintético subido desde el dashboard para demostración',
    points: serieDia(),
  }
}

const hora = (iso) => Number(iso.slice(11, 13))

function despachar(points, b) {
  const conf = 1 - b.alpha
  const enPico = (h) => h >= b.peak_start_hour && h < b.peak_end_hour
  const hayPico = points.some((p) => enPico(hora(p.interval_start)) && p.demand_kwh > p.pv_generation_kwh)
  let soc = b.initial_soc_kwh
  return points.map((p, i) => {
    const h = hora(p.interval_start)
    const c = p.demand_kwh
    const pv = p.pv_generation_kwh
    const deficit = Math.max(c - pv, 0)
    const excedente = Math.max(pv - c, 0)
    let regime = 'autoconsumo'
    let carga = 0
    let descarga = 0
    let exporta = 0
    if (deficit > 0) {
      const maxDesc = Math.min(b.power_kw, soc - b.min_soc_kwh)
      if (hayPico && maxDesc > 0 && (enPico(h) || h >= b.peak_end_hour)) {
        regime = enPico(h) ? 'peak_shaving' : 'descarga_tras_pico'
        descarga = Math.min(deficit, maxDesc)
        soc -= descarga
      }
    } else if (excedente > 0) {
      if (!hayPico && p.probability_within_margin >= conf) {
        regime = 'exportacion'
        exporta = excedente
      } else {
        regime = 'carga'
        const maxCarga = Math.min(b.power_kw, (b.capacity_kwh - soc) / b.charge_efficiency)
        carga = Math.min(excedente, maxCarga)
        soc = Math.min(b.capacity_kwh, soc + carga * b.charge_efficiency)
        exporta = excedente - carga
      }
    }
    return {
      id: i + 1,
      interval_start: p.interval_start,
      regime,
      demand_kwh: c,
      pv_generation_kwh: pv,
      probability_within_margin: p.probability_within_margin,
      grid_import_kwh: deficit - descarga,
      battery_charge_kwh: carga,
      battery_discharge_kwh: descarga,
      export_kwh: exporta,
      soc_after_kwh: soc,
    }
  })
}

export function dashboard(bateria) {
  const ahora = new Date().toISOString()
  const pronostico = {
    id: 1,
    ...pronosticoParaSubir(),
    generated_at: ahora,
    points: serieDia().map((p, i) => ({ id: i + 1, ...p })),
  }
  const puntos = despachar(pronostico.points, bateria)
  return {
    health: { status: 'ok', database: 'sin conexión', version: 'ejemplo' },
    campus: { id: 1, campus_name: 'Universidad Americana (UAM)', timezone: 'America/Managua', description: null },
    medicion: {
      id: 1,
      interval_start: pronostico.points[14].interval_start,
      temperature_c: 33.2,
      humidity_pct: 68,
      activity_index: 0.82,
      conditioned_area_m2: 7600,
      consumption_kwh: 612.4,
      pv_generation_kwh: 540.1,
      source: 'ejemplo',
    },
    pronostico,
    despacho: {
      id: 1,
      forecast_run_id: 1,
      battery_capacity_kwh: bateria.capacity_kwh,
      battery_power_kw: bateria.power_kw,
      initial_soc_kwh: bateria.initial_soc_kwh,
      min_soc_kwh: bateria.min_soc_kwh,
      charge_efficiency: bateria.charge_efficiency,
      final_soc_kwh: puntos.at(-1).soc_after_kwh,
      created_at: ahora,
      points: puntos,
    },
    mesh: {
      flows: [
        { origin: 'Copérnico', destination: 'Pabellón C', energy_kwh: 60 },
        { origin: 'Copérnico', destination: 'Biblioteca', energy_kwh: 20 },
        { origin: 'Biblioteca', destination: 'Pabellón C', energy_kwh: 19.6 },
      ],
      switches_closed: [
        { origin: 'Copérnico', destination: 'Pabellón C' },
        { origin: 'Copérnico', destination: 'Biblioteca' },
        { origin: 'Biblioteca', destination: 'Pabellón C' },
      ],
      central_supply_kwh: { 'Copérnico': 0, 'Pabellón C': 2.6, Biblioteca: 0 },
      curtailment_kwh: { 'Copérnico': 0, 'Pabellón C': 0, Biblioteca: 0 },
      shadow_prices: { 'Copérnico': 0.0918, 'Pabellón C': 0.12, Biblioteca: 0.1063 },
      total_cost: 1.06,
    },
  }
}
