// Cliente de la API de C. Santana (docs/API_CONTRACT.md, rama C.santana).
// Si la API no responde, el dashboard usa datos de ejemplo con el mismo formato.
import * as mock from './mock.js'

// Por defecto la misma ruta del sitio: en desarrollo el proxy de Vite la reenvía al back (vite.config.js).
const BASE = (import.meta.env.VITE_API_URL ?? '/api/v1').replace(/\/+$/, '')

export class ApiError extends Error {
  constructor(status, message) {
    super(message)
    this.status = status
  }
}

async function request(path, options = {}) {
  const headers = new Headers(options.headers ?? {})
  if (options.body !== undefined && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  const res = await fetch(BASE + path, {
    ...options,
    headers,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    const rawDetail = data.detail
    const detail = Array.isArray(rawDetail)
      ? rawDetail.map((item) => {
          const location = Array.isArray(item.loc) ? item.loc.filter((part) => part !== 'body').join('.') : ''
          return `${location ? `${location}: ` : ''}${item.msg ?? 'Dato inválido'}`
        }).join('; ')
      : typeof rawDetail === 'string'
        ? rawDetail
        : rawDetail?.message ?? res.statusText
    throw new ApiError(res.status, detail || `HTTP ${res.status}`)
  }
  return res.json()
}

// Configuración de batería por defecto (la misma de la demo de Python).
export const BATERIA_DEFECTO = {
  capacity_kwh: 1500,
  power_kw: 300,
  initial_soc_kwh: 500,
  min_soc_kwh: 100,
  charge_efficiency: 0.95,
  peak_start_hour: 14,
  peak_end_hour: 17,
  alpha: 0.05,
  delta: 0.1,
}

// Red mesh de ejemplo; se reemplaza cuando el back defina los edificios reales.
export const RED_MESH_DEFECTO = {
  nodes: [
    { name: 'Copérnico', generation_kwh: 120, demand_kwh: 40 },
    { name: 'Pabellón C', generation_kwh: 10, demand_kwh: 90 },
    { name: 'Biblioteca', generation_kwh: 30, demand_kwh: 30 },
  ],
  links: [
    { origin: 'Copérnico', destination: 'Pabellón C', capacity_kwh: 60, transfer_cost_per_kwh: 0.02, loss_fraction: 0.03, switch_cost: 0 },
    { origin: 'Copérnico', destination: 'Biblioteca', capacity_kwh: 60, transfer_cost_per_kwh: 0.01, loss_fraction: 0.02, switch_cost: 0 },
    { origin: 'Biblioteca', destination: 'Pabellón C', capacity_kwh: 60, transfer_cost_per_kwh: 0.01, loss_fraction: 0.02, switch_cost: 0 },
  ],
  central_cycling_cost_per_kwh: 0.12,
}

const notFoundToNull = (err) => {
  if (err instanceof ApiError && err.status === 404) return null
  throw err
}

/** Carga todo lo que muestra el dashboard. Devuelve { fuente, ...datos }. */
export async function cargarDashboard() {
  try {
    const health = await request('/health')
    const [campus, mediciones, pronostico, despacho, meshResult] = await Promise.all([
      request('/campus'),
      request('/measurements?limit=48'), // llegan de la más reciente a la más antigua
      request('/forecasts/latest').catch(notFoundToNull),
      request('/dispatch/latest').catch(notFoundToNull),
      // Si la red mesh falla, el resto del dashboard sigue funcionando.
      request('/mesh/solve', { method: 'POST', body: RED_MESH_DEFECTO })
        .then((mesh) => ({ mesh, meshError: null }))
        .catch((err) => ({ mesh: null, meshError: err.message })),
    ])
    mediciones.reverse()
    return {
      fuente: 'api', health, campus, medicion: mediciones.at(-1) ?? null, mediciones, pronostico, despacho, ...meshResult,
    }
  } catch (err) {
    if (err instanceof ApiError) throw err // la API respondió con un error real
    return { fuente: 'ejemplo', ...mock.dashboard(BATERIA_DEFECTO) }
  }
}

/**
 * Prepara una API sin datos: sube mediciones si no hay, un pronóstico si no se pasa uno existente,
 * y calcula su despacho. Con un pronóstico existente no lo duplica.
 */
export async function sembrarDemo(forecastRunId = null) {
  const existentes = await request('/measurements?limit=1')
  if (existentes.length === 0) {
    await request('/measurements/batch', { method: 'POST', body: { records: mock.medicionesParaSubir() } })
  }
  let runId = forecastRunId
  if (!runId) {
    const pronostico = await request('/forecasts', { method: 'POST', body: mock.pronosticoParaSubir() })
    runId = pronostico.id
  }
  return request('/dispatch/plan', {
    method: 'POST',
    body: { forecast_run_id: runId, battery: BATERIA_DEFECTO },
  })
}

/** Recalcula el despacho del último pronóstico con otra configuración de batería. */
export function recalcularDespacho(forecastRunId, battery) {
  return request('/dispatch/plan', { method: 'POST', body: { forecast_run_id: forecastRunId, battery } })
}
