import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

from .comparison.routes import router as comparison_router
from .comparison.store import ComparisonStore
from .documents.retrieval import retrieve_property_context
from .photos.analysis import analyze_photos
from .properties.catalog import DEFAULT_CATALOG_PATH, CatalogLoadError, load_catalog
from .properties.routes import router as properties_router

logger = logging.getLogger(__name__)
PHOTO_REFRESH_INTERVAL_SECONDS = 15


async def refresh_catalog_photos(application: FastAPI) -> None:
    catalog_path = DEFAULT_CATALOG_PATH.resolve()
    while True:
        try:
            catalog = load_catalog(catalog_path)
        except CatalogLoadError:
            logger.warning("Catalog refresh failed. Keeping the last valid catalog.")
        else:
            application.state.catalog = catalog
            for item in catalog.properties:
                try:
                    await analyze_photos(item, catalog_path.parent)
                except Exception as exc:
                    logger.warning("Photo preparation failed property_id=%s error_type=%s",
                                   item.id, type(exc).__name__)

        await asyncio.sleep(PHOTO_REFRESH_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    application.state.catalog = load_catalog(DEFAULT_CATALOG_PATH)
    application.state.comparisons = ComparisonStore()
    application.state.document_context = retrieve_property_context
    preparation = asyncio.create_task(refresh_catalog_photos(application))
    try:
        yield
    finally:
        preparation.cancel()
        with suppress(asyncio.CancelledError):
            await preparation

app = FastAPI(title="AccessMatch", lifespan=lifespan)

app.include_router(properties_router)
app.include_router(comparison_router)
