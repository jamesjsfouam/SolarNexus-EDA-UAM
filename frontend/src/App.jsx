import { useCallback, useEffect, useMemo, useState } from 'react'
import { BATERIA_DEFECTO, RED_MESH_DEFECTO, cargarDashboard, recalcularDespacho, sembrarDemo } from './api.js'
import * as mock from './mock.js'
import { fechaLocal, GLOSARIO, horaLocal, kwh, num1, pct, REGIMENES } from './formato.js'
import Ayuda from './components/Ayuda.jsx'
import { DiaCampus } from './components/DiaCampus.jsx'
import Guia from './components/Guia.jsx'
import SelectorTema from './components/SelectorTema.jsx'
import {
  Activity, BatteryCharging, BookOpen, Calculator, ChartColumn, ChartLine, CircleCheck, DatabaseZap, Network,
  RefreshCw, Sun, Table, TriangleAlert, UtilityPole, WifiOff, Zap,
} from 'lucide-react'
import {
  GraficoBateria, GraficoDespacho, GraficoMedicionesEnergia, GraficoPronostico, GraficoTemperatura,
} from './components/Graficos.jsx'
import RedMesh from './components/RedMesh.jsx'

// Configuración completa del último despacho guardado; el back guarda también la ventana pico y alpha/delta.
function bateriaDesdeDespacho(despacho) {
  return {
    ...BATERIA_DEFECTO,
    capacity_kwh: despacho.battery_capacity_kwh,
    power_kw: despacho.battery_power_kw,
    initial_soc_kwh: despacho.initial_soc_kwh,
    min_soc_kwh: despacho.min_soc_kwh,
    charge_efficiency: despacho.charge_efficiency,
    peak_start_hour: despacho.peak_start_hour ?? BATERIA_DEFECTO.peak_start_hour,
    peak_end_hour: despacho.peak_end_hour ?? BATERIA_DEFECTO.peak_end_hour,
    alpha: despacho.alpha ?? BATERIA_DEFECTO.alpha,
    delta: despacho.delta ?? BATERIA_DEFECTO.delta,
  }
}

// Posición (slot) y etiquetas de hora de un intervalo; el siguiente se toma del punto que sigue o +1 h.
function intervalo(p, slot, points, tz) {
  const hora = horaLocal(p.interval_start, tz)
  const siguiente = points[slot + 1]?.interval_start
    ?? new Date(Date.parse(p.interval_start) + 60 * 60 * 1000).toISOString()
  const etiqueta = (h) => `${String(h).padStart(2, '0')}:00`
  return { slot, hora, horaLabel: etiqueta(hora), horaSiguienteLabel: etiqueta(horaLocal(siguiente, tz)) }
}

function Tile({ icono: Icono, label, valor, unidad, nota, ayuda }) {
  return (
    <div className="tile">
      <div className="label"><Icono size={16} aria-hidden="true" />{label}{ayuda && <Ayuda texto={ayuda} etiqueta={`Qué es: ${label}`} />}</div>
      <div className="valor">{valor}{unidad && <span className="unidad">{unidad}</span>}</div>
      {nota && <div className="nota">{nota}</div>}
    </div>
  )
}

// Silueta de la página mientras llega la primera respuesta: evita una pantalla vacía.
function Esqueleto() {
  return (
    <div className="esqueleto" aria-busy="true" aria-label="Cargando datos del despacho">
      <div className="hueso hueso-protagonista" />
      <div className="hueso hueso-dia" />
      <div className="tiles">
        {[0, 1, 2, 3].map((i) => <div key={i} className="hueso hueso-tile" />)}
      </div>
      <div className="grid-2">
        <div className="hueso hueso-grafico" />
        <div className="hueso hueso-grafico" />
      </div>
    </div>
  )
}

// Mismas reglas que BatteryConfig en el back, con mensajes en lenguaje llano.
function erroresBateria(c) {
  const e = {}
  if (!(c.capacity_kwh > 0)) e.capacity_kwh = 'Debe ser mayor que 0'
  if (!(c.power_kw > 0)) e.power_kw = 'Debe ser mayor que 0'
  if (c.initial_soc_kwh > c.capacity_kwh) e.initial_soc_kwh = 'No puede superar la capacidad'
  if (c.min_soc_kwh > c.initial_soc_kwh) e.min_soc_kwh = 'No puede superar la carga inicial'
  if (!(c.peak_start_hour >= 0 && c.peak_start_hour <= 23)) e.peak_start_hour = 'Entre 0 y 23'
  if (!(c.peak_end_hour >= 1 && c.peak_end_hour <= 24)) e.peak_end_hour = 'Entre 1 y 24'
  else if (c.peak_start_hour >= c.peak_end_hour) e.peak_end_hour = 'Debe ser después del inicio'
  return e
}

function FormBateria({ inicial, onCalcular, ocupado }) {
  const [cfg, setCfg] = useState(inicial)
  const errores = erroresBateria(cfg)
  const valido = Object.keys(errores).length === 0
  const campo = (clave, label, max) => (
    <label className={errores[clave] ? 'con-error' : ''}>
      {label}
      <input type="number" min="0" max={max} value={Number.isNaN(cfg[clave]) ? '' : cfg[clave]}
        aria-invalid={Boolean(errores[clave])} aria-describedby={errores[clave] ? `err-${clave}` : undefined}
        onChange={(e) => setCfg({ ...cfg, [clave]: e.target.value === '' ? NaN : Number(e.target.value) })} />
      {errores[clave] && <span className="error-campo" id={`err-${clave}`}>{errores[clave]}</span>}
    </label>
  )
  return (
    <form className="form-bateria" noValidate onSubmit={(e) => { e.preventDefault(); if (valido) onCalcular(cfg) }}>
      {campo('capacity_kwh', 'Capacidad (kWh)')}
      {campo('power_kw', 'Potencia (kW)')}
      {campo('initial_soc_kwh', 'Carga inicial (kWh)')}
      {campo('min_soc_kwh', 'Reserva mínima (kWh)')}
      {campo('peak_start_hour', 'Pico desde (h)', 23)}
      {campo('peak_end_hour', 'Pico hasta (h)', 24)}
      <button className="btn" disabled={ocupado || !valido}>
        <Calculator size={16} aria-hidden="true" />{ocupado ? 'Calculando…' : 'Recalcular despacho'}
      </button>
    </form>
  )
}

// Frase principal: qué parte del déficit de la franja pico cubrió la batería.
function Protagonista({ franja, pico }) {
  const deficit = franja.reduce((s, d) => s + Math.max(d.demanda - d.pv, 0), 0)
  const bateria = franja.reduce((s, d) => s + d.descarga, 0)
  const red = franja.reduce((s, d) => s + d.red, 0)
  const rango = `de ${pico.inicio} a ${pico.fin} h`
  let titulo
  let detalle
  if (deficit < 0.5) {
    titulo = `La energía solar cubre toda la franja pico ${rango}.`
    detalle = 'Ese día no hace falta descargar la batería para evitar la tarifa de máxima demanda.'
  } else if (red < 0.5) {
    titulo = `La batería cubrió el 100 % del pico ${rango}.`
    detalle = `Se evitó comprar ${kwh(bateria)} kWh a la red nacional en tarifa de máxima demanda.`
  } else {
    titulo = `La batería cubrió el ${pct(bateria / deficit)} del pico ${rango}.`
    detalle = `Evitó ${kwh(bateria)} kWh de compra en tarifa de máxima demanda; aún se compran ${kwh(red)} kWh en esa franja.`
  }
  return (
    <section className="protagonista" aria-label="Resultado del despacho en la franja pico">
      <BatteryCharging size={28} aria-hidden="true" />
      <div>
        <p className="protagonista-titulo">{titulo}</p>
        <p className="protagonista-detalle">{detalle}</p>
      </div>
      <div className="protagonista-cifra">
        <span>{kwh(bateria)}</span>
        <small>kWh evitados en el pico</small>
      </div>
    </section>
  )
}

export default function App() {
  const [estado, setEstado] = useState({ cargando: true })
  const [bateria, setBateria] = useState(BATERIA_DEFECTO)
  const [ocupado, setOcupado] = useState(false)
  const [verTabla, setVerTabla] = useState(false)
  const [cambio, setCambio] = useState(null) // { red: [antes, después], bateria: [antes, después] }
  const [guiaAbierta, setGuiaAbierta] = useState(false)

  useEffect(() => {
    if (!cambio) return undefined
    const t = setTimeout(() => setCambio(null), 6000)
    return () => clearTimeout(t)
  }, [cambio])

  const cargar = useCallback(async () => {
    setEstado((s) => ({ ...s, cargando: true, error: null }))
    try {
      const datos = await cargarDashboard()
      // El formulario parte de la batería con la que se calculó el último plan guardado.
      if (datos.fuente === 'api' && datos.despacho) setBateria(bateriaDesdeDespacho(datos.despacho))
      setEstado({ cargando: false, ...datos })
    } catch (err) {
      setEstado({ cargando: false, error: err.message })
    }
  }, [])

  useEffect(() => { cargar() }, [cargar])

  const { fuente, campus, medicion, mediciones, pronostico, despacho, mesh, meshError, health } = estado
  const tz = campus?.timezone ?? 'America/Managua'
  const pico = { inicio: bateria.peak_start_hour, fin: bateria.peak_end_hour }

  const serieDespacho = useMemo(() => (despacho?.points ?? []).slice(0, 24).map((p, slot, points) => ({
    ...intervalo(p, slot, points, tz),
    interval_start: p.interval_start,
    regimen: p.regime,
    solar: p.pv_generation_kwh - p.battery_charge_kwh - p.export_kwh,
    descarga: p.battery_discharge_kwh,
    red: p.grid_import_kwh,
    carga: p.battery_charge_kwh,
    exporta: p.export_kwh,
    soc: p.soc_after_kwh,
    demanda: p.demand_kwh,
    pv: p.pv_generation_kwh,
    prob: p.probability_within_margin,
  })), [despacho, tz])

  const seriePronostico = useMemo(() => (pronostico?.points ?? []).slice(0, 24).map((p, slot, points) => ({
    ...intervalo(p, slot, points, tz),
    demanda: p.demand_kwh,
    pv: p.pv_generation_kwh,
    prob: p.probability_within_margin,
  })), [pronostico, tz])

  const serieMediciones = useMemo(() => {
    const dia = new Intl.DateTimeFormat('es-NI', { weekday: 'short', timeZone: tz })
    return (mediciones ?? []).map((m, i) => {
      const h = horaLocal(m.interval_start, tz)
      const d = dia.format(new Date(m.interval_start))
      return {
        i,
        hora: h,
        corta: h === 0 ? d : `${h}h`,
        etiqueta: `${d} ${h}:00`,
        consumo: m.consumption_kwh,
        pv: m.pv_generation_kwh,
        temp: m.temperature_c,
        hum: m.humidity_pct,
      }
    })
  }, [mediciones, tz])

  const totales = useMemo(() => serieDespacho.reduce((t, d) => ({
    demanda: t.demanda + d.demanda, pv: t.pv + d.pv, red: t.red + d.red,
    descarga: t.descarga + d.descarga, exporta: t.exporta + d.exporta,
  }), { demanda: 0, pv: 0, red: 0, descarga: 0, exporta: 0 }), [serieDespacho])

  async function recalcular(cfg) {
    setOcupado(true)
    try {
      const nuevo = fuente === 'api' ? await recalcularDespacho(pronostico.id, cfg) : mock.dashboard(cfg).despacho
      const suma = (pts, k) => pts.reduce((s, p) => s + p[k], 0)
      setCambio({
        red: [suma(despacho.points, 'grid_import_kwh'), suma(nuevo.points, 'grid_import_kwh')],
        bateria: [suma(despacho.points, 'battery_discharge_kwh'), suma(nuevo.points, 'battery_discharge_kwh')],
      })
      setBateria(cfg)
      setEstado((s) => ({ ...s, despacho: nuevo, error: null }))
    } catch (err) {
      setEstado((s) => ({ ...s, error: err.message }))
    } finally {
      setOcupado(false)
    }
  }

  async function sembrar() {
    setOcupado(true)
    try {
      await sembrarDemo(pronostico?.id) // si ya hay pronóstico, solo calcula su despacho
      await cargar()
    } catch (err) {
      setEstado((s) => ({ ...s, error: err.message }))
    } finally {
      setOcupado(false)
    }
  }

  const sinDatos = fuente === 'api' && (!pronostico || !despacho)
  const horaPico = serieDespacho.filter((d) => d.hora >= pico.inicio && d.hora < pico.fin)
  const redEnPico = horaPico.reduce((s, d) => s + d.red, 0)
  const bateriaEnPico = horaPico.reduce((s, d) => s + d.descarga, 0)

  return (
    <div className="app">
      <header className="header">
        <div>
          <h1>SolarNexus · Despacho energético</h1>
          <p>
            {campus?.campus_name ?? 'Campus UAM'}
            {despacho?.points?.length ? ` · ${fechaLocal(despacho.points[0].interval_start, tz)}` : ''}
          </p>
        </div>
        <div className="header-actions">
          {fuente && (
            <span className="badge" title={fuente === 'api' ? `API ${health?.version} · base de datos ${health?.database}` : ''}>
              <span className="dot" style={{ background: fuente === 'api' ? 'var(--ok)' : 'var(--warn)' }} />
              {fuente === 'api' ? 'Conectado a la API' : 'Datos de ejemplo'}
            </span>
          )}
          <button className="btn" onClick={() => setGuiaAbierta(true)} aria-haspopup="dialog">
            <BookOpen size={16} aria-hidden="true" />Guía
          </button>
          <SelectorTema />
          <button className="btn" onClick={cargar} disabled={estado.cargando}>
            <RefreshCw size={16} aria-hidden="true" className={estado.cargando ? 'girando' : ''} />
            {estado.cargando ? 'Cargando…' : 'Actualizar'}
          </button>
        </div>
      </header>
      <Guia abierta={guiaAbierta} onCerrar={() => setGuiaAbierta(false)} />

      {estado.error && (
        <div className="aviso error">
          <TriangleAlert size={20} aria-hidden="true" />
          <div><strong>La API respondió con un error</strong>{estado.error}</div>
        </div>
      )}
      {fuente === 'ejemplo' && (
        <div className="aviso">
          <WifiOff size={20} aria-hidden="true" />
          <div>
            <strong>La API no está disponible: se muestran datos de ejemplo.</strong>
            Levántala desde la raíz del repo con <code>uvicorn solarnexus.api.main:app --reload</code> y pulsa Actualizar.
          </div>
        </div>
      )}
      {meshError && (
        <div className="aviso">
          <Network size={20} aria-hidden="true" />
          <div><strong>La red mesh no está disponible en este momento.</strong>{meshError}</div>
        </div>
      )}

      {estado.cargando && !despacho && <Esqueleto />}

      {sinDatos && (
        <div className="card vacio">
          <DatabaseZap size={32} aria-hidden="true" />
          <p>
            {pronostico
              ? 'Ya hay un pronóstico, pero todavía no tiene un plan de despacho.'
              : 'La API está conectada pero todavía no tiene pronósticos ni planes de despacho.'}
          </p>
          <button className="btn btn-primary" onClick={sembrar} disabled={ocupado}>
            <DatabaseZap size={16} aria-hidden="true" />
            {ocupado ? 'Procesando…' : pronostico ? 'Calcular el despacho del pronóstico' : 'Cargar datos de demostración'}
          </button>
        </div>
      )}

      {!sinDatos && despacho && (
        <>
          <Protagonista franja={horaPico} pico={pico} />

          <section className="card">
            <div className="card-head">
              <div>
                <h2><Sun size={18} aria-hidden="true" />El día del campus</h2>
                <div className="sub">
                  El cielo sigue la producción solar prevista; la línea blanca es el consumo y abajo, qué hace el sistema en cada tramo
                  <Ayuda texto={GLOSARIO.franjaPico} etiqueta="Qué es la franja pico" />
                </div>
              </div>
            </div>
            <DiaCampus datos={serieDespacho} pico={pico} />
          </section>

          <section className="tiles">
            <Tile icono={Zap} label="Demanda prevista" valor={kwh(totales.demanda)} unidad="kWh" nota="Total de las primeras 24 horas" />
            <Tile icono={Sun} label="Generación solar" valor={kwh(totales.pv)} unidad="kWh"
              nota={`${pct(totales.pv / totales.demanda)} de la demanda · ${kwh(totales.exporta)} kWh exportados`} />
            <Tile icono={UtilityPole} label="Compra a la red" ayuda={GLOSARIO.sin} valor={kwh(totales.red)} unidad="kWh" nota={`${kwh(redEnPico)} kWh en la franja pico`} />
            <Tile icono={BatteryCharging} label="Aporte de la batería" ayuda={GLOSARIO.peakShaving} valor={kwh(totales.descarga)} unidad="kWh" nota={`${kwh(bateriaEnPico)} kWh en la franja pico`} />
          </section>

          <div className="grid-2">
            <section className="card">
              <div className="card-head">
                <div>
                  <h2><ChartLine size={18} aria-hidden="true" />Pronóstico de 24 horas</h2>
                  <div className="sub">kWh por hora · modelo {pronostico.model_name} v{pronostico.model_version}</div>
                </div>
              </div>
              <GraficoPronostico datos={seriePronostico} pico={pico} />
            </section>

            <section className="card">
              <div className="card-head">
                <div>
                  <h2><BatteryCharging size={18} aria-hidden="true" />Batería</h2>
                  <div className="sub">kWh guardados al final de cada hora · termina en {kwh(despacho.final_soc_kwh)} kWh</div>
                </div>
              </div>
              <GraficoBateria datos={serieDespacho} capacidad={despacho.battery_capacity_kwh} minimo={despacho.min_soc_kwh} pico={pico} />
            </section>
          </div>

          <section className="card">
            <div className="card-head">
              <div>
                <h2><ChartColumn size={18} aria-hidden="true" />Despacho por hora</h2>
                <div className="sub">kWh por hora · de dónde sale la energía que consume el campus y en qué modo opera el sistema</div>
              </div>
              <button className="toggle" aria-expanded={verTabla} onClick={() => setVerTabla(!verTabla)}>
                <Table size={16} aria-hidden="true" />{verTabla ? 'Ocultar tabla' : 'Ver tabla'}
              </button>
            </div>
            <GraficoDespacho datos={serieDespacho} pico={pico} />
            {verTabla && (
              <div className="tabla-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Hora</th><th>Modo</th><th>Demanda</th><th>Solar</th><th>Red</th>
                      <th>Carga bat.</th><th>Descarga bat.</th><th>Exporta</th><th>Batería</th>
                      <th>Prob. <Ayuda texto={GLOSARIO.probMargen} etiqueta="Qué es la probabilidad dentro del margen" /></th>
                    </tr>
                  </thead>
                  <tbody>
                    {serieDespacho.map((d) => (
                      <tr key={d.interval_start}>
                        <td>{d.horaLabel}</td><td>{REGIMENES[d.regimen]?.nombre ?? d.regimen}</td>
                        <td>{kwh(d.demanda)}</td><td>{kwh(d.pv)}</td><td>{kwh(d.red)}</td><td>{kwh(d.carga)}</td>
                        <td>{kwh(d.descarga)}</td><td>{kwh(d.exporta)}</td><td>{kwh(d.soc)}</td><td>{pct(d.prob)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <div className="sub">Valores en kWh.</div>
              </div>
            )}
            <FormBateria key={JSON.stringify(bateria)} inicial={bateria} onCalcular={recalcular} ocupado={ocupado} />
            <div className="cambio" role="status" aria-live="polite">
              {cambio && (
                <>
                  <CircleCheck size={16} aria-hidden="true" />
                  Despacho recalculado. Compra a la red: {kwh(cambio.red[0])} → {kwh(cambio.red[1])} kWh
                  ({cambio.red[1] - cambio.red[0] >= 0 ? '+' : '−'}{kwh(Math.abs(cambio.red[1] - cambio.red[0]))}) ·
                  batería: {kwh(cambio.bateria[0])} → {kwh(cambio.bateria[1])} kWh
                </>
              )}
            </div>
          </section>

          <section className="card">
            <div className="card-head">
              <div>
                <h2><Activity size={18} aria-hidden="true" />Mediciones recientes</h2>
                <div className="sub">
                  {serieMediciones.length
                    ? `Últimas ${serieMediciones.length} horas registradas en el campus · ahora ${num1(medicion.temperature_c)} °C y ${kwh(medicion.humidity_pct)} % de humedad`
                    : 'Todavía no hay mediciones registradas'}
                </div>
              </div>
            </div>
            {serieMediciones.length > 0 && (
              <div className="grid-2 interno">
                <div>
                  <h3>Consumo y solar (kWh)</h3>
                  <GraficoMedicionesEnergia datos={serieMediciones} />
                </div>
                <div>
                  <h3>Temperatura (°C)</h3>
                  <GraficoTemperatura datos={serieMediciones} />
                </div>
              </div>
            )}
          </section>

          {mesh && (
            <section className="card">
              <div className="card-head">
                <div>
                  <h2><Network size={18} aria-hidden="true" />Red mesh DC<Ayuda texto={GLOSARIO.redMesh} etiqueta="Qué es la red mesh DC" /></h2>
                  <div className="sub">
                    Intercambio directo entre edificios (red de ejemplo) · costo del intervalo ${mesh.total_cost.toFixed(2)} ·
                    λ = precio sombra<Ayuda texto={GLOSARIO.precioSombra} etiqueta="Qué es el precio sombra" />
                  </div>
                </div>
              </div>
              <RedMesh red={RED_MESH_DEFECTO} resultado={mesh} />
            </section>
          )}
        </>
      )}

      <footer className="pie">
        {pronostico?.generated_at
          ? `Pronóstico generado el ${new Intl.DateTimeFormat('es-NI', { dateStyle: 'medium', timeStyle: 'short', timeZone: tz }).format(new Date(pronostico.generated_at))}`
          : 'Sin pronóstico cargado'}
        {' · '}Datos {fuente === 'api' ? 'de la API' : 'de ejemplo'} · SolarNexus-EDA-UAM
      </footer>
    </div>
  )
}
