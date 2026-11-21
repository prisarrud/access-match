import argparse
import asyncio
import base64
import os
import sys
from io import BytesIO
from pathlib import Path
from typing import Literal
from langchain_core.exceptions import OutputParserException
from langchain_core.messages import HumanMessage
from langchain_ollama import ChatOllama
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from ..config import load_ollama_base_url
from ..properties.catalog import DEFAULT_CATALOG_PATH, load_catalog
from ..properties.schemas import RelativeFile

ImageError = Literal["missing_file", "unreadable_image"]

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

PROMPT = (
    "Examine o piso por onde as pessoas passam nesta foto. Registre apenas um degrau "
    "(uma face vertical visível entre dois níveis de piso) ou uma rampa de acesso "
    "(uma superfície de passagem visivelmente inclinada) quando essa geometria estiver clara. "
    "Piso plano visto de cima, soleira, corrimão isolado, reflexo e mudança de material "
    "não caracterizam degrau nem rampa. Omita elementos incertos ou fora do quadro. "
    "Use degrau ou rampa e escolha o código do local visível em location. "
    "Use null se o local for incerto. Se nenhum elemento estiver visível, retorne observations vazio."
)

COVERAGE_PROMPT = (
    "Identifique as partes visíveis do acesso externo nesta foto. Ignore reflexos e áreas atrás do vidro "
    "ou além da entrada. calcada é a calçada pública junto à rua, portao é o portão da cerca, "
    "trajeto é o caminho externo antes do patamar, patamar é o piso imediatamente em frente à porta "
    "e porta_entrada é a porta do edifício. Para cada parte, use visible se estiver visível, "
    "partial se estiver cortada pelo quadro, out_of_frame se não aparecer ou indeterminate "
    "se estiver encoberta ou se a cena não puder ser reconhecida. Se a foto mostrar apenas a porta "
    "e o piso imediatamente à frente, esse piso é o patamar. Marque calcada e trajeto como out_of_frame. "
    "Em uma imagem totalmente escura ou encoberta, marque as cinco partes como indeterminate."
)

class ImageReadError(ValueError):
    def __init__(self, code: ImageError, message: str):
        super().__init__(message)
        self.code = code

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

def summarize_photo(
    photo_id: str, source_path: str, coverage: VisibleParts, findings: list[VisualFinding],
) -> PhotoAnalysis:
    parts = coverage.model_dump()

    shown_parts = {part for part, state in parts.items() if state in {"visible", "partial"}}

    floor_visible = bool(shown_parts.intersection(("calcada", "trajeto", "patamar")))

    transitions = {
        "entre_calcada_e_patamar": ("calcada", "patamar"),
        "entre_trajeto_e_patamar": ("trajeto", "patamar"),
    }

    observations = []

    if floor_visible:
        for finding in findings:
            location = finding.location
            if location is not None and not shown_parts.issuperset(transitions.get(location, (location,))):
                location = None
            observations.append(PhotoObservation(
                element=finding.element, location=location, photo_id=photo_id,
            ))

    observed = {observation.element for observation in observations}

    assessments = [
        ElementAssessment(
            element=element,
            state="observed" if element in observed else "not_observed" if floor_visible else "not_assessable",
        )
        for element in ("degrau", "rampa")
    ]

    to_confirm: list[Confirmation] = ["route_continuity", "alternate_access"]

    if "rampa" in observed:
        to_confirm.extend(("ramp_slope", "ramp_width", "ramp_continuity"))

    return PhotoAnalysis(
        photo_id=photo_id, source_path=source_path, status="analyzed",
        coverage=PhotoCoverage(
            framing="partial" if shown_parts else "indeterminate",
            parts=coverage,
            unverified_parts=[part for part, state in parts.items() if state != "visible"],
        ),
        assessments=assessments, observations=observations, to_confirm=to_confirm,
    )

def read_image(catalog_dir: Path, source_path: str) -> str | None:
    """Return the original image bytes as a data URL, or None for a featureless frame."""
    try:
        path = (catalog_dir / source_path).resolve()

        if not path.is_relative_to(catalog_dir):
            raise ImageReadError("unreadable_image", "Photo path is outside the catalog directory.")

        data = path.read_bytes()

        with Image.open(BytesIO(data)) as image:
            image.load()
            media_type = Image.MIME.get(image.format)

            if media_type not in {"image/jpeg", "image/png", "image/webp"}:
                raise ImageReadError("unreadable_image", "Expected a JPEG, PNG, or WebP image.")
            if all(low == high for low, high in image.convert("RGB").getextrema()):
                return None
    except ImageReadError:
        raise
    except FileNotFoundError as exc:
        raise ImageReadError("missing_file", "Photo file not found.") from exc
    except (OSError, RuntimeError, SyntaxError, ValueError, Image.DecompressionBombError) as exc:
        raise ImageReadError("unreadable_image", f"Could not decode photo: {exc}") from exc

    return f"data:{media_type};base64,{base64.b64encode(data).decode('ascii')}"

def load_vision_model() -> ChatOllama:
    base_url = load_ollama_base_url()

    return ChatOllama(
        base_url=base_url,
        model=os.getenv("OLLAMA_VISION_MODEL") or "gemma3:4b",
        temperature=0,
        num_ctx=4096,
        client_kwargs={"timeout": 120},
    )

async def analyze_property_photos(
    property_id: str, catalog_path: Path = DEFAULT_CATALOG_PATH,
) -> PropertyPhotoAnalysis:
    catalog_path = catalog_path.resolve()

    property_item = next(
        (item for item in load_catalog(catalog_path).properties if item.id == property_id), None,
    )

    if property_item is None:
        raise ValueError(f"Unknown property: {property_id!r}.")

    if not property_item.photos:
        return PropertyPhotoAnalysis(property_id=property_id, status="no_photos", photos=[])

    results = []
    coverage_chain = findings_chain = None

    for photo in property_item.photos:
        reference = {"photo_id": photo.id, "source_path": photo.path}

        try:
            image_url = read_image(catalog_path.parent, photo.path)
        except ImageReadError as exc:
            results.append(PhotoAnalysis(
                **reference, status="pending", error=exc.code, detail=str(exc),
            ))
            continue

        if image_url is None:
            coverage = VisibleParts(**dict.fromkeys(VisibleParts.model_fields, "indeterminate"))
            results.append(summarize_photo(photo.id, photo.path, coverage, []))
            continue

        image = {"type": "image_url", "image_url": image_url}

        try:
            if coverage_chain is None or findings_chain is None:
                model = load_vision_model()
                coverage_chain = model.with_structured_output(VisibleParts, method="json_schema")
                findings_chain = model.with_structured_output(ModelAnalysis, method="json_schema")
            coverage = VisibleParts.model_validate(await coverage_chain.ainvoke([
                HumanMessage(content=[{"type": "text", "text": COVERAGE_PROMPT}, image]),
            ]))
            findings = ModelAnalysis.model_validate(await findings_chain.ainvoke([
                HumanMessage(content=[{"type": "text", "text": PROMPT}, image]),
            ]))
        except (ValidationError, OutputParserException):
            results.append(PhotoAnalysis(
                **reference, status="pending", error="model_error",
                detail="The model returned an invalid visual analysis.",
            ))
        except Exception as exc:
            results.append(PhotoAnalysis(
                **reference, status="pending", error="model_error", detail=str(exc),
                infrastructure_failure=isinstance(exc, OSError),
            ))
        else:
            results.append(summarize_photo(photo.id, photo.path, coverage, findings.observations))

    pending = sum(result.status == "pending" for result in results)
    status = "failed" if pending == len(results) else "partial" if pending else "complete"

    return PropertyPhotoAnalysis(property_id=property_id, status=status, photos=results)

def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze catalog photos for visible steps and ramps.")

    parser.add_argument("property_id")

    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG_PATH,
                        help="path to the catalog JSON file (default: data/demo/properties.json)")

    args = parser.parse_args()

    try:
        result = asyncio.run(analyze_property_photos(args.property_id, args.catalog))
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(result.model_dump_json(indent=2))

    return int(result.status in {"partial", "failed"})

if __name__ == "__main__":
    raise SystemExit(main())
