from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from solarnexus.api import main as main_module
from solarnexus.api.database import Base, get_db

@pytest.fixture()
def client(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()
    monkeypatch.setattr(main_module, "init_db", lambda: None)
    main_module.app.dependency_overrides[get_db] = override_get_db
    with TestClient(main_module.app) as test_client:
        yield test_client
    main_module.app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()

def test_health_and_default_campus(client):
    health = client.get("/api/v1/health")
    assert health.status_code == 200
    assert health.json()["database"] == "connected"
    campus = client.get("/api/v1/campus")
    assert campus.status_code == 200
    assert campus.json()["timezone"] == "America/Managua"

def test_measurement_ingestion_and_latest(client):
    stamp = datetime(2026, 11, 27, 14, tzinfo=timezone(timedelta(hours=-6))).isoformat()
    payload = {"records": [{"interval_start": stamp, "temperature_c": 33.2, "humidity_pct": 68,
        "activity_index": 0.82, "conditioned_area_m2": 7600, "consumption_kwh": 420.5,
        "pv_generation_kwh": 180, "source": "test-meter"}]}
    response = client.post("/api/v1/measurements/batch", json=payload)
    assert response.status_code == 201
    assert response.json()[0]["consumption_kwh"] == 420.5
    assert response.json()[0]["interval_start"].endswith("Z")
    assert client.get("/api/v1/measurements/latest").status_code == 200

def test_duplicate_measurement_returns_conflict(client):
    record = {"interval_start": "2026-11-27T14:00:00-06:00", "temperature_c": 30,
        "humidity_pct": 60, "activity_index": 0.5, "conditioned_area_m2": 1000}
    assert client.post("/api/v1/measurements/batch", json={"records": [record]}).status_code == 201
    assert client.post("/api/v1/measurements/batch", json={"records": [record]}).status_code == 409

def test_statistics_forecast_then_dispatch(client):
    start = datetime(2026, 11, 27, 13, tzinfo=timezone(timedelta(hours=-6)))
    forecast = {"model_name": "test-model", "model_version": "test-1", "points": [
        {"interval_start": (start + timedelta(hours=i)).isoformat(), "demand_kwh": demand,
         "pv_generation_kwh": pv, "probability_within_margin": 0.99}
        for i, (demand, pv) in enumerate([(150, 300), (150, 300), (450, 200), (450, 200)])]}
    created = client.post("/api/v1/forecasts", json=forecast)
    assert created.status_code == 201
    plan = client.post("/api/v1/dispatch/plan", json={
        "forecast_run_id": created.json()["id"],
        "battery": {"capacity_kwh": 500, "power_kw": 150, "initial_soc_kwh": 100,
            "min_soc_kwh": 50, "charge_efficiency": 1, "peak_start_hour": 14, "peak_end_hour": 17}})
    assert plan.status_code == 201, plan.text
    result = plan.json()
    assert len(result["points"]) == 4
    assert result["points"][2]["regime"] == "peak_shaving"
    assert result["peak_start_hour"] == 14
    assert result["peak_end_hour"] == 17
    assert result["alpha"] == pytest.approx(0.05)
    assert result["delta"] == pytest.approx(0.10)
    assert client.get(f"/api/v1/dispatch/{result['id']}").status_code == 200
    assert client.get("/api/v1/dispatch/latest").json()["id"] == result["id"]

def test_forecast_requires_timezone(client):
    response = client.post("/api/v1/forecasts", json={"model_name": "test", "model_version": "1", "points": [{
        "interval_start": "2026-11-27T14:00:00", "demand_kwh": 100,
        "pv_generation_kwh": 50, "probability_within_margin": 0.9}]})
    assert response.status_code == 422


def test_mesh_solver_endpoint(client):
    response = client.post("/api/v1/mesh/solve", json={
        "nodes": [
            {"name": "A", "generation_kwh": 100, "demand_kwh": 20},
            {"name": "B", "generation_kwh": 0, "demand_kwh": 50},
        ],
        "links": [{
            "origin": "A", "destination": "B", "capacity_kwh": 100,
            "transfer_cost_per_kwh": 0.02, "loss_fraction": 0, "switch_cost": 0,
        }],
        "central_cycling_cost_per_kwh": 0.12,
    })
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["flows"][0]["energy_kwh"] == pytest.approx(50)
    assert result["switches_closed"] == [{"origin": "A", "destination": "B"}]

def test_invalid_campus_timezone_is_rejected(client):
    response = client.put("/api/v1/campus", json={
        "campus_name": "UAM", "timezone": "Not/A_Real_Zone"
    })
    assert response.status_code == 422


def test_dashboard_summary_handles_empty_database(client):
    response = client.get("/api/v1/dashboard/summary")
    assert response.status_code == 200
    result = response.json()
    assert result["campus_name"] == "Universidad Americana (UAM)"
    assert result["measurement_count"] == 0
    assert result["forecast_run_id"] is None
    assert result["dispatch_run_id"] is None

def test_dashboard_summary_aggregates_forecast_and_dispatch(client):
    start = datetime(2026, 11, 27, 13, tzinfo=timezone(timedelta(hours=-6)))
    forecast = {"model_name": "dashboard-test", "model_version": "1", "points": [
        {"interval_start": (start + timedelta(hours=i)).isoformat(),
         "demand_kwh": 100, "pv_generation_kwh": 80, "probability_within_margin": 0.99}
        for i in range(4)]}
    forecast_response = client.post("/api/v1/forecasts", json=forecast)
    assert forecast_response.status_code == 201
    plan_response = client.post("/api/v1/dispatch/plan", json={
        "forecast_run_id": forecast_response.json()["id"],
        "battery": {"capacity_kwh": 500, "power_kw": 100, "initial_soc_kwh": 100,
            "min_soc_kwh": 0, "charge_efficiency": 1, "peak_start_hour": 14, "peak_end_hour": 17}})
    assert plan_response.status_code == 201
    summary = client.get("/api/v1/dashboard/summary").json()
    assert summary["forecast_points_count"] == 4
    assert summary["forecast_demand_kwh"] == pytest.approx(400)
    assert summary["forecast_pv_generation_kwh"] == pytest.approx(320)
    assert summary["dispatch_run_id"] == plan_response.json()["id"]
    assert summary["dispatch_points_count"] == 4

def test_api_key_is_optional_but_enforced_when_configured(client, monkeypatch):
    monkeypatch.setattr(main_module, "API_KEY", "test-api-key")
    assert client.get("/api/v1/health").status_code == 200
    assert client.get("/api/v1/campus").status_code == 401
    assert client.get("/api/v1/campus", headers={"X-API-Key": "wrong"}).status_code == 401
    assert client.get("/api/v1/campus", headers={"X-API-Key": "test-api-key"}).status_code == 200

def test_request_payload_rejects_unknown_and_non_finite_fields(client):
    unknown = client.post("/api/v1/forecasts", json={
        "model_name": "test", "model_version": "1", "unexpected": True,
        "points": [{"interval_start": "2026-11-27T14:00:00-06:00",
            "demand_kwh": 100, "pv_generation_kwh": 50,
            "probability_within_margin": 0.9}]
    })
    assert unknown.status_code == 422
    non_finite = client.post(
        "/api/v1/forecasts",
        content='{"model_name":"test","model_version":"1","points":[{"interval_start":"2026-11-27T14:00:00-06:00","demand_kwh":NaN,"pv_generation_kwh":50,"probability_within_margin":0.9}]}',
        headers={"Content-Type": "application/json"},
    )
    assert non_finite.status_code == 422


def test_alembic_initial_migration_creates_database_schema(tmp_path):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, inspect

    database_path = tmp_path / "migration-test.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")

    engine = create_engine(database_url)
    table_names = set(inspect(engine).get_table_names())
    assert {"alembic_version", "campus_config", "measurements", "forecast_runs",
        "forecast_points", "dispatch_runs", "dispatch_points"}.issubset(table_names)
    dispatch_columns = {column["name"] for column in inspect(engine).get_columns("dispatch_runs")}
    assert {"peak_start_hour", "peak_end_hour", "alpha", "delta"}.issubset(dispatch_columns)
    engine.dispose()


def test_weather_endpoint_returns_current_and_hourly_data(client, monkeypatch):
    from solarnexus.api.routers import weather as weather_router
    monkeypatch.setattr(weather_router, "_cache", {})

    async def fake_fetch(params):
        assert params["latitude"] == pytest.approx(12.1328)
        assert "shortwave_radiation" in params["hourly"]
        return {
            "latitude": 12.1328, "longitude": -86.2504,
            "timezone": "America/Managua", "elevation": 56,
            "current": {"time": "2026-11-26T12:00", "temperature_2m": 32,
                "apparent_temperature": 36, "relative_humidity_2m": 65,
                "precipitation": 0, "weather_code": 2, "cloud_cover": 30,
                "wind_speed_10m": 12, "wind_direction_10m": 90, "is_day": 1},
            "hourly": {"time": [f"2026-11-26T{i:02d}:00" for i in range(24)],
                "temperature_2m": [30] * 24, "relative_humidity_2m": [60] * 24,
                "precipitation_probability": [10] * 24, "precipitation": [0] * 24,
                "weather_code": [1] * 24, "cloud_cover": [20] * 24,
                "wind_speed_10m": [10] * 24, "shortwave_radiation": [500] * 24,
                "direct_radiation": [350] * 24, "diffuse_radiation": [150] * 24},
        }

    monkeypatch.setattr(weather_router, "fetch_open_meteo", fake_fetch)
    response = client.get("/api/v1/weather")
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["provider"] == "Open-Meteo"
    assert result["current"]["temperature_c"] == 32
    assert len(result["hourly"]) == 24
    assert result["hourly"][0]["shortwave_radiation_w_m2"] == 500


def test_weather_endpoint_validates_coordinates(client):
    response = client.get("/api/v1/weather?latitude=120&longitude=-86")
    assert response.status_code == 422
