"""HTTP routes and composition of storage, providers and decision modules."""
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from psycopg import Error
from psycopg.errors import UndefinedTable
from psycopg_pool import ConnectionPool, PoolTimeout

from .contracts import Assessment, FieldRecord
from .agronomy import DemoYieldModel
from .planning import router as planning_router
from .accounts import admin, load_accounts, router as session_router
from .dashboards import WEB, router
from .gaez import GaezCatalog
from .plantings import PlantingRepository
from .decisions import assess
from .providers import WeatherUnavailable
from .operations import Settings, get_settings, router as operations_router, weather_for
from .repository import FieldConflict, FieldRepository


@asynccontextmanager
async def lifespan(app: FastAPI):
    mode = os.getenv("CROSAFE_MODE", "fixture")
    app.state.default_settings = Settings(weather_mode=mode)
    app.state.yield_model = DemoYieldModel()
    app.state.accounts = load_accounts()
    app.state.gaez = GaezCatalog(Path(os.getenv("CROSAFE_GAEZ_DIRECTORY", "/data/gaez")))
    with ConnectionPool(os.environ["DATABASE_URL"], min_size=1,
                        max_size=5, timeout=5, open=False) as pool:
        pool.wait(timeout=10)
        app.state.pool = pool
        app.state.fields = FieldRepository(pool)
        app.state.plantings = PlantingRepository(pool)
        yield


app = FastAPI(title="CroSafe Prototype", version="0.1.0", lifespan=lifespan)
app.include_router(router)
app.include_router(session_router)
app.include_router(operations_router)
app.include_router(planning_router)
app.mount("/assets", StaticFiles(directory=WEB / "assets"), name="assets")


@app.exception_handler(UndefinedTable)
async def incomplete_database(request: Request, error: UndefinedTable):
    logging.getLogger(__name__).error("CroSafe database migration required: %s", error)
    return JSONResponse(
        {"detail": "Database setup is incomplete. Apply the CroSafe migrations and try again."},
        status_code=503,
        headers={"Cache-Control": "no-store"},
    )



@app.middleware("http")
async def protect_dashboard_responses(request: Request, call_next):
    if request.method in {"POST", "PUT", "PATCH", "DELETE"} and request.url.path.startswith("/v1/"):
        content_type = request.headers.get("content-type", "").partition(";")[0]
        if content_type.lower().strip() != "application/json":
            return JSONResponse({"detail": "Expected application/json"}, status_code=415)
    response = await call_next(request)
    if request.url.path.startswith("/v1/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/health")
def health(request: Request) -> dict[str, str]:
    try:
        with request.app.state.pool.connection() as connection:
            connection.execute("SELECT id FROM fields LIMIT 0")
            connection.execute("SELECT id FROM plantings LIMIT 0")
            connection.execute("SELECT id FROM notifications LIMIT 0")
            connection.execute("SELECT id FROM farm_fields LIMIT 0")
            connection.execute("SELECT PostGIS_Version()")
        settings = get_settings(request)
    except (Error, PoolTimeout) as error:
        raise HTTPException(503, "Database unavailable") from error
    return {"status": "ok", "weather_source": "Open-Meteo" if settings.weather_mode == "live" else "synthetic"}


@app.post("/v1/fields/sync", dependencies=[Depends(admin)])
def sync(field: FieldRecord, request: Request) -> FieldRecord:
    try:
        return request.app.state.fields.save(field)
    except FieldConflict as error:
        raise HTTPException(409, "Capture ID already has different content") from error


@app.get("/v1/fields/{field_id}", dependencies=[Depends(admin)])
def get_field(field_id: UUID, request: Request) -> FieldRecord:
    field = request.app.state.fields.get(field_id)
    if field is None:
        raise HTTPException(404, "Field not found")
    return field


@app.get("/v1/fields/{field_id}/assessment", dependencies=[Depends(admin)])
def assessment(field_id: UUID, request: Request) -> Assessment:
    field = get_field(field_id, request)
    try:
        return assess(field, weather_for(get_settings(request)))
    except WeatherUnavailable as error:
        raise HTTPException(503, "Weather provider unavailable") from error
