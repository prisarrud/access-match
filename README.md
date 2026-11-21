# access-match
AccessMatch is an AI-powered tool that helps wheelchair users compare property entrances before booking a viewing. It analyzes listing descriptions, photos, and property documents to highlight barriers, show how each entrance matches the user’s access needs, and flag details to confirm with the advertiser.

## Getting Started - Web

Start the API using the instructions below. In a second terminal, run the frontend from the repository root.

```bash
cd web

npm install

API_BASE_URL=http://127.0.0.1:8000 npm run dev
```

Open [the local catalog](http://localhost:3000), select two properties, and choose **Comparar imóveis**. Reload the comparison page to check that the selection is kept in the URL.

To save the setting, add `API_BASE_URL=http://127.0.0.1:8000` to `web/.env.local` and run `npm run dev`. The Next.js server fetches the catalog from this address, and the browser opens cover images directly from the API. Use an address reachable by both.

## Getting Started - API

From the repository root, create a virtual environment with Python 3.11 or later and install the API dependencies.

```bash
python3 -m venv api/.venv

source api/.venv/bin/activate

python -m pip install -r api/requirements.txt

python -m uvicorn api.app.main:app --reload
```

Open [the local API catalog](http://127.0.0.1:8000/properties) to inspect the summaries and their cover image URLs.
