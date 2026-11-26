import { useId, useState } from 'react'
import { Info } from 'lucide-react'

/**
 * Ícono de ayuda con una explicación corta. Se abre al pasar el mouse, con el foco del teclado
 * o tocándolo (celular); Escape lo cierra.
 */
export default function Ayuda({ texto, etiqueta = 'Más información' }) {
  const [abierta, setAbierta] = useState(false)
  const id = useId()
  return (
    <span className={`ayuda ${abierta ? 'abierta' : ''}`} onMouseLeave={() => setAbierta(false)}>
      <button type="button" className="ayuda-boton" aria-label={etiqueta} aria-describedby={id}
        aria-expanded={abierta} onClick={() => setAbierta(!abierta)} onBlur={() => setAbierta(false)}
        onKeyDown={(e) => { if (e.key === 'Escape') setAbierta(false) }}>
        <Info size={14} aria-hidden="true" />
      </button>
      <span role="tooltip" id={id} className="ayuda-texto">{texto}</span>
    </span>
  )
}
