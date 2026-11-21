# access-match
AccessMatch is an AI-powered tool that helps wheelchair users compare property entrances before booking a viewing. It analyzes listing descriptions, photos, and property documents to highlight barriers, show how each entrance matches the user’s access needs, and flag details to confirm with the advertiser.

## Getting Started - Web

First, run the development server:

```bash
cd web

npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

## Getting Started - API

From the repository root, create a virtual environment with Python 3.11 or later and install the API dependencies.

```bash
python3 -m venv api/.venv

source api/.venv/bin/activate

python -m pip install -r api/requirements.txt

python -m uvicorn api.app.main:app --reload
```
