# Proton-X

Платформа для сборки и проверки маленького `tool-router` для structured tool calling.

## Назначение

Подробно про внутреннее устройство LLM-сервиса: [service/README.md](service/README.md)

Рабочий цикл `v1`:

- создать tools registry
- выбрать dataset для обучения явным именем файла
- выбрать активную модель через верхний toolbar и задать пути артефактов
- запустить обучение или дообучение выбранной модели
- протестировать tool calling
- разобрать fallback/error cases через logs

Это маленький router, где большая часть логики живёт в:

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
- **Dataset + Training** — явный выбор dataset, запуск обучения/дообучения активной модели и отображение прогресса
- **Test** — основной экран для проверки запросов на текущей выбранной модели и просмотра отладочного пайплайна
- **Logs** — просмотр fallback- и error-case сценариев в читаемом виде

Состояние model workspace хранится в `web_backend` и сериализуется в файл настроек:

- `data/workspace/settings.json`
- путь можно переопределить через `PROTONX_WORKSPACE_FILE`
- фронтенд читает и обновляет этот файл через `/api/workspace`
- `localStorage` для выбранной модели, training defaults и test-page state не используется

Управление активной моделью находится в верхнем toolbar:

- `Create model` — задаёт новую архитектуру tiny-router и целевые пути сохранения
- `Load model` — импортирует checkpoint `.pt` и tokenizer `.model` через UI
- выбранная модель используется и на странице обучения, и на странице теста

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

Datasets для обучения не выбираются автоматически по карточкам. На экране Dataset + Training указывается конкретное имя dataset-файла, при этом UI может подсказывать уже обнаруженные файлы из `PROTONX_DATASET_DIR`.

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
export PROTONX_WORKSPACE_FILE=$(pwd)/data/workspace/settings.json
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

Рабочий цикл в UI:

1. В верхнем toolbar выбрать `Create model` или `Load model`
2. На `Dataset + Training` указать dataset file, epochs и batch size, затем запустить train или fine-tune
3. На `Test` прогонять запросы на активной модели

Если нужно изменить активную модель, dataset по умолчанию, training defaults или test-page state без открытия UI, достаточно поправить [data/workspace/settings.json](data/workspace/settings.json).

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

UI и backend работают с моделью, указанной в workspace settings, а не с жёстко зашитым именем checkpoint-файла.
