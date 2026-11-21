from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .catalog import DEFAULT_CATALOG_PATH
from .schemas import Property, PropertyCatalog

router = APIRouter(prefix="/properties", tags=["properties"])

class CoverPhoto(BaseModel):
    url: str
    alt: str

class PropertySummary(BaseModel):
    id: str
    title: str
    description: str
    cover: CoverPhoto | None = None

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
        )
        for item in catalog.properties
    ]

@router.get("/cover")
def property_cover(id: str, request: Request) -> FileResponse:
    catalog: PropertyCatalog = request.app.state.catalog

    item = next((item for item in catalog.properties if item.id == id), None)

    if item is None or not item.photos:
        raise HTTPException(status_code=404, detail="Foto de capa indisponível.")

    demo_dir = DEFAULT_CATALOG_PATH.parent

    path = (demo_dir / item.photos[0].path).resolve()

    if not path.is_relative_to(demo_dir) or not path.is_file():
        raise HTTPException(status_code=404, detail="Foto de capa indisponível.")

    return FileResponse(path)
