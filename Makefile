PYTHON ?= python3
API_PYTHON := api/.venv/bin/python
API_BASE_URL ?= http://127.0.0.1:8000

.PHONY: help setup db dev prepare-photos

help:
	@printf '%s\n' 'make setup  Install dependencies, download models, index PDFs, and prepare photos' \
		'make prepare-photos  Analyze and cache photos for the demo catalog' \
		'make dev    Start PostgreSQL, the API, and the frontend'

setup:
	@test -f .env || cp .env.example .env
	@test -x $(API_PYTHON) || $(PYTHON) -m venv api/.venv
	$(API_PYTHON) -m pip install -r api/requirements.txt
	npm --prefix web ci
	@printf '%s\n' \
		'import os' \
		'import subprocess' \
		'from dotenv import load_dotenv' \
		'load_dotenv(".env")' \
		'os.environ["OLLAMA_HOST"] = os.getenv("OLLAMA_BASE_URL") or "http://127.0.0.1:11434"' \
		'embedding = os.getenv("OLLAMA_EMBEDDING_MODEL") or "nomic-embed-text"' \
		'extraction = os.getenv("OLLAMA_EXTRACTION_MODEL") or "llama3.2"' \
		'vision = os.getenv("OLLAMA_VISION_MODEL") or "gemma3:4b"' \
		'for model in dict.fromkeys((embedding, extraction, vision)):' \
		'    subprocess.run(["ollama", "pull", model], check=True)' | $(API_PYTHON) -
	$(MAKE) db
	$(API_PYTHON) -m api.app.documents.ingestion
	$(MAKE) prepare-photos PROPERTY_ID=

db:
	docker compose up -d --wait postgres

prepare-photos:
	$(API_PYTHON) -m api.app.photos.analysis $${PROPERTY_ID:+-- "$$PROPERTY_ID"}

dev: db
	@$(API_PYTHON) -m uvicorn api.app.main:app --reload & api_pid=$$!; \
		trap 'kill "$$api_pid" 2>/dev/null || true; wait "$$api_pid" 2>/dev/null || true' 0; \
		trap 'exit 130' INT; trap 'exit 143' TERM; \
		API_BASE_URL="$(API_BASE_URL)" npm --prefix web run dev
