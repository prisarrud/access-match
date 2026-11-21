from fastapi import APIRouter, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from ..properties.schemas import PropertyCatalog
from .schemas import ComparisonRequest, ComparisonResponse
from .service import calculate_comparison, collect_comparison_evidence
from .store import ComparisonStore

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

    evidence = await collect_comparison_evidence((first, second))

    store: ComparisonStore = request.app.state.comparisons

    comparison_id = store.save(evidence)

    return calculate_comparison(comparison_id, evidence, payload.criteria)


@router.post("/{comparison_id}/recalculate")
async def recalculate_comparison(
    comparison_id: str, payload: ComparisonRequest, request: Request,
) -> ComparisonResponse:
    store: ComparisonStore = request.app.state.comparisons

    active = store.get(comparison_id)

    if active is None or tuple(item.propertyId for item in active.properties) != payload.propertyIds:
        raise HTTPException(
            status_code=410, detail="Esta análise expirou ou não está disponível para estes imóveis.",
        )

    return calculate_comparison(comparison_id, active.properties, payload.criteria)
