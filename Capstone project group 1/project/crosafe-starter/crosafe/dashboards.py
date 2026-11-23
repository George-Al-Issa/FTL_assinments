"""Dashboard pages and role-scoped planting and map endpoints."""
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, RedirectResponse
from rasterio.errors import RasterioError

from .accounts import Account, admin, customer, identify
from .gaez import Layer
from .plantings import Planting

router = APIRouter()
WEB = Path(__file__).with_name("web")


@router.get("/", include_in_schema=False)
def dashboard(request: Request):
    try:
        account = identify(request, None)
    except HTTPException as error:
        if error.status_code != 401:
            raise
        return RedirectResponse("/login", status_code=303)
    return FileResponse(WEB / f"{account.role}.html", headers={"Cache-Control": "no-store"})


@router.get("/login", include_in_schema=False)
def login_page():
    return FileResponse(WEB / "login.html", headers={"Cache-Control": "no-store"})


@router.get("/v1/customer/plantings")
def own_plantings(
    request: Request, limit: int = Query(250, ge=1, le=250),
    offset: int = Query(0, ge=0), account: Account = Depends(customer),
) -> list[Planting]:
    return request.app.state.plantings.list(owner=account.username, limit=limit, offset=offset)


@router.get("/v1/admin/plantings.geojson", dependencies=[Depends(admin)])
def map_plantings(
    request: Request, limit: int = Query(250, ge=1, le=250), offset: int = Query(0, ge=0),
) -> dict:
    records = request.app.state.plantings.list(limit=limit, offset=offset)
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": str(record.id),
                "geometry": {"type": "Point", "coordinates": [record.longitude, record.latitude]},
                "properties": record.model_dump(
                    mode="json", exclude={"id", "longitude", "latitude"},
                ),
            }
            for record in records
        ],
    }


@router.get("/v1/admin/gaez/layers", dependencies=[Depends(admin)])
def gaez_layers(request: Request) -> list[Layer]:
    return list(request.app.state.gaez.layers.values())


@router.get("/v1/admin/gaez/sample", dependencies=[Depends(admin)])
def gaez_sample(
    request: Request, layer_id: str, longitude: float = Query(ge=-180, le=180),
    latitude: float = Query(ge=-90, le=90),
) -> dict:
    catalog = request.app.state.gaez
    layer = catalog.layers.get(layer_id)
    if layer is None:
        raise HTTPException(404, "GAEZ layer not configured")
    try:
        return {"layer": layer, "value": catalog.sample(layer, longitude, latitude)}
    except (RasterioError, ValueError) as error:
        raise HTTPException(503, "GAEZ layer is unavailable") from error
