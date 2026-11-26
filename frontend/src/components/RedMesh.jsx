import { kwh, num1, usd } from '../formato.js'

const W = 520
const H = 300
const R = 46

// Nodos repartidos en un círculo; con coordenadas reales del campus se reemplaza esta función.
function posiciones(nombres) {
  const n = nombres.length
  return Object.fromEntries(nombres.map((nombre, i) => {
    const ang = -Math.PI / 2 + (2 * Math.PI * i) / n
    return [nombre, { x: W / 2 + Math.cos(ang) * (W / 2 - 90), y: H / 2 + 14 + Math.sin(ang) * (H / 2 - 64) }]
  }))
}

/** Red mesh DC: edificios, enlaces DC con su flujo y precio sombra de cada nodo. */
export default function RedMesh({ red, resultado }) {
  const pos = posiciones(red.nodes.map((n) => n.name))
  const flujo = Object.fromEntries(resultado.flows.map((f) => [`${f.origin}→${f.destination}`, f.energy_kwh]))
  const cerrado = new Set(resultado.switches_closed.map((s) => `${s.origin}→${s.destination}`))

  return (
    <>
      <svg className="mesh-svg" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Diagrama de la red mesh DC">
        <defs>
          <marker id="flecha" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M0,0 L10,5 L0,10 z" fill="var(--s-solar)" />
          </marker>
        </defs>
        {red.links.map((l) => {
          const a = pos[l.origin]
          const b = pos[l.destination]
          const dx = b.x - a.x
          const dy = b.y - a.y
          const len = Math.hypot(dx, dy)
          const [ux, uy] = [dx / len, dy / len]
          const clave = `${l.origin}→${l.destination}`
          const activo = cerrado.has(clave)
          return (
            <g key={clave}>
              <line className={`enlace ${activo ? '' : 'abierto'}`} markerEnd={activo ? 'url(#flecha)' : undefined}
                x1={a.x + ux * R} y1={a.y + uy * R} x2={b.x - ux * (R + 4)} y2={b.y - uy * (R + 4)} />
              <text className="enlace-dato" x={(a.x + b.x) / 2} y={(a.y + b.y) / 2 - 6} textAnchor="middle">
                {activo ? `${num1(flujo[clave] ?? 0)} kWh` : 'abierto'}
              </text>
            </g>
          )
        })}
        {red.nodes.map((n) => {
          const p = pos[n.name]
          return (
            <g key={n.name}>
              <circle className="nodo" cx={p.x} cy={p.y} r={R} />
              <text className="nodo-nombre" x={p.x} y={p.y - 6} textAnchor="middle">{n.name}</text>
              <text className="nodo-dato" x={p.x} y={p.y + 10} textAnchor="middle">λ {usd(resultado.shadow_prices[n.name] ?? 0)}</text>
              <text className="nodo-dato" x={p.x} y={p.y + 24} textAnchor="middle">{kwh(n.generation_kwh)}↑ {kwh(n.demand_kwh)}↓</text>
            </g>
          )
        })}
      </svg>
      <div className="tabla-scroll">
        <table>
          <thead>
            <tr>
              <th>Edificio</th><th>Genera (kWh)</th><th>Consume (kWh)</th>
              <th>Desde inversor central (kWh)</th><th>Precio sombra λ (USD/kWh)</th>
            </tr>
          </thead>
          <tbody>
            {red.nodes.map((n) => (
              <tr key={n.name}>
                <td>{n.name}</td>
                <td>{kwh(n.generation_kwh)}</td>
                <td>{kwh(n.demand_kwh)}</td>
                <td>{num1(resultado.central_supply_kwh[n.name] ?? 0)}</td>
                <td>{usd(resultado.shadow_prices[n.name] ?? 0)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}
