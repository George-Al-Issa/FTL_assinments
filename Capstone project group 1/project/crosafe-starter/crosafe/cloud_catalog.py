"""Browse the official FAO object namespace and sample selected GeoTIFFs."""
from pathlib import PurePosixPath
from tempfile import NamedTemporaryFile
from urllib.parse import quote

import httpx
import rasterio

from .gaez import sample_dataset

BUCKET = "fao-gismgr-gaez-v5-data"
ROOT = "DATA/GAEZ-V5/"
BASE = f"https://storage.googleapis.com/{BUCKET}/"
LIST_URL = f"https://storage.googleapis.com/storage/v1/b/{BUCKET}/o"
MAX_BYTES = 32 * 1024 * 1024


def validate_path(name: str) -> str:
    parts = name.rstrip("/").split("/")
    if not name.startswith(ROOT) or any(part in {"", ".", ".."} for part in parts):
        raise ValueError("Expected a path within the official GAEZ v5 catalog")
    return name


def list_objects(prefix: str = ROOT, token: str = "", recursive: bool = False) -> dict:
    params = {
        "prefix": validate_path(prefix),
        "maxResults": 1000 if recursive else 250,
        "fields": "prefixes,nextPageToken,items(name,size,updated)",
    }
    if not recursive:
        params["delimiter"] = "/"
    if token:
        params["pageToken"] = token
    response = httpx.get(LIST_URL, params=params, timeout=12)
    response.raise_for_status()
    data = response.json()
    return {
        "prefixes": data.get("prefixes", []),
        "objects": [
            {**item, "url": BASE + quote(item["name"], safe="/")}
            for item in data.get("items", []) if not item["name"].endswith("/")
        ],
        "next": data.get("nextPageToken"),
    }


def sample_object(name: str, longitude: float, latitude: float) -> dict:
    name = validate_path(name)
    if PurePosixPath(name).suffix.lower() not in {".tif", ".tiff"}:
        raise ValueError("Point sampling requires a GeoTIFF")
    # Cap both advertised size and bytes actually received.
    with NamedTemporaryFile(suffix=".tif") as raster:
        with httpx.stream("GET", BASE + quote(name, safe="/"), timeout=12) as response:
            response.raise_for_status()
            size = int(response.headers.get("content-length", "0"))
            if size > MAX_BYTES:
                raise ValueError("Raster exceeds the 32 MiB interactive limit")
            received = 0
            for chunk in response.iter_bytes(64 * 1024):
                received += len(chunk)
                if received > MAX_BYTES:
                    raise ValueError("Raster exceeds the 32 MiB interactive limit")
                raster.write(chunk)
        raster.flush()
        with rasterio.open(raster.name) as dataset:
            return {
                "object": name,
                "value": sample_dataset(dataset, longitude, latitude),
                "crs": str(dataset.crs),
                "pixel_size": dataset.res,
                "unit": dataset.units[0],
            }
