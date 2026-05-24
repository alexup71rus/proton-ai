# Proton-X LLM Service

Этот сервис не является general-purpose chat LLM. Текущая реализация представляет собой маленький FastAPI-сервис для обучения и исполнения tiny tool-router:

- на вход получает user text и tools registry
- лексически выбирает top-k candidate tools
- сериализует компактный prompt
- запускает маленькую causal-модель
- валидирует JSON-ответ модели
- либо возвращает tool call, либо уходит в fallback

Большая часть runtime-политики находится не в модели, а в коде сервиса: candidate filtering, validator, fallback policy и OpenAI-compatible adapter.

## Что умеет сервис

- валидировать tools registry
- строить synthetic dataset для routing
- запускать обучение tiny router model
- отдавать training status
- показывать полный debug pipeline через route preview
- адаптировать внутренний результат в OpenAI-like tool-calling response

Точка входа: `service/main.py`

## Запуск

```bash
cd service
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Проверка:

```bash
curl http://127.0.0.1:8000/health
```

Важно: сам service не читает `PROTONX_*` env-переменные. Пути к данным берутся из `service/protonx/config.py` относительно корня репозитория:

- `data/train/routing`
- `data/tokenizers`
- `data/weights`
- `data/logs`

`PROTONX_*` env сейчас относятся к `web_backend`, а не к `service`.

## Основные модули

- `main.py` — FastAPI endpoints
- `protonx/model_contract.py` — compact model-facing contract
- `protonx/routing/filter.py` — lexical candidate ranking
- `protonx/routing/prompt.py` — сборка runtime prompt payload
- `protonx/routing/model_runtime.py` — загрузка checkpoint/tokenizer и greedy generation
- `protonx/routing/validate.py` — строгая проверка model output
- `protonx/routing/adapter.py` — OpenAI-like финальный ответ
- `protonx/training/dataset_builder.py` — synthetic dataset generation
- `protonx/training/dataset_validation.py` — dataset validation перед training
- `protonx/training/format.py` — сериализация prompt+target для training/inference
- `protonx/training/model.py` — tiny decoder-only model
- `protonx/training/tokenizer.py` — SentencePiece BPE training
- `protonx/training/trainer.py` — training loop и checkpoint writing

## HTTP API

### `GET /health`

Простой healthcheck.

Ответ:

```json
{"status": "ok"}
```

### `POST /tools/validate`

Проверяет tools registry.

Ожидает:

```json
{
  "tools": [
    {
      "name": "light",
      "description": "Light control",
      "tags": ["light", "lamp"],
      "arguments_schema": {
        "type": "object",
        "properties": {
          "state": {"type": "string", "enum": ["on", "off"]}
        },
        "required": ["state"]
      }
    }
  ]
}
```

Проверки:

- имена tools должны быть уникальными
- поддерживается только `arguments_schema.type = object`
- поддерживаются только string-поля
- `enum`, если есть, должен быть списком

Что сейчас не используется сервисом для routing/training:

- `description` обязателен по схеме, но в model-facing prompt не попадает
- scorer не использует `description`

### `POST /route/preview`

Возвращает полный debug-срез runtime pipeline без OpenAI adapter layer.

Запрос:

```json
{
  "user_text": "turn on the lamp",
  "tools": [...],
  "answer_allowed": false,
  "max_candidates": 3,
  "strict_mode": true
}
```

Ответ содержит:

- `candidate_tools` — имена выбранных candidate tools
- `serialized_prompt` — prompt в том виде, как он ушёл в модель
- `model_output` — сырой output модели
- `repaired_output` — output после минимального JSON repair
- `validation_error` — причина отклонения, если validator не принял ответ
- `validator_result` — `valid`, `error`, `final_action`
- `confidence` — `high` или `low`
- `final_action` — `tool_call` или `fallback`

### `POST /chat/completions`

OpenAI-like wrapper поверх того же routing pipeline.

Особенности текущей реализации:

- используется только последнее сообщение: `messages[-1].content`
- `tool_choice` принимается, но сейчас не влияет на поведение
- `max_candidates` и `strict_mode` берутся из дефолтов `RoutePreviewRequest`: `3` и `true`

На успешном tool routing ответ выглядит так:

```json
{
  "tool_calls": [
    {
      "id": "call_1",
      "type": "function",
      "name": "light",
      "arguments": {"state": "on"}
    }
  ],
  "answer": false
}
```

На fallback:

```json
{
  "tool_calls": [],
  "answer": true,
  "fallback": true,
  "response": "I work only with available tools."
}
```

Если `answer_allowed = false`, то fallback остаётся без `response`, а `answer` будет `false`.

### `POST /train/dataset/build`

Генерирует synthetic dataset и всегда пишет его в `data/train/routing/routing.jsonl`.

Вход: тот же tools registry.

Ответ:

```json
{
  "rows_written": 89,
  "output_path": ".../data/train/routing/routing.jsonl"
}
```

Количество строк зависит от входного registry.

### `GET /train/status`

Возвращает текущее состояние global training job:

- `status`
- `current_epoch`, `total_epochs`
- `current_step`, `total_steps`
- `loss`, `loss_history`, `metrics`
- `error`
- `batch_size`, `model_name`, `tokenizer_name`
- `checkpoint_path`, `model_path`, `tokenizer_path`

### `POST /train/start`

Запускает background training thread.

Запрос:

```json
{
  "dataset_path": "/absolute/or/repo-local/path/to/routing.jsonl",
  "epochs": 1,
  "batch_size": 1,
  "model_name": "tiny-router",
  "tokenizer_name": "sentencepiece-bpe"
}
```

Важно:

- dataset валидируется до старта
- если validation не проходит, сервис отвечает `400`
- если training уже идёт, новый job не стартует и возвращается текущее состояние

## Контракт tools registry

Внутренний Pydantic-контракт:

```json
{
  "name": "tool_name",
  "description": "Human-readable description",
  "tags": ["alias 1", "alias 2"],
  "arguments_schema": {
    "type": "object",
    "properties": {
      "field": {"type": "string"}
    },
    "required": ["field"]
  }
}
```

Что реально влияет на routing:

- `name`
- `tags`
- `arguments_schema`

Что не попадает в модель:

- `description`

## Runtime pipeline: как сервис принимает решение

Ниже описан текущий путь для `/route/preview` и `/chat/completions`.

### 1. Лексический pre-router

Сервис сначала не вызывает модель, а ранжирует все tools в `routing/filter.py`.

Скоринг очень простой:

- за пересечение токенов user text и tag: `+2`
- за вхождение полного tag как подстроки: `+3`
- за вхождение `tool.name` как подстроки: `+5`

Дальше:

- tools сортируются по score по убыванию
- при равенстве — по имени
- берётся `max_candidates`

Ранний fallback происходит до модели, если:

- tools нет
- лучший score `<= 0`
- два лучших кандидата имеют одинаковый top score

Во втором и третьем случае это считается low-confidence route.

### 2. Сборка model-facing prompt

Если кандидаты есть, сервис собирает компактный prompt payload:

```json
{
  "answer_allowed": false,
  "tools": [
    {"name": "light", "tags": ["lamp", "light"], "args": {"state": ["on", "off"]}}
  ],
  "user": "turn on the lamp"
}
```

Но в текст, который реально видит модель, попадают только tools и user text:

```text
TOOLS:
- light: lamp | light ; args: state=on | off
USER:
turn on the lamp
OUTPUT:
```

Ключевой момент: `answer_allowed` не сериализуется в prompt text. Сейчас это runtime policy, а не часть model-visible сигнала.

Что происходит с tools перед сериализацией:

- берётся только `name`, `tags`, опционально `args`
- `description` отбрасывается
- tags дедуплицируются
- порядок tags детерминированно тасуется на основе `variation_key`, чтобы dataset не учил модель на одном и том же fixed order
- `args` компактизируются из JSON Schema:
  - enum-поля становятся списком строк
  - остальные поля становятся строкой с типом, обычно `string`

### 3. ModelRuntime

`routing/model_runtime.py` делает следующее:

- проверяет наличие `data/weights/tiny_router_v1.pt`
- проверяет наличие `data/tokenizers/routing_spm.model`
- загружает checkpoint и tokenizer с диска
- проверяет `prompt_format == compact-v1`
- сериализует prompt в текст
- кодирует prompt через SentencePiece
- делает greedy decoding без sampling
- генерирует максимум 64 новых токена
- декодирует итоговую последовательность
- берёт всё, что идёт после `OUTPUT:\n`

Если что-то из этого не получилось, сервис сразу возвращает fallback payload, а не пробует восстановиться через дополнительные шаги.

Важно: модель и tokenizer сейчас загружаются заново на каждый вызов. Постоянно живущего inference runtime в памяти нет.

### 4. Минимальный repair

Перед валидацией используется очень простой repair из `routing/repair.py`:

- если не хватает `}` — они дописываются
- если не хватает `]` — они дописываются

Других repair-правил нет.

### 5. Validator

После repair JSON проходит через `routing/validate.py`.

Модель должна вернуть JSON object следующего вида:

```json
{
  "tool_calls": [
    {
      "name": "light",
      "arguments": {"state": "on"}
    }
  ],
  "answer": false,
  "fallback": false
}
```

Обязательные top-level поля:

- `tool_calls` — список
- `answer` — boolean

Опционально:

- `fallback` — boolean

Правила validator:

- если `fallback = true`, то `tool_calls` обязаны быть пустыми
- если `answer = true`, это допустимо только вместе с `fallback = true`
- пустой `tool_calls` без fallback запрещён
- каждая `tool_call.name` должна входить в candidate set
- `arguments` должны быть объектом
- required аргументы обязаны присутствовать
- в `strict_mode = true` нельзя передавать лишние поля вне schema
- enum-значения обязаны совпадать с schema

Если validator отклоняет output, итоговое действие сервиса всегда `fallback`.

### 6. Logging

В `data/logs/router.jsonl` пишутся только случаи, где модель была вызвана, но validator отклонил output.

Туда сохраняются:

- `user_text`
- `candidate_tools`
- `model_output`
- `validation_error`
- `final_action`

Ранние fallback-сценарии до вызова модели туда не попадают.

### 7. OpenAI adapter

`routing/adapter.py` переводит внутренний payload в внешний ответ.

Принципиально важно:

- fallback text генерируется не моделью
- fallback text добавляется только adapter/runtime слоем
- текущий текст fallback: `I work only with available tools.`

То есть модель не учится выдавать human-readable fallback response. Она учится только structured JSON decision.

## Что именно ожидается от модели

### Валидный tool-call output

```json
{
  "tool_calls": [
    {
      "name": "search_files",
      "arguments": {"query": "package.json"}
    }
  ],
  "answer": false,
  "fallback": false
}
```

### Валидный fallback, когда пользователю можно ответить текстом

```json
{
  "tool_calls": [],
  "answer": true,
  "fallback": true
}
```

### Валидный fallback, когда answer не разрешён

```json
{
  "tool_calls": [],
  "answer": false,
  "fallback": true
}
```

Важно: это валидный runtime output, но не валидная training row. Dataset validator для обучения сейчас требует, чтобы fallback rows были записаны с `answer = true`.

### Что считается невалидным

- не-JSON output
- отсутствие `tool_calls` или `answer`
- `tool_calls: []` без `fallback: true`
- `answer: true` без `fallback: true`
- tool call на tool вне candidate set
- аргументы, не проходящие schema или enum
- лишние аргументы в `strict_mode = true`

## Формат dataset и что попадает в обучение

### Поддерживаемые форматы строк dataset

Сервис принимает два формата JSONL rows.

Компактный формат:

```json
{
  "tools": [
    {"name": "light", "tags": ["light", "lamp"], "args": {"state": ["on", "off"]}}
  ],
  "user": "turn on the lamp",
  "assistant": {
    "tool_calls": [{"name": "light", "arguments": {"state": "on"}}],
    "answer": false,
    "fallback": false
  }
}
```

Legacy формат:

```json
{
  "tools": [...],
  "messages": [
    {"role": "user", "content": "turn on the lamp"},
    {"role": "assistant", "content": "{\"tool_calls\":[...],\"answer\":false}"}
  ]
}
```

Оба формата внутри training нормализуются к compact representation.

### Что dataset validator проверяет

Перед training каждая строка проходит через `training/dataset_validation.py`.

Проверяется:

- строка должна быть валидным JSON object
- должен существовать compact или legacy row shape
- `tools` должен быть списком объектов с `name` и `tags`
- tool args должны быть либо compact `args`, либо legacy `arguments_schema`
- assistant обязан содержать `tool_calls` и `answer`
- fallback rows обязаны иметь `tool_calls = []` и `answer = true`
- non-fallback rows не могут иметь `answer = true`
- каждая tool call должна ссылаться на tool внутри той же строки
- аргументы должны соответствовать schema

Training не стартует, если dataset validation вернул хотя бы одну ошибку.

Отдельно важно: runtime validator и dataset validator здесь не полностью совпадают. Runtime допускает fallback с `answer = false`, если `answer_allowed = false`, но training JSONL сейчас принимает только fallback rows с `answer = true`.

## Как строится synthetic dataset

`training/dataset_builder.py` создаёт dataset из tools registry.

### Обычные tool-call примеры

Для каждого tool builder:

- выбирает 1-2 alias из tags и tool name
- старается смешивать латиницу и кириллицу, если они есть
- генерирует user requests по шаблонам

Шаблоны зависят от типа tool:

- zero-arg tool: `show me ...`, `check ...`, `покажи ...`, `проверь ...`
- single `state` arg: `set ... to on`, `change ... to off`, `поставь ... на ...`
- general args: `use ... with field value`, `run ... with field value`

### Fallback и hard negative примеры

Builder дополнительно добавляет:

- fallback rows: `how are you`, `как дела`, `tell me a joke`, `change it`
- ambiguous hard negatives для overlapping tools
- version ambiguity примеры вроде `show me version`
- argument-probe rows для `search_files` и `search_web`

Последний пункт важен: argument-probe rows добавляются всегда как самостоятельные compact rows, даже если таких tools нет в исходном registry.

### Почему в dataset почти везде `answer = false`

Это ожидаемое поведение контракта:

- `answer = false` означает нормальный tool-call route
- `answer = true` используется только для fallback rows

То есть positive signal для обычной успешной маршрутизации — это не `answer = true`, а валидный `tool_calls`.

Чтобы fallback rows не лежали только в хвосте dataset, builder теперь интерливит special rows в общий поток.

## Как происходит обучение

Текущий training pipeline находится в `training/trainer.py`.

### 1. Проверка dataset

`/train/start` валидирует dataset до запуска background thread.

Внутри `run_training()` dataset дополнительно валидируется ещё раз в `_load_records()`. Это защита от запуска training на битом JSONL даже при прямом вызове trainer.

### 2. Сериализация training text

Каждая запись dataset сериализуется как:

```text
TOOLS:
- ...
USER:
...
OUTPUT:
{"answer":false,"fallback":false,"tool_calls":[...]}
```

Важно:

- training идёт на полном concatenated тексте prompt + assistant JSON
- модель учится как обычная next-token causal LM
- никакого отдельного classification head нет

### 3. Обучение tokenizer

Перед model training сервис заново строит tokenizer corpus и обучает SentencePiece:

- corpus: `data/tokenizers/routing_corpus.txt`
- model prefix: `data/tokenizers/routing_spm`
- tokenizer type: BPE
- `vocab_size = 512`
- `pad_id = 0`, `bos_id = 1`, `eos_id = 2`, `unk_id = 3`

### 4. Архитектура модели

Используется собственная минимальная decoder-only модель `TinyRouterModel`:

- embedding + positional embedding
- 2 transformer blocks
- `hidden_dim = 64`
- `num_heads = 4`
- `max_seq_len = 256`
- финальная linear head в размер словаря

Это не Gemma/Llama-совместимая архитектура и не production LLM. Это минимальный учебный baseline.

### 5. Training loop

Training устроен так:

- optimizer: `AdamW(lr=1e-3)`
- loss: `CrossEntropyLoss`
- данные идут батчами по `batch_size`
- для каждого batch текст токенизируется SentencePiece tokenizer-ом
- модель предсказывает следующий токен по схеме teacher forcing

Что важно понимать про текущую реализацию:

- shuffle dataset сейчас нет
- train/val split сейчас нет
- evaluation loop сейчас нет
- early stopping сейчас нет
- best-checkpoint selection сейчас нет
- loss считается по всему padded batch без явного masking pad positions
- `model_name` и `tokenizer_name` сохраняются в status, но не переключают реализацию

### 6. Артефакты training

После обучения сохраняются:

- `data/weights/tiny_router_v1.pt`
- `data/tokenizers/routing_spm.model`
- `data/tokenizers/routing_spm.vocab`
- `data/tokenizers/routing_corpus.txt`

Checkpoint содержит:

- `config`
- `state_dict`
- `prompt_format`

`prompt_format` сейчас должен быть равен `compact-v1`. Если checkpoint обучен на старом формате, runtime не пытается использовать его и сразу уходит в fallback.

## Почему fallback и human response вынесены из модели

Текущее проектное решение такое:

- модель должна принимать только routing decision
- user-facing fallback text должен добавляться снаружи
- validator и adapter контролируют итоговый безопасный output

Это уменьшает загрязнение training signal runtime-политикой и не заставляет tiny router учить лишний natural language output.

## Практические ограничения текущей версии

- это не chat model, а router
- routing scorer лексический и очень простой
- `description` tools не используется
- `tool_choice` в `/chat/completions` сейчас игнорируется
- `answer_allowed` не попадает в model-visible prompt
- модель и tokenizer загружаются заново на каждый inference call
- JSON repair минимальный
- логируются только post-model validation failures
- в сервисе только один global training state, очереди job-ов нет

## Полезные файлы для чтения

- `service/main.py`
- `service/protonx/model_contract.py`
- `service/protonx/routing/inference.py`
- `service/protonx/routing/validate.py`
- `service/protonx/training/dataset_builder.py`
- `service/protonx/training/dataset_validation.py`
- `service/protonx/training/trainer.py`
- `service/tests/test_preview.py`
- `service/tests/test_validation.py`
- `service/tests/test_adapter.py`

Коротко: текущий сервис учит маленькую causal LM продолжать compact prompt до валидного JSON tool-routing decision, а всё остальное — candidate filtering, fallback policy, schema validation и human-readable fallback response — делается кодом вокруг модели.