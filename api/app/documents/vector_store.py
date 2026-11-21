from collections.abc import Sequence
from json import dumps
from uuid import NAMESPACE_URL, uuid5

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_postgres import PGEngine, PGVectorStore
from psycopg import Connection

TABLE_NAME = "document_chunks"
METADATA_COLUMNS = (
    "property_id",
    "document_id",
    "document_type",
    "document_date",
    "source_path",
    "page",
    "chunk_index",
    "embedding_model",
)

async def create_vector_store(engine: PGEngine, embeddings: Embeddings) -> PGVectorStore:
    return await PGVectorStore.create(
        engine=engine,
        table_name=TABLE_NAME,
        embedding_service=embeddings,
        metadata_columns=list(METADATA_COLUMNS),
    )

def initialize_index(connection: Connection) -> None:
    with connection.transaction():
        connection.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended('accessmatch:document_chunks', 0))"
        )

        connection.execute("CREATE EXTENSION IF NOT EXISTS vector")

        connection.execute("""
            CREATE TABLE IF NOT EXISTS document_chunks (
                langchain_id uuid PRIMARY KEY,
                content text NOT NULL,
                embedding vector NOT NULL,
                property_id text NOT NULL,
                document_id text NOT NULL,
                document_type text NOT NULL,
                document_date date,
                source_path text NOT NULL,
                page integer NOT NULL CHECK (page > 0),
                chunk_index integer NOT NULL CHECK (chunk_index > 0),
                embedding_model text NOT NULL,
                UNIQUE (property_id, document_id, page, chunk_index)
            )
        """)

def replace_document(
    connection: Connection,
    property_id: str,
    document_id: str,
    chunks: Sequence[Document],
    vectors: Sequence[list[float]],
    model: str,
) -> None:
    if not chunks or len(chunks) != len(vectors):
        raise ValueError("The number of embeddings does not match the number of chunks.")

    dimensions = len(vectors[0])

    if dimensions == 0 or any(len(vector) != dimensions for vector in vectors):
        raise ValueError("Ollama returned embeddings with invalid or inconsistent dimensions.")

    rows = []

    for chunk, vector in zip(chunks, vectors, strict=True):
        metadata = chunk.metadata
        page = metadata["page"]
        chunk_index = metadata["chunk_index"]
        chunk_id = uuid5(
            NAMESPACE_URL, dumps(["accessmatch", property_id, document_id, page, chunk_index])
        )
        rows.append((
            chunk_id,
            chunk.page_content,
            dumps(vector, allow_nan=False),
            property_id,
            document_id,
            metadata["document_type"],
            metadata["document_date"],
            metadata["source_path"],
            page,
            chunk_index,
            model,
        ))

    with connection.transaction(), connection.cursor() as cursor:
        cursor.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
            (dumps(["accessmatch", property_id, document_id]),),
        )

        cursor.execute(
            "DELETE FROM document_chunks WHERE property_id = %s AND document_id = %s",
            (property_id, document_id),
        )

        cursor.executemany("""
            INSERT INTO document_chunks (
                langchain_id, content, embedding, property_id, document_id, document_type,
                document_date, source_path, page, chunk_index, embedding_model
            )
            VALUES (%s, %s, %s::vector, %s, %s, %s, %s, %s, %s, %s, %s)
        """, rows)
