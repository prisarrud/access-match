import argparse
import asyncio
import base64
import json
import logging
import os
import sys
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Literal
from weakref import WeakValueDictionary
from langchain_core.exceptions import OutputParserException
from langchain_core.messages import HumanMessage
from langchain_ollama import ChatOllama
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from ..config import load_ollama_base_url
from ..properties.catalog import DEFAULT_CATALOG_PATH, load_catalog
from ..properties.schemas import Property, RelativeFile
from ..request_context import request_context, request_id

logger = logging.getLogger(__name__)
VISION_PIPELINE_VERSION = 1
_property_locks: WeakValueDictionary[tuple[asyncio.AbstractEventLoop, Path, str], asyncio.Lock] = WeakValueDictionary()

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
    cache_write_failures: list[str] = Field(default_factory=list)


class VisionConfiguration(BaseModel):
    model: str
    prompt_version: str
    pipeline_version: int
    endpoint_sha256: str
    temperature: float = 0
    num_ctx: int = 4096


class PhotoCacheKey(BaseModel):
    property_id: str
    photo_id: str
    file_sha256: str
    configuration: VisionConfiguration

    def path_in(self, catalog_dir: Path) -> Path:
        key_hash = sha256(self.model_dump_json().encode()).hexdigest()
        return catalog_dir / ".photo-analysis" / f"{key_hash}.json"


class PhotoCacheEntry(BaseModel):
    key: PhotoCacheKey
    analysis: PhotoAnalysis


def vision_configuration(base_url: str) -> VisionConfiguration:
    prompt_inputs = [COVERAGE_PROMPT, PROMPT, VisibleParts.model_json_schema(), ModelAnalysis.model_json_schema()]
    return VisionConfiguration(
        model=os.getenv("OLLAMA_VISION_MODEL") or "gemma3:4b",
        prompt_version=sha256(json.dumps(prompt_inputs, sort_keys=True).encode()).hexdigest(),
        pipeline_version=VISION_PIPELINE_VERSION,
        endpoint_sha256=sha256(base_url.encode()).hexdigest(),
    )


def load_cached_photo(path: Path, key: PhotoCacheKey) -> PhotoAnalysis | None:
    try:
        entry = PhotoCacheEntry.model_validate_json(path.read_bytes(), strict=True)
    except FileNotFoundError:
        return None
    except (OSError, ValidationError) as exc:
        logger.warning("Photo cache read failed request_id=%s property_id=%s photo_id=%s error_type=%s",
                       request_id(), key.property_id, key.photo_id, type(exc).__name__)
        return None

    analysis = entry.analysis
    if (
        entry.key != key or analysis.photo_id != key.photo_id or analysis.status != "analyzed"
        or analysis.coverage is None or analysis.error is not None or analysis.infrastructure_failure
        or any(item.photo_id != key.photo_id for item in analysis.observations)
    ):
        return None
    return analysis


def save_cached_photo(path: Path, key: PhotoCacheKey, analysis: PhotoAnalysis) -> None:
    path.parent.mkdir(exist_ok=True)
    with NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(PhotoCacheEntry(key=key, analysis=analysis).model_dump_json())
            stream.close()
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)

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

def read_photo_bytes(catalog_dir: Path, source_path: str) -> bytes:
    try:
        path = (catalog_dir / source_path).resolve()
        if not path.is_relative_to(catalog_dir):
            raise ImageReadError("unreadable_image", "Photo path is outside the catalog directory.")
        return path.read_bytes()
    except ImageReadError:
        raise
    except FileNotFoundError as exc:
        raise ImageReadError("missing_file", "Photo file not found.") from exc
    except (OSError, RuntimeError, ValueError) as exc:
        raise ImageReadError("unreadable_image", "Could not read photo.") from exc


def encode_image(data: bytes) -> str | None:
    """Return the original bytes as a data URL, or None for a featureless frame."""
    try:
        with Image.open(BytesIO(data)) as image:
            image.load()
            media_type = Image.MIME.get(image.format)

            if media_type not in {"image/jpeg", "image/png", "image/webp"}:
                raise ImageReadError("unreadable_image", "Expected a JPEG, PNG, or WebP image.")
            if all(low == high for low, high in image.convert("RGB").getextrema()):
                return None
    except ImageReadError:
        raise
    except (OSError, RuntimeError, SyntaxError, ValueError, Image.DecompressionBombError) as exc:
        raise ImageReadError("unreadable_image", f"Could not decode photo: {exc}") from exc

    return f"data:{media_type};base64,{base64.b64encode(data).decode('ascii')}"

def load_vision_model(base_url: str, configuration: VisionConfiguration) -> ChatOllama:
    return ChatOllama(
        base_url=base_url,
        model=configuration.model,
        temperature=configuration.temperature,
        num_ctx=configuration.num_ctx,
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

    return await analyze_photos(property_item, catalog_path.parent)


async def analyze_photos(property_item: Property, catalog_dir: Path) -> PropertyPhotoAnalysis:
    key = (asyncio.get_running_loop(), catalog_dir, property_item.id)
    lock = _property_locks.setdefault(key, asyncio.Lock())
    async with lock:
        return await _analyze_photos(property_item, catalog_dir)


async def _analyze_photos(property_item: Property, catalog_dir: Path) -> PropertyPhotoAnalysis:
    property_id = property_item.id
    if not property_item.photos:
        return PropertyPhotoAnalysis(property_id=property_id, status="no_photos", photos=[])

    base_url = load_ollama_base_url()
    configuration = vision_configuration(base_url)
    results = []
    cache_write_failures = []
    coverage_chain = findings_chain = None

    for photo in property_item.photos:
        reference = {"photo_id": photo.id, "source_path": photo.path}

        try:
            data = read_photo_bytes(catalog_dir, photo.path)
            key = PhotoCacheKey(
                property_id=property_id, photo_id=photo.id, file_sha256=sha256(data).hexdigest(),
                configuration=configuration,
            )
            cache_path = key.path_in(catalog_dir)
            cached = load_cached_photo(cache_path, key)
            if cached is not None:
                results.append(cached.model_copy(update={"source_path": photo.path}))
                continue
            image_url = encode_image(data)
        except ImageReadError as exc:
            results.append(PhotoAnalysis(
                **reference, status="pending", error=exc.code, detail=str(exc),
            ))
            continue

        if image_url is None:
            coverage = VisibleParts(**dict.fromkeys(VisibleParts.model_fields, "indeterminate"))
            observations = []
        else:
            image = {"type": "image_url", "image_url": image_url}
            try:
                if coverage_chain is None or findings_chain is None:
                    model = load_vision_model(base_url, configuration)
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
                continue
            except Exception as exc:
                results.append(PhotoAnalysis(
                    **reference, status="pending", error="model_error", detail=str(exc),
                    infrastructure_failure=isinstance(exc, OSError),
                ))
                continue
            observations = findings.observations

        result = summarize_photo(photo.id, photo.path, coverage, observations)
        results.append(result)
        try:
            save_cached_photo(cache_path, key, result)
        except OSError as exc:
            cache_write_failures.append(photo.id)
            logger.warning("Photo cache write failed request_id=%s property_id=%s photo_id=%s error_type=%s",
                           request_id(), property_id, photo.id, type(exc).__name__)

    pending = 0
    for result in results:
        if result.status == "pending":
            pending += 1
            logger.warning("Photo analysis failed request_id=%s property_id=%s photo_id=%s error=%s",
                           request_id(), property_id, result.photo_id, result.error)
    status = "failed" if pending == len(results) else "partial" if pending else "complete"

    return PropertyPhotoAnalysis(
        property_id=property_id, status=status, photos=results, cache_write_failures=cache_write_failures,
    )

def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare photo observations for a catalog or one property.")

    parser.add_argument("property_id", nargs="?", help="omit to prepare every property")

    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG_PATH,
                        help="path to the catalog JSON file (default: data/demo/properties.json)")

    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING)
    catalog_path = args.catalog.resolve()
    try:
        if not catalog_path.is_file():
            raise ValueError("Photo catalog not found.")
        properties = load_catalog(catalog_path).properties
        if args.property_id is not None:
            properties = [item for item in properties if item.id == args.property_id]
            if not properties:
                raise ValueError(f"Unknown property: {args.property_id!r}.")

        async def prepare() -> list[PropertyPhotoAnalysis]:
            return [await analyze_photos(item, catalog_path.parent) for item in properties]

        with request_context():
            results = asyncio.run(prepare())
        failed = any(item.status in {"partial", "failed"} or item.cache_write_failures for item in results)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.property_id is not None:
        print(results[0].model_dump_json(indent=2))
    else:
        print(json.dumps([item.model_dump(mode="json") for item in results], indent=2))

    return int(failed)

if __name__ == "__main__":
    raise SystemExit(main())
