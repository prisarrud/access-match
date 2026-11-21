import datetime
from pathlib import PurePosixPath, PureWindowsPath
from typing import Annotated, Literal, Self

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints, model_validator

NonBlankText = Annotated[str, StringConstraints(pattern=r"\S")]

def validate_relative_path(value: str) -> str:
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or PureWindowsPath(value).drive
        or "\\" in value
        or ".." in path.parts
        or not path.parts
    ):
        raise ValueError("use a path relative to data/demo with '/' separators and no '..'")
    return value

RelativeFile = Annotated[NonBlankText, AfterValidator(validate_relative_path)]

class Source(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: NonBlankText
    path: RelativeFile

class Photo(Source):
    alt: NonBlankText

class Document(Source):
    title: NonBlankText
    type: Literal["memorial", "vistoria"]
    date: datetime.date | None = None

class Property(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: NonBlankText
    title: NonBlankText
    description: NonBlankText
    photos: list[Photo] = Field(default_factory=list)
    documents: list[Document] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_source_ids(self) -> Self:
        seen: set[str] = set()
        for source in [*self.photos, *self.documents]:
            if source.id in seen:
                raise ValueError(f"Duplicate source ID for property {self.id!r}: {source.id!r}")
            seen.add(source.id)
        return self

class PropertyCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    properties: list[Property]

    @model_validator(mode="after")
    def validate_property_ids(self) -> Self:
        seen: set[str] = set()
        for item in self.properties:
            if item.id in seen:
                raise ValueError(f"Duplicate property ID in the catalog: {item.id!r}")
            seen.add(item.id)
        return self
