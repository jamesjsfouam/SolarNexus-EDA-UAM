import { useId } from 'react'
import { Sun } from 'lucide-react'
import { REGIMENES } from '../formato.js'

const finHora = (h) => (h + 1 === 24 ? 24 : (h + 1) % 24)

/** Agrupa horas seguidas con el mismo modo: [{ regimen, desde, hasta, slots }]. */
function agrupar(datos) {
  const tramos = []
  for (const d of datos) {
    const ultimo = tramos.at(-1)
    if (ultimo && ultimo.regimen === d.regimen) {
      ultimo.hasta = finHora(d.hora)
      ultimo.slots += 1
    } else {
      tramos.push({ regimen: d.regimen, desde: d.hora, hasta: finHora(d.hora), slots: 1 })
    }
  }
  return tramos
}

/**
 * Modos de operación del día como tramos con nombre, de ancho proporcional a sus horas.
 * Reemplaza la franja de letras A/C/P/D: el nombre se lee sin consultar una leyenda.
 */
export function Tramos({ datos, className = '' }) {
  return (
    <ol className={`tramos ${className}`} aria-label="Modo de operación por tramos del día">
      {agrupar(datos).map((t) => {
        const r = REGIMENES[t.regimen] ?? { letra: '?', corto: t.regimen, nombre: t.regimen, tono: 'neutro', ayuda: '' }
        const texto = t.slots >= 5 ? r.nombre : t.slots >= 2 ? r.corto : r.letra
        const descripcion = `${r.nombre}, de ${t.desde} a ${t.hasta} h. ${r.ayuda}`
        return (
          <li key={`${t.desde}-${t.regimen}`} className={`tramo tono-${r.tono}`} style={{ flexGrow: t.slots }}
            title={descripcion} aria-label={descripcion}>
            <span className="tramo-nombre" aria-hidden="true">{texto}</span>
            {t.slots >= 3 && <span className="tramo-horas" aria-hidden="true">{t.desde}–{t.hasta} h</span>}
          </li>
        )
      })}
    </ol>
  )
}

// Color del cielo según la fracción de la producción solar máxima: noche → amanecer → mediodía.
const NOCHE = [27, 35, 64]
const ALBA = [224, 136, 74]
const DIA = [255, 211, 110]
const mezcla = (a, b, t) => a.map((v, i) => Math.round(v + (b[i] - v) * t))
function cielo(f) {
  const rgb = f < 0.35 ? mezcla(NOCHE, ALBA, f / 0.35) : mezcla(ALBA, DIA, (f - 0.35) / 0.65)
  return `rgb(${rgb.join(',')})`
}

/**
 * "El día del campus": el cielo de 24 h pintado con la curva solar, el consumo previsto encima,
 * la franja pico marcada y debajo los tramos de operación. Resume todo el despacho de un vistazo.
 */
export function DiaCampus({ datos, pico }) {
  const id = `cielo${useId().replace(/[^a-zA-Z0-9]/g, '')}`
  const n = datos.length || 24
  const pvMax = Math.max(1, ...datos.map((d) => d.pv))
  const demMax = Math.max(1, ...datos.map((d) => d.demanda))
  const x = (slot) => ((slot + 0.5) / n) * 100
  const puntos = datos.map((d) => `${x(d.slot)},${56 - (d.demanda / demMax) * 44}`).join(' ')
  const slotSol = datos.reduce((m, d) => (d.pv > (datos[m]?.pv ?? -1) ? d.slot : m), 0)
  const enPico = datos.filter((d) => d.hora >= pico.inicio && d.hora < pico.fin)
  const marcas = datos.filter((d) => d.hora % 6 === 0)

  return (
    <div className="dia">
      <div className="dia-cielo">
        <svg viewBox="0 0 100 60" preserveAspectRatio="none" aria-hidden="true">
          <defs>
            <linearGradient id={id} x1="0" x2="1" y1="0" y2="0">
              {datos.map((d) => (
                <stop key={d.slot} offset={`${x(d.slot)}%`} stopColor={cielo(d.pv / pvMax)} />
              ))}
            </linearGradient>
          </defs>
          <rect width="100" height="60" fill={`url(#${id})`} />
          <polyline points={puntos} fill="none" stroke="rgba(0,0,0,0.35)" strokeWidth="4" vectorEffect="non-scaling-stroke" strokeLinejoin="round" />
          <polyline points={puntos} fill="none" stroke="#ffffff" strokeWidth="2" vectorEffect="non-scaling-stroke" strokeLinejoin="round" />
        </svg>
        {enPico.length > 0 && (
          <div className="dia-pico" style={{ left: `${(enPico[0].slot / n) * 100}%`, width: `${(enPico.length / n) * 100}%` }}>
            <span>Pico</span>
          </div>
        )}
        {datos[slotSol]?.pv > 0 && (
          <Sun className="dia-sol" size={22} aria-hidden="true" style={{ left: `${x(slotSol)}%` }} />
        )}
        <span className="dia-leyenda" aria-hidden="true">— consumo previsto</span>
      </div>
      <div className="dia-horas" aria-hidden="true">
        {marcas.map((d) => (
          <span key={d.slot} style={{ left: `${(d.slot / n) * 100}%` }}>{d.hora}h</span>
        ))}
      </div>
      <Tramos datos={datos} />
    </div>
  )
}
