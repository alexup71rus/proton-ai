# Proton-X Service

`service/` — FastAPI сервис для обучения и запуска текущей tiny router модели.

В v1 модель делает одну узкую вещь: выбирает инструмент из кандидатов и возвращает OpenAI-style `tool_calls` JSON. Это не chat LLM; ответы пользователю и будущие цепочки действий должны строиться поверх validated tool execution.

## Контракт модели

```text
tools registry + user_text -> tool_calls JSON
```

Пример обычного выбора:

```json
{"tool_calls":[{"name":"get_current_time","arguments":{}}]}
```

Fallback тоже является tool call:

```json
{"tool_calls":[{"name":"__fallback__","arguments":{}}]}
```

Модель v1 не пишет обычный текст, fallback copy, объяснения и ответы пользователю. Это делает внешний слой после validation/execution.

## Runtime path

```text
user_text
  -> tools registry
  -> compact prompt
  -> ModelRuntime.generate()
  -> JSON repair
  -> validator
  -> final_output
```

`/route/preview` возвращает debug этого же прохода: prompt, raw/repaired output, validation result, final action и `final_output`.

`/chat/completions` — совместимый adapter поверх того же router path. Политика вроде `answer_allowed` относится к adapter/template слою и не попадает в prompt или validator.

## Что видит модель

В prompt попадают только routing-поля инструмента:

- `name`
- `tags`
- compact `args` summary

Не попадают:

- `description`
- полный `arguments_schema`
- executor path/config
- fallback text
- response-generation policy

Текущая версия prompt/checkpoint compatibility: `compact-v2`.

## Validator

Validator проверяет JSON shape, candidate membership, required arguments, enum values, лишние arguments в strict mode и правило, что `__fallback__` не смешивается с обычными tools.

При ошибке route уходит в canonical fallback output.

## Training data

Основной компактный JSONL формат:

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

Legacy chat-shaped rows ещё принимаются для совместимости, но новые данные лучше держать в компактном формате.

## API минимум

- `GET /health`
- `POST /tools/validate`
- `POST /route/preview`
- `POST /chat/completions`
- `POST /train/dataset/build`
- `POST /train/start`
- `GET /train/status`

## Запуск

Из корня репозитория:

```bash
make run-service
```

Или вручную:

```bash
cd service
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

## Проверка

Из корня репозитория:

```bash
pytest --import-mode=importlib service/tests web_backend/tests -q
```
