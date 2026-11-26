import { useEffect, useRef } from 'react'
import { X } from 'lucide-react'
import { GLOSARIO, REGIMENES } from '../formato.js'

const SECCIONES = [
  { id: 'guia-que-es', titulo: '¿Qué es SolarNexus?' },
  { id: 'guia-leer', titulo: 'Cómo leer el panel' },
  { id: 'guia-modos', titulo: 'Modos de operación' },
  { id: 'guia-escenarios', titulo: 'Probar otra batería' },
  { id: 'guia-datos', titulo: 'De dónde salen los datos' },
  { id: 'guia-glosario', titulo: 'Glosario' },
]

const TERMINOS = [
  ['Franja pico', GLOSARIO.franjaPico],
  ['Peak shaving', GLOSARIO.peakShaving],
  ['SIN', GLOSARIO.sin],
  ['Precio sombra (λ)', GLOSARIO.precioSombra],
  ['Probabilidad dentro del margen', GLOSARIO.probMargen],
  ['Red mesh DC', GLOSARIO.redMesh],
  ['Modelo 3P (ASHRAE)', 'Modelo estadístico que relaciona el consumo eléctrico con el calor, la humedad, la actividad académica y el área climatizada. Aquí se usa para pronosticar las próximas 24 horas.'],
  ['kWh', 'Kilovatio-hora: la energía que consume un equipo de 1 kW durante una hora. Todas las cifras del panel son kWh por hora.'],
]

/**
 * Guía de uso en texto, en un diálogo modal nativo (<dialog>): atrapa el foco, se cierra con Escape
 * o con el botón, y devuelve el foco al botón que la abrió.
 */
export default function Guia({ abierta, onCerrar }) {
  const ref = useRef(null)

  useEffect(() => {
    const d = ref.current
    if (!d) return
    if (abierta && !d.open) d.showModal()
    if (!abierta && d.open) d.close()
  }, [abierta])

  const ir = (id) => document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })

  return (
    <dialog ref={ref} className="guia" aria-labelledby="guia-titulo" onClose={onCerrar}
      onClick={(e) => { if (e.target === ref.current) onCerrar() }}>
      <div className="guia-cabecera">
        <h2 id="guia-titulo">Guía de uso</h2>
        <button type="button" className="btn" onClick={onCerrar} aria-label="Cerrar la guía">
          <X size={16} aria-hidden="true" />Cerrar
        </button>
      </div>
      <div className="guia-cuerpo">
        <nav className="guia-indice" aria-label="Secciones de la guía">
          <ol>
            {SECCIONES.map((s) => (
              <li key={s.id}><button type="button" onClick={() => ir(s.id)}>{s.titulo}</button></li>
            ))}
          </ol>
        </nav>
        <div className="guia-texto">
          <section id="guia-que-es">
            <h3>¿Qué es SolarNexus?</h3>
            <p>
              SolarNexus decide cada día cómo usar la energía solar del campus UAM: cuándo guardarla en baterías,
              cuándo usarla y cuándo venderla a la red nacional. Lo hace a partir de un pronóstico de consumo de las
              próximas 24 horas.
            </p>
            <p>
              El objetivo es comprar menos energía en las horas pico, que es cuando la red es más cara y depende de
              plantas térmicas a búnker.
            </p>
          </section>

          <section id="guia-leer">
            <h3>Cómo leer el panel</h3>
            <ol>
              <li><strong>Resultado del pico</strong> (franja de arriba): qué parte del consumo de la franja pico cubrió la batería y cuántos kWh de compra a la red se evitaron. Es la cifra más importante.</li>
              <li><strong>El día del campus</strong>: el color del cielo sigue la producción solar prevista (azul = noche, amarillo = mediodía). La línea blanca es el consumo previsto y la zona punteada, la franja pico. Debajo están los tramos con lo que hace el sistema.</li>
              <li><strong>Tarjetas</strong>: totales del día (demanda, solar, compra a la red y aporte de la batería), con su parte en la franja pico.</li>
              <li><strong>Pronóstico de 24 horas</strong>: consumo previsto contra generación solar. Donde la línea de consumo supera a la solar, hay déficit.</li>
              <li><strong>Batería</strong>: cuánta energía guarda al final de cada hora. Sube cuando sobra sol y baja en el pico.</li>
              <li><strong>Despacho por hora</strong>: de dónde sale la energía de cada hora (solar, batería o red). «Ver tabla» muestra los números exactos.</li>
              <li><strong>Mediciones recientes</strong>: consumo, solar y temperatura reales de las últimas 48 horas.</li>
              <li><strong>Red mesh DC</strong>: cuánta energía se pasan los edificios directamente y su precio sombra.</li>
            </ol>
            <p>Pasa el mouse (o toca) sobre cualquier gráfico para ver los valores de esa hora, y sobre el ícono ⓘ para leer qué significa un término.</p>
          </section>

          <section id="guia-modos">
            <h3>Modos de operación</h3>
            <dl>
              {Object.values(REGIMENES).map((r) => (
                <div key={r.nombre}><dt>{r.nombre}</dt><dd>{r.ayuda}</dd></div>
              ))}
            </dl>
            <p>
              El sistema solo exporta si el pronóstico es confiable (probabilidad dentro del margen ≥ 95 %) y no se
              espera pico; si hay dudas, prefiere guardar la energía.
            </p>
          </section>

          <section id="guia-escenarios">
            <h3>Probar otra batería</h3>
            <ol>
              <li>Baja hasta «Despacho por hora».</li>
              <li>Cambia la capacidad, la potencia, la carga inicial, la reserva mínima o las horas de la franja pico.</li>
              <li>Pulsa «Recalcular despacho». Si un valor no tiene sentido (por ejemplo, el pico termina antes de empezar), el campo se marca en rojo y explica el problema.</li>
              <li>Debajo del botón aparece cuánto cambió la compra a la red y el aporte de la batería. Todo el panel se actualiza con el nuevo plan.</li>
            </ol>
          </section>

          <section id="guia-datos">
            <h3>De dónde salen los datos</h3>
            <ul>
              <li><strong>Conectado a la API</strong> (punto verde arriba): los datos vienen del backend de SolarNexus.</li>
              <li><strong>Datos de ejemplo</strong> (punto amarillo): la API no respondió y se muestran datos sintéticos con el mismo formato, para poder ver el panel igual.</li>
              <li>Si la API está vacía, el botón «Cargar datos de demostración» sube 48 horas de mediciones, un pronóstico y su despacho.</li>
              <li>Por ahora todos los datos son sintéticos: todavía no hay acceso a las mediciones reales del campus. La red mesh usa tres edificios de ejemplo.</li>
            </ul>
          </section>

          <section id="guia-glosario">
            <h3>Glosario</h3>
            <dl>
              {TERMINOS.map(([termino, def]) => (
                <div key={termino}><dt>{termino}</dt><dd>{def}</dd></div>
              ))}
            </dl>
          </section>
        </div>
      </div>
    </dialog>
  )
}
