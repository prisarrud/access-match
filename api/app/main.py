from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .comparison.routes import router as comparison_router
from .properties.catalog import load_catalog
from .properties.routes import router as properties_router

@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    application.state.catalog = load_catalog()
    yield

app = FastAPI(title="AccessMatch", lifespan=lifespan)

app.include_router(properties_router)
app.include_router(comparison_router)
