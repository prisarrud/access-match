from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator

from ..documents.extraction import Criterion, EvidenceSource, GroundedObservation
from ..photos.analysis import Confirmation, PhotoAnalysis
from ..properties.schemas import NonBlankText


class ComparisonCriteria(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stepFree: StrictBool = False
    ramp: StrictBool = False
    minimumClearWidthCm: float | None = Field(default=None, gt=0, allow_inf_nan=False, strict=True)

    def requested(self) -> list[Criterion]:
        criteria: list[Criterion] = []
        if self.stepFree:
            criteria.append("degraus")
        if self.ramp:
            criteria.append("rampas")
        if self.minimumClearWidthCm is not None:
            criteria.append("largura")
        return criteria

    @model_validator(mode="after")
    def validate_requested(self) -> Self:
        if not self.requested():
            raise ValueError("Selecione pelo menos um critério.")
        return self


class ComparisonRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    propertyIds: tuple[NonBlankText, NonBlankText]
    criteria: ComparisonCriteria

    @model_validator(mode="after")
    def validate_distinct_properties(self) -> Self:
        if self.propertyIds[0] == self.propertyIds[1]:
            raise ValueError("Selecione dois imóveis diferentes.")
        return self


class AnalysisIssue(BaseModel):
    stage: Literal["retrieval", "extraction", "visual"]
    kind: Literal["infrastructure", "analysis", "source_file"]
    message: str
    criterion: Criterion | None = None
    photoId: str | None = None


class ComparisonEvidence(BaseModel):
    textSources: list[EvidenceSource] = Field(default_factory=list)
    textual: list[GroundedObservation] = Field(default_factory=list)
    visual: list[PhotoAnalysis] = Field(default_factory=list)


class CriterionResult(BaseModel):
    criterion: Criterion
    status: Literal["atende", "nao_atende", "a_confirmar"]
    justification: str
    referenceIds: list[str] = Field(default_factory=list)
    divergence: bool = False
    toConfirm: list[Confirmation | Literal["current_entrance_width"]] = Field(default_factory=list)


class PropertyComparisonResult(BaseModel):
    propertyId: str
    title: str
    evidence: ComparisonEvidence
    results: list[CriterionResult]
    issues: list[AnalysisIssue]


class ComparisonResponse(BaseModel):
    properties: list[PropertyComparisonResult]
