import { useEffect, useState } from 'react'
import { Monitor, Moon, Sun } from 'lucide-react'

const CLAVE = 'solarnexus-tema'
const OPCIONES = [
  { valor: 'system', nombre: 'Sistema', Icono: Monitor },
  { valor: 'light', nombre: 'Claro', Icono: Sun },
  { valor: 'dark', nombre: 'Oscuro', Icono: Moon },
]

function leer() {
  try {
    const t = localStorage.getItem(CLAVE)
    return t === 'light' || t === 'dark' ? t : 'system'
  } catch {
    return 'system'
  }
}

/** Selector de tema: sigue al sistema o fuerza claro/oscuro; la elección se recuerda en el navegador. */
export default function SelectorTema() {
  const [tema, setTema] = useState(leer)

  useEffect(() => {
    const raiz = document.documentElement
    if (tema === 'system') delete raiz.dataset.theme
    else raiz.dataset.theme = tema
    try {
      if (tema === 'system') localStorage.removeItem(CLAVE)
      else localStorage.setItem(CLAVE, tema)
    } catch { /* sin localStorage la elección dura solo esta visita */ }
  }, [tema])

  return (
    <div className="selector-tema" role="radiogroup" aria-label="Tema de color">
      {OPCIONES.map(({ valor, nombre, Icono }) => (
        <button key={valor} type="button" role="radio" aria-checked={tema === valor} title={`Tema: ${nombre}`}
          className={tema === valor ? 'activo' : ''} onClick={() => setTema(valor)}>
          <Icono size={16} aria-hidden="true" />
          <span className="solo-lectores">{nombre}</span>
        </button>
      ))}
    </div>
  )
}
