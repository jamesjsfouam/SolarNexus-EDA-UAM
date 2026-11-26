// La API devuelve las fechas en UTC ("...Z"); se muestran en la zona del campus.
export function horaLocal(iso, timeZone = 'America/Managua') {
  const h = new Intl.DateTimeFormat('es-NI', { hour: 'numeric', hourCycle: 'h23', timeZone }).format(new Date(iso))
  return Number(h)
}

export function fechaLocal(iso, timeZone = 'America/Managua') {
  return new Intl.DateTimeFormat('es-NI', { dateStyle: 'full', timeZone }).format(new Date(iso))
}

const nf0 = new Intl.NumberFormat('es-NI', { maximumFractionDigits: 0 })
const nf1 = new Intl.NumberFormat('es-NI', { maximumFractionDigits: 1 })
export const kwh = (v) => nf0.format(v)
export const num1 = (v) => nf1.format(v)
export const pct = (v) => `${nf0.format(v * 100)} %`
export const usd = (v) => `$${v.toFixed(3)}`

export const REGIMENES = {
  carga: { letra: 'C', nombre: 'Carga de batería' },
  peak_shaving: { letra: 'P', nombre: 'Peak shaving' },
  descarga_tras_pico: { letra: 'D', nombre: 'Descarga tras el pico' },
  exportacion: { letra: 'E', nombre: 'Exportación al SIN' },
  autoconsumo: { letra: 'A', nombre: 'Autoconsumo' },
}
