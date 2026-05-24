# Proton-X v1 handoff for the next AI agent

Документ для следующей нейронки. Цель: продолжить работу без возврата к уже отвергнутым обходным решениям.

## Главная цель

Proton-X v1 сейчас должен быть маленькой generative tool-calling моделью, а не чат-моделью.

Модель получает полный registry доступных tools и текст пользователя, затем сама возвращает строго структурированный JSON:

```json
{"tool_calls":[{"name":"get_node_version","arguments":{}}]}
```

Если запрос не подходит ни под один tool, модель должна вернуть синтетический tool `__fallback__`:

```json
{"tool_calls":[{"name":"__fallback__","arguments":{}}]}
```

Важные продуктовые решения:

- Не возвращать pre-router/top-k candidate filtering. Он противоречит концепции полного registry.
- Не возвращать `call-v1 + constrained scoring` как основной runtime. Это работало лучше как классификатор, но не учит модель честно писать JSON, аргументы и будущие цепочки tool calls.
- Не делать JSON repair. Если модель сгенерировала некорректный JSON, это ошибка модели/данных, а не место для скрытой починки.
- Не вводить tool ids/indexes в v1. Это было отклонено как преждевременное усложнение.
- Не подгонять dataset под конкретные smoke-фразы. Нужны вариативные данные: разные формулировки, decoy tools, fallback-примеры.
- Основной artifact name: `proton_router_v1`.
- Eval должен быть коротким и формальным, уникальным относительно train rows.

## Очень важные ограничения

- Не делать `git commit` и `git push`, если пользователь явно не попросил.
- Перед правкой файлов в [service](../service/) проверь статус обучения. Service запущен через `uvicorn --reload`, поэтому изменение service-файлов во время training может перезапустить процесс.
- Если training уже идёт, сначала проверь `/api/training/status` и дождись `completed` или спроси пользователя, если нужно прервать.
- Не запускай долгий eval внутри training.
- Для fresh training через BFF обязательно передавай `"resume_model_path": null` и `"resume_tokenizer_path": null`. Иначе BFF может автоматически сделать resume из выбранной loaded model, и параметры архитектуры будут проигнорированы.

## Текущее целевое состояние

Целевой режим: `json-v1` generative output.

Смысл:

- training target: полный JSON `{"tool_calls":[...]}`;
- runtime: raw greedy generation;
- validator получает сырой `model_output`;
- `repaired_output` в debug/API должен быть `null`;
- если JSON invalid, frontend/debug должен показать raw `model_output`, `validation_error` и `validator_result`;
- canonical fallback JSON допустим в `final_output` только как безопасный результат для executor/frontend после ошибки validation;
- infrastructure fallback допустим, когда runtime не смог загрузить artifacts.

Ключевые файлы:

- [service/protonx/training/format.py](../service/protonx/training/format.py): `json-v1` serialization of prompt + assistant target.
- [service/protonx/routing/model_runtime.py](../service/protonx/routing/model_runtime.py): greedy generation of raw model continuation.
- [service/protonx/routing/inference.py](../service/protonx/routing/inference.py): validation of raw model output without repair.
- [service/protonx/routing/validate.py](../service/protonx/routing/validate.py): JSON/shape/tool/schema validation.
- [service/protonx/training/evaluation.py](../service/protonx/training/evaluation.py): короткий unique holdout eval.
- [service/protonx/training/trainer.py](../service/protonx/training/trainer.py): сохраняет `output_format: "json-v1"` и evaluation summary.

## Рабочая зона параметров

Текущий production artifact после fresh run:

```text
model_path: data/weights/proton_router_v1.pt
tokenizer_path: data/tokenizers/proton_router_v1.model
output_format: json-v1
hidden_dim: 256
num_layers: 4
num_heads: 8
vocab_size: 512
max_seq_len: 319
best_epoch: 10
best_epoch_loss: 0.03868323729987791
dataset_row_count: 1500
```

Короткий unique holdout eval текущего `proton_router_v1`:

```text
eval_total: 14
eval_valid: 14
eval_exact: 2
eval_positive_total: 10
eval_positive_exact: 2
eval_fallback_total: 4
eval_fallback_exact: 0
invalid_json: 0
invalid_shape: 0
unknown_tool: 0
schema_error: 0
```

Параметры fresh run, от которых стоит стартовать:

```text
hidden_dim: 256
num_layers: 4
num_heads: 8
batch_size: 16
learning_rate: 0.0005
epochs: 10
vocab_size: 512
target/output_format: json-v1
runtime: raw greedy JSON generation, no repair
```

Качество пока не принято как финальное: holdout `2/14` слабый. Но это честная generative JSON baseline. Следующий прирост надо искать в данных, prompt format, tokenization/model capacity и обучающем flow, не в repair/scoring.

## Команда fresh training

Если нужен новый production run, стартуй fresh, без resume:

```bash
curl -sS -X POST http://127.0.0.1:8000/train/start \
  -H 'Content-Type: application/json' \
  -d '{"dataset_path":"/Users/aleksandr/Documents/Projects/proton-x/data/train/routing/routing.jsonl","epochs":10,"batch_size":16,"model_name":"tiny-router","tokenizer_name":"sentencepiece-bpe","output_root_dir":"/Users/aleksandr/Documents/Projects/proton-x/data","artifact_name":"proton_router_v1","resume_model_path":null,"resume_tokenizer_path":null,"hidden_dim":256,"num_layers":4,"num_heads":8,"learning_rate":0.0005}'
```

После training проверь, что [data/workspace/settings.json](../data/workspace/settings.json) содержит относительные пути:

```json
{
  "output_root_dir": "data",
  "model_path": "data/weights/proton_router_v1.pt",
  "tokenizer_path": "data/tokenizers/proton_router_v1.model"
}
```

## Как проверить статус

```bash
cd /Users/aleksandr/Documents/Projects/proton-x
curl --max-time 10 -sS http://127.0.0.1:8100/api/training/status | python -m json.tool
```

Если BFF не отвечает, проверь service напрямую:

```bash
curl --max-time 10 -sS http://127.0.0.1:8000/train/status | python -m json.tool
```

## Как запущены сервисы

Service, порт 8000:

```bash
cd /Users/aleksandr/Documents/Projects/proton-x/service
/usr/local/Cellar/python@3.11/3.11.13/bin/python3.11 -m uvicorn main:app --reload --port 8000
```

BFF, порт 8100:

```bash
cd /Users/aleksandr/Documents/Projects/proton-x
/usr/local/Cellar/python@3.11/3.11.13/bin/python3.11 -m uvicorn web_backend.app:app --reload --port 8100
```

## Dataset

Текущий dataset:

- Файл: [data/train/routing/routing.jsonl](../data/train/routing/routing.jsonl)
- Размер: 1500 rows
- Формат строки: `tools`, `user`, `assistant`
- `assistant` содержит целевой JSON `tool_calls`
- Training loss считается только на assistant continuation; prompt tokens masked через `IGNORE_INDEX`

Распределение классов на момент handoff:

```text
list_downloads: 237
get_node_version: 236
get_python_version: 236
get_current_time: 236
get_disk_usage: 236
__fallback__: 319
```

Распределение количества tools в prompt:

```text
6 tools: 515 rows
7 tools: 495 rows
8 tools: 490 rows
```

Seed/mixer:

- [service/protonx/training/bootstrap_dataset_mixer_for_tools.json](../service/protonx/training/bootstrap_dataset_mixer_for_tools.json)
- [service/protonx/training/bootstrap_dataset_mixer_for_tools.py](../service/protonx/training/bootstrap_dataset_mixer_for_tools.py)

Команда генерации:

```bash
cd /Users/aleksandr/Documents/Projects/proton-x
PYTHONPATH=service /usr/local/Cellar/python@3.11/3.11.13/bin/python3.11 \
  -m protonx.training.bootstrap_dataset_mixer_for_tools \
  --tools data/tools/tools.json \
  --output data/train/routing/routing.jsonl \
  --target-rows 1500
```

## Почему старый eval убрали из critical path

Старый post-training eval был тяжёлым, опирался на train rows и плохо показывал реальные ошибки JSON. Правильная схема сейчас:

1. `/train/start` обучает и сохраняет checkpoint.
2. После сохранения checkpoint запускается короткий unique holdout eval.
3. Training становится `completed`.
4. Отдельно можно запускать ручной smoke через `/api/test`.
5. Не возвращать тяжёлый train-row eval в critical path.

## Smoke test

Используй `/api/test` и поле `user_text`.

```bash
cd /Users/aleksandr/Documents/Projects/proton-x
python - <<'PY'
import json
import urllib.request

phrases = [
    "node version",
    "python version",
    "check python version",
    "what time is it",
    "check disk space",
    "Show me downloads?",
    "show me version",
    "какая версия установлена",
    "tell me a joke",
    "open browser",
    "как дела",
    "расскажи шутку",
    "Какая версия ноды у меня установлена?",
    "Покажи версию ноды?",
    "который час",
    "покажи версию питона",
]

for phrase in phrases:
    body = json.dumps({"user_text": phrase}).encode("utf-8")
    request = urllib.request.Request(
        "http://127.0.0.1:8100/api/test",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        payload = json.loads(response.read().decode("utf-8"))
    result = payload.get("result") or {}
    preview = payload.get("preview") or {}
    print(
        phrase,
        "=>",
        result.get("status"),
        result.get("tool_name"),
        preview.get("validation_error"),
    )
PY
```

Ожидаемое поведение в общих чертах:

- запросы про node/npm -> `get_node_version`;
- запросы про python/pip -> `get_python_version`;
- запросы про время -> `get_current_time`;
- disk/free space -> `get_disk_usage`;
- downloads -> `list_downloads`;
- jokes/open browser/how are you/unknown intents -> `__fallback__`;
- ambiguous `show me version` может быть спорным; не используй одну такую фразу как единственный критерий качества.

## Проверка checkpoint config

```bash
cd /Users/aleksandr/Documents/Projects/proton-x
python - <<'PY'
import torch
checkpoint = torch.load("data/weights/proton_router_v1.pt", map_location="cpu")
print(checkpoint.get("config"))
print("output_format", checkpoint.get("output_format"))
print("dataset_row_count", checkpoint.get("dataset_row_count"))
print("evaluation", checkpoint.get("evaluation"))
PY
```

Ожидаемо для текущего `proton_router_v1`:

```text
hidden_dim: 256
num_layers: 4
num_heads: 8
vocab_size: 512
output_format: json-v1
evaluation.mode: unique_holdout
```

## Что делать дальше

1. Улучшать generative JSON, а не скрывать его ошибки runtime-слоем.
2. Проверить, хватает ли текущего prompt contract для аргументов и будущих chain calls.
3. Усилить dataset hard negatives для fallback: jokes, poems, open browser, how are you, общие вопросы без tool.
4. Усилить positives/negatives для `get_current_time` vs `get_disk_usage` vs `get_python_version`.
5. Проверить, не мешает ли SentencePiece vocab 512 для устойчивого JSON; если мешает, пробовать больший vocab или character/BPE стратегию.
6. Если параметры крутить, стартовать от рабочей зоны `256/4/8`, batch 16, lr 0.0005, epochs 10.
7. Не принимать качество только по loss: смотреть short unique holdout, smoke и raw debug outputs.

## Не повторять

- Не делать resume случайно. Для смены архитектуры всегда explicit null resume paths.
- Не оценивать качество только по training loss.
- Не запускать полный train-row eval внутри `/train/start`.
- Не чинить плохой smoke точечными exact phrase patches.
- Не возвращать pre-router/top-k filtering.
- Не возвращать JSON repair.
- Не возвращать constrained scoring как основной runtime.
- Не переименовывать v1 artifacts обратно в `routing_spm` или `custom_router_v1`.
