import { useCallback, useEffect, useMemo, useState } from 'react'
import { BATERIA_DEFECTO, RED_MESH_DEFECTO, cargarDashboard, recalcularDespacho, sembrarDemo } from './api.js'
import * as mock from './mock.js'
import { fechaLocal, horaLocal, kwh, num1, pct, REGIMENES } from './formato.js'
import { GraficoBateria, GraficoDespacho, GraficoPronostico } from './components/Graficos.jsx'
import RedMesh from './components/RedMesh.jsx'

function Tile({ label, valor, unidad, nota }) {
  return (
    <div className="tile">
      <div className="label">{label}</div>
      <div className="valor">{valor}{unidad && <span className="unidad">{unidad}</span>}</div>
      {nota && <div className="nota">{nota}</div>}
    </div>
  )
}

function FormBateria({ inicial, onCalcular, ocupado }) {
  const [cfg, setCfg] = useState(inicial)
  const campo = (clave, label) => (
    <label>
      {label}
      <input type="number" min="0" value={cfg[clave]} onChange={(e) => setCfg({ ...cfg, [clave]: Number(e.target.value) })} />
    </label>
  )
  return (
    <form className="form-bateria" onSubmit={(e) => { e.preventDefault(); onCalcular(cfg) }}>
      {campo('capacity_kwh', 'Capacidad (kWh)')}
      {campo('power_kw', 'Potencia (kW)')}
      {campo('initial_soc_kwh', 'Carga inicial (kWh)')}
      {campo('min_soc_kwh', 'Reserva mínima (kWh)')}
      {campo('peak_start_hour', 'Pico desde (h)')}
      {campo('peak_end_hour', 'Pico hasta (h)')}
      <button className="btn" disabled={ocupado}>{ocupado ? 'Calculando…' : 'Recalcular despacho'}</button>
    </form>
  )
}

export default function App() {
  const [estado, setEstado] = useState({ cargando: true })
  const [bateria, setBateria] = useState(BATERIA_DEFECTO)
  const [ocupado, setOcupado] = useState(false)
  const [verTabla, setVerTabla] = useState(false)

  const cargar = useCallback(async () => {
    setEstado((s) => ({ ...s, cargando: true, error: null }))
    try {
      setEstado({ cargando: false, ...(await cargarDashboard()) })
    } catch (err) {
      setEstado({ cargando: false, error: err.message })
    }
  }, [])

  useEffect(() => { cargar() }, [cargar])

  const { fuente, campus, medicion, pronostico, despacho, mesh, health } = estado
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

  const totales = useMemo(() => serieDespacho.reduce((t, d) => ({
    demanda: t.demanda + d.demanda, pv: t.pv + d.pv, red: t.red + d.red,
    descarga: t.descarga + d.descarga, exporta: t.exporta + d.exporta,
  }), { demanda: 0, pv: 0, red: 0, descarga: 0, exporta: 0 }), [serieDespacho])

  async function recalcular(cfg) {
    setOcupado(true)
    try {
      const nuevo = fuente === 'api' ? await recalcularDespacho(pronostico.id, cfg) : mock.dashboard(cfg).despacho
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
          <button className="btn" onClick={cargar} disabled={estado.cargando}>{estado.cargando ? 'Cargando…' : 'Actualizar'}</button>
        </div>
      </header>

      {estado.error && (
        <div className="aviso error"><strong>La API respondió con un error</strong>{estado.error}</div>
      )}
      {fuente === 'ejemplo' && (
        <div className="aviso">
          <strong>La API no está disponible: se muestran datos de ejemplo.</strong>
          Levántala con <code>uvicorn solarnexus.api.main:app --reload</code> (rama <code>C.santana</code>) y pulsa Actualizar.
        </div>
      )}

      {sinDatos && (
        <div className="card vacio">
          <p>La API está conectada pero todavía no tiene pronósticos ni planes de despacho.</p>
          <button className="btn btn-primary" onClick={sembrar} disabled={ocupado}>
            {ocupado ? 'Cargando…' : 'Cargar pronóstico de demostración'}
          </button>
        </div>
      )}

      {!sinDatos && despacho && (
        <>
          <section className="tiles">
            <Tile label="Demanda prevista" valor={kwh(totales.demanda)} unidad="kWh" nota="Total del día" />
            <Tile label="Generación solar" valor={kwh(totales.pv)} unidad="kWh" nota={`${pct(totales.pv / totales.demanda)} de la demanda`} />
            <Tile label="Compra a la red" valor={kwh(totales.red)} unidad="kWh" nota={`${kwh(redEnPico)} kWh en la franja pico`} />
            <Tile label="Aporte de la batería" valor={kwh(totales.descarga)} unidad="kWh" nota={`${kwh(bateriaEnPico)} kWh en la franja pico`} />
            <Tile label="Exportación al SIN" valor={kwh(totales.exporta)} unidad="kWh" />
            {medicion && (
              <Tile label="Última medición" valor={num1(medicion.temperature_c)} unidad="°C"
                nota={`Humedad ${kwh(medicion.humidity_pct)} % · ${kwh(medicion.consumption_kwh ?? 0)} kWh`} />
            )}
          </section>

          <div className="grid-2">
            <section className="card">
              <div className="card-head">
                <div>
                  <h2>Pronóstico de 24 horas</h2>
                  <div className="sub">Modelo {pronostico.model_name} v{pronostico.model_version}</div>
                </div>
              </div>
              <GraficoPronostico datos={seriePronostico} pico={pico} />
            </section>

            <section className="card">
              <div className="card-head">
                <div>
                  <h2>Batería</h2>
                  <div className="sub">Energía guardada al final de cada hora · termina en {kwh(despacho.final_soc_kwh)} kWh</div>
                </div>
              </div>
              <GraficoBateria datos={serieDespacho} capacidad={despacho.battery_capacity_kwh} minimo={despacho.min_soc_kwh} pico={pico} />
            </section>
          </div>

          <section className="card">
            <div className="card-head">
              <div>
                <h2>Despacho por hora</h2>
                <div className="sub">De dónde sale la energía que consume el campus y en qué modo opera el sistema</div>
              </div>
              <button className="toggle" onClick={() => setVerTabla(!verTabla)}>{verTabla ? 'Ocultar tabla' : 'Ver tabla'}</button>
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
            <FormBateria inicial={bateria} onCalcular={recalcular} ocupado={ocupado} />
          </section>

          {mesh && (
            <section className="card">
              <div className="card-head">
                <div>
                  <h2>Red mesh DC</h2>
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
