# SolarNexus · Dashboard (frontend)

Dashboard de monitoreo en React + Vite que consume la API REST del backend
(`src/solarnexus/api`, contrato en `docs/API_CONTRACT.md`).

## Puesta en marcha

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173
```

Para ver datos reales, levanta la API desde la raíz del repo (necesita `alembic.ini` en el directorio actual):

```bash
python -m pip install -e ".[dev]"
uvicorn solarnexus.api.main:app --reload    # http://localhost:8000/docs
```

Si la API no responde, el dashboard muestra **datos de ejemplo** con el mismo formato (`src/mock.js`)
y lo indica en la cabecera. Si la API responde pero no tiene datos, ofrece cargar un pronóstico de
demostración (`POST /measurements/batch` + `POST /forecasts` + `POST /dispatch/plan`).

## Configuración

| Variable | Por defecto | Uso |
| :--- | :--- | :--- |
| `VITE_API_URL` | `http://localhost:8000/api/v1` | URL base de la API |

Si usas otro puerto para Vite, agrégalo a `SOLARNEXUS_CORS_ORIGINS` en el backend.
No se soporta `SOLARNEXUS_API_KEY`: el contrato pide no incrustar esa clave en el navegador.

## Estructura

| Archivo | Contenido |
| :--- | :--- |
| `src/api.js` | Cliente de la API, batería y red mesh por defecto |
| `src/mock.js` | Datos de ejemplo; replica las reglas de `despacho.py` |
| `src/formato.js` | Horas en la zona del campus, números y nombres de los regímenes |
| `src/components/Graficos.jsx` | Pronóstico, despacho por hora, batería y mediciones (Recharts) |
| `src/components/RedMesh.jsx` | Diagrama y tabla de la red mesh DC |
| `src/App.jsx` | Página: tarjetas, gráficos, formulario de batería e íconos (`lucide-react`) |
