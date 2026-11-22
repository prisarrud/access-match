import argparse
import sys
from pathlib import Path
import psycopg
from langchain_core.documents import Document as Chunk
from langchain_core.embeddings import Embeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader
from ..properties.catalog import DEFAULT_CATALOG_PATH, CatalogLoadError, load_catalog
from ..properties.schemas import Document
from .config import load_index_config
from .vector_store import initialize_index, replace_document

EMBEDDING_BATCH_SIZE = 32

class PdfExtractionError(ValueError):
    """Text could not be extracted from a catalog PDF."""

def prepare_chunks(
    property_id: str,
    document: Document,
    catalog_dir: Path,
    splitter: RecursiveCharacterTextSplitter | None,
) -> list[Chunk]:
    chunks = []
    try:
        path = (catalog_dir / document.path).resolve()
        if not path.is_relative_to(catalog_dir):
            raise PdfExtractionError("PDF path is outside the catalog directory")
        with path.open("rb") as stream:
            reader = PdfReader(stream)
            for page_number, page in enumerate(reader.pages, start=1):
                text = (page.extract_text() or "").replace("\x00", " ").strip()
                contents = splitter.split_text(text) if splitter is not None else [text]
                for chunk_index, content in enumerate(contents, start=1):
                    chunks.append(Chunk(
                        page_content=content,
                        metadata={
                            "property_id": property_id,
                            "document_id": document.id,
                            "document_type": document.type,
                            "document_date": document.date,
                            "source_path": document.path,
                            "page": page_number,
                            "chunk_index": chunk_index,
                        },
                    ))
    except PdfExtractionError:
        raise
    except FileNotFoundError as exc:
        raise PdfExtractionError("PDF not found") from exc
    except Exception as exc:
        raise PdfExtractionError(f"Unreadable PDF: {exc}") from exc

    if not chunks:
        raise PdfExtractionError("PDF has no extractable text")
    return chunks


def embed_chunks(embeddings: Embeddings, chunks: list[Chunk]) -> list[list[float]]:
    vectors = []
    for start in range(0, len(chunks), EMBEDDING_BATCH_SIZE):
        texts = [chunk.page_content for chunk in chunks[start:start + EMBEDDING_BATCH_SIZE]]
        batch = embeddings.embed_documents(texts)
        if len(batch) != len(texts):
            raise ValueError("Ollama returned an unexpected number of embeddings.")
        vectors.extend(batch)
    return vectors


def index_catalog(catalog_path: Path) -> int:
    catalog_path = catalog_path.resolve()

    if not catalog_path.is_file():
        raise CatalogLoadError(f"Catalog not found: {catalog_path}")

    catalog = load_catalog(catalog_path)

    documents = [
        (item.id, document)
        for item in catalog.properties
        for document in item.documents
        if Path(document.path).suffix.lower() == ".pdf"
    ]

    if not documents:
        print("The catalog has no linked PDFs.")
        return 0

    database_url, embeddings = load_index_config()

    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=120)

    failures = 0

    with psycopg.connect(database_url, autocommit=True, connect_timeout=5) as connection:
        initialize_index(connection)
        for property_id, document in documents:
            source = f"{property_id} / {document.id} ({document.path})"
            try:
                chunks = prepare_chunks(property_id, document, catalog_path.parent, splitter)
                vectors = embed_chunks(embeddings, chunks)
                replace_document(connection, property_id, document.id, chunks, vectors, embeddings.model)
            except Exception as exc:
                failures += 1
                print(f"ERROR {source}: {exc}", file=sys.stderr)
            else:
                print(f"Indexed {source}: {len(chunks)} chunk(s).")

    print(f"PDFs indexed: {len(documents) - failures}/{len(documents)}.")

    return int(failures > 0)

def main() -> int:
    parser = argparse.ArgumentParser(description="Index the PDFs linked in the catalog.")

    parser.add_argument(
        "--catalog",
        type=Path,
        default=DEFAULT_CATALOG_PATH,
        help="path to the catalog JSON file (default: data/demo/properties.json)",
    )

    args = parser.parse_args()

    try:
        return index_catalog(args.catalog)
    except (OSError, ValueError, psycopg.Error) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
