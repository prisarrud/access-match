import argparse
import asyncio
import base64
import os
import sys
from io import BytesIO
from pathlib import Path
from typing import Literal
from langchain_core.messages import HumanMessage
from langchain_ollama import ChatOllama
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field
from ..config import load_ollama_base_url
from ..properties.catalog import DEFAULT_CATALOG_PATH, load_catalog
from ..properties.schemas import NonBlankText, RelativeFile

ImageError = Literal["missing_file", "unreadable_image"]
PROMPT = """
Analise somente a parte do acesso de pedestres que aparece na foto.
Liste apenas degraus e rampas claramente visíveis nesse trecho. Um degrau requer
uma face vertical visível separando dois níveis do piso. Uma rampa requer uma
superfície inclinada e contínua visível no trajeto. Um corrimão sozinho não prova
que há rampa. Uma soleira, o batente da porta, reflexos, sombras e juntas de piso
não são evidência de degrau. Se a foto mostrar somente a porta e piso contínuo,
retorne observations vazio.
Use elemento "degrau" ou "rampa". Descreva o local visível em português, como
calçada, portão, patamar ou porta de entrada. Use null se o local for incerto.
Mencione a calçada somente se ela estiver diretamente visível. Para uma rampa que
sai do enquadramento, descreva só o trecho visível. Omita elementos incertos ou
fora do enquadramento. Retorne observations vazio se nenhum for visível.
"""

class ImageReadError(ValueError):
    def __init__(self, code: ImageError, message: str):
        super().__init__(message)
        self.code = code

class VisualFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    element: Literal["degrau", "rampa"]
    location: NonBlankText | None

class ModelAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observations: list[VisualFinding]

class PhotoObservation(VisualFinding):
    photo_id: str

class PhotoAnalysis(BaseModel):
    photo_id: str
    source_path: RelativeFile
    status: Literal["analyzed", "pending"]
    observations: list[PhotoObservation] = Field(default_factory=list)
    error: Literal["missing_file", "unreadable_image", "model_error"] | None = None
    detail: str | None = None

class PropertyPhotoAnalysis(BaseModel):
    property_id: str
    status: Literal["complete", "partial", "failed", "no_photos"]
    photos: list[PhotoAnalysis]

def read_image(catalog_dir: Path, source_path: str) -> str:
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
    chain = None

    for photo in property_item.photos:
        reference = {"photo_id": photo.id, "source_path": photo.path}

        try:
            image_url = read_image(catalog_path.parent, photo.path)
        except ImageReadError as exc:
            results.append(PhotoAnalysis(
                **reference, status="pending", error=exc.code, detail=str(exc),
            ))
            continue

        message = HumanMessage(content=[
            {"type": "text", "text": PROMPT},
            {"type": "image_url", "image_url": image_url},
        ])

        try:
            if chain is None:
                chain = load_vision_model().with_structured_output(ModelAnalysis, method="json_schema")

            findings = ModelAnalysis.model_validate(await chain.ainvoke([message]))
        except Exception as exc:
            results.append(PhotoAnalysis(
                **reference, status="pending", error="model_error", detail=str(exc),
            ))
        else:
            results.append(PhotoAnalysis(
                **reference, status="analyzed",
                observations=[
                    PhotoObservation(**finding.model_dump(), photo_id=photo.id)
                    for finding in findings.observations
                ],
            ))

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
