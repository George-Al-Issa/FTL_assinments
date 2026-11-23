"""PostGIS storage. SQL coordinates are always ordered longitude, latitude."""
from uuid import UUID

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .contracts import FieldRecord

SELECT_FIELD = """
    SELECT id, ST_Y(location) AS latitude, ST_X(location) AS longitude,
           area_ha, captured_at, irrigation
    FROM fields WHERE id = %s
"""


class FieldConflict(Exception):
    """The client reused a capture ID with different content."""


class FieldRepository:
    def __init__(self, pool: ConnectionPool):
        self.pool = pool

    def get(self, field_id: UUID) -> FieldRecord | None:
        with self.pool.connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                row = cursor.execute(SELECT_FIELD, (field_id,)).fetchone()
        return FieldRecord.model_validate(row) if row else None

    def save(self, field: FieldRecord) -> FieldRecord:
        with self.pool.connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    INSERT INTO fields (id, location, area_ha, captured_at, irrigation)
                    VALUES (%s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (field.id, field.longitude, field.latitude, field.area_ha,
                     field.captured_at, field.irrigation),
                )
                row = cursor.execute(SELECT_FIELD, (field.id,)).fetchone()
                stored = FieldRecord.model_validate(row)
                if stored != field:
                    raise FieldConflict
                return stored
