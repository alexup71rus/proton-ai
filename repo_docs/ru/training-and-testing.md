# Training и Testing

## Compact JSONL

Рекомендуемый row format:

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

Fallback - обычный supervised row:

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

## Генерация bootstrap dataset

Из корня repository:

```bash
PYTHONPATH=service python -m protonx.training.bootstrap_dataset_mixer_for_tools \
  --tools data/tools/tools.json \
  --output data/train/routing/routing.jsonl \
  --target-rows 50000
```

Внутренний package name остается `protonx`; публичное имя проекта - Proton AI.

## Training через API

Используй UI или API, чтобы progress был виден в web UI. Прямой вызов model service:

```bash
curl -X POST http://127.0.0.1:8000/train/start \
  -H 'Content-Type: application/json' \
  -d "{
    \"dataset_path\": \"$PWD/data/train/routing/routing.jsonl\",
    \"epochs\": 2,
    \"batch_size\": 8,
    \"output_root_dir\": \"$PWD/data\",
    \"artifact_name\": \"router\",
    \"hidden_dim\": 256,
    \"num_layers\": 6,
    \"num_heads\": 8,
    \"learning_rate\": 0.0005,
    \"training_device\": \"auto\",
    \"vocab_size\": 1024
  }"
```

Новая модель создается, если не передавать `resume_model_path` и `resume_tokenizer_path`.

## Artifacts

Для `artifact_name: "router"`:

```text
data/weights/router.pt
data/tokenizers/router.model
data/tokenizers/router.vocab
data/tokenizers/router.corpus.txt
```

## Evaluation

После training model service строит holdout из строк, которые не использовались в train dataset. Основные metrics:

- `Exact match` - tool call и arguments совпали полностью.
- `Valid output` - model output является валидным JSON по контракту.
- `Positive rows` - accuracy на обычных tool calls.
- `Fallback rows` - accuracy на fallback rows.
- `Invalid outputs` - JSON, schema или tool membership errors.

Для маленького router `Valid output` и `Fallback rows` так же важны, как `Exact match`. Они показывают, держит ли модель контракт и не вызывает ли случайные tools.

## Test и Logs

**Test** отправляет user text в выбранную модель и показывает final action, arguments, validation error, executor output и debug data.

**Logs** хранит routing incidents и умеет export failed cases в dataset draft. Обычно это полезнее, чем добавлять epochs без изменения данных: реальные ошибки показывают, каких phrases, aliases и argument values не хватает в corpus.
