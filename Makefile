PYTHON ?= python3
API_PYTHON := api/.venv/bin/python
API_BASE_URL ?= http://127.0.0.1:8000

.PHONY: help setup db dev stop-demo-api prepare-demo prepare-photos validate-evaluation evaluate

help:
	@printf '%s\n' 'make setup  Install dependencies, download models, index PDFs, and prepare photos' \
		'make prepare-demo  Prepare the demo and start the API and frontend' \
		'make prepare-photos  Analyze and cache photos for the demo catalog' \
		'make validate-evaluation  Check evaluation cases and source references' \
		'make evaluate  Compare RAG and full PDF context on the evaluation cases' \
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

prepare-demo: setup
	$(MAKE) dev

db:
	docker compose up -d --wait postgres

prepare-photos:
	$(API_PYTHON) -m api.app.photos.analysis $${PROPERTY_ID:+-- "$$PROPERTY_ID"}

validate-evaluation:
	$(API_PYTHON) -m evaluation.validate

evaluate: validate-evaluation db
	$(API_PYTHON) -m api.app.documents.ingestion --catalog evaluation/fixtures/properties.json
	$(API_PYTHON) -m evaluation.run --prompt-version v2-candidate --num-predict 1536 --output evaluation/results.json

stop-demo-api:
	@command -v lsof >/dev/null || { echo 'Install lsof to check API port 8000.' >&2; exit 1; }; \
		root=$$(pwd -P); owners=''; \
		for pid in $$(lsof -tiTCP:8000 -sTCP:LISTEN); do \
			owner=''; \
			for candidate in "$$pid" $$(ps -p "$$pid" -o ppid=); do \
				cmd=$$(ps -p "$$candidate" -o command=); \
				dir=$$(lsof -a -p "$$candidate" -d cwd -Fn | sed -n 's/^n//p'); \
				case "$$cmd" in \
					*' -m uvicorn api.app.main:app'*) \
						if [ "$$dir" = "$$root" ]; then owner=$$candidate; break; fi ;; \
				esac; \
			done; \
			if [ -z "$$owner" ]; then echo "Port 8000 is in use by PID $$pid outside this AccessMatch API." >&2; exit 1; fi; \
			case " $$owners " in *" $$owner "*) ;; *) owners="$$owners $$owner" ;; esac; \
		done; \
		for owner in $$owners; do \
			echo "Stopping previous AccessMatch API (PID $$owner)."; \
			kill "$$owner" || exit 1; \
		done; \
		remaining=10; \
		while lsof -tiTCP:8000 -sTCP:LISTEN >/dev/null; do \
			if [ "$$remaining" -eq 0 ]; then echo 'Port 8000 is still in use.' >&2; exit 1; fi; \
			sleep 1; remaining=$$((remaining - 1)); \
		done

dev: db stop-demo-api
	@$(API_PYTHON) -m uvicorn api.app.main:app --reload & api_pid=$$!; \
		trap 'kill "$$api_pid" 2>/dev/null || true; wait "$$api_pid" 2>/dev/null || true' 0; \
		trap 'exit 130' INT; trap 'exit 143' TERM; \
		API_BASE_URL="$(API_BASE_URL)" npm --prefix web run dev
