# AccessMatch

AccessMatch helps wheelchair users compare the route from the sidewalk to a property's entrance before booking a viewing. It focuses on steps, ramps, and clear passage width.

## Prerequisites

- Make, Python 3.11 or later, and Node.js with npm.
- Docker with Compose. Start Docker before running the project. [Installation guide](https://docs.docker.com/compose/install/)
- Ollama. Install it for your operating system and open the app. If you installed only the CLI, start the server in a separate terminal and leave it running. [Ollama download](https://ollama.com/download)

```bash
ollama serve
```

<a id="getting-started---api"></a>

## Run locally

Run these commands from the repository root.

### Set up the project

`make setup` creates the Python environment, installs the API and frontend dependencies, creates `.env` if needed, and downloads the configured Ollama embedding and extraction models. Run it during initial setup and whenever dependencies or the configured models change.

```bash
make setup
```

### Index the demo documents

`make index` starts PostgreSQL and indexes the PDFs in the demo catalog. Run it during initial setup and whenever the PDFs or embedding model change. Keep Ollama running during indexing.

```bash
make index
```

### Start the application

`make dev` starts PostgreSQL, the API, and the frontend. Run it each session, then open the [catalog](http://localhost:3000).

```bash
make dev
```
