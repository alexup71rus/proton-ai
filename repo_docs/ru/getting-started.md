# Быстрый старт

## Установка

Используй Python 3.11 или 3.12 и Node.js 18+.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r service/requirements.txt
python -m pip install -r web_backend/requirements.txt
python -m pip install -r requirements-dev.txt
(cd web_ui && npm install)
```

## Запуск

Все local services:

```bash
make run-dev
```

Или по процессам:

```bash
make run-service
make run-ui-backend
make run-web-ui
```

Адреса:

- `http://127.0.0.1:8000/health` - model service
- `http://127.0.0.1:8100/health` - UI backend
- `http://localhost:8501` - web UI

Vite web UI проксирует `/api` в `http://127.0.0.1:8100`.

## Проверка

```bash
python -m pytest --import-mode=importlib service/tests web_backend/tests -q
(cd web_ui && npm run build)
```
