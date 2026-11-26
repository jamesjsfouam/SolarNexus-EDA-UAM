import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Line, LineChart, ReferenceArea,
  ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { GLOSARIO, kwh, pct, REGIMENES } from '../formato.js'
import Ayuda from './Ayuda.jsx'
import { Tramos } from './DiaCampus.jsx'

const EJE = { stroke: 'var(--text-2)', fontSize: 12 }
// El eje X usa la posición del intervalo (slot), no la hora: así un horizonte que cruza la
// medianoche o que no empieza a las 0 h se dibuja en orden.
const ejeX = (datos) => ({
  dataKey: 'slot', type: 'number', domain: [-0.5, 23.5], ticks: [0, 3, 6, 9, 12, 15, 18, 21],
  tickFormatter: (slot) => {
    const h = datos[Math.round(slot)]?.hora
    return h === undefined ? '' : `${h}h`
  },
  tick: EJE, axisLine: { stroke: 'var(--grid)' }, tickLine: false,
})
const ejeY = { tick: EJE, axisLine: false, tickLine: false, width: 52, tickFormatter: kwh }
const grid = <CartesianGrid stroke="var(--grid)" vertical={false} />

function Leyenda({ items }) {
  return (
    <ul className="legend">
      {items.map((it) => (
        <li key={it.nombre}>
          <span className={`sw ${it.tipo ?? ''}`} style={{ background: it.color }} />
          {it.nombre}
          {it.ayuda && <Ayuda texto={it.ayuda} etiqueta={`Qué es: ${it.nombre}`} />}
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
      <div className="t-title">{d.horaLabel} – {d.horaSiguienteLabel}</div>
      {filas.map((f) => (
        <div className="t-row" key={f.nombre}>
          <span>{f.color && <i className="sw" style={{ background: f.color }} />}{f.nombre}</span>
          <span>{f.valor(d)}</span>
        </div>
      ))}
    </div>
  )
}

// Una banda por hora de la franja pico (puede no ser contigua si el horizonte cruza la medianoche).
const franjasPico = (datos, pico) => datos
  .filter((d) => d.hora >= pico.inicio && d.hora < pico.fin)
  .map((d) => (
    <ReferenceArea key={`pico-${d.slot}`} x1={d.slot - 0.5} x2={d.slot + 0.5}
      fill="var(--peak)" stroke="none" ifOverflow="extendDomain" />
  ))

const leyendaPico = (pico) => ({
  nombre: `Franja pico ${pico.inicio}–${pico.fin} h`, tipo: 'peak', ayuda: GLOSARIO.franjaPico,
})

/** Demanda prevista vs. generación solar, con la franja pico marcada. */
export function GraficoPronostico({ datos, pico }) {
  return (
    <>
      <Leyenda items={[
        { nombre: 'Demanda prevista', color: 'var(--s-demanda)', tipo: 'line' },
        { nombre: 'Generación solar', color: 'var(--s-solar)', tipo: 'line' },
        leyendaPico(pico),
      ]} />
      <ResponsiveContainer width="100%" height={260}>
        <LineChart data={datos} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
          {grid}
          {franjasPico(datos, pico)}
          <XAxis {...ejeX(datos)} />
          <YAxis {...ejeY} />
          <Tooltip cursor={{ stroke: 'var(--text-2)', strokeDasharray: '3 3' }} content={
            <CajaTooltip filas={[
              { nombre: 'Demanda', color: 'var(--s-demanda)', valor: (d) => `${kwh(d.demanda)} kWh` },
              { nombre: 'Solar', color: 'var(--s-solar)', valor: (d) => `${kwh(d.pv)} kWh` },
              { nombre: 'Prob. dentro del margen', valor: (d) => pct(d.prob) },
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
        { nombre: 'Batería', color: 'var(--s-bateria)', ayuda: GLOSARIO.peakShaving },
        { nombre: 'Compra a la red', color: 'var(--s-red)', ayuda: GLOSARIO.sin },
        leyendaPico(pico),
      ]} />
      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={datos} margin={{ top: 8, right: 12, bottom: 0, left: 0 }} barCategoryGap={2}>
          {grid}
          {franjasPico(datos, pico)}
          <XAxis {...ejeX(datos)} />
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
      <Tramos datos={datos} className="tramos-alineados" />
    </>
  )
}

/** Energía guardada en la batería al final de cada hora. */
export function GraficoBateria({ datos, capacidad, minimo, pico }) {
  return (
    <ResponsiveContainer width="100%" height={200}>
      <AreaChart data={datos} margin={{ top: 16, right: 12, bottom: 0, left: 0 }}>
        {grid}
        {franjasPico(datos, pico)}
        <XAxis {...ejeX(datos)} />
        <YAxis {...ejeY} domain={[0, capacidad]} />
        <ReferenceLine y={capacidad} stroke="var(--text-2)" strokeDasharray="4 4"
          label={{ value: `Capacidad ${kwh(capacidad)} kWh`, position: 'insideTopRight', fill: 'var(--text-2)', fontSize: 11 }} />
        {minimo > 0 && (
          <ReferenceLine y={minimo} stroke="var(--text-2)" strokeDasharray="2 4"
            label={{ value: `Reserva mínima ${kwh(minimo)} kWh`, position: 'insideTopLeft', fill: 'var(--text-2)', fontSize: 11 }} />
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

const ejeTiempo = {
  dataKey: 'i', type: 'number', domain: ['dataMin', 'dataMax'], tick: EJE,
  axisLine: { stroke: 'var(--grid)' }, tickLine: false,
}

function TooltipMedicion({ active, payload, filas }) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div className="tooltip">
      <div className="t-title">{d.etiqueta}</div>
      {filas.map((f) => (
        <div className="t-row" key={f.nombre}>
          <span>{f.color && <i className="sw" style={{ background: f.color }} />}{f.nombre}</span>
          <span>{f.valor(d)}</span>
        </div>
      ))}
    </div>
  )
}

/** Consumo y generación solar medidos (kWh por hora). */
export function GraficoMedicionesEnergia({ datos }) {
  const etiqueta = (i) => datos.find((d) => d.i === i)?.corta ?? ''
  return (
    <>
      <Leyenda items={[
        { nombre: 'Consumo medido', color: 'var(--s-demanda)', tipo: 'line' },
        { nombre: 'Solar medida', color: 'var(--s-solar)', tipo: 'line' },
      ]} />
      <ResponsiveContainer width="100%" height={200}>
        <LineChart data={datos} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
          {grid}
          <XAxis {...ejeTiempo} ticks={datos.filter((d) => d.hora % 6 === 0).map((d) => d.i)} tickFormatter={etiqueta} />
          <YAxis {...ejeY} />
          <Tooltip cursor={{ stroke: 'var(--text-2)', strokeDasharray: '3 3' }} content={
            <TooltipMedicion filas={[
              { nombre: 'Consumo', color: 'var(--s-demanda)', valor: (d) => `${kwh(d.consumo)} kWh` },
              { nombre: 'Solar', color: 'var(--s-solar)', valor: (d) => `${kwh(d.pv)} kWh` },
            ]} />
          } />
          <Line dataKey="consumo" stroke="var(--s-demanda)" strokeWidth={2} dot={false} activeDot={{ r: 4 }} isAnimationActive={false} connectNulls />
          <Line dataKey="pv" stroke="var(--s-solar)" strokeWidth={2} dot={false} activeDot={{ r: 4 }} isAnimationActive={false} connectNulls />
        </LineChart>
      </ResponsiveContainer>
    </>
  )
}

/** Temperatura medida (°C); va aparte del consumo para no mezclar escalas. */
export function GraficoTemperatura({ datos }) {
  const etiqueta = (i) => datos.find((d) => d.i === i)?.corta ?? ''
  return (
    <ResponsiveContainer width="100%" height={200}>
      <LineChart data={datos} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
        {grid}
        <XAxis {...ejeTiempo} ticks={datos.filter((d) => d.hora % 6 === 0).map((d) => d.i)} tickFormatter={etiqueta} />
        <YAxis {...ejeY} tickFormatter={(v) => `${v}°`} domain={['dataMin - 2', 'dataMax + 2']} allowDecimals={false} />
        <Tooltip cursor={{ stroke: 'var(--text-2)', strokeDasharray: '3 3' }} content={
          <TooltipMedicion filas={[
            { nombre: 'Temperatura', color: 'var(--accent)', valor: (d) => `${d.temp.toFixed(1)} °C` },
            { nombre: 'Humedad', valor: (d) => `${Math.round(d.hum)} %` },
          ]} />
        } />
        <Line dataKey="temp" stroke="var(--accent)" strokeWidth={2} dot={false} activeDot={{ r: 4 }} isAnimationActive={false} />
      </LineChart>
    </ResponsiveContainer>
  )
}
