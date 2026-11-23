"""Weather adapters. The live adapter is intended for synthetic test points."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Protocol

import httpx

from .contracts import FieldRecord, ForecastDay


class WeatherUnavailable(Exception):
    """The provider failed or returned an unusable response."""


class WeatherProvider(Protocol):
    source: str

    def forecast(self, field: FieldRecord) -> list[ForecastDay]: ...


class FixtureWeather:
    source = "synthetic"

    def forecast(self, field: FieldRecord) -> list[ForecastDay]:
        today = datetime.now(ZoneInfo("Asia/Damascus")).date()
        return [
            ForecastDay(day=today + timedelta(days=index), max_temperature_c=39 if index == 0 else 25,
                        min_temperature_c=12, precipitation_mm=0)
            for index in range(7)
        ]


class OpenMeteoWeather:
    source = "Open-Meteo"

    def __init__(self, days: int = 7, api_key: str = ""):
        self.days = days
        self.api_key = api_key

    def forecast(self, field: FieldRecord) -> list[ForecastDay]:
        try:
            response = httpx.get(
                (
                    "https://customer-api.open-meteo.com/v1/forecast"
                    if self.api_key else "https://api.open-meteo.com/v1/forecast"
                ),
                params={
                    "latitude": field.latitude,
                    "longitude": field.longitude,
                    "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
                    "temperature_unit": "celsius",
                    "precipitation_unit": "mm",
                    "timezone": "Asia/Damascus",
                    "forecast_days": self.days,
                    **({"apikey": self.api_key} if self.api_key else {}),
                },
                timeout=5.0,
            )
            response.raise_for_status()
            daily = response.json()["daily"]
            forecast = [
                ForecastDay(day=day, max_temperature_c=temperature,
                            min_temperature_c=minimum, precipitation_mm=rain)
                for day, temperature, minimum, rain in zip(
                    daily["time"], daily["temperature_2m_max"],
                    daily["temperature_2m_min"], daily["precipitation_sum"], strict=True,
                )
            ]
            if not forecast:
                raise WeatherUnavailable
            return forecast
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
            raise WeatherUnavailable from error
