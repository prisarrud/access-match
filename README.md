# AccessMatch

AccessMatch helps wheelchair users compare property entrances before booking a viewing.

<a id="getting-started---api"></a>

## Prerequisites

- Make, Python 3.11 or later, and Node.js with npm.
- Docker with Compose. On macOS, open Docker Desktop before starting the project. [Installation guide](https://docs.docker.com/compose/install/)
- Ollama. On macOS, open the installer, drag Ollama to **Applications**, and allow it to install the terminal command if prompted. On Linux, follow the official guide. Open the app or run `ollama serve` in a separate terminal, then check the connection with `ollama list`. [Download](https://ollama.com/download) · [macOS guide](https://docs.ollama.com/macos) · [Linux guide](https://docs.ollama.com/linux)

## Run locally

From the repository root, run `make setup` during initial setup and whenever dependencies change. It creates the Python environment, installs dependencies, copies [.env.example](.env.example) if `.env` does not exist, and downloads the configured Ollama model.

For each session, run `make dev` and open the [catalog](http://localhost:3000). The command starts PostgreSQL, the API, and the frontend. The [API](http://127.0.0.1:8000/docs) runs on port `8000`. Press Ctrl+C to stop the API and frontend.

To index the demo PDFs, run `make index` with Ollama running. The chunks are stored in `public.document_chunks`. The default local connection uses `127.0.0.1:5433` and `accessmatch` as the database name, username, and password. If you change the model in `.env`, run `make model` followed by `make index`.
