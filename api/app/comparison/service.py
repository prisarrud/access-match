import asyncio
import logging
from psycopg import OperationalError
from ..documents.extraction import Criterion, ExtractionError, extract_evidence, prepare_sources
from ..documents.retrieval import retrieve_evidence
from ..photos.analysis import PhotoAnalysis, analyze_property_photos
from ..properties.schemas import Property
from .rules import compare_criteria
from .schemas import AnalysisIssue, ComparisonCriteria, ComparisonEvidence, PropertyComparisonResult

logger = logging.getLogger(__name__)

def failure_kind(error: BaseException):
    cause = error

    while cause is not None:
        if isinstance(cause, (OSError, OperationalError)):
            return "infrastructure"
        cause = cause.__cause__

    return "analysis"


async def collect_text_evidence(
    property_item: Property, criteria: list[Criterion],
) -> tuple[ComparisonEvidence, list[AnalysisIssue]]:
    sources = {source.source_id: source for source in prepare_sources(property_item, [])}

    observations = []

    issues = []

    for criterion in criteria:
        chunks = []

        if property_item.documents:
            try:
                chunks = await retrieve_evidence(property_item.id, criterion)
            except Exception as exc:
                logger.warning("Evidence retrieval failed for %s / %s", property_item.id, criterion, exc_info=True)
                issues.append(AnalysisIssue(
                    stage="retrieval", kind=failure_kind(exc), criterion=criterion,
                    message="Não foi possível consultar os trechos dos PDFs para este critério.",
                ))

        try:
            extraction = await extract_evidence(property_item, criterion, chunks)
        except Exception as exc:
            if isinstance(exc, ExtractionError):
                sources.update((source.source_id, source) for source in exc.sources)

            logger.warning("Evidence extraction failed for %s / %s", property_item.id, criterion, exc_info=True)

            issues.append(AnalysisIssue(
                stage="extraction", kind=failure_kind(exc), criterion=criterion,
                message="Não foi possível extrair observações textuais para este critério.",
            ))
        else:
            observations.extend(extraction.observations)
            sources.update((source.source_id, source) for source in extraction.sources)

    return ComparisonEvidence(textSources=list(sources.values()), textual=observations), issues


async def collect_photo_evidence(
    property_item: Property, criteria: ComparisonCriteria,
) -> tuple[list[PhotoAnalysis], list[AnalysisIssue]]:
    if not property_item.photos or not (criteria.stepFree or criteria.ramp):
        return [], []

    try:
        analysis = await analyze_property_photos(property_item.id)
    except Exception as exc:
        logger.warning("Visual analysis failed for %s", property_item.id, exc_info=True)
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


async def compare_property(property_item: Property, criteria: ComparisonCriteria) -> PropertyComparisonResult:
    evidence, text_issues = await collect_text_evidence(property_item, criteria.requested())

    evidence.visual, visual_issues = await collect_photo_evidence(property_item, criteria)

    return PropertyComparisonResult(
        propertyId=property_item.id, title=property_item.title,
        evidence=evidence, results=compare_criteria(criteria, evidence),
        issues=[*text_issues, *visual_issues],
    )


async def compare_properties(
    properties: tuple[Property, Property], criteria: ComparisonCriteria,
) -> list[PropertyComparisonResult]:
    return await asyncio.gather(*(compare_property(item, criteria) for item in properties))
