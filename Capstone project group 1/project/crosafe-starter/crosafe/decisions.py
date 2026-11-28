"""Decision entry points. Implementations can evolve independently of HTTP and SQL."""
from .contracts import Assessment, FieldRecord, ForecastDay, Module, Result
from .providers import WeatherProvider
from functools import lru_cache
from pathlib import Path
import math
import pandas as pd
from .predict import predict

def crop_suitability(field: FieldRecord, demo: bool) -> Result:
    """George connects a versioned GAEZ v5 suitability adapter here."""
    if demo:
        return Result(module="crop", status="demo", source="synthetic",
                      message="Illustrative ordering independent of location.",
                      crop_codes=["wheat", "barley", "lentil"])
    return unavailable("crop", "GAEZ v5 suitability layers are not configured.")
@lru_cache(maxsize=1)
def load_drought_data():
    """Load prepared NASA POWER data."""

    data_path = Path(__file__).resolve().parent / "CroSafe_Predictions.csv"

    if not data_path.exists():
        raise FileNotFoundError(
            f"Drought data file not found: {data_path}"
        )

    data = pd.read_csv(data_path)

    required = [
        "LAT", "LON", "DATE",
        "PREDICTED_DROUGHT_CLASS"
    ]

    missing = [col for col in required if col not in data.columns]

    if missing:
        raise ValueError(f"Missing CSV columns: {missing}")

    data["DATE"] = pd.to_datetime(data["DATE"], errors="coerce")
    data = data.dropna(subset=["DATE", "LAT", "LON"])

    if data.empty:
        raise ValueError("No valid NASA records found.")

    return data


def distance_km(lat1, lon1, lat2, lon2):
    """Calculate geographical distance using Haversine formula."""

    radius = 6371

    lat1, lon1, lat2, lon2 = map(
        math.radians,
        [lat1, lon1, lat2, lon2]
    )

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1)
        * math.cos(lat2)
        * math.sin(dlon / 2) ** 2
    )

    return 2 * radius * math.asin(math.sqrt(a))

def irrigation(field: FieldRecord, forecast: list[ForecastDay]) -> Result:
    """Predict drought class using the CroSafe XGBoost model."""

    try:
        data = load_drought_data()

        # Find available NASA grid locations.
        locations = data[["LAT", "LON"]].drop_duplicates()

        # Select the nearest NASA location.
        locations = locations.copy()

        locations["DISTANCE_KM"] = locations.apply(
            lambda row: distance_km(
                field.latitude,
                field.longitude,
                row["LAT"],
                row["LON"]
            ),
            axis=1
        )

        nearest = locations.loc[
            locations["DISTANCE_KM"].idxmin()
        ]

        # Get the latest available record for that location.
        site_data = data[
            (data["LAT"] == nearest["LAT"])
            & (data["LON"] == nearest["LON"])
        ].copy()

        latest_record = (
            site_data.sort_values("DATE")
            .tail(1)
            .copy()
        )

        # Run the trained model through the public interface.
        prediction = predict(latest_record)

        drought_class = prediction["drought_class"]

        date_used = latest_record.iloc[0]["DATE"].strftime("%Y-%m")

        return Result(
            module="irrigation",
            status="ready",
            source="CroSafe XGBoost + NASA POWER",
            message=(
                f"Drought prediction: {drought_class}. "
                f"Latest available data: {date_used}. "
                f"Nearest NASA grid distance: "
                f"{nearest['DISTANCE_KM']:.1f} km."
            ),
            drought_class=drought_class
        )

    except (FileNotFoundError, ValueError, KeyError) as error:
        return unavailable(
            "irrigation",
            f"Drought prediction unavailable: {error}"
        )   


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
