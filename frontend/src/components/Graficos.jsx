import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Line, LineChart, ReferenceArea,
  ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { kwh, pct, REGIMENES } from '../formato.js'

const EJE = { stroke: 'var(--text-2)', fontSize: 12 }
const ejeX = {
  dataKey: 'hora', type: 'number', domain: [-0.5, 23.5], ticks: [0, 3, 6, 9, 12, 15, 18, 21],
  tickFormatter: (h) => `${h}h`, tick: EJE, axisLine: { stroke: 'var(--grid)' }, tickLine: false,
}
const ejeY = { tick: EJE, axisLine: false, tickLine: false, width: 52, tickFormatter: kwh }
const grid = <CartesianGrid stroke="var(--grid)" vertical={false} />

function Leyenda({ items }) {
  return (
    <ul className="legend">
      {items.map((it) => (
        <li key={it.nombre}>
          <span className={`sw ${it.tipo ?? ''}`} style={{ background: it.color }} />
          {it.nombre}
        </li>
      ))}
    </ul>
  )
}

function CajaTooltip({ active, payload, filas }) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div className="tooltip">
      <div className="t-title">{d.hora}:00 – {d.hora + 1}:00</div>
      {filas.map((f) => (
        <div className="t-row" key={f.nombre}>
          <span>{f.color && <i className="sw" style={{ background: f.color }} />}{f.nombre}</span>
          <span>{f.valor(d)}</span>
        </div>
      ))}
    </div>
  )
}

const franjaPico = (pico) => (
  <ReferenceArea x1={pico.inicio - 0.5} x2={pico.fin - 0.5} fill="var(--peak)" stroke="none" ifOverflow="extendDomain" />
)

/** Demanda prevista vs. generación solar, con la franja pico marcada. */
export function GraficoPronostico({ datos, pico }) {
  return (
    <>
      <Leyenda items={[
        { nombre: 'Demanda prevista', color: 'var(--s-demanda)', tipo: 'line' },
        { nombre: 'Generación solar', color: 'var(--s-solar)', tipo: 'line' },
        { nombre: `Franja pico ${pico.inicio}–${pico.fin} h`, tipo: 'peak' },
      ]} />
      <ResponsiveContainer width="100%" height={260}>
        <LineChart data={datos} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
          {grid}
          {franjaPico(pico)}
          <XAxis {...ejeX} />
          <YAxis {...ejeY} unit="" />
          <Tooltip cursor={{ stroke: 'var(--text-2)', strokeDasharray: '3 3' }} content={
            <CajaTooltip filas={[
              { nombre: 'Demanda', color: 'var(--s-demanda)', valor: (d) => `${kwh(d.demanda)} kWh` },
              { nombre: 'Solar', color: 'var(--s-solar)', valor: (d) => `${kwh(d.pv)} kWh` },
              { nombre: 'Prob. en margen', valor: (d) => pct(d.prob) },
            ]} />
          } />
          <Line dataKey="demanda" stroke="var(--s-demanda)" strokeWidth={2} dot={false} activeDot={{ r: 4 }} isAnimationActive={false} />
          <Line dataKey="pv" stroke="var(--s-solar)" strokeWidth={2} dot={false} activeDot={{ r: 4 }} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </>
  )
}

/** De dónde sale la energía que consume el campus cada hora (suma = demanda). */
export function GraficoDespacho({ datos, pico }) {
  return (
    <>
      <Leyenda items={[
        { nombre: 'Solar directa', color: 'var(--s-solar)' },
        { nombre: 'Batería', color: 'var(--s-bateria)' },
        { nombre: 'Compra a la red', color: 'var(--s-red)' },
      ]} />
      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={datos} margin={{ top: 8, right: 12, bottom: 0, left: 0 }} barCategoryGap={2}>
          {grid}
          {franjaPico(pico)}
          <XAxis {...ejeX} />
          <YAxis {...ejeY} />
          <Tooltip cursor={{ fill: 'var(--grid)', opacity: 0.5 }} content={
            <CajaTooltip filas={[
              { nombre: 'Modo', valor: (d) => REGIMENES[d.regimen]?.nombre ?? d.regimen },
              { nombre: 'Solar directa', color: 'var(--s-solar)', valor: (d) => `${kwh(d.solar)} kWh` },
              { nombre: 'Batería', color: 'var(--s-bateria)', valor: (d) => `${kwh(d.descarga)} kWh` },
              { nombre: 'Red', color: 'var(--s-red)', valor: (d) => `${kwh(d.red)} kWh` },
              { nombre: 'Carga batería', valor: (d) => `${kwh(d.carga)} kWh` },
              { nombre: 'Exportación', valor: (d) => `${kwh(d.exporta)} kWh` },
            ]} />
          } />
          <Bar dataKey="solar" stackId="s" fill="var(--s-solar)" stroke="var(--surface)" strokeWidth={1} isAnimationActive={false} />
          <Bar dataKey="descarga" stackId="s" fill="var(--s-bateria)" stroke="var(--surface)" strokeWidth={1} isAnimationActive={false} />
          <Bar dataKey="red" stackId="s" fill="var(--s-red)" stroke="var(--surface)" strokeWidth={1} radius={[4, 4, 0, 0]} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
      <div className="regimen-strip" aria-label="Modo de operación por hora">
        {datos.map((d) => (
          <div key={d.hora} className={d.regimen !== 'autoconsumo' ? 'activo' : ''} title={`${d.hora}h · ${REGIMENES[d.regimen]?.nombre ?? d.regimen}`}>
            {REGIMENES[d.regimen]?.letra ?? '?'}
          </div>
        ))}
      </div>
      <div className="regimen-leyenda">
        {Object.values(REGIMENES).map((r) => `${r.letra} = ${r.nombre}`).join(' · ')}
      </div>
    </>
  )
}

/** Energía guardada en la batería al final de cada hora. */
export function GraficoBateria({ datos, capacidad, minimo, pico }) {
  return (
    <ResponsiveContainer width="100%" height={200}>
      <AreaChart data={datos} margin={{ top: 16, right: 12, bottom: 0, left: 0 }}>
        {grid}
        {franjaPico(pico)}
        <XAxis {...ejeX} />
        <YAxis {...ejeY} domain={[0, capacidad]} />
        <ReferenceLine y={capacidad} stroke="var(--text-2)" strokeDasharray="4 4"
          label={{ value: `Capacidad ${kwh(capacidad)} kWh`, position: 'insideTopRight', fill: 'var(--text-2)', fontSize: 11 }} />
        {minimo > 0 && (
          <ReferenceLine y={minimo} stroke="var(--text-2)" strokeDasharray="2 4"
            label={{ value: 'Reserva mínima', position: 'insideBottomRight', fill: 'var(--text-2)', fontSize: 11 }} />
        )}
        <Tooltip cursor={{ stroke: 'var(--text-2)', strokeDasharray: '3 3' }} content={
          <CajaTooltip filas={[
            { nombre: 'Energía guardada', color: 'var(--s-bateria)', valor: (d) => `${kwh(d.soc)} kWh` },
            { nombre: 'Nivel', valor: (d) => pct(d.soc / capacidad) },
          ]} />
        } />
        <Area dataKey="soc" type="stepAfter" stroke="var(--s-bateria)" strokeWidth={2} fill="var(--s-bateria)" fillOpacity={0.15} isAnimationActive={false} />
      </AreaChart>
    </ResponsiveContainer>
  )
}
