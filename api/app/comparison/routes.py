from fastapi import APIRouter, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from ..properties.schemas import PropertyCatalog
from .schemas import ComparisonRequest, ComparisonResponse
from .service import compare_properties

class ComparisonRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def handle(request: Request):
            try:
                return await handler(request)
            except RequestValidationError as error:
                detail = [
                    {key: item[key] for key in ("loc", "msg", "type")}
                    for item in error.errors()
                ]
                return JSONResponse(status_code=422, content={"detail": detail})

        return handle


router = APIRouter(prefix="/comparisons", tags=["comparisons"], route_class=ComparisonRoute)


@router.post("")
async def create_comparison(payload: ComparisonRequest, request: Request) -> ComparisonResponse:
    catalog: PropertyCatalog = request.app.state.catalog

    properties = {item.id: item for item in catalog.properties}

    first, second = (properties.get(property_id) for property_id in payload.propertyIds)

    if first is None or second is None:
        raise HTTPException(status_code=404, detail="Um ou mais imóveis da seleção não estão no catálogo.")

    return ComparisonResponse(properties=await compare_properties((first, second), payload.criteria))
