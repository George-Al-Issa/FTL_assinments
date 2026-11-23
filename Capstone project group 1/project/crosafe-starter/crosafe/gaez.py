"""Read point values from mounted, catalogued GAEZ v5 GeoTIFF layers."""
import json
import math
from pathlib import Path

import rasterio
from pydantic import BaseModel, Field
from rasterio.warp import transform


class Layer(BaseModel):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]+$")
    filename: str = Field(pattern=r"^[a-zA-Z0-9._-]+[.]tif(f)?$")
    title: str
    source_url: str
    units: str
    scenario: str
    interpretation: str


class GaezCatalog:
    def __init__(self, directory: Path):
        self.directory = directory
        manifest = directory / "layers.json"
        layers = json.loads(manifest.read_text(encoding="utf-8")) if manifest.is_file() else []
        self.layers = {layer.id: layer for layer in map(Layer.model_validate, layers)}
        if len(self.layers) != len(layers):
            raise ValueError("Duplicate GAEZ layer IDs")

    def sample(self, layer: Layer, longitude: float, latitude: float) -> float | None:
        with rasterio.open(self.directory / layer.filename) as dataset:
            return sample_dataset(dataset, longitude, latitude)


def sample_dataset(dataset, longitude: float, latitude: float) -> float | None:
    x, y = transform("EPSG:4326", dataset.crs, [longitude], [latitude])
    row, column = dataset.index(x[0], y[0])
    if not (0 <= row < dataset.height and 0 <= column < dataset.width):
        return None
    value = next(dataset.sample([(x[0], y[0])], indexes=1, masked=True))
    if value.mask.any() or not math.isfinite(value[0]):
        return None
    return float(value[0])
