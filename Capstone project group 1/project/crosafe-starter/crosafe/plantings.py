"""Customer-reported planting storage, independent of model recommendations."""
from datetime import date
from uuid import UUID

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from typing import Annotated

from .repository import FieldConflict

Crop = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
COLUMNS = """
    id, customer, crop, planted_on, ST_X(location) AS longitude,
    ST_Y(location) AS latitude, area_ha
"""


class PlantingInput(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    id: UUID
    crop: Crop
    planted_on: date
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    area_ha: float = Field(gt=0)


class Planting(PlantingInput):
    customer: str


class PlantingRepository:
    def __init__(self, pool: ConnectionPool):
        self.pool = pool

    def save(self, owner: str, data: PlantingInput) -> Planting:
        with self.pool.connection() as connection, connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                INSERT INTO plantings (id, customer, crop, planted_on, location, area_ha)
                VALUES (%s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s)
                ON CONFLICT (id) DO NOTHING
                """,
                (data.id, owner, data.crop, data.planted_on, data.longitude,
                 data.latitude, data.area_ha),
            )
            row = cursor.execute(
                f"SELECT {COLUMNS} FROM plantings WHERE id = %s", (data.id,),
            ).fetchone()
            stored = Planting.model_validate(row)
            if stored != Planting(customer=owner, **data.model_dump()):
                raise FieldConflict
            return stored

    def list(self, owner: str | None = None, limit: int = 250, offset: int = 0) -> list[Planting]:
        where = "WHERE customer = %s" if owner is not None else ""
        params = (owner, limit, offset) if owner is not None else (limit, offset)
        with self.pool.connection() as connection, connection.cursor(row_factory=dict_row) as cursor:
            rows = cursor.execute(
                f"SELECT {COLUMNS} FROM plantings {where} "
                "ORDER BY created_at DESC, id DESC LIMIT %s OFFSET %s", params,
            ).fetchall()
        return [Planting.model_validate(row) for row in rows]
