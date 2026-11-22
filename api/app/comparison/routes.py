import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from ..properties.schemas import PropertyCatalog
from .questions import QuestionsError, generate_questions
from .schemas import ComparisonRequest, ComparisonResponse, QuestionsRequest, QuestionsResponse
from .service import calculate_comparison, collect_comparison_evidence
from .store import ActiveComparison, ComparisonStore

logger = logging.getLogger(__name__)

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


def require_active_comparison(
    store: ComparisonStore, comparison_id: str, payload: ComparisonRequest,
) -> ActiveComparison:
    active = store.get(comparison_id)

    if active is None or tuple(item.propertyId for item in active.properties) != payload.propertyIds:
        raise HTTPException(
            status_code=410, detail="Esta análise expirou ou não está disponível para estes imóveis.",
        )
    return active


@router.post("/{comparison_id}/recalculate")
async def recalculate_comparison(
    comparison_id: str, payload: ComparisonRequest, request: Request,
) -> ComparisonResponse:
    active = require_active_comparison(request.app.state.comparisons, comparison_id, payload)

    return calculate_comparison(comparison_id, active.properties, payload.criteria)


@router.post("/{comparison_id}/questions")
async def create_questions(comparison_id: str, payload: QuestionsRequest, request: Request) -> QuestionsResponse:
    store: ComparisonStore = request.app.state.comparisons
    active = require_active_comparison(store, comparison_id, payload)
    property_item = next(item for item in active.properties if item.propertyId == payload.propertyId)

    try:
        questions = await generate_questions(property_item, payload.criteria)
    except QuestionsError as exc:
        logger.warning("Question generation failed for %s", property_item.propertyId, exc_info=True)
        raise HTTPException(status_code=503, detail="Não foi possível gerar as perguntas.") from exc

    require_active_comparison(store, comparison_id, payload)
    return QuestionsResponse(propertyId=property_item.propertyId, questions=questions)
