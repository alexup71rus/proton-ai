# Быстрый Старт

## Установка

Из корня репозитория:

```bash
cd service && pip install -r requirements.txt
cd ../web_backend && pip install -r requirements.txt
cd ../web_ui && npm install
```

## Запуск

Самый простой вариант:

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
- `http://localhost:8501` - React UI

Vite UI проксирует `/api` в `http://127.0.0.1:8100`.

## Проверка

```bash
pytest --import-mode=importlib service/tests web_backend/tests -q
cd web_ui && npm run build
```

Если `python3` указывает на Python без зависимостей, используй тот же interpreter, на котором запускается `uvicorn`. На macOS в этом проекте часто подходит `python3.11`.

