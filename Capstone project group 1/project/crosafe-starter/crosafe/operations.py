"""Administrator analysis, provider controls, and in-app notifications."""
import os
from datetime import date, datetime, timezone
from typing import Literal
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field
from rasterio.errors import RasterioError

from .accounts import Account, admin, identify
from .cloud_catalog import ROOT, list_objects, sample_object
from .contracts import FieldRecord
from .providers import FixtureWeather, OpenMeteoWeather, WeatherUnavailable

router = APIRouter(prefix="/v1", tags=["operations"])


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    weather_mode: Literal["fixture", "live"] = "fixture"
    forecast_days: int = Field(default=7, ge=1, le=14)
    gaez_online: bool = True
    weather_paid: bool = False
    world_bank_online: bool = True
    world_bank_indicator: Literal["AG.LND.AGRI.ZS", "AG.LND.ARBL.ZS", "AG.PRD.CROP.XD"] = "AG.LND.AGRI.ZS"


class Notice(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    message: str = Field(min_length=1, max_length=1000)
    recipient: str | None = Field(default=None, max_length=150)


def get_settings(request: Request) -> Settings:
    with request.app.state.pool.connection() as connection:
        row = connection.execute("SELECT settings FROM provider_settings WHERE singleton").fetchone()
    return Settings.model_validate(row[0]) if row else request.app.state.default_settings


def weather_for(settings: Settings):
    if settings.weather_mode == "fixture":
        return FixtureWeather()
    key = os.getenv("OPEN_METEO_API_KEY", "") if settings.weather_paid else ""
    if settings.weather_paid and not key:
        raise WeatherUnavailable
    return OpenMeteoWeather(settings.forecast_days, key)


@router.get("/admin/providers", dependencies=[Depends(admin)])
def providers(request: Request) -> dict:
    return {
        "settings": get_settings(request),
        "open_meteo_key_configured": bool(os.getenv("OPEN_METEO_API_KEY")),
    }


@router.put("/admin/providers", dependencies=[Depends(admin)])
def save_providers(settings: Settings, request: Request) -> Settings:
    if settings.weather_paid and not os.getenv("OPEN_METEO_API_KEY"):
        raise HTTPException(422, "Set OPEN_METEO_API_KEY on the server first")
    with request.app.state.pool.connection() as connection:
        connection.execute(
            "INSERT INTO provider_settings (settings) VALUES (%s) "
            "ON CONFLICT (singleton) DO UPDATE SET settings = excluded.settings",
            (Jsonb(settings.model_dump()),),
        )
    return settings


@router.post("/admin/providers/check", dependencies=[Depends(admin)])
def check_provider(request: Request, provider: Literal["weather", "gaez", "world-bank"]) -> dict:
    settings = get_settings(request)
    if provider == "gaez":
        if not settings.gaez_online:
            raise HTTPException(409, "Online GAEZ catalog disabled")
        page = cloud_list(ROOT, "")
        return {"message": f"Official catalog reached. {len(page['prefixes'])} top-level folders."}
    if provider == "world-bank":
        context = national_context(request)
        return {"message": f"World Bank returned {len(context['observations'])} published observations."}
    point = FieldRecord(id=uuid4(), latitude=35.1234, longitude=37.1234, area_ha=1,
                        captured_at=datetime.now(timezone.utc))
    try:
        adapter = weather_for(settings)
        days = adapter.forecast(point)
    except WeatherUnavailable as error:
        raise HTTPException(502, "Weather provider unavailable") from error
    return {"message": f"{adapter.source} returned {len(days)} forecast days."}


@router.get("/admin/national-context", dependencies=[Depends(admin)])
def national_context(request: Request) -> dict:
    settings = get_settings(request)
    if not settings.world_bank_online:
        raise HTTPException(409, "World Bank API disabled")
    indicator = settings.world_bank_indicator
    try:
        response = httpx.get(
            f"https://api.worldbank.org/v2/country/SYR/indicator/{indicator}",
            params={"format": "json", "per_page": 10, "mrv": 10}, timeout=8,
        )
        response.raise_for_status()
        rows = response.json()[1] or []
        return {
            "indicator": indicator,
            "label": rows[0]["indicator"]["value"] if rows else indicator,
            "observations": [
                {"year": row["date"], "value": row["value"]}
                for row in rows if row["value"] is not None
            ],
        }
    except (httpx.HTTPError, IndexError, KeyError, TypeError, ValueError) as error:
        raise HTTPException(502, "World Bank indicator unavailable") from error


def cloud_list(prefix: str, token: str) -> dict:
    try:
        return list_objects(prefix, token)
    except ValueError as error:
        raise HTTPException(422, "Invalid catalog path or response") from error
    except httpx.HTTPError as error:
        raise HTTPException(502, "FAO catalog temporarily unavailable") from error


@router.get("/admin/gaez/catalog", dependencies=[Depends(admin)])
def catalog(request: Request, prefix: str = Query(ROOT, max_length=500),
            token: str = Query("", max_length=3000)) -> dict:
    if not get_settings(request).gaez_online:
        raise HTTPException(409, "Online GAEZ catalog disabled")
    return cloud_list(prefix, token)


@router.get("/admin/gaez/remote-sample", dependencies=[Depends(admin)])
def remote_sample(request: Request, name: str = Query(max_length=500),
                  longitude: float = Query(ge=-180, le=180),
                  latitude: float = Query(ge=-90, le=90)) -> dict:
    if not get_settings(request).gaez_online:
        raise HTTPException(409, "Online GAEZ catalog disabled")
    try:
        return sample_object(name, longitude, latitude)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    except (httpx.HTTPError, RasterioError) as error:
        raise HTTPException(502, "Official raster could not be read") from error


@router.get("/admin/analysis", dependencies=[Depends(admin)])
def analysis(request: Request, start: date | None = None, end: date | None = None) -> dict:
    if start and end and start > end:
        raise HTTPException(422, "Start date must be before the end date")
    where = "WHERE (%s::date IS NULL OR planted_on >= %s) AND (%s::date IS NULL OR planted_on <= %s)"
    params = (start, start, end, end)
    with request.app.state.pool.connection() as connection, connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        totals = cursor.execute(
            "SELECT count(*) AS plantings, count(DISTINCT customer) AS customers, "
            "count(DISTINCT lower(crop)) AS crops, coalesce(sum(area_ha),0) AS area_ha "
            f"FROM plantings {where}", params,
        ).fetchone()
        crops = cursor.execute(
            f"SELECT lower(crop) AS crop, count(*) AS plantings, sum(area_ha) AS area_ha "
            f"FROM plantings {where} GROUP BY lower(crop) ORDER BY area_ha DESC, crop LIMIT 20",
            params,
        ).fetchall()
        months = cursor.execute(
            "SELECT date_trunc('month',planted_on::timestamp)::date AS month, "
            f"count(*) AS plantings, sum(area_ha) AS area_ha FROM plantings {where} "
            "GROUP BY 1 ORDER BY 1 DESC LIMIT 24", params,
        ).fetchall()
    return {"totals": totals, "crops": crops, "months": list(reversed(months))}


VISIBLE = "n.audience = %s AND (n.recipient IS NULL OR n.recipient = %s)"


@router.get("/notifications")
def notifications(request: Request, before: int | None = Query(None, ge=1),
                  account: Account = Depends(identify)) -> list[dict]:
    with request.app.state.pool.connection() as connection, connection.cursor(row_factory=dict_row) as cursor:
        return cursor.execute(
            "SELECT n.id, n.title, n.message, n.created_at, (r.username IS NOT NULL) AS read "
            "FROM notifications n LEFT JOIN notification_reads r "
            "ON r.notification_id = n.id AND r.username = %s "
            f"WHERE {VISIBLE} AND (%s::bigint IS NULL OR n.id < %s) ORDER BY n.id DESC LIMIT 50",
            (account.username, account.role, account.username, before, before),
        ).fetchall()


@router.get("/notifications/unread")
def unread_count(request: Request, account: Account = Depends(identify)) -> dict:
    with request.app.state.pool.connection() as connection:
        row = connection.execute(
            "SELECT count(*) FROM notifications n "
            f"WHERE {VISIBLE} AND NOT EXISTS (SELECT 1 FROM notification_reads r "
            "WHERE r.notification_id = n.id AND r.username = %s)",
            (account.role, account.username, account.username),
        ).fetchone()
    return {"unread": row[0]}


@router.post("/notifications/read")
def mark_read(request: Request, notification_id: int | None = Query(None, ge=1),
              through: int | None = Query(None, ge=1), account: Account = Depends(identify)) -> dict:
    if (notification_id is None) == (through is None):
        raise HTTPException(422, "Provide a notification ID or a read-through ID")
    with request.app.state.pool.connection() as connection:
        connection.execute(
            "INSERT INTO notification_reads (username, notification_id) "
            f"SELECT %s, n.id FROM notifications n WHERE {VISIBLE} "
            "AND (%s::bigint IS NULL OR n.id = %s) AND (%s::bigint IS NULL OR n.id <= %s) "
            "ON CONFLICT DO NOTHING",
            (account.username, account.role, account.username,
             notification_id, notification_id, through, through),
        )
    return {"saved": True}


@router.get("/admin/customers", dependencies=[Depends(admin)])
def customers(request: Request) -> list[str]:
    return sorted(account.username for account in request.app.state.accounts.values()
                  if account.role == "customer")


@router.post("/admin/notifications", dependencies=[Depends(admin)])
def send_notice(notice: Notice, request: Request) -> dict:
    if notice.recipient is not None and notice.recipient not in customers(request):
        raise HTTPException(422, "Select an existing customer")
    title, message = notice.title.strip(), notice.message.strip()
    if not title or not message:
        raise HTTPException(422, "Enter a title and a message")
    with request.app.state.pool.connection() as connection:
        row = connection.execute(
            "INSERT INTO notifications (audience, recipient, title, message) "
            "VALUES ('customer', %s, %s, %s) RETURNING id",
            (notice.recipient, title, message),
        ).fetchone()
    return {"id": row[0]}
