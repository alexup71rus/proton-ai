# Getting Started

## Install

Use Python 3.11 or 3.12 and Node.js 18+.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r service/requirements.txt
python -m pip install -r web_backend/requirements.txt
python -m pip install -r requirements-dev.txt
(cd web_ui && npm install)
```

## Run

Start all local services:

```bash
make run-dev
```

Or run them separately:

```bash
make run-service
make run-ui-backend
make run-web-ui
```

URLs:

- `http://127.0.0.1:8000/health` - model service
- `http://127.0.0.1:8100/health` - UI backend
- `http://localhost:8501` - web UI

The Vite web UI proxies `/api` to `http://127.0.0.1:8100`.

## Verify

```bash
python -m pytest --import-mode=importlib service/tests web_backend/tests -q
(cd web_ui && npm run build)
```
