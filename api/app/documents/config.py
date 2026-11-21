import os
from pathlib import Path
from dotenv import load_dotenv
from langchain_ollama import ChatOllama, OllamaEmbeddings

ENV_PATH = Path(__file__).resolve().parents[3] / ".env"


def load_extraction_model() -> ChatOllama:
    load_dotenv(ENV_PATH)
    return ChatOllama(
        base_url=os.getenv("OLLAMA_BASE_URL") or "http://127.0.0.1:11434",
        model=os.getenv("OLLAMA_EXTRACTION_MODEL") or "llama3.2",
        temperature=0,
        num_ctx=8192,
        client_kwargs={"timeout": 120},
    )

def load_index_config() -> tuple[str, OllamaEmbeddings]:
    load_dotenv(ENV_PATH)

    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise ValueError("Set DATABASE_URL or copy .env.example to .env in the repository root.")

    embeddings = OllamaEmbeddings(
        base_url=os.getenv("OLLAMA_BASE_URL") or "http://127.0.0.1:11434",
        model=os.getenv("OLLAMA_EMBEDDING_MODEL") or "nomic-embed-text",
        client_kwargs={"timeout": 120},
    )

    return database_url, embeddings
