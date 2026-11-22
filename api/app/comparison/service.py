import asyncio
import logging
from ..documents.context import DocumentContextProvider
from ..documents.extraction import extract_evidence_batch, prepare_sources
from ..documents.schemas import Criterion, ExtractionError
from ..photos.analysis import analyze_property_photos
from ..photos.schemas import PhotoAnalysis
from ..properties.schemas import Property, PropertyCatalog
from ..request_context import request_id
from .store import ActiveComparison, ComparisonStore
from .questions import generate_questions
from .rules import compare_criteria
from .schemas import (
    AnalysisIssue, ComparisonCriteria, ComparisonEvidence, ComparisonResponse, PropertyComparisonResult,
    PropertyEvidence, TextSearch, ComparisonRequest, QuestionsRequest, QuestionsResponse,
)

logger = logging.getLogger(__name__)
EVIDENCE_CRITERIA: tuple[Criterion, ...] = ("largura", "degraus", "rampas")

def failure_kind(error: BaseException):
    cause = error

    while cause is not None:
        if isinstance(cause, OSError):
            return "infrastructure"
        cause = cause.__cause__

    return "analysis"


async def collect_text_evidence(
    property_item: Property, provider: DocumentContextProvider,
) -> tuple[ComparisonEvidence, list[AnalysisIssue]]:
    sources = {source.source_id: source for source in prepare_sources(property_item, [])}

    observations = []

    issues = []
    searches = []
    chunks_by_criterion = {}
    retrieval_statuses = {}

    for criterion in EVIDENCE_CRITERIA:
        chunks = []
        retrieval_status = "no_documents"

        if property_item.documents:
            try:
                chunks = await provider(property_item, criterion)
            except Exception as exc:
                retrieval_status = "failed"
                logger.warning("Evidence retrieval failed request_id=%s property_id=%s criterion=%s error_type=%s",
                               request_id(), property_item.id, criterion, type(exc).__name__)
                issues.append(AnalysisIssue(
                    stage="retrieval", kind=failure_kind(exc), criterion=criterion,
                    message="Não foi possível consultar os trechos dos PDFs para este critério.",
                ))
            else:
                retrieval_status = "found" if chunks else "no_results"

        chunks_by_criterion[criterion] = chunks
        retrieval_statuses[criterion] = retrieval_status

    try:
        extractions = await extract_evidence_batch(property_item, chunks_by_criterion)
    except Exception as exc:
        extractions = dict.fromkeys(chunks_by_criterion, exc)

    for criterion, retrieval_status in retrieval_statuses.items():
        extraction = extractions[criterion]
        if isinstance(extraction, Exception):
            extraction_status = "failed"
            if isinstance(extraction, ExtractionError):
                sources.update((source.source_id, source) for source in extraction.sources)

            logger.warning("Evidence extraction failed request_id=%s property_id=%s criterion=%s error_type=%s",
                           request_id(), property_item.id, criterion, type(extraction).__name__)

            issues.append(AnalysisIssue(
                stage="extraction", kind=failure_kind(extraction), criterion=criterion,
                message="Não foi possível extrair observações textuais para este critério.",
            ))
        else:
            extraction_status = "found" if extraction.observations else "no_results"
            observations.extend(extraction.observations)
            sources.update((source.source_id, source) for source in extraction.sources)
        searches.append(TextSearch(criterion=criterion, retrieval=retrieval_status, extraction=extraction_status))

    return ComparisonEvidence(textSources=list(sources.values()), textual=observations, textSearches=searches), issues


async def collect_photo_evidence(
    property_item: Property,
) -> tuple[list[PhotoAnalysis], list[AnalysisIssue]]:
    if not property_item.photos:
        return [], []

    try:
        analysis = await analyze_property_photos(property_item.id)
    except Exception as exc:
        logger.warning("Visual analysis failed request_id=%s property_id=%s error_type=%s",
                       request_id(), property_item.id, type(exc).__name__)
        return [], [AnalysisIssue(
            stage="visual", kind=failure_kind(exc), message="Não foi possível analisar as fotos deste imóvel.",
        )]

    photos = []
    issues = []

    for photo in analysis.photos:
        if photo.status == "pending":
            kind = "analysis"
            message = "Uma foto do acesso ficou sem análise."
            if photo.error in {"missing_file", "unreadable_image"}:
                kind = "source_file"
                message = "O arquivo desta foto não está disponível para análise."
            elif photo.infrastructure_failure:
                kind = "infrastructure"
                message = "O serviço de análise visual estava indisponível para esta foto."

            issues.append(AnalysisIssue(
                stage="visual", kind=kind, photoId=photo.photo_id, message=message,
            ))

        photos.append(photo.model_copy(update={"detail": None}))

    return photos, issues


async def collect_property_evidence(property_item: Property, provider: DocumentContextProvider) -> PropertyEvidence:
    evidence, text_issues = await collect_text_evidence(property_item, provider)

    evidence.visual, visual_issues = await collect_photo_evidence(property_item)

    return PropertyEvidence(
        propertyId=property_item.id, title=property_item.title, evidence=evidence,
        issues=[*text_issues, *visual_issues],
    )


async def collect_comparison_evidence(
    properties: tuple[Property, Property], provider: DocumentContextProvider,
) -> list[PropertyEvidence]:
    return await asyncio.gather(*(collect_property_evidence(item, provider) for item in properties))


def calculate_comparison(
    comparison_id: str, properties: list[PropertyEvidence], criteria: ComparisonCriteria,
) -> ComparisonResponse:
    return ComparisonResponse(comparisonId=comparison_id, properties=[
        PropertyComparisonResult(
            propertyId=item.propertyId, title=item.title, evidence=item.evidence, issues=item.issues,
            results=compare_criteria(criteria, item.evidence),
        )
        for item in properties
    ])

class UnknownProperties(ValueError):
    pass


class ComparisonUnavailable(ValueError):
    pass


async def create_comparison(
    catalog: PropertyCatalog, store: ComparisonStore, payload: ComparisonRequest,
    provider: DocumentContextProvider,
) -> ComparisonResponse:
    properties = {item.id: item for item in catalog.properties}
    first, second = (properties.get(property_id) for property_id in payload.propertyIds)
    if first is None or second is None:
        raise UnknownProperties
    evidence = await collect_comparison_evidence((first, second), provider)
    return calculate_comparison(store.save(evidence), evidence, payload.criteria)


def require_active_comparison(
    store: ComparisonStore, comparison_id: str, payload: ComparisonRequest,
) -> ActiveComparison:
    active = store.get(comparison_id)
    if active is None or tuple(item.propertyId for item in active.properties) != payload.propertyIds:
        raise ComparisonUnavailable
    return active


def recalculate_comparison(
    store: ComparisonStore, comparison_id: str, payload: ComparisonRequest,
) -> ComparisonResponse:
    active = require_active_comparison(store, comparison_id, payload)
    return calculate_comparison(comparison_id, active.properties, payload.criteria)


async def create_questions(
    store: ComparisonStore, comparison_id: str, payload: QuestionsRequest,
) -> QuestionsResponse:
    active = require_active_comparison(store, comparison_id, payload)
    property_item = next(item for item in active.properties if item.propertyId == payload.propertyId)
    questions = await generate_questions(property_item, payload.criteria)
    require_active_comparison(store, comparison_id, payload)
    return QuestionsResponse(propertyId=property_item.propertyId, questions=questions)
