from pathlib import Path

from pydantic import ValidationError

from .schemas import PropertyCatalog

DEFAULT_CATALOG_PATH = Path(__file__).resolve().parents[3] / "data" / "demo" / "properties.json"

class CatalogLoadError(ValueError):
    """The catalog could not be read or validated."""

def load_catalog(path: Path = DEFAULT_CATALOG_PATH) -> PropertyCatalog:
    try:
        content = path.read_bytes()
    except FileNotFoundError:
        return PropertyCatalog(properties=[])
    except OSError as exc:
        raise CatalogLoadError(f"Could not read the catalog {path}: {exc}") from exc

    try:
        return PropertyCatalog.model_validate_json(content, strict=True)
    except ValidationError as exc:
        raise CatalogLoadError(f"Invalid catalog at {path}:\n{exc}") from exc
