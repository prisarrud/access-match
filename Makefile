PYTHON ?= python3
API_PYTHON := api/.venv/bin/python
API_BASE_URL ?= http://127.0.0.1:8000

.PHONY: help setup model db dev index

help:
	@printf '%s\n' 'make setup  Install dependencies, create .env, and download the model' \
		'make dev    Start PostgreSQL, the API, and the frontend' \
		'make index  Index the PDFs in PostgreSQL' \
		'make model  Download the model configured in .env'

setup:
	@test -f .env || cp .env.example .env
	@test -x $(API_PYTHON) || $(PYTHON) -m venv api/.venv
	$(API_PYTHON) -m pip install -r api/requirements.txt
	npm --prefix web ci
	$(MAKE) model

model:
	@printf '%s\n' \
		'import os' \
		'from dotenv import load_dotenv' \
		'load_dotenv(".env")' \
		'model = os.getenv("OLLAMA_EMBEDDING_MODEL") or "nomic-embed-text"' \
		'os.environ["OLLAMA_HOST"] = os.getenv("OLLAMA_BASE_URL") or "http://127.0.0.1:11434"' \
		'os.execlp("ollama", "ollama", "pull", model)' | $(API_PYTHON) -

db:
	docker compose up -d --wait postgres

dev: db
	@$(API_PYTHON) -m uvicorn api.app.main:app --reload & api_pid=$$!; \
		trap 'kill "$$api_pid" 2>/dev/null || true; wait "$$api_pid" 2>/dev/null || true' 0; \
		trap 'exit 130' INT; trap 'exit 143' TERM; \
		API_BASE_URL="$(API_BASE_URL)" npm --prefix web run dev

index: db
	$(API_PYTHON) -m api.app.documents.ingestion
