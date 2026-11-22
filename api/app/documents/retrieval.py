import argparse
import asyncio
import json
import sys
from langchain_core.documents import Document
from langchain_postgres import PGEngine
from psycopg import OperationalError
from ..properties.schemas import Property
from .schemas import Criterion
from .config import load_index_config
from .vector_store import create_vector_store

CRITERION_QUERIES = {
    "largura": (
        "Porta de entrada do hall no acesso principal do edifício, da calçada até a entrada. "
        "Vão livre, largura útil e largura de passagem da porta de entrada. "
        "Medida prevista em projeto e medida aferida em vistoria."
    ),
    "degraus": (
        "Degraus, escadas, desníveis e soleiras no percurso da calçada até a porta de entrada "
        "do edifício. Quantidade e altura dos degraus no acesso principal."
    ),
    "rampas": (
        "Rampa de acesso no percurso da calçada até a porta de entrada do edifício. "
        "Presença de rampa, inclinação, comprimento e patamar no acesso principal."
    ),
}

class RetrievalError(RuntimeError):
    """The evidence search could not be completed."""

async def retrieve_evidence(
    property_id: str, criterion: str, *, document_ids: list[str] | None = None,
) -> list[Document]:
    """Return candidate passages with source metadata, or an empty list for no results."""

    if not property_id.strip():
        raise ValueError("Property ID must not be blank.")

    if criterion not in CRITERION_QUERIES:
        raise ValueError(f"Unsupported criterion: {criterion!r}.")

    if document_ids == []:
        return []

    try:
        database_url, embeddings = load_index_config()

        _, separator, address = database_url.partition("://")

        if not separator or not database_url.startswith(("postgresql://", "postgres://")):
            raise ValueError("DATABASE_URL must be a PostgreSQL URL.")

        engine = PGEngine.from_connection_string(
            f"postgresql+psycopg://{address}",
            connect_args={"connect_timeout": 5},
        )

        try:
            store = await create_vector_store(engine, embeddings)
            filters = {"property_id": property_id, "embedding_model": embeddings.model}
            if document_ids is not None:
                filters["document_id"] = {"$in": document_ids}

            return await store.asimilarity_search(
                CRITERION_QUERIES[criterion],
                k=4,
                filter=filters,
            )
        finally:
            await engine.close()
    except Exception as exc:
        raise RetrievalError("Could not retrieve evidence from PostgreSQL and Ollama.") from exc

async def retrieve_property_context(property_item: Property, criterion: Criterion) -> list[Document]:
    if not property_item.documents:
        return []
    try:
        return await retrieve_evidence(
            property_item.id, criterion, document_ids=[document.id for document in property_item.documents],
        )
    except RetrievalError as exc:
        cause = exc.__cause__
        while cause is not None:
            if isinstance(cause, OperationalError):
                raise OSError("Document index unavailable.") from exc
            cause = cause.__cause__
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect candidate evidence from catalog PDFs.")
    parser.add_argument("property_id")
    parser.add_argument("criterion", choices=CRITERION_QUERIES)
    args = parser.parse_args()

    try:
        chunks = asyncio.run(retrieve_evidence(args.property_id, args.criterion))
    except RetrievalError as exc:
        print(f"ERROR: {exc} {exc.__cause__}", file=sys.stderr)
        return 1
    except ValueError as exc:
        parser.error(str(exc))

    result = {
        "status": "candidates" if chunks else "no_results",
        "chunks": [{"text": chunk.page_content, **chunk.metadata} for chunk in chunks],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
