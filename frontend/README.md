# SolarNexus · Dashboard frontend

Dashboard React + Vite que consume la API REST descrita en `docs/API_CONTRACT.md`.

## Puesta en marcha

Desde la carpeta `frontend/`:

```bash
cp .env.example .env        # Windows: Copy-Item .env.example .env
npm install
npm run dev                 # http://localhost:5173
```

Desde la raíz del repositorio, levanta la API en otra terminal:

```bash
python -m pip install -e ".[dev]"
uvicorn solarnexus.api.main:app --reload
```

El frontend usa por defecto `/api/v1` y Vite reenvía esas peticiones a
`http://127.0.0.1:8000`. Así el desarrollo local no depende de CORS ni de
que el navegador conozca la dirección interna del backend.

## Configuración y seguridad

- `VITE_API_URL`: URL base consumida por el navegador. Déjala en `/api/v1`
  para utilizar el proxy de desarrollo.
- `SOLARNEXUS_API_PROXY_TARGET`: dirección del backend a la que Vite reenvía
  las peticiones. Usa la IP o hostname correcto si la API está en otro equipo.
- `SOLARNEXUS_API_KEY`: opcional; Vite la lee solo en el servidor de desarrollo
  y añade `X-API-Key` al reenviar las peticiones. No la escribas con prefijo
  `VITE_` ni la incluyas en el bundle del navegador.

El proxy de Vite solo sirve para desarrollo. En producción utiliza un reverse
proxy/backend del mismo origen que proteja la clave compartida. Si se define
una URL absoluta en `VITE_API_URL`, las peticiones salen directamente desde
el navegador y el proxy local no se utiliza.

Si la API no responde, el dashboard presenta datos de ejemplo. Si el backend
responde pero aún no tiene un pronóstico, permite cargar uno de demostración.
Si ya existe un pronóstico sin despacho, calcula el despacho sobre ese mismo
pronóstico sin duplicarlo.

## Comandos

```bash
npm run dev
npm run lint
npm run build
npm run preview
```

## Estructura

| Archivo | Contenido |
| --- | --- |
| `src/api.js` | Cliente HTTP, manejo de errores, batería y red Mesh |
| `src/mock.js` | Datos sintéticos para modo sin API |
| `src/formato.js` | Formato de horas, números y regímenes |
| `src/components/Graficos.jsx` | Gráficos horarios de demanda, despacho y batería |
| `src/components/RedMesh.jsx` | Diagrama y tabla de red Mesh DC |
| `src/App.jsx` | Panel principal y formulario de batería |
| `vite.config.js` | Proxy local para API y encabezado de servicio opcional |


## Clima

El dashboard consulta `GET /api/v1/weather` a través del proxy de Vite. No se
necesita una clave de Open-Meteo. Si el servicio meteorológico no responde,
el resto del dashboard sigue disponible y muestra un aviso no bloqueante.
