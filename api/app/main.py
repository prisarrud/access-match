from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .properties.catalog import load_catalog

@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    application.state.catalog = load_catalog()
    yield

app = FastAPI(title="AccessMatch", lifespan=lifespan)
