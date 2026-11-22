import asyncio
import logging
from psycopg import OperationalError
from ..documents.extraction import ExtractionError, extract_evidence_batch, prepare_sources
from ..documents.retrieval import CRITERION_QUERIES, retrieve_evidence
from ..photos.analysis import PhotoAnalysis, analyze_property_photos
from ..properties.schemas import Property
from ..request_context import request_id
from .rules import compare_criteria
from .schemas import (
    AnalysisIssue, ComparisonCriteria, ComparisonEvidence, ComparisonResponse, PropertyComparisonResult,
    PropertyEvidence, TextSearch,
)

logger = logging.getLogger(__name__)

def failure_kind(error: BaseException):
    cause = error

    while cause is not None:
        if isinstance(cause, (OSError, OperationalError)):
            return "infrastructure"
        cause = cause.__cause__

    return "analysis"


async def collect_text_evidence(
    property_item: Property,
) -> tuple[ComparisonEvidence, list[AnalysisIssue]]:
    sources = {source.source_id: source for source in prepare_sources(property_item, [])}

    observations = []

    issues = []
    searches = []
    chunks_by_criterion = {}
    retrieval_statuses = {}

    for criterion in CRITERION_QUERIES:
        chunks = []
        retrieval_status = "no_documents"

        if property_item.documents:
            try:
                chunks = await retrieve_evidence(property_item.id, criterion)
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


async def collect_property_evidence(property_item: Property) -> PropertyEvidence:
    evidence, text_issues = await collect_text_evidence(property_item)

    evidence.visual, visual_issues = await collect_photo_evidence(property_item)

    return PropertyEvidence(
        propertyId=property_item.id, title=property_item.title, evidence=evidence,
        issues=[*text_issues, *visual_issues],
    )


async def collect_comparison_evidence(properties: tuple[Property, Property]) -> list[PropertyEvidence]:
    return await asyncio.gather(*(collect_property_evidence(item) for item in properties))


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
