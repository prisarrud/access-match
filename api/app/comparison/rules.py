import re
from decimal import Decimal

from ..documents.measurements import WIDTH_FACTORS, width_cm
from ..documents.coverage import describes_full_route
from ..documents.schemas import GroundedObservation
from ..photos.schemas import Element
from .schemas import ComparisonCriteria, ComparisonEvidence, CriterionResult

STEP_FREE = re.compile(r"\b(?:sem degraus|não (?:há|tem|possui|apresenta) degraus|0 degraus)\b")

STEP_PRESENT = re.compile(r"\b(?:(?:um|dois|três|[1-9]\d*) degraus?|há (?:um )?degrau)\b")

RAMP_PRESENT = re.compile(
    r"\b(?:há rampa|tem rampa|com rampa|possui rampa|rampa de acesso|rampa existente)\b"
)

RAMP_ABSENT = re.compile(r"\b(?:sem rampa|não (?:há|tem|possui|apresenta) rampa|ausência de rampa)\b")


ACCESS = re.compile(r"\b(?:entrada|acesso|trajeto|calçada)\b")


OTHER_ACCESS = re.compile(r"\b(?:garagem|serviço|lateral|outro acesso)\b")

OTHER_DOOR = re.compile(r"\b(?:porta interna|porta (?:do depósito|da sala de apoio|de serviço))\b")

def source_ids(observations: list[GroundedObservation]) -> list[str]:
    return list(dict.fromkeys(item.source_id for item in observations))

def width_labels(widths: set[Decimal]) -> str:
    return " e ".join(f'{format(width.normalize(), "f").replace(".", ",")} cm' for width in sorted(widths))

def is_entrance_width(item: GroundedObservation) -> bool:
    return (
        item.criterion == "largura" and item.scope == "entrada"
        and not OTHER_DOOR.search(item.location.casefold())
    )

def compare_width(minimum_cm: float, evidence: ComparisonEvidence) -> CriterionResult:
    minimum = Decimal(str(minimum_cm))
    minimum_label = width_labels({minimum})

    widths = [
        (item, width_cm(item.value, item.unit))
        for item in evidence.textual
        if is_entrance_width(item) and item.value is not None and item.value > 0 and item.unit in WIDTH_FACTORS
    ]

    references = source_ids([item for item, _ in widths])

    if not references:
        references = source_ids([item for item in evidence.textual if is_entrance_width(item)])

    measured = {width for item, width in widths if item.nature == "observacao_vistoria"}
    planned = {width for item, width in widths if item.nature == "especificacao_projeto"}

    if len(measured) == 1:
        width = next(iter(measured))
        meets_minimum = width >= minimum
        comparison = "atende ao" if meets_minimum else "fica abaixo do"

        justification = (
            f"A vistoria mediu {width_labels({width})} de vão livre na porta de entrada, "
            f"o que {comparison} mínimo de {minimum_label}."
        )

        if planned:
            justification += f" O memorial registra {width_labels(planned)} em projeto."

        return CriterionResult(
            criterion="largura", status="atende" if meets_minimum else "nao_atende",
            justification=justification, referenceIds=references,
        )

    if measured:
        justification = "As medidas de vistoria diferem. Confirme a largura livre da porta de entrada aplicável."
    elif planned:
        justification = f"O memorial indica {width_labels(planned)} em projeto. A largura atual precisa ser medida."
    elif widths:
        justification = "A largura declarada precisa ser confirmada na porta de entrada."
    else:
        search = next((item for item in evidence.textSearches if item.criterion == "largura"), None)
        if search and (search.retrieval == "failed" or search.extraction == "failed"):
            justification = (
                f"A análise das fontes ficou incompleta. Execute uma nova análise para verificar o mínimo de {minimum_label}."
            )
        elif search and search.retrieval == "no_results":
            justification = (
                f"A busca nos PDFs não retornou trechos para verificar o mínimo de {minimum_label}."
            )
        else:
            justification = (
                f"Para verificar o mínimo de {minimum_label}, é preciso medir o vão livre da porta de entrada."
            )
    return CriterionResult(
        criterion="largura", status="a_confirmar", justification=justification,
        referenceIds=references, toConfirm=["current_entrance_width"],
    )


def photo_evidence(evidence: ComparisonEvidence, element: Element) -> tuple[list[str], list[str]]:
    observed = []
    evaluated = []

    for photo in evidence.visual:
        if any(item.element == element for item in photo.observations):
            observed.append(photo.photo_id)
        elif any(item.element == element and item.state == "not_observed" for item in photo.assessments):
            evaluated.append(photo.photo_id)

    return observed, evaluated


def confirms_full_route(item: GroundedObservation) -> bool:
    return (
        item.nature == "observacao_vistoria" and item.scope == "percurso"
        and describes_full_route(item.quote)
    )


def compare_steps(evidence: ComparisonEvidence) -> CriterionResult:
    observations = [
        item for item in evidence.textual
        if item.criterion == "degraus" and item.scope in {"entrada", "percurso"}
    ]

    photo_steps, evaluated = photo_evidence(evidence, "degrau")

    step_free = [item for item in observations if STEP_FREE.search(item.quote.casefold())]

    listing_claims = [
        source.source_id for source in evidence.textSources
        if source.nature == "declaracao_anuncio"
        and any(ACCESS.search(sentence) and STEP_FREE.search(sentence) and not OTHER_ACCESS.search(sentence)
                for sentence in re.split(r"[.!?\n]", source.text.casefold()))
    ]

    listing_claims.extend(source_ids([item for item in step_free if item.nature == "declaracao_anuncio"]))

    inspected_steps = [
        item for item in observations
        if item.nature == "observacao_vistoria" and item not in step_free
        and ((item.unit == "degraus" and item.value is not None and item.value > 0)
             or STEP_PRESENT.search(item.quote.casefold()))
    ]

    if photo_steps or inspected_steps:
        divergence = bool(listing_claims)
        justification = "Foi observado um degrau no trecho documentado do acesso."
        if divergence:
            justification = "O anúncio declara acesso sem degraus, mas foi observado um degrau no trecho documentado."
        return CriterionResult(
            criterion="degraus", status="nao_atende", divergence=divergence,
            justification=f"{justification} A existência de outro acesso sem degraus precisa ser confirmada.",
            referenceIds=list(dict.fromkeys([*photo_steps, *source_ids(inspected_steps), *listing_claims])),
            toConfirm=["alternate_access", "route_continuity"],
        )

    full_inspection = [item for item in step_free if confirms_full_route(item)]

    if full_inspection:
        return CriterionResult(
            criterion="degraus", status="atende",
            justification="A vistoria registra um trajeto sem degraus da calçada até a porta de entrada.",
            referenceIds=source_ids(full_inspection),
        )

    if listing_claims:
        justification = "O anúncio declara acesso sem degraus. Confirme se a declaração cobre todo o trajeto."
    elif evaluated or step_free:
        justification = "Nenhum degrau foi registrado no trecho avaliado. O restante do trajeto precisa ser confirmado."
    else:
        justification = "As fontes analisadas não permitem confirmar um trajeto sem degraus."
    return CriterionResult(
        criterion="degraus", status="a_confirmar", justification=justification,
        referenceIds=list(dict.fromkeys([*listing_claims, *source_ids(observations), *evaluated])),
        toConfirm=["route_continuity", "alternate_access"],
    )


def compare_ramp(evidence: ComparisonEvidence) -> CriterionResult:
    observations = [
        item for item in evidence.textual
        if item.criterion == "rampas" and item.scope in {"entrada", "percurso"}
    ]

    photo_ramps, evaluated = photo_evidence(evidence, "rampa")

    negatives = [item for item in observations if RAMP_ABSENT.search(item.quote.casefold())]

    positives = [item for item in observations
                 if item not in negatives and RAMP_PRESENT.search(item.quote.casefold())]

    inspected_ramps = [item for item in positives if item.nature == "observacao_vistoria"]

    if photo_ramps or inspected_ramps:
        return CriterionResult(
            criterion="rampas", status="atende",
            justification="Há uma rampa no trecho documentado. A ligação com o restante do trajeto precisa ser confirmada.",
            referenceIds=list(dict.fromkeys([*photo_ramps, *source_ids(inspected_ramps)])),
            toConfirm=["route_continuity", "ramp_continuity", "ramp_slope", "ramp_width"],
        )

    full_inspection = [item for item in negatives if confirms_full_route(item)]

    if full_inspection:
        return CriterionResult(
            criterion="rampas", status="nao_atende",
            justification="A vistoria registra ausência de rampa no trajeto da calçada até a porta de entrada.",
            referenceIds=source_ids(full_inspection),
        )

    if positives:
        justification = "Uma fonte declara ou prevê uma rampa. Confirme sua presença e a ligação com o trajeto."
    elif evaluated or negatives:
        justification = "Não foi observada rampa no trecho avaliado. O restante do trajeto precisa ser confirmado."
    else:
        justification = "As fontes analisadas não permitem confirmar a presença de rampa."
    return CriterionResult(
        criterion="rampas", status="a_confirmar", justification=justification,
        referenceIds=list(dict.fromkeys([*source_ids(observations), *evaluated])),
        toConfirm=["route_continuity"],
    )


def compare_criteria(criteria: ComparisonCriteria, evidence: ComparisonEvidence) -> list[CriterionResult]:
    results = []

    if criteria.stepFree:
        results.append(compare_steps(evidence))

    if criteria.ramp:
        results.append(compare_ramp(evidence))

    if criteria.minimumClearWidthCm is not None:
        results.append(compare_width(criteria.minimumClearWidthCm, evidence))

    return results
