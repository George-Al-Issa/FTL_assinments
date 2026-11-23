"""Decision entry points. Implementations can evolve independently of HTTP and SQL."""
from .contracts import Assessment, FieldRecord, ForecastDay, Module, Result
from .providers import WeatherProvider


def crop_suitability(field: FieldRecord, demo: bool) -> Result:
    """George connects a versioned GAEZ v5 suitability adapter here."""
    if demo:
        return Result(module="crop", status="demo", source="synthetic",
                      message="Illustrative ordering independent of location.",
                      crop_codes=["wheat", "barley", "lentil"])
    return unavailable("crop", "GAEZ v5 suitability layers are not configured.")


def irrigation(field: FieldRecord, forecast: list[ForecastDay]) -> Result:
    """AbdAlrhman connects the validated drought model here."""
    return unavailable("irrigation", "Water-stress model is not connected.")


def wildfire(field: FieldRecord, forecast: list[ForecastDay]) -> Result:
    """Bayan connects hotspot, wind and freshness checks here."""
    return unavailable("fire", "Hotspot and wind inputs are not connected.")


def harvest(field: FieldRecord, forecast: list[ForecastDay]) -> Result:
    """Bayan connects validated crop-specific maturity inputs here."""
    return unavailable("harvest", "Validated maturity observations are required.")


def unavailable(module: Module, message: str) -> Result:
    return Result(module=module, status="unavailable", message=message)


def assess(field: FieldRecord, weather: WeatherProvider) -> Assessment:
    forecast = weather.forecast(field)
    return Assessment(
        field_id=field.id,
        weather_source=weather.source,
        forecast=forecast,
        results=[
            crop_suitability(field, demo=weather.source == "synthetic"),
            irrigation(field, forecast),
            wildfire(field, forecast),
            harvest(field, forecast),
        ],
        arabic_review_note="نسخة تجريبية لمراجعة المهندس الزراعي فقط.",
    )
