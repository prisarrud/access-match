import os
from langchain_ollama import ChatOllama, OllamaEmbeddings

from ..config import load_ollama_base_url


def load_extraction_model(*, num_predict: int | None = None) -> ChatOllama:
    base_url = load_ollama_base_url()
    return ChatOllama(
        base_url=base_url,
        model=os.getenv("OLLAMA_EXTRACTION_MODEL") or "llama3.2",
        temperature=0,
        num_ctx=8192,
        num_predict=num_predict,
        client_kwargs={"timeout": 120},
    )

def load_index_config() -> tuple[str, OllamaEmbeddings]:
    base_url = load_ollama_base_url()

    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise ValueError("Set DATABASE_URL or copy .env.example to .env in the repository root.")

    embeddings = OllamaEmbeddings(
        base_url=base_url,
        model=os.getenv("OLLAMA_EMBEDDING_MODEL") or "nomic-embed-text",
        client_kwargs={"timeout": 120},
    )

    return database_url, embeddings
