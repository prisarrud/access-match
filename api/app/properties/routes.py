from mimetypes import guess_type
from pathlib import Path
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .catalog import DEFAULT_CATALOG_PATH
from .schemas import Document, Photo, Property, PropertyCatalog

router = APIRouter(prefix="/properties", tags=["properties"])

class CoverPhoto(BaseModel):
    url: str
    alt: str

class PhotoMedia(BaseModel):
    id: str
    alt: str
    url: str | None

class DocumentMedia(BaseModel):
    id: str
    title: str
    url: str | None

class PropertySummary(BaseModel):
    id: str
    title: str
    description: str
    cover: CoverPhoto | None = None
    photos: list[PhotoMedia]
    documents: list[DocumentMedia]

def catalog_file(relative_path: str) -> Path | None:
    demo_dir = DEFAULT_CATALOG_PATH.parent
    try:
        path = (demo_dir / relative_path).resolve()
        if path.is_relative_to(demo_dir) and path.is_file():
            return path
    except (OSError, RuntimeError, ValueError):
        return None
    return None

def source_file(source: Photo | Document) -> tuple[Path, str] | None:
    path = catalog_file(source.path)
    if path is None:
        return None

    if isinstance(source, Document):
        return (path, "application/pdf") if path.suffix.lower() == ".pdf" else None

    media_type, _ = guess_type(path.name)
    if media_type and media_type.startswith("image/") and media_type != "image/svg+xml":
        return path, media_type
    return None

def source_url(item: Property, source: Photo | Document, request: Request) -> str | None:
    if source_file(source) is None:
        return None
    return str(request.url_for("property_source").include_query_params(property_id=item.id, source_id=source.id))

def cover_photo(item: Property, request: Request) -> CoverPhoto | None:
    if not item.photos:
        return None

    url = request.url_for("property_cover").include_query_params(id=item.id)

    return CoverPhoto(url=str(url), alt=item.photos[0].alt)

@router.get("")
def list_properties(request: Request) -> list[PropertySummary]:
    catalog: PropertyCatalog = request.app.state.catalog

    return [
        PropertySummary(
            id=item.id,
            title=item.title,
            description=item.description,
            cover=cover_photo(item, request),
            photos=[PhotoMedia(id=photo.id, alt=photo.alt, url=source_url(item, photo, request)) for photo in item.photos],
            documents=[
                DocumentMedia(id=document.id, title=document.title, url=source_url(item, document, request))
                for document in item.documents
            ],
        )
        for item in catalog.properties
    ]

@router.get("/cover")
def property_cover(id: str, request: Request) -> FileResponse:
    catalog: PropertyCatalog = request.app.state.catalog

    item = next((item for item in catalog.properties if item.id == id), None)

    if item is None or not item.photos:
        raise HTTPException(status_code=404, detail="Foto de capa indisponível.")

    path = catalog_file(item.photos[0].path)
    if path is None:
        raise HTTPException(status_code=404, detail="Foto de capa indisponível.")

    return FileResponse(path)

@router.get("/source")
def property_source(property_id: str, source_id: str, request: Request) -> FileResponse:
    catalog: PropertyCatalog = request.app.state.catalog
    item = next((item for item in catalog.properties if item.id == property_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail="Arquivo da evidência indisponível.")

    source = next((source for source in [*item.photos, *item.documents] if source.id == source_id), None)
    asset = source_file(source) if source is not None else None
    if asset is None:
        raise HTTPException(status_code=404, detail="Arquivo da evidência indisponível.")

    path, media_type = asset
    return FileResponse(
        path, media_type=media_type, filename=path.name, content_disposition_type="inline",
        headers={"X-Content-Type-Options": "nosniff"},
    )
