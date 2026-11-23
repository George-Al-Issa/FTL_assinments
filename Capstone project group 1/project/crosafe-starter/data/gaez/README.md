# FAO/IIASA GAEZ v5 pilot data

This directory contains two unchanged official wheat suitability GeoTIFFs and their source metadata. The layer manifest adds CroSafe display labels and links to the original Google Cloud objects.

- Variable: RES05-SIX, wheat (WHE), AgERA5 historical 2001–2020.
- Scenarios: rain-fed low input (LRLM) and irrigated low input (LILM).
- Grid: EPSG:4326, 5 arc-minutes, 4320 × 2160. The source rasters flag 0 as nodata.
- The dashboard displays source raster values as published. Confirm the source legend before interpreting values as grades or converting them to another scale.

Source: Food and Agriculture Organization of the United Nations (FAO) and International Institute for Applied Systems Analysis (IIASA), Global Agro-Ecological Zoning v5.
[Model documentation](https://github.com/un-fao/gaezv5/wiki) · [FAO catalog](https://data.fao.org/catalog/dataset/gaez-v5-master-config/resource/31abf121-1644-4473-8c1b-bfec83112749)

Run `python scripts/fetch_gaez.py` from the project root to refresh the original files. To add other crops or scenarios, select the exact raster from the official variable catalog and add a row to `layers.json`. Restart the API to reload the manifest. Preserve the source reference, scenario, units and interpretation for every layer.
