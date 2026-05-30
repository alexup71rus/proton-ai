# Datasets, Обучение И Проверка

## Compact JSONL

Новый dataset лучше держать в compact формате:

```json
{
  "tools": [
    {"name":"get_current_time","tags":["время","дата"]},
    {"name":"__fallback__","tags":["нет инструмента","неподдерживаемый запрос"]}
  ],
  "user": "который час",
  "assistant": {
    "tool_calls": [{"name":"get_current_time","arguments":{}}]
  }
}
```

Fallback тоже является обычным supervised row:

```json
{
  "tools": [
    {"name":"get_current_time","tags":["время"]},
    {"name":"__fallback__","tags":["нет инструмента"]}
  ],
  "user": "напиши стихотворение",
  "assistant": {
    "tool_calls": [{"name":"__fallback__","arguments":{}}]
  }
}
```

## Генерация Bootstrap Dataset

Из корня проекта:

```bash
PYTHONPATH=service python3.11 -m protonx.training.bootstrap_dataset_mixer_for_tools \
  --tools data/tools/tools.json \
  --output data/train/routing/routing.jsonl \
  --target-rows 50000
```

Если окружение настроено на другой Python, используй interpreter, где установлены зависимости `service/requirements.txt`.

## Обучение Через API

Чтобы progress был виден в web UI, запускай через service API или через UI backend. Пример прямого вызова service:

```bash
curl -X POST http://127.0.0.1:8000/train/start \
  -H 'Content-Type: application/json' \
  -d '{
    "dataset_path": "/Users/aleksandr/Documents/Projects/proton-x/data/train/routing/routing.jsonl",
    "epochs": 2,
    "batch_size": 8,
    "output_root_dir": "/Users/aleksandr/Documents/Projects/proton-x/data",
    "artifact_name": "router",
    "hidden_dim": 256,
    "num_layers": 6,
    "num_heads": 8,
    "learning_rate": 0.0005,
    "training_device": "auto",
    "vocab_size": 1024
  }'
```

Новая модель создается, если не передавать `resume_model_path` и `resume_tokenizer_path`.

## Артефакты

При `artifact_name: "router"`:

```text
data/weights/router.pt
data/tokenizers/router.model
data/tokenizers/router.vocab
data/tokenizers/router.corpus.txt
```

## Evaluation

После обучения service строит holdout из строк, которых нет в train dataset. Основные метрики:

- `Exact match` - полностью совпал tool call и arguments.
- `Valid output` - модель вернула валидный JSON по контракту.
- `Positive rows` - точность на обычных tool calls.
- `Fallback rows` - точность на fallback.
- `Invalid outputs` - JSON/schema/tool errors.

Для маленькой модели `Valid output` и `Fallback rows` так же важны, как `Exact match`: они показывают, что модель держит контракт и не вызывает случайные tools.

## Test И Logs

`Test` отправляет user request в текущую выбранную модель, показывает final action, arguments, validation error, executor output и debug.

`Logs` хранит routing incidents и умеет экспортировать failed cases в dataset draft. Это полезнее, чем вслепую добавлять эпохи: реальные промахи показывают, какие слова, aliases и argument values нужно добавить в corpus.

