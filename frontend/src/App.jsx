import { useCallback, useEffect, useMemo, useState } from 'react'
import { BATERIA_DEFECTO, RED_MESH_DEFECTO, cargarDashboard, recalcularDespacho, sembrarDemo } from './api.js'
import * as mock from './mock.js'
import { fechaLocal, horaLocal, kwh, num1, pct, REGIMENES } from './formato.js'
import {
  Activity, BatteryCharging, Calculator, ChartColumn, ChartLine, CircleCheck, DatabaseZap, Network,
  RefreshCw, Sun, Table, TriangleAlert, UtilityPole, WifiOff, Zap,
} from 'lucide-react'
import {
  GraficoBateria, GraficoDespacho, GraficoMedicionesEnergia, GraficoPronostico, GraficoTemperatura,
} from './components/Graficos.jsx'
import RedMesh from './components/RedMesh.jsx'

function Tile({ icono: Icono, label, valor, unidad, nota }) {
  return (
    <div className="tile">
      <div className="label"><Icono size={16} aria-hidden="true" />{label}</div>
      <div className="valor">{valor}{unidad && <span className="unidad">{unidad}</span>}</div>
      {nota && <div className="nota">{nota}</div>}
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

  useEffect(() => {
    if (!cambio) return undefined
    const t = setTimeout(() => setCambio(null), 6000)
    return () => clearTimeout(t)
  }, [cambio])

  const cargar = useCallback(async () => {
    setEstado((s) => ({ ...s, cargando: true, error: null }))
    try {
      const datos = await cargarDashboard()
      const d = datos.despacho
      if (datos.fuente === 'api' && d) {
        // El formulario parte de la batería con la que se calculó el último plan guardado.
        // La API no guarda la ventana pico ni alpha/delta, así que esos se mantienen.
        setBateria((b) => ({
          ...b,
          capacity_kwh: d.battery_capacity_kwh,
          power_kw: d.battery_power_kw,
          initial_soc_kwh: d.initial_soc_kwh,
          min_soc_kwh: d.min_soc_kwh,
          charge_efficiency: d.charge_efficiency,
        }))
      }
      setEstado({ cargando: false, ...datos })
    } catch (err) {
      setEstado({ cargando: false, error: err.message })
    }
  }, [])

  useEffect(() => { cargar() }, [cargar])

  const { fuente, campus, medicion, mediciones, pronostico, despacho, mesh, health } = estado
  const tz = campus?.timezone ?? 'America/Managua'
  const pico = { inicio: bateria.peak_start_hour, fin: bateria.peak_end_hour }

  const serieDespacho = useMemo(() => (despacho?.points ?? []).map((p) => ({
    hora: horaLocal(p.interval_start, tz),
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
  })).sort((a, b) => a.hora - b.hora), [despacho, tz])

  const seriePronostico = useMemo(() => (pronostico?.points ?? []).slice(0, 24).map((p) => ({
    hora: horaLocal(p.interval_start, tz),
    demanda: p.demand_kwh,
    pv: p.pv_generation_kwh,
    prob: p.probability_within_margin,
  })).sort((a, b) => a.hora - b.hora), [pronostico, tz])

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
      await sembrarDemo()
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
          <button className="btn" onClick={cargar} disabled={estado.cargando}>
            <RefreshCw size={16} aria-hidden="true" className={estado.cargando ? 'girando' : ''} />
            {estado.cargando ? 'Cargando…' : 'Actualizar'}
          </button>
        </div>
      </header>

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

      {sinDatos && (
        <div className="card vacio">
          <DatabaseZap size={32} aria-hidden="true" />
          <p>La API está conectada pero todavía no tiene pronósticos ni planes de despacho.</p>
          <button className="btn btn-primary" onClick={sembrar} disabled={ocupado}>
            <DatabaseZap size={16} aria-hidden="true" />
            {ocupado ? 'Cargando…' : 'Cargar datos de demostración'}
          </button>
        </div>
      )}

      {!sinDatos && despacho && (
        <>
          <Protagonista franja={horaPico} pico={pico} />

          <section className="tiles">
            <Tile icono={Zap} label="Demanda prevista" valor={kwh(totales.demanda)} unidad="kWh" nota="Total del día" />
            <Tile icono={Sun} label="Generación solar" valor={kwh(totales.pv)} unidad="kWh"
              nota={`${pct(totales.pv / totales.demanda)} de la demanda · ${kwh(totales.exporta)} kWh exportados`} />
            <Tile icono={UtilityPole} label="Compra a la red" valor={kwh(totales.red)} unidad="kWh" nota={`${kwh(redEnPico)} kWh en la franja pico`} />
            <Tile icono={BatteryCharging} label="Aporte de la batería" valor={kwh(totales.descarga)} unidad="kWh" nota={`${kwh(bateriaEnPico)} kWh en la franja pico`} />
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
                      <th>Carga bat.</th><th>Descarga bat.</th><th>Exporta</th><th>Batería</th><th>Prob.</th>
                    </tr>
                  </thead>
                  <tbody>
                    {serieDespacho.map((d) => (
                      <tr key={d.hora}>
                        <td>{d.hora}:00</td><td>{REGIMENES[d.regimen]?.nombre ?? d.regimen}</td>
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
                  <h2><Network size={18} aria-hidden="true" />Red mesh DC</h2>
                  <div className="sub">Intercambio directo entre edificios (red de ejemplo) · costo del intervalo ${mesh.total_cost.toFixed(2)}</div>
                </div>
              </div>
              <RedMesh red={RED_MESH_DEFECTO} resultado={mesh} />
            </section>
          )}
        </>
      )}

      <footer className="pie">SolarNexus-EDA-UAM · Modelo 3P ASHRAE · Datos {fuente === 'api' ? 'de la API' : 'de ejemplo'}</footer>
    </div>
  )
}
