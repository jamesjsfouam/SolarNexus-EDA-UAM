# SolarNexus backend integration contract

Shared contract for the backend, frontend and statistics workstreams.

## Responsibilities

- Backend (branch C.santana): persistence, validation, REST API and dispatch orchestration.
- Statistics component: fit and validate the econometric model; produce demand forecasts and calibrated confidence probability per interval.
- Frontend: consume the REST API and display telemetry, forecasts and dispatch results.

The backend does not refit the econometric model. It accepts statistical output through the forecast-ingestion endpoint, so the statistics teammate owns that logic.

## Run locally

~~~bash
python -m venv .venv
# Windows PowerShell: .venv/Scripts/Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install -e ".[dev]"
uvicorn solarnexus.api.main:app --reload
~~~

The default database is SQLite at ./solarnexus.db. For PostgreSQL, set SOLARNEXUS_DATABASE_URL, for example:

~~~text
postgresql+psycopg://solarnexus:solarnexus@localhost:5432/solarnexus
~~~

Interactive API documentation: http://localhost:8000/docs. On startup, the application applies pending Alembic migrations.

## Endpoints

All business endpoints are prefixed with /api/v1.

| Method | Path | Purpose |
|---|---|---|
| GET | /health | API and database health |
| GET | /dashboard/summary | Aggregated KPIs for the frontend dashboard |
| GET | /campus | Get campus configuration |
| PUT | /campus | Update campus configuration |
| POST | /measurements/batch | Ingest 1–1000 telemetry records |
| GET | /measurements | Query historical telemetry (start, end, limit, offset) |
| GET | /measurements/latest | Latest telemetry record |
| POST | /forecasts | Store statistical forecast output |
| GET | /forecasts/latest | Latest forecast run |
| GET | /forecasts/{id} | Retrieve one forecast run |
| POST | /dispatch/plan | Calculate and persist a dispatch plan |
| GET | /dispatch/{id} | Retrieve a dispatch plan |
| GET | /dispatch/latest | Retrieve the most recent dispatch plan |
| POST | /mesh/solve | Solve the DC mesh optimization model |

## Contract for the statistics teammate

After the statistical model has generated a forecast horizon, send it to POST /api/v1/forecasts:

~~~json
{
  "model_name": "ASHRAE-3P-log-linear",
  "model_version": "0.1.0",
  "source": "statistics-service",
  "notes": "Training window and validation notes",
  "points": [
    {
      "interval_start": "2026-11-27T14:00:00-06:00",
      "demand_kwh": 420.5,
      "pv_generation_kwh": 180.0,
      "probability_within_margin": 0.97
    },
    {
      "interval_start": "2026-11-27T15:00:00-06:00",
      "demand_kwh": 455.2,
      "pv_generation_kwh": 150.0,
      "probability_within_margin": 0.96
    }
  ]
}
~~~

Field meanings:

- demand_kwh: point forecast of consumption for the interval, in kWh.
- pv_generation_kwh: expected photovoltaic energy for the same interval, in kWh.
- probability_within_margin: calibrated probability in [0, 1] that the forecast error falls inside the agreed tolerance. This is not R² or a generic confidence score.
- interval_start: ISO-8601 timestamp with an explicit timezone offset.

The endpoint accepts 1–168 ordered, unique intervals. Dispatch currently requires hourly, consecutive timestamps aligned to the top of the hour. Use one consistent timezone throughout a forecast.

## Contract for the frontend teammate

1. Call GET /api/v1/health to check service availability.
2. Call GET /api/v1/campus to display the campus name and timezone.
3. Read telemetry from GET /api/v1/measurements and /measurements/latest.
4. Read the latest forecast from GET /api/v1/forecasts/latest.
5. Submit a dispatch request to POST /api/v1/dispatch/plan and display the returned points.

Example dispatch request:

~~~json
{
  "forecast_run_id": 1,
  "battery": {
    "capacity_kwh": 1500,
    "power_kw": 300,
    "initial_soc_kwh": 500,
    "min_soc_kwh": 100,
    "charge_efficiency": 0.95,
    "peak_start_hour": 14,
    "peak_end_hour": 17,
    "alpha": 0.05,
    "delta": 0.10
  }
}
~~~

## Telemetry payload

POST /api/v1/measurements/batch receives:

~~~json
{
  "records": [
    {
      "interval_start": "2026-11-27T14:00:00-06:00",
      "temperature_c": 33.2,
      "humidity_pct": 68.0,
      "activity_index": 0.82,
      "conditioned_area_m2": 7600,
      "consumption_kwh": 420.5,
      "pv_generation_kwh": 180.0,
      "source": "campus-meter"
    }
  ]
}
~~~

Humidity is expressed as a percentage in the API contract. The statistics component must convert it to the units required by its model. activity_index may be zero for an inactive campus; the statistical implementation must decide how to handle zero before applying logarithms.

## Operational notes and limitations

- SQLite is the local default; PostgreSQL is supported with SOLARNEXUS_DATABASE_URL.
- Alembic migrations are applied at application startup. Create and commit a new revision whenever the SQLAlchemy schema changes.
- Optional shared API-key authentication is supported with SOLARNEXUS_API_KEY. Production mode requires a key of at least 32 characters. This is service-level protection, not per-user authorization; keep the API behind a trusted gateway and do not embed a shared key in a public browser bundle.
- CORS origins are configurable through SOLARNEXUS_CORS_ORIGINS.
- Dispatch reuses the existing hourly simulation controller. It is not a command channel to batteries, inverters, breakers or SCADA.
- Battery behavior currently models charge efficiency but not discharge efficiency, degradation, thermal limits, tariffs or electrical protection. Do not use results to control physical equipment.
- Use synthetic data until the university authorizes access to real telemetry.


## DC mesh optimization

POST /api/v1/mesh/solve accepts a set of directed nodes and links, then returns optimized link flows, closed switches, central supply, curtailed energy and conditional nodal shadow prices. Example:

~~~json
{
  "nodes": [
    {"name": "Copernico", "generation_kwh": 120, "demand_kwh": 40},
    {"name": "Pabellon-C", "generation_kwh": 10, "demand_kwh": 90}
  ],
  "links": [
    {"origin": "Copernico", "destination": "Pabellon-C", "capacity_kwh": 60,
     "transfer_cost_per_kwh": 0.02, "loss_fraction": 0.03, "switch_cost": 0}
  ],
  "central_cycling_cost_per_kwh": 0.12
}
~~~

The resulting shadow prices are duals of the linear program after fixing the MILP switch decisions. They are conditional prices, not global dual values of the original mixed-integer problem.


## Security

- Set SOLARNEXUS_API_KEY to require the X-API-Key header on all /api/v1 endpoints except /health. An empty key keeps local development friction-free.
- Set SOLARNEXUS_ENV=production to make the API refuse startup unless the key contains at least 32 characters.
- Do not embed a shared API key in a public browser bundle. For a public SPA, put the API behind a same-origin backend/proxy or implement per-user authentication and authorization.
- Configure explicit allowed browser origins through SOLARNEXUS_CORS_ORIGINS.

## Database migrations

Alembic is configured in alembic.ini, with the initial schema in migrations/versions. The API applies pending migrations at startup. To inspect the current version or apply migrations manually:

~~~bash
alembic current
alembic upgrade head
~~~

Create future revisions after changing SQLAlchemy models:

~~~bash
alembic revision --autogenerate -m "describe schema change"
alembic upgrade head
~~~

## Dashboard summary

GET /api/v1/dashboard/summary returns campus name/timezone, measurement count and latest measurement, totals for the latest forecast, and totals for the latest dispatch. Missing forecast/dispatch data is represented with null IDs and zero counts rather than fabricated values.


## Frontend integration details

The React dashboard lives in `frontend/` and consumes the same `/api/v1`
routes listed above. Dispatch responses also include the saved battery peak
window (`peak_start_hour`, `peak_end_hour`) and forecast-risk parameters
(`alpha`, `delta`) so the dashboard can restore the settings used by the
last saved dispatch.

For local development, Vite proxies `/api` to the backend. An optional
`SOLARNEXUS_API_KEY` can be supplied to the Vite development server; the proxy
adds it server-side as `X-API-Key`. Do not use a `VITE_*` variable for this
secret. Production deployments must use a trusted same-origin reverse proxy or
gateway and must not expose a shared service key in browser JavaScript.
