"""Shared API and decision-module contracts."""
from datetime import date, datetime, timezone
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

Module = Literal["crop", "irrigation", "fire", "harvest"]


class FieldRecord(BaseModel):
    """Client-generated UUID makes replay of an immutable capture safe."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    id: UUID
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    area_ha: float = Field(gt=0)
    captured_at: AwareDatetime
    irrigation: Literal["unknown", "rainfed", "irrigated"] = "unknown"


    @field_validator("captured_at")
    @classmethod
    def captured_at_utc(cls, value: datetime) -> datetime:
        return value.astimezone(timezone.utc)


class ForecastDay(BaseModel):
    day: date
    max_temperature_c: float | None
    min_temperature_c: float | None = None
    precipitation_mm: float | None

class Result(BaseModel):
    module: Module
    status: Literal["demo", "unavailable", "ready"]
    source: str | None = None
    message: str
    crop_codes: list[str] = Field(default_factory=list)
    drought_class: str | None = None


class Assessment(BaseModel):
    field_id: UUID
    weather_source: str
    forecast: list[ForecastDay]
    results: list[Result]
    arabic_review_note: str
