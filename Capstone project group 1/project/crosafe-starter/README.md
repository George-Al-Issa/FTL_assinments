# CroSafe

FastAPI and PostGIS power a customer planting dashboard and a Directorate workspace. Docker Compose is the runtime. Colab can be used for experimentation and training.

## Start

Copy `.env.example` to `.env` and set distinct test passwords. Then run:

```sh
docker compose up --build -d
docker compose logs -f api
```

Open [CroSafe](http://127.0.0.1:8000/). Sign in as the customer, record a synthetic Wheat planting (latitude 35.1234, longitude 37.1234, area 2.5 ha), and sign out. Sign in as admin to review the record in Analysis, Planting map, and Notifications.

### Updating an existing Docker volume

Keep the same Compose project and database volume. Run the normal startup
command from the updated project directory:

```sh
docker compose up --build -d
```

Compose runs the idempotent SQL migrations after PostgreSQL is ready and waits
for success before starting the API. If setup fails, inspect
`docker compose logs migrate`. For an already running copy of the earlier
Operations release, you can apply its mounted migration directly:

```sh
docker compose exec db psql -U crosafe -d crosafe -v ON_ERROR_STOP=1 -f /docker-entrypoint-initdb.d/40-operations.sql
```

Existing planting records and provider settings are preserved.

## Admin navigation

| Page | Operations |
| --- | --- |
| Analysis | Date-filtered totals, crop breakdown, monthly activity, optional Syria-level World Bank indicator |
| Planting map | Customer-reported PostGIS locations, crop filter, paginated records, and local GAEZ sampling |
| GAEZ catalog | Browse every official collection, paginate objects, open source downloads, and inspect a selected GeoTIFF |
| Notifications | See new-planting notifications and send a targeted or broadcast in-app notice |
| API configuration | Save weather mode, forecast days, credential usage, GAEZ access and World Bank indicator. Check each connection. |

Accounts are configured in the environment. The browser signs in with an eight-hour session stored as a server-side token hash. Signing out invalidates that session. Authorized scripts can still send Basic credentials explicitly. Notification channels are in-app. A customer homescreen includes their own planting records and inbox. Crop, irrigation, wildfire, and harvest decision hooks remain available in the separate assessment API, with synthetic or unavailable outputs where a model is absent.

## GAEZ v5

The official FAO/IIASA cloud namespace is the data catalog. The app browses the full namespace on demand, with seven top-level collections available at the time of verification. Two official wheat rasters are bundled for local testing. The UI can read official GeoTIFFs up to 32 MiB per interactive sample. Larger files remain available from their source links. Source values follow their original grid and metadata. Check the dataset's units, scenario and legend before interpretation. Reported planting coordinates and acreage come from PostGIS.

After installing Python requirements, generate the complete metadata inventory or scope it to a collection:

```sh
python -m scripts.index_gaez data/gaez_inventory.ndjson
python -m scripts.index_gaez data/wheat_context.ndjson --prefix DATA/GAEZ-V5/MAPSET/RES05-SIX/
```

The inventory lists metadata and official source URLs. It does not copy raster bytes. The full run can be large and take time. Use `python scripts/fetch_gaez.py` to refresh the two bundled rasters.

[FAO/IIASA GAEZ v5 documentation](https://github.com/un-fao/gaezv5/wiki)

## Verification and deployment

Export `CROSAFE_ADMIN_USER` and `CROSAFE_ADMIN_PASSWORD` in your shell before running:

```sh
python examples/smoke.py
python examples/performance.py --requests 100 --concurrency 10
```

The smoke script expects synthetic weather mode. Set `CROSAFE_TEST_URL` for a different smoke target. See [TEAM_TASKS.md](TEAM_TASKS.md) for performance assignments.

For shared test access, place the API behind authenticated HTTPS or a private VPN, set `CROSAFE_SECURE_COOKIE=true` for HTTPS, and rate-limit the sign-in endpoint at the proxy. Use synthetic farm records. Keep `.env` private. The API configuration displays whether `OPEN_METEO_API_KEY` is set. The secret is supplied by the deployment environment. Basic credentials on an HTTP endpoint are suitable only for loopback testing. A production rollout requires managed identity and farm data controls.

Carried forward the `libexpat1` Docker runtime dependency. A mounted folder provides the local GAEZ files. Docker Compose keeps PostGIS on the internal service network and the API binds to loopback on the host.

## Farmer planning and regional limits

1. Sign in as a farmer. Open My fields, drop a map pin or enter coordinates,
   then save the field and water source. The governorate is resolved with PostGIS
   using 14 geoBoundaries polygons. Pins outside the supported boundaries or
   matching multiple regions are rejected. The dashboard opens in Arabic and
   includes an English switch. Some legacy admin pages and API errors use English.
2. Pick a field and intended planting date. The report shows up to three options,
   with modeled GAEZ context where configured, demo harvest tonnes, suggested
   moisture-check intervals for irrigated fields, and fertilizer and pest guidance.
   Irrigation scheduling needs field moisture, crop stage and local calibration.
3. Confirm a crop to record it. Viewing the report does not use quota. Quota is
   checked again in the same transaction as confirmation. Replaying a saved
   confirmation ID is safe. This prototype permits one planting per saved field
   per planting date. Use separately measured field locations/areas for separate plots.
4. In the admin Crop limits tab, choose the governorate, crop, inclusive season
   dates, and cap in projected tonnes. Saving the same season updates the cap.
   Overlapping seasons for a single crop and region are rejected. A crop is blocked
   when the cap is reached or adding that field would exceed it. Changing limits
   preserves previous plantings. Uncapped crops are still eligible.
5. Farmers can check the forecast for a saved field. Admins can configure heat,
   frost, heavy rain and dry-spell thresholds and screen a selected governorate.
   The screen reports dates, registered fields, exposed hectares, failed lookups
   and coverage. It uses the latest recorded planting per field on or before
   the selected date as an exposure proxy, up to 20 fields per check. When the
   area crosses the configured threshold, the event is flagged for regional
   review. Use Recheck and notify farmers to send targeted in-app notices based
   on refreshed results. Repeat publishing deduplicates by field, hazard, window
   and forecast source. Forecast screening and publishing are on demand.

The quota uses new confirmations with saved projections. Legacy planting rows
remain visible in the original analysis and maps. They lack a verified crop
code, season and projection, so they do not consume quota. The legacy
POST /v1/customer/plantings route was replaced by /v1/planning/confirm to
apply quota on every new write. The legacy GET route remains available.

`CROSAFE_MODE=fixture` is the starting weather mode. It uses synthetic weather.
Open-Meteo can be enabled from API configuration. The default yield adapter
`DemoYieldModel` multiplies illustrative tonnes per hectare by saved field size.
It is wired in the FastAPI lifespan through the `YieldModel` protocol.
Bundled GAEZ wheat suitability accompanies the crop report as source context.
An optional validated soil raster can be mounted with manifest ID `soil-type`.
Values are reported as source codes until a verified legend is available.
The team still needs calibrated crop/soil/climate inputs, validated yield and
damage models, and region-specific irrigation and agronomic rules.
No payments are configured.

Boundary data is the geoBoundaries gbOpen Syria ADM1 simplified export,
pinned at commit 9469f09, with Arabic display labels added by CroSafe.
See [boundary source and license](data/regions/README.md).
