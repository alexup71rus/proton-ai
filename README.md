# Proton-X

Платформа для сборки и проверки маленького `tool-router` для structured tool calling.

## Что сейчас есть

Подробно про внутреннее устройство LLM-сервиса: [service/README.md](service/README.md)

Текущий `v1` построен вокруг сценария:

- создать tools registry
- сгенерировать или импортировать dataset
- запустить обучение tiny routing model
- протестировать tool calling
- разобрать fallback/error cases через logs

Это не general-purpose чат-модель. Это маленький router, где большая часть логики живёт в:

- candidate filtering
- validator
- fallback policy
- OpenAI-compatible adapter

## Структура проекта

```
proton-x/
├── service/          # LLM-сервис (FastAPI)
│   ├── main.py
│   ├── protonx/      # Runtime, training, validation
│   └── requirements.txt
├── web_backend/      # UI backend / BFF (FastAPI)
│   ├── app.py
│   ├── requirements.txt
│   └── tests/
├── web_ui/           # Operator UI (React + Vite + TypeScript)
│   ├── src/
│   ├── package.json
│   └── vite.config.ts
├── web/              # Legacy Streamlit UI stub
│   ├── app.py
│   ├── pages/
│   └── requirements.txt
├── data/             # Данные (не в git)
│   ├── tools/        # Tools registry file
│   ├── train/        # Synthetic/imported datasets
│   ├── tokenizers/
│   ├── weights/
│   └── logs/
├── docs/             # Документация и планы
└── README.md
```

## Интерфейс

Интерфейс состоит из четырёх основных экранов:

- **Tools** — редактор файла с реестром инструментов
- **Dataset + Training** — генерация датасета, импорт и экспорт, запуск обучения и отображение прогресса
- **Test** — основной экран для проверки запросов и просмотра отладочного пайплайна
- **Logs** — просмотр fallback- и error-case сценариев в читаемом виде

Роли компонентов распределены следующим образом:

- `web_ui` — SPA на React/Vite
- `web_backend` — BFF-слой, который работает с файлами и проксирует runtime- и training-запросы в `service`
- `service` — основной сервис для routing, preview, сборки датасета и training runtime

## Tools registry

Tools хранятся в обычном JSON/YAML-файле.

Путь к файлу задаётся через env:

```bash
export PROTONX_TOOLS_FILE=/absolute/path/to/tools.json
```

Если env не задан, по умолчанию используется:

```text
data/tools/tools.json
```

UI редактирует этот файл, но файл остаётся source of truth и может правиться вручную.

## Быстрый старт

### 1. Установка зависимостей

```bash
# LLM-сервис
cd service && pip install -r requirements.txt

# UI backend / BFF
cd web_backend && pip install -r requirements.txt

# Frontend
cd web_ui && npm install
```

### 2. Настроить data paths

```bash
cd /path/to/proton-x
export PROTONX_TOOLS_FILE=$(pwd)/data/tools/tools.json
export PROTONX_DATASET_DIR=$(pwd)/data/train/routing
export PROTONX_ROUTER_LOG_FILE=$(pwd)/data/logs/router.jsonl
export PROTONX_SERVICE_URL=http://127.0.0.1:8000
```

### 3. Запуск

Самый удобный вариант из корня репозитория:

```bash
make run-service
make run-ui-backend
make run-web-ui
```

Или одним процессом:

```bash
make run-dev
```

Если нужен ручной запуск без Makefile:

```bash
# Терминал 1
cd service && uvicorn main:app --reload --port 8000

# Терминал 2
cd /path/to/proton-x && uvicorn web_backend.app:app --reload --port 8100

# Терминал 3
cd web_ui && npm run dev
```

### 4. Проверка

- LLM-сервис: http://localhost:8000/health
- UI backend: http://127.0.0.1:8100/api/tools
- Веб-интерфейс: http://localhost:8501

### 5. Legacy Streamlit

Папка `web/` больше не является основным UI. Она оставлена только как legacy-notice, чтобы явно показывать, что старый Streamlit workflow снят с эксплуатации.

## Стек

- Python 3.11+
- FastAPI + Uvicorn
- React 18 + TypeScript + Vite
- PyTorch
- SentencePiece
- Transformers, Datasets, Accelerate, TRL
- Safetensors, Einops

## Текущая модель

Текущая baseline-модель — маленький causal decoder для routing-SFT.

Это не Gemma-compatible architecture и не production LLM. Это учебный/инженерный baseline для:

- `top-k candidate tools`
- structured output
- validator-driven fallback
