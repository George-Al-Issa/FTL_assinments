import requests
import pandas as pd
from pathlib import Path

# Damascus coordinates
LATITUDE = 33.5138
LONGITUDE = 36.2765

START_DATE = "2000-01-01"
END_DATE = "2025-12-31"

URL = "https://archive-api.open-meteo.com/v1/archive"

PARAMS = {
    "latitude": LATITUDE,
    "longitude": LONGITUDE,
    "start_date": START_DATE,
    "end_date": END_DATE,
    "daily": [
        "temperature_2m_mean",
        "precipitation_sum",
        "et0_fao_evapotranspiration",
        "soil_moisture_0_to_100cm_mean"
    ],
    "timezone": "Asia/Damascus",
    "models": "era5_land"
}


def download_data():
    response = requests.get(
        URL,
        params=PARAMS,
        timeout=120
    )
    response.raise_for_status()

    result = response.json()
    data = pd.DataFrame(result["daily"])

    data = data.rename(columns={
        "time": "date",
        "temperature_2m_mean": "temperature_c",
        "precipitation_sum": "rainfall_mm",
        "et0_fao_evapotranspiration": "et0_mm",
        "soil_moisture_0_to_100cm_mean": "soil_moisture"
    })

    data["date"] = pd.to_datetime(data["date"])

    output_dir = Path(file).resolve().parents[1] / "data"
    output_dir.mkdir(exist_ok=True)

    output_file = output_dir / "damascus_climate.csv"
    data.to_csv(output_file, index=False)

    print("Climate data downloaded successfully.")
    print(f"Records: {len(data)}")
    print(f"Saved to: {output_file}")
    print(data.head())


if name == "main":
    download_data()
