# AccessMatch

AccessMatch helps wheelchair users compare the route from the sidewalk to a property's entrance before booking a viewing. It focuses on steps, ramps, and clear passage width.

## Prerequisites

- Make, Python 3.11 or later, and Node.js 20.9 or later with npm.
- Docker with Compose. Start Docker before running the project. Compose downloads and runs PostgreSQL with pgvector. [Docker installation guide](https://docs.docker.com/compose/install/)
- Ollama. Install it and open the app, or run the server in a separate terminal if you use the CLI. Keep Ollama running during setup and while using the project. [Ollama installation](https://ollama.com/download)

```bash
ollama serve
```

<a id="getting-started---api"></a>

## Run locally

Run these commands from the repository root.

### Set up the project

`make setup` creates `.env` from [`.env.example`](.env.example) if needed, installs the API and frontend dependencies, downloads the configured Ollama models, starts PostgreSQL, indexes the demo PDFs, and prepares all demo photos. Run it on a fresh checkout and when dependencies, models, or demo PDFs change.

```bash
make setup
```

### Start the application

`make dev` starts PostgreSQL, the API, and the frontend. Run it each session, then open the [catalog](http://localhost:3000) and select two properties to compare.

```bash
make dev
```

### Run the demo

With Docker and Ollama running, `make prepare-demo` runs the full setup and starts the API and frontend. Open the [catalog](http://localhost:3000) and follow the [demo walkthrough](docs/demo.md).

```bash
make prepare-demo
```

### Run the evaluation

After `make setup`, keep Ollama running and use `make evaluate` to compare two ways of reading PDFs across 20 test cases. One uses retrieved excerpts and the other uses full PDF text. The command prepares the test data, reuses the existing photo analyses, and saves the results to `evaluation/results.json`.

```bash
make evaluate
```

To check the cases, expected results, and source references on their own, run:

```bash
make validate-evaluation
```
