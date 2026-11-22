from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ..properties.schemas import RelativeFile


Element = Literal["degrau", "rampa"]

ElementState = Literal["observed", "not_observed", "not_assessable"]

Part = Literal["calcada", "portao", "trajeto", "patamar", "porta_entrada"]

PartState = Literal["visible", "partial", "out_of_frame", "indeterminate"]

Location = Literal[
    "calcada", "portao", "trajeto", "patamar", "porta_entrada",
    "entre_calcada_e_patamar", "entre_trajeto_e_patamar",
]

Confirmation = Literal[
    "route_continuity", "alternate_access", "ramp_slope", "ramp_width", "ramp_continuity",
]

class VisualFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    element: Element
    location: Location | None

class VisibleParts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    calcada: PartState
    portao: PartState
    trajeto: PartState
    patamar: PartState
    porta_entrada: PartState

class ModelAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observations: list[VisualFinding]

class PhotoObservation(VisualFinding):
    photo_id: str

class PhotoCoverage(BaseModel):
    framing: Literal["partial", "indeterminate"]
    parts: VisibleParts
    unverified_parts: list[Part]

class ElementAssessment(BaseModel):
    element: Element
    state: ElementState

class PhotoAnalysis(BaseModel):
    photo_id: str
    source_path: RelativeFile
    status: Literal["analyzed", "pending"]
    observations: list[PhotoObservation] = Field(default_factory=list)
    coverage: PhotoCoverage | None = None
    assessments: list[ElementAssessment] = Field(default_factory=list)
    to_confirm: list[Confirmation] = Field(default_factory=list)
    error: Literal["missing_file", "unreadable_image", "model_error"] | None = None
    detail: str | None = None
    infrastructure_failure: bool = False

class PropertyPhotoAnalysis(BaseModel):
    property_id: str
    status: Literal["complete", "partial", "failed", "no_photos"]
    photos: list[PhotoAnalysis]
    cache_write_failures: list[str] = Field(default_factory=list)
