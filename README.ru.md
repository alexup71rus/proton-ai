# Proton AI

Proton AI - AI constructor для создания маленьких локальных моделей, которые выбирают tool call по пользовательскому запросу. Пользователь описывает tools и executors, собирает supervised dataset, обучает tiny-router модель и проверяет структурированные вызовы в web UI.

Runtime-модель не является универсальным chat assistant. Ее задача уже: получить tools registry и текст пользователя, затем вернуть валидный `tool_calls` JSON. Validation и execution остаются в контролируемом коде вне модели.

English documentation: [README.md](README.md)

## Контракт модели

```text
tools registry + user_text -> tool_calls JSON
```

Обычный tool call:

```json
{"tool_calls":[{"name":"get_current_time","arguments":{}}]}
```

Fallback тоже является структурированным tool call:

```json
{"tool_calls":[{"name":"__fallback__","arguments":{}}]}
```

Основной цикл продукта:

```text
define tools -> build dataset -> train model -> test -> inspect logs -> improve dataset
```

## Для чего это нужно

Во многих automation-системах человек или разработчик должен заранее выбрать точную команду. Proton AI заменяет этот шаг: пользователь пишет обычный запрос, а маленькая обученная модель выбирает действие только из разрешенного tools registry.

Подход подходит там, где нужен структурированный результат, а не свободный текст:

- локальные automation commands;
- выбор внутренних API operations;
- classification в разрешенные actions;
- запуск scripts с validated arguments;
- маленькие offline routers под фиксированный набор tools.

## Архитектура

```text
service/      FastAPI model service: routing, validation, dataset build, training
web_backend/  FastAPI UI backend: workspace, tools, datasets, execution, logs
web_ui/       React/Vite web UI
web/          retired Streamlit UI для совместимости
data/         local tools, datasets, weights, tokenizers, logs, workspace state
repo_docs/    tracked project documentation на английском и русском
```

Внутренний Python package пока называется `protonx`. Публичное имя проекта - `Proton AI`, repository slug - `proton-ai`.

## Требования

- Python 3.11 или 3.12
- Node.js 18+ и npm
- macOS, Linux или другая среда, поддерживаемая PyTorch

Рекомендуется virtual environment:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r service/requirements.txt
python -m pip install -r web_backend/requirements.txt
python -m pip install -r requirements-dev.txt
(cd web_ui && npm install)
```

Если используется другой Python command, используй один и тот же interpreter для install, tests и `uvicorn`.

## Локальный запуск

Все процессы:

```bash
make run-dev
```

Отдельно:

```bash
make run-service
make run-ui-backend
make run-web-ui
```

Адреса:

- `http://127.0.0.1:8000/health` - model service
- `http://127.0.0.1:8100/health` - UI backend
- `http://localhost:8501` - web UI

Страницы web UI:

- **Tools** - редактирование tools registry и executor paths.
- **Training** - import/generate datasets, validation и запуск training.
- **Test** - проверка user text на выбранной модели, validation output и execution output.
- **Logs** - routing incidents и export failed cases в dataset drafts.

## Как собрать модель

1. Добавь tools на странице **Tools** или в `data/tools/tools.json`.
2. Укажи безопасные и доверенные `executor_path`.
3. Открой **Training** и выбери dataset storage.
4. Импортируй compact JSONL dataset или сгенерируй bootstrap dataset из tools registry.
5. Запусти training новой модели.
6. Проверь реальные запросы на странице **Test**.
7. Используй **Logs**, чтобы найти недостающие phrases, aliases, argument values и fallback cases.

Compact JSONL row:

```json
{
  "tools": [
    {"name":"get_current_time","tags":["time","date"]},
    {"name":"__fallback__","tags":["fallback","no tool"]}
  ],
  "user": "what time is it",
  "assistant": {
    "tool_calls": [{"name":"get_current_time","arguments":{}}]
  }
}
```

## Environment variables

Публичные имена используют `PROTON_AI_*`. Старые `PROTONX_*` имена пока поддерживаются для совместимости.

| Variable | Назначение | Default |
| --- | --- | --- |
| `PROTON_AI_TOOLS_FILE` | tools registry file | `data/tools/tools.json` |
| `PROTON_AI_DATASET_DIR` | dataset storage folder | `data/train/routing` |
| `PROTON_AI_ROUTER_LOG_FILE` | router log JSONL file | `data/logs/router.jsonl` |
| `PROTON_AI_WORKSPACE_FILE` | UI workspace settings file | `data/workspace/settings.json` |
| `PROTON_AI_SERVICE_URL` | model service URL для UI backend | `http://127.0.0.1:8000` |
| `PROTON_AI_TRAIN_DEVICE` | training device override | `cpu` |
| `PROTON_AI_TRAIN_STATE_PATH` | training status file | `data/workspace/training_state.json` |

## Проверка

```bash
python -m pytest --import-mode=importlib service/tests web_backend/tests -q
(cd web_ui && npm run build)
```

Длинные synthetic dataset tests полезны перед изменениями генератора датасета, но не обязательны для обычных UI/backend правок.

## Перед публикацией

Сгенерированное состояние не должно попадать в git:

- `data/train/*`
- `data/weights/*`
- `data/tokenizers/*`
- `data/tools/*`
- `data/logs/*`
- `data/workspace/settings.json`

В git остаются examples и `.gitkeep`, чтобы структура локальных папок была понятна.

## Документация

- [Documentation index](repo_docs/README.md)
- [English guides](repo_docs/en/README.md)
- [Russian guides](repo_docs/ru/README.md)
- [Project concept](PROJECT_CONCEPT.ru.md)
- [Service reference](service/README.md)
