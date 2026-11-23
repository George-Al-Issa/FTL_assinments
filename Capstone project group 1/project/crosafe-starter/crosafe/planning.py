"""Owner-scoped field planning and transactional regional production limits."""
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from typing import Annotated
from rasterio.errors import RasterioError

from .accounts import Account, admin, customer
from .agronomy import CROPS, DemoYieldModel, forecast_events
from .contracts import FieldRecord
from .operations import get_settings, weather_for
from .providers import WeatherUnavailable

router = APIRouter(prefix="/v1/planning", tags=["planning"])
FIELDS = """id, name, region, area_ha, irrigation,
            ST_X(location) AS longitude, ST_Y(location) AS latitude"""
TOTAL = """SELECT coalesce(sum(p.projected_tonnes), 0) FROM plantings p
           WHERE p.planning_region = t.region AND p.crop = t.crop
             AND p.planted_on BETWEEN t.starts AND t.ends"""


class FarmInput(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False, extra="forbid")
    id: UUID
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-90, le=90)
    area_ha: float = Field(ge=0.001, le=100000)
    irrigation: Literal["rainfed", "irrigated"]


class Target(BaseModel):
    region: str = Field(min_length=1, max_length=20)
    crop: str
    starts: date
    ends: date
    tonnes: Decimal = Field(ge=0, max_digits=15, decimal_places=3)

    @model_validator(mode="after")
    def valid_season(self):
        if self.ends < self.starts or self.crop not in CROPS:
            raise ValueError("Use a supported crop and valid season dates")
        return self


class Confirmation(BaseModel):
    id: UUID
    field_id: UUID
    crop: str
    planted_on: date


class Policy(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False, extra="forbid")
    heat_c: float = Field(38, ge=20, le=60)
    frost_c: float = Field(0, ge=-20, le=10)
    rain_mm: float = Field(30, gt=0, le=200)
    dry_mm: float = Field(1, ge=0, le=10)
    dry_days: int = Field(5, ge=2, le=14)
    regional_review_ha: float = Field(100, gt=0, le=10000000)


def get_policy(request):
    with request.app.state.pool.connection() as connection:
        row = connection.execute("SELECT rules FROM planning_policy WHERE singleton").fetchone()
    return Policy.model_validate(row[0]) if row else Policy()


@router.get("/policy", dependencies=[Depends(admin)])
def policy(request: Request) -> Policy:
    return get_policy(request)


@router.put("/policy", dependencies=[Depends(admin)])
def save_policy(data: Policy, request: Request) -> Policy:
    with request.app.state.pool.connection() as connection:
        connection.execute(
            "INSERT INTO planning_policy(rules) VALUES (%s) "
            "ON CONFLICT(singleton) DO UPDATE SET rules = excluded.rules",
            (Jsonb(data.model_dump()),),
        )
    return data


@router.get("/catalog", dependencies=[Depends(customer)])
@router.get("/admin/catalog", dependencies=[Depends(admin)])
def catalog(request: Request):
    with request.app.state.pool.connection() as connection:
        rows = connection.execute("SELECT id, name, name_ar FROM planning_regions ORDER BY name").fetchall()
    return {"regions": [dict(zip(("id", "en", "ar"), row)) for row in rows],
            "crops": {code: {key: item[key] for key in ("en", "ar")} for code, item in CROPS.items()}}


def owned_field(cursor, owner, field_id):
    row = cursor.execute(f"SELECT {FIELDS} FROM farm_fields WHERE id = %s AND owner = %s",
                         (field_id, owner)).fetchone()
    if not row:
        raise HTTPException(404, "Field not found")
    return row


@router.get("/fields")
def fields(request: Request, account: Account = Depends(customer)):
    with request.app.state.pool.connection() as connection, connection.cursor(row_factory=dict_row) as cursor:
        return cursor.execute(f"SELECT {FIELDS} FROM farm_fields WHERE owner = %s ORDER BY name, id",
                              (account.username,)).fetchall()


@router.post("/fields")
def save_field(data: FarmInput, request: Request, account: Account = Depends(customer)):
    with request.app.state.pool.connection() as connection, connection.cursor(row_factory=dict_row) as cursor:
        matches = cursor.execute(
            "SELECT id FROM planning_regions WHERE ST_Covers(boundary, ST_SetSRID(ST_MakePoint(%s,%s),4326))",
            (data.longitude, data.latitude),
        ).fetchall()
        if len(matches) != 1:
            raise HTTPException(422, "Pin must be inside exactly one supported governorate")
        cursor.execute(
            """INSERT INTO farm_fields(id, owner, name, region, location, area_ha, irrigation)
               VALUES (%s,%s,%s,%s,ST_SetSRID(ST_MakePoint(%s,%s),4326),%s,%s)
               ON CONFLICT(id) DO NOTHING""",
            (data.id, account.username, data.name, matches[0]["id"], data.longitude,
             data.latitude, data.area_ha, data.irrigation),
        )
        row = owned_field(cursor, account.username, data.id)
        if any(row[key] != value for key, value in data.model_dump().items()):
            raise HTTPException(409, "Field ID already in use")
        return row


def targets(cursor, region, day):
    return {row["crop"]: row for row in cursor.execute(
        f"SELECT t.crop, t.tonnes, ({TOTAL}) AS projected FROM crop_targets t "
        "WHERE t.region = %s AND %s BETWEEN t.starts AND t.ends", (region, day),
    ).fetchall()}


def layer_context(request, field, layer_id):
    catalog = request.app.state.gaez
    layer = catalog.layers.get(layer_id)
    if layer is None:
        return None
    try:
        value = catalog.sample(layer, field["longitude"], field["latitude"])
    except (RasterioError, ValueError):
        return None
    return {"value": value, "layer": layer.title, "source_url": layer.source_url} if value is not None else None


@router.get("/fields/{field_id}/recommendations")
def recommendations(field_id: UUID, day: date, request: Request, account: Account = Depends(customer)):
    with request.app.state.pool.connection() as connection, connection.cursor(row_factory=dict_row) as cursor:
        field = owned_field(cursor, account.username, field_id)
        limits = targets(cursor, field["region"], day)
    model = request.app.state.yield_model
    options, blocked = [], []
    for crop, profile in CROPS.items():
        projected = model.tonnes(crop, field)
        limit = limits.get(crop)
        if limit and (limit["projected"] >= limit["tonnes"] or limit["projected"] + projected > limit["tonnes"]):
            blocked.append(crop)
            continue
        options.append({"crop": crop, "tonnes": float(projected), "info": profile["info"],
                        "check_days": profile["check_days"] if field["irrigation"] == "irrigated" else None,
                        "suitability": layer_context(request, field, f"{crop}-{field['irrigation']}"),
                        "remaining_tonnes": float(limit["tonnes"] - limit["projected"]) if limit else None})
    # Availability of source context breaks ties in the fixed demo crop order.
    options.sort(key=lambda option: option["suitability"] is None)
    return {"options": options[:3], "blocked": blocked, "source": model.source,
            "soil": layer_context(request, field, "soil-type")}


@router.post("/confirm")
def confirm(data: Confirmation, request: Request, account: Account = Depends(customer)):
    if data.crop not in CROPS:
        raise HTTPException(422, "Unknown crop")
    with request.app.state.pool.connection() as connection, connection.cursor(row_factory=dict_row) as cursor:
        # Shared lock with target writes. The quota lookup and insert use the same transaction.
        cursor.execute("SELECT pg_advisory_xact_lock(772844)")
        field = owned_field(cursor, account.username, data.field_id)
        existing = cursor.execute(
            "SELECT customer, farm_field, crop, planted_on, projected_tonnes FROM plantings WHERE id = %s", (data.id,),
        ).fetchone()
        if existing:
            if (existing["customer"], existing["farm_field"], existing["crop"], existing["planted_on"]) != (
                account.username, data.field_id, data.crop, data.planted_on,
            ):
                raise HTTPException(409, "Planting ID already in use")
            return {"id": data.id, "tonnes": existing["projected_tonnes"]}
        model = request.app.state.yield_model
        tonnes = model.tonnes(data.crop, field)
        limit = targets(cursor, field["region"], data.planted_on).get(data.crop)
        if limit and (limit["projected"] >= limit["tonnes"] or limit["projected"] + tonnes > limit["tonnes"]):
            raise HTTPException(409, "Regional crop limit would be exceeded")
        if cursor.execute(
            """INSERT INTO plantings(id, customer, crop, planted_on, location, area_ha,
               farm_field, planning_region, projected_tonnes, projection_source)
               SELECT %s,%s,%s,%s,location,area_ha,id,region,%s,%s FROM farm_fields WHERE id = %s
               ON CONFLICT DO NOTHING RETURNING id""",
            (data.id, account.username, data.crop, data.planted_on, tonnes, model.source, data.field_id),
        ).fetchone() is None:
            raise HTTPException(409, "A planting is already confirmed for this field and date")
    return {"id": data.id, "tonnes": tonnes}


@router.get("/targets", dependencies=[Depends(admin)])
def list_targets(request: Request):
    with request.app.state.pool.connection() as connection, connection.cursor(row_factory=dict_row) as cursor:
        return cursor.execute(
            f"SELECT t.*, ({TOTAL}) AS projected FROM crop_targets t ORDER BY t.starts DESC, t.region, t.crop",
        ).fetchall()


@router.put("/targets", dependencies=[Depends(admin)])
def save_target(data: Target, request: Request):
    key = (data.region, data.crop, data.starts, data.ends)
    with request.app.state.pool.connection() as connection:
        connection.execute("SELECT pg_advisory_xact_lock(772844)")
        if not connection.execute("SELECT 1 FROM planning_regions WHERE id = %s", (data.region,)).fetchone():
            raise HTTPException(422, "Unknown governorate")
        if connection.execute(
            """SELECT 1 FROM crop_targets
               WHERE region = %s AND crop = %s AND ends >= %s AND starts <= %s
                 AND (starts, ends) <> (%s, %s)""", (*key, data.starts, data.ends),
        ).fetchone():
            raise HTTPException(409, "Season overlaps another target for this crop and governorate")
        connection.execute(
            """INSERT INTO crop_targets(region,crop,starts,ends,tonnes) VALUES (%s,%s,%s,%s,%s)
               ON CONFLICT(region,crop,starts,ends) DO UPDATE SET tonnes = excluded.tonnes""",
            (*key, data.tonnes),
        )
    return data


@router.delete("/targets", dependencies=[Depends(admin)])
def remove_target(data: Target, request: Request):
    with request.app.state.pool.connection() as connection:
        connection.execute("SELECT pg_advisory_xact_lock(772844)")
        connection.execute("DELETE FROM crop_targets WHERE (region,crop,starts,ends) = (%s,%s,%s,%s)",
                           (data.region, data.crop, data.starts, data.ends))
    return {"removed": True}


def weather_events(adapter, field, policy):
    point = FieldRecord(id=field["id"], latitude=field["latitude"], longitude=field["longitude"],
                        area_ha=field["area_ha"], captured_at=datetime.now(timezone.utc))
    return forecast_events(adapter.forecast(point), policy.model_dump())


@router.get("/fields/{field_id}/weather")
def field_weather(field_id: UUID, request: Request, account: Account = Depends(customer)):
    with request.app.state.pool.connection() as connection, connection.cursor(row_factory=dict_row) as cursor:
        field = owned_field(cursor, account.username, field_id)
    try:
        adapter = weather_for(get_settings(request))
        return {"source": adapter.source, "events": weather_events(adapter, field, get_policy(request))}
    except WeatherUnavailable as error:
        raise HTTPException(503, "Forecast unavailable") from error


@router.get("/exposure", dependencies=[Depends(admin)])
def exposure(region: str, day: date, request: Request):
    """Screen the latest planting on up to 20 registered fields as of the selected date."""
    with request.app.state.pool.connection() as connection, connection.cursor(row_factory=dict_row) as cursor:
        fields = cursor.execute(
            """SELECT f.id, f.name, ST_X(f.location) AS longitude, ST_Y(f.location) AS latitude,
                      f.area_ha, p.crop
               FROM farm_fields f JOIN LATERAL (
                   SELECT crop FROM plantings
                   WHERE farm_field = f.id AND planted_on <= %s
                   ORDER BY planted_on DESC LIMIT 1
               ) p ON true WHERE f.region = %s ORDER BY f.id LIMIT 21""", (day, region),
        ).fetchall()
    policy = get_policy(request)
    try:
        adapter = weather_for(get_settings(request))
    except WeatherUnavailable as error:
        raise HTTPException(503, "Forecast unavailable") from error
    groups, failures = {}, 0
    for field in fields[:20]:
        try:
            events = weather_events(adapter, field, policy)
        except WeatherUnavailable:
            failures += 1
            continue
        for event in events:
            key = (event["kind"], event["start"], event["end"])
            group = groups.setdefault(key, {**event, "hectares": 0, "fields": []})
            group["hectares"] += field["area_ha"]
            group["fields"].append(field)
    for group in groups.values():
        group["review"] = group["hectares"] >= policy.regional_review_ha
    return {"source": adapter.source, "checked": min(len(fields), 20) - failures, "failed": failures,
            "partial": len(fields) > 20, "events": list(groups.values())}


@router.post("/exposure/publish", dependencies=[Depends(admin)])
def publish_exposure(region: str, day: date, request: Request):
    """Refresh the regional screening and deliver each result once per field."""
    result = exposure(region, day, request)
    sent = 0
    with request.app.state.pool.connection() as connection:
        for event in result["events"]:
            kind, starts, ends = event["kind"], event["start"], event["end"]
            for field in event["fields"]:
                inserted = connection.execute(
                    """INSERT INTO planning_alert_deliveries VALUES (%s,%s,%s,%s,%s)
                       ON CONFLICT DO NOTHING RETURNING field_id""",
                    (field["id"], kind, starts, ends, result["source"]),
                ).fetchone()
                if inserted is None:
                    continue
                english, arabic = event["guidance"]
                demo = "Demo / تجريبي · " if result["source"] == "synthetic" else ""
                connection.execute(
                    """INSERT INTO notifications (audience, recipient, title, message)
                       SELECT 'customer', owner, %s, %s FROM farm_fields WHERE id = %s""",
                    (f"{demo}Weather screening / تنبيه الطقس",
                     f"{field['name']} · {kind} · {starts} – {ends}\n{arabic}\n{english}", field["id"]),
                )
                sent += 1
    return {"sent": sent, "partial": result["partial"], "failed": result["failed"]}
