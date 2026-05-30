# Proton-X Service

`service/` — FastAPI ядро для обучения и запуска tiny-router модели Proton-X.

В продуктовой модели Proton-X пользователь описывает свои автоматизации как tools, генерирует dataset и обучает маленькую модель выбирать нужную команду с аргументами. `service/` отвечает именно за модельную часть этого цикла: validation контракта, prompt/runtime path, dataset bootstrap и training.

Это не chat LLM и не универсальный ассистент. В v1 модель делает одну узкую вещь: получает registry инструментов и текст пользователя, затем генерирует OpenAI-style `tool_calls` JSON. Ответы пользователю, выполнение скриптов, UI state и будущие цепочки действий строятся поверх validated tool execution во внешнем слое.

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

## Роль сервиса в Proton-X

`service/` должен оставаться модельным ядром, а не местом для продуктовой логики автоматизации.

Он отвечает за:

- валидацию tool registry для поддерживаемого schema subset;
- сборку компактного routing prompt;
- запуск tiny-router runtime;
- проверку JSON output и аргументов;
- canonical fallback при ошибках;
- генерацию bootstrap dataset;
- обучение и сохранение checkpoint/tokenizer artifacts.

Он не отвечает за:

- исполнение пользовательских скриптов;
- хранение UI workspace settings;
- редактирование tools registry;
- форматирование человекочитаемых ответов;
- будущий marketplace/tools authoring слой.

Такое разделение важно для будущей архитектуры: более умная модель или marketplace могут помогать создавать tools и datasets, но маленькая локальная модель должна только выбирать разрешённые tools и аргументы в строгом контракте.

## Runtime path

```text
user_text
  -> tools registry
  -> compact prompt
  -> ModelRuntime.generate()
  -> validator
  -> final_output
```

Runtime не чинит JSON и не делает constrained scoring по registry. Если модель вернула invalid JSON, validator возвращает ошибку, `final_output` становится canonical fallback для безопасного executor/frontend path, а debug сохраняет сырой `model_output`.

`/route/preview` возвращает debug этого же прохода: prompt, raw model output, validation result, final action и `final_output`. Поле `repaired_output` оставлено только для API compatibility и в текущем режиме должно быть `null`.

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

Это принципиально для сценария автоматизации: модель может ошибаться, но executor/frontend должны получать безопасный и предсказуемый результат, а не произвольный текст.

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

Dataset должен учить модель двум вещам:

- выбирать правильный tool среди доступных candidates;
- заполнять только валидные аргументы по компактному описанию schema.

Fallback rows так же важны, как positive rows: они учат модель не вызывать случайную команду, когда запрос не покрывается текущим registry.

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
