from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ..properties.schemas import NonBlankText, RelativeFile


Criterion = Literal["largura", "degraus", "rampas"]

Nature = Literal["declaracao_anuncio", "especificacao_projeto", "observacao_vistoria"]

Unit = Literal["mm", "cm", "m", "%", "graus", "degraus"]

class EvidenceSource(BaseModel):
    source_id: str
    property_id: str
    nature: Nature
    text: str
    document_id: str | None = None
    document_type: Literal["memorial", "vistoria"] | None = None
    document_date: date | None = None
    source_path: RelativeFile | None = None
    page: int | None = Field(default=None, gt=0)
    chunk_index: int | None = Field(default=None, gt=0)

class ExtractionError(RuntimeError):
    """The extraction failed or returned an invalid observation."""

    sources: tuple[EvidenceSource, ...] = ()

class Observation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    criterion: Criterion
    location: NonBlankText
    scope: Literal["entrada", "percurso", "outra_porta", "ambiguo"]
    value: float | None = Field(allow_inf_nan=False, strict=True)
    unit: Unit | None
    nature: Nature
    source_id: NonBlankText
    quote: NonBlankText

class ModelExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observations: list[Observation]

class GroundedObservation(Observation):
    source: EvidenceSource

class ExtractionResult(BaseModel):
    property_id: str
    criterion: Criterion
    status: Literal["evidence_found", "insufficient_evidence"]
    sources: list[EvidenceSource]
    observations: list[GroundedObservation]
