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

// `tono` agrupa los modos por lo que hace la batería: se carga, se descarga o no participa.
export const REGIMENES = {
  carga: { letra: 'C', corto: 'Carga', nombre: 'Carga de batería', tono: 'carga',
    ayuda: 'Se guarda el excedente solar para usarlo en la franja pico.' },
  peak_shaving: { letra: 'P', corto: 'Peak shaving', nombre: 'Peak shaving', tono: 'descarga',
    ayuda: 'La batería cubre el consumo en la franja pico para no comprar energía cara.' },
  descarga_tras_pico: { letra: 'D', corto: 'Descarga', nombre: 'Descarga tras el pico', tono: 'descarga',
    ayuda: 'Lo que quedó en la batería cubre el consumo de la tarde-noche.' },
  exportacion: { letra: 'E', corto: 'Exporta', nombre: 'Exportación a la red nacional', tono: 'exporta',
    ayuda: 'No se espera pico, así que el excedente solar se vende a la red nacional (SIN).' },
  autoconsumo: { letra: 'A', corto: 'Autoconsumo', nombre: 'Autoconsumo', tono: 'neutro',
    ayuda: 'El campus usa la energía solar disponible y compra a la red lo que falta.' },
}

// Términos técnicos que se explican en la interfaz con un ícono de ayuda.
export const GLOSARIO = {
  franjaPico: 'Horas de tarifa de máxima demanda, cuando la energía de la red es más cara y más contaminante (plantas térmicas a búnker).',
  peakShaving: 'Recortar el pico: descargar la batería en la franja pico para no comprar energía cara a la red.',
  sin: 'Sistema Interconectado Nacional: la red eléctrica de Nicaragua.',
  precioSombra: 'Precio sombra (λ): cuánto costaría llevar 1 kWh más a ese edificio con la red como está. Más alto = edificio más necesitado de energía.',
  probMargen: 'Probabilidad de que el consumo real quede dentro del margen de error aceptado (±10 %) del pronóstico. Si es baja, el sistema no exporta.',
  redMesh: 'Red de corriente continua que conecta los techos solares de los edificios para pasarse energía directamente, sin pasar por el inversor central.',
}
