import os
from pathlib import Path
from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parents[2] / ".env"

def load_ollama_base_url() -> str:
    load_dotenv(ENV_PATH)

    return os.getenv("OLLAMA_BASE_URL") or "http://127.0.0.1:11434"
