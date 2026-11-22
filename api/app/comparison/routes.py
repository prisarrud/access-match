import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from starlette.exceptions import HTTPException as StarletteHTTPException
from ..request_context import request_context, request_id
from .questions import QuestionsError
from .schemas import ComparisonRequest, ComparisonResponse, QuestionsRequest, QuestionsResponse
from . import service

logger = logging.getLogger(__name__)

class ComparisonRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def handle(request: Request):
            with request_context(request.headers.get("X-Request-ID")) as identifier:
                try:
                    response = await handler(request)
                except RequestValidationError as error:
                    detail = [
                        {key: item[key] for key in ("loc", "msg", "type")}
                        for item in error.errors()
                    ]
                    response = JSONResponse(status_code=422, content={"detail": detail})
                except StarletteHTTPException as error:
                    error.headers = {**(error.headers or {}), "X-Request-ID": identifier}
                    raise
                response.headers["X-Request-ID"] = identifier
                return response

        return handle


router = APIRouter(prefix="/comparisons", tags=["comparisons"], route_class=ComparisonRoute)


@router.post("")
async def create_comparison(payload: ComparisonRequest, request: Request) -> ComparisonResponse:
    try:
        return await service.create_comparison(
            request.app.state.catalog, request.app.state.comparisons, payload, request.app.state.document_context,
        )
    except service.UnknownProperties:
        raise HTTPException(status_code=404, detail="Um ou mais imóveis da seleção não estão no catálogo.") from None


def unavailable_error() -> HTTPException:
    return HTTPException(status_code=410, detail="Esta análise expirou ou não está disponível para estes imóveis.")


@router.post("/{comparison_id}/recalculate")
async def recalculate_comparison(
    comparison_id: str, payload: ComparisonRequest, request: Request,
) -> ComparisonResponse:
    try:
        return service.recalculate_comparison(request.app.state.comparisons, comparison_id, payload)
    except service.ComparisonUnavailable:
        raise unavailable_error() from None


@router.post("/{comparison_id}/questions")
async def create_questions(comparison_id: str, payload: QuestionsRequest, request: Request) -> QuestionsResponse:
    try:
        return await service.create_questions(request.app.state.comparisons, comparison_id, payload)
    except service.ComparisonUnavailable:
        raise unavailable_error() from None
    except QuestionsError as exc:
        logger.warning("Question generation failed request_id=%s property_id=%s error_type=%s",
                       request_id(), payload.propertyId, type(exc).__name__)
        raise HTTPException(status_code=503, detail="Não foi possível gerar as perguntas.") from exc
