# Proton-X v1 handoff for the next AI agent

Документ для следующей нейронки. Цель: быстро продолжить работу без повторения уже найденных ошибок.

## Главная цель

Proton-X v1 сейчас должен быть маленьким tool-router, а не чат-моделью.

Модель получает полный registry доступных tools и текст пользователя, затем возвращает строго структурированный JSON:

```json
{"tool_calls":[{"name":"get_node_version","arguments":{}}]}
```

Если запрос не подходит ни под один tool, модель должна вернуть `__fallback__`.

Важные продуктовые решения:

- Не возвращать pre-router/top-k candidate filtering. Он уже удалялся, потому что противоречит концепции полного registry.
- Не вводить tool ids/indexes в v1. Это было отклонено как преждевременное усложнение.
- Не подгонять dataset под конкретные smoke-фразы. Нужны вариативные данные: больше разных формулировок, decoy tools, fallback-примеры.
- Основной artifact name: `proton_router_v1`. Старые `routing_spm` и `custom_router_v1` больше не должны быть default.
- Eval должен быть коротким и формальным. Старый тяжёлый eval по train rows удаляли не зря; текущий short holdout eval допустим после сохранения checkpoint.

## Очень важные ограничения

- Не делать `git commit` и `git push`, если пользователь явно не попросил.
- Перед правкой файлов в [service](../service/) проверь статус обучения. Service запущен через `uvicorn --reload`, поэтому изменение service-файлов во время training может перезапустить процесс.
- Если training уже идёт, сначала проверь `/api/training/status` и дождись `completed` или спроси пользователя, если нужно прервать.
- Не запускай долгий eval внутри training. Пользователь прямо раздражён тем, что eval приходилось останавливать и из-за этого всё ломалось.
- Для fresh training через BFF обязательно передавай `"resume_model_path": null` и `"resume_tokenizer_path": null`. Иначе BFF может автоматически сделать resume из выбранной loaded model, и параметры архитектуры будут проигнорированы.

## Текущее состояние на момент handoff

Старый baseline run был запущен так:

```bash
curl -sS -X POST http://127.0.0.1:8100/api/training/start \
  -H 'Content-Type: application/json' \
  -d '{"artifact_name":"custom_router_v1","epochs":5,"batch_size":16,"hidden_dim":128,"num_layers":3,"num_heads":4,"learning_rate":0.0007,"resume_model_path":null,"resume_tokenizer_path":null}'
```

Фактический итоговый статус:

```text
status: completed
current_epoch: 5 / 5
current_step: 470 / 470
loss: 0.1883116066455841
artifact_name: custom_router_v1
dataset_row_count: 1500
model_path: /Users/aleksandr/Documents/Projects/proton-x/data/weights/custom_router_v1.pt
tokenizer_path: /Users/aleksandr/Documents/Projects/proton-x/data/tokenizers/custom_router_v1.model
error: null
```

Фактический checkpoint [data/weights/custom_router_v1.pt](../data/weights/custom_router_v1.pt) после завершения run:

```text
vocab_size: 512
hidden_dim: 128
num_layers: 3
num_heads: 4
max_seq_len: 319
dataset_row_count: 1500
evaluation: {}
```

Качество этого checkpoint не принято. На новом unique holdout eval старый `custom_router_v1` дал:

```text
eval_total: 14
eval_valid: 6
eval_exact: 0
unknown_tool: 8
```

Основная проблема старой схемы: модель свободно генерировала JSON и имена tools, поэтому появлялись несуществующие имена вроде `get_downloads`, `get_version`, `get_python_node_version`. Loss выглядел неплохо, но routing был плохой.

## Рабочая зона, найденная после диагностики

Лучшее найденное направление: `call-v1` target + constrained scoring.

Смысл:

- training target больше не полный JSON, а короткий вид `CALL:<tool_name>` и при необходимости `ARGS:<json>`;
- runtime для `call-v1` checkpoint не генерирует имя tool свободно, а скорит все tools из полного registry и выбирает лучший;
- наружу по-прежнему возвращается старый JSON-контракт `{"tool_calls":[...]}`;
- старые JSON checkpoints остаются совместимыми, потому что у них нет `output_format: "call-v1"`.

Ключевые файлы:

- [service/protonx/training/format.py](../service/protonx/training/format.py): `CALL` serialization/parsing.
- [service/protonx/routing/model_runtime.py](../service/protonx/routing/model_runtime.py): constrained scoring для `call-v1`.
- [service/protonx/training/evaluation.py](../service/protonx/training/evaluation.py): короткий unique holdout eval.
- [service/protonx/training/trainer.py](../service/protonx/training/trainer.py): сохраняет `output_format: "call-v1"` и evaluation summary.

Базовая команда для нового production fresh run:

```bash
curl -sS -X POST http://127.0.0.1:8000/train/start \
  -H 'Content-Type: application/json' \
  -d '{"dataset_path":"/Users/aleksandr/Documents/Projects/proton-x/data/train/routing/routing.jsonl","epochs":10,"batch_size":16,"model_name":"tiny-router","tokenizer_name":"sentencepiece-bpe","output_root_dir":"/Users/aleksandr/Documents/Projects/proton-x/data","artifact_name":"proton_router_v1","resume_model_path":null,"resume_tokenizer_path":null,"hidden_dim":256,"num_layers":4,"num_heads":8,"learning_rate":0.0005}'
```

Фактический production checkpoint после cleanup:

```text
model_path: data/weights/proton_router_v1.pt
tokenizer_path: data/tokenizers/proton_router_v1.model
output_format: call-v1
hidden_dim: 256
num_layers: 4
num_heads: 8
vocab_size: 512
max_seq_len: 309
best_epoch: 10
best_epoch_loss: 0.031733579259920625
```

Evaluation:

```text
eval_total: 14
eval_valid: 14
eval_exact: 9
eval_positive_total: 10
eval_positive_exact: 7
eval_fallback_total: 4
eval_fallback_exact: 2
invalid_json: 0
unknown_tool: 0
schema_error: 0
```

Smoke на 16 ручных фразах: `12/16`.

Фактический результат был получен исторически через дополнительный resume run и затем переименован в production artifact `proton_router_v1`. Intermediate probe artifacts удалены.

```text
artifact: proton_router_v1
model_path: data/weights/proton_router_v1.pt
tokenizer_path: data/tokenizers/proton_router_v1.model
best_epoch_loss: 0.0016429127361798817
eval_total: 14
eval_valid: 14
eval_exact: 9
eval_positive_exact: 5
eval_fallback_exact: 4
unknown_tool: 0
smoke: 14/16
```

Вывод: рабочая зона параметров найдена:

```text
hidden_dim: 256
num_layers: 4
num_heads: 8
batch_size: 16
learning_rate: 0.0005 для fresh run
epochs: 10
vocab_size: 512
target/output_format: call-v1
runtime: constrained scoring over full registry
```

Продолжение до почти нулевого train loss (`lr=0.0002`, ещё 5 эпох) улучшило smoke, но не подняло holdout выше `9/14`. Значит следующий прирост качества надо искать в dataset/hard negatives/calibration, а не просто в количестве эпох.

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

Это сделано специально: prompts включают runtime-like rows без decoys и noisy rows с 1-2 decoy tools.

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

## Ключевые файлы

- [service/protonx/model_contract.py](../service/protonx/model_contract.py): prompt contract, compact format, fallback tool.
- [service/protonx/training/format.py](../service/protonx/training/format.py): serialization of prompt + assistant target.
- [service/protonx/training/dataset_builder.py](../service/protonx/training/dataset_builder.py): synthetic rows, class balancing, decoy tools.
- [service/protonx/training/trainer.py](../service/protonx/training/trainer.py): training loop and checkpoint saving.
- [service/protonx/routing/inference.py](../service/protonx/routing/inference.py): runtime routing, default `proton_router_v1`.
- [service/protonx/routing/model_runtime.py](../service/protonx/routing/model_runtime.py): checkpoint/tokenizer loading and generation.
- [web_backend/app.py](../web_backend/app.py): BFF training/test APIs and resume behavior.
- [data/tools/tools.json](../data/tools/tools.json): real runtime tools.

## Что уже изменено по смыслу

- Убран pre-router/candidates/debug narrowing.
- Routing runtime теперь работает с full registry + synthetic `__fallback__`.
- Prompt format сейчас `compact-v2`.
- Default artifact должен быть `proton_router_v1`.
- Dataset mixer расширен: больше phrase variations, fallback rows, decoy tools.
- Decoy count переменный: 0..`decoy_tools_per_row`, чтобы model видела и runtime-like prompts.
- `trainer.py` изменён так, чтобы после сохранения checkpoint training сразу ставил `status="completed"`. `_evaluate_model` больше не вызывается из `/train/start`.
- Training теперь запускает короткий unique holdout eval после сохранения checkpoint. Он не должен быть тяжёлым и не должен основываться на train rows.
- Тесты обновлены под `call-v1`, short eval и `learning_rate` в workspace settings.

## Почему старый eval убрали из training

Старый post-training eval делал greedy generation по dataset/sample и валидировал JSON. Для текущей итерации это вредно:

- он долгий;
- он блокирует `completed`;
- его приходилось вручную останавливать;
- остановка ломала service/reloader;
- checkpoint уже нужен сразу после обучения, а не после тяжёлой проверки.

Правильная схема сейчас:

1. `/train/start` обучает и сохраняет checkpoint.
2. После сохранения checkpoint запускается короткий unique holdout eval.
3. Training становится `completed`.
4. Отдельно можно запускать ручной smoke через `/api/test`.
5. Не возвращать тяжёлый train-row eval в critical path.

## Smoke test после завершения training

Используй `/api/test` и поле `user_text`.

```bash
cd /Users/aleksandr/Documents/Projects/proton-x
python - <<'PY'
import json
import urllib.request

phrases = [
    'node version',
    'python version',
    'check python version',
    'what time is it',
    'check disk space',
    'Show me downloads?',
    'show me version',
    'какая версия установлена',
    'tell me a joke',
    'open browser',
    'как дела',
    'расскажи шутку',
    'Какая версия ноды у меня установлена?',
    'Покажи версию ноды?',
    'который час',
    'покажи версию питона',
]

for phrase in phrases:
    body = json.dumps({'user_text': phrase}).encode('utf-8')
    request = urllib.request.Request(
        'http://127.0.0.1:8100/api/test',
        data=body,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        payload = json.loads(response.read().decode('utf-8'))
    result = payload.get('result') or {}
    print(f'{phrase} => {result.get("status")}:{result.get("tool_name")}')
PY
```

Ожидаемое поведение в общих чертах:

- `node version`, русские запросы про ноду -> `get_node_version`
- `python version`, русские запросы про питон -> `get_python_version`
- `what time is it`, `который час` -> `get_current_time`
- disk/free space -> `get_disk_usage`
- downloads -> `list_downloads`
- jokes/open browser/how are you/unknown intents -> fallback
- ambiguous `show me version` может быть спорным; не используй одну такую фразу как единственный критерий качества.

Фактический smoke старого checkpoint `128/3/4`, 5 эпох, batch 16, lr 0.0007:

```text
node version => tool_call:get_node_version
python version => tool_call:get_node_version
check python version => fallback:None
what time is it => tool_call:get_node_version
check disk space => fallback:None
Show me downloads? => fallback:None
show me version => fallback:None
какая версия установлена => tool_call:get_python_version
tell me a joke => tool_call:get_node_version
open browser => fallback:None
как дела => fallback:None
расскажи шутку => fallback:None
Какая версия ноды у меня установлена? => fallback:None
Покажи версию ноды? => tool_call:get_node_version
который час => tool_call:get_node_version
покажи версию питона => tool_call:get_node_version
```

Вывод по старому checkpoint: checkpoint сохранён, но качество routing плохое.

Фактический smoke `proton_router_v1`:

```text
node version => get_node_version
python version => get_python_version
check python version => get_python_version
what time is it => get_python_version  # ошибка
check disk space => get_disk_usage
Show me downloads? => list_downloads
show me version => __fallback__
какая версия установлена => __fallback__
tell me a joke => __fallback__
open browser => __fallback__
как дела => __fallback__
расскажи шутку => get_python_version  # ошибка
Какая версия ноды у меня установлена? => get_node_version
Покажи версию ноды? => get_node_version
который час => get_current_time
покажи версию питона => get_python_version
```

Итого: `14/16`, все outputs valid, `unknown_tool=0`.

## Проверка checkpoint config

```bash
cd /Users/aleksandr/Documents/Projects/proton-x
python - <<'PY'
import torch
checkpoint = torch.load('data/weights/proton_router_v1.pt', map_location='cpu')
print(checkpoint.get('config'))
print('dataset_row_count', checkpoint.get('dataset_row_count'))
print('evaluation', checkpoint.get('evaluation'))
PY
```

Для старого `custom_router_v1`:

```text
hidden_dim: 128
num_layers: 3
num_heads: 4
vocab_size: 512
dataset_row_count: 1500
evaluation: {}
```

Для нового `call-v1` checkpoint должно быть:

```text
hidden_dim: 256
num_layers: 4
num_heads: 8
vocab_size: 512
output_format: call-v1
evaluation.mode: unique_holdout
evaluation.eval_valid: 14
evaluation.unknown_tool: 0
```

## Тесты, которые уже проходили

После `call-v1`, constrained scoring и short holdout eval проходил полный backend/service suite:

```bash
cd /Users/aleksandr/Documents/Projects/proton-x
pytest --import-mode=importlib service/tests web_backend/tests -q
```

Результат: `83 passed, 2 warnings`.

После удаления eval из training path проходили:

```bash
cd /Users/aleksandr/Documents/Projects/proton-x
PYTHONPATH=service /usr/local/Cellar/python@3.11/3.11.13/bin/python3.11 \
  -m pytest --import-mode=importlib \
  service/tests/test_trainer.py \
  service/tests/test_training_api.py \
  service/tests/test_preview.py \
  service/tests/test_dataset_builder.py -q
```

Результат: `28 passed, 2 warnings`.

```bash
cd /Users/aleksandr/Documents/Projects/proton-x
PYTHONPATH=web_backend /usr/local/Cellar/python@3.11/3.11.13/bin/python3.11 \
  -m pytest --import-mode=importlib \
  web_backend/tests/test_training_api.py \
  web_backend/tests/test_test_api.py -q
```

Результат: `8 passed`.

## Что делать дальше

1. Не возвращаться к свободной JSON generation для выбора tool names. `call-v1 + constrained scoring` уже убрал `unknown_tool`.
2. Если нужен новый основной artifact, запустить fresh training с рабочей зоной и artifact name `proton_router_v1`, explicit null resume paths.
3. Не принимать качество только по loss: e15 run почти занулил train loss, но holdout остался `9/14`.
4. Следующий прирост искать в dataset:
   - добавить hard negatives для fallback, особенно jokes/poems/open browser/how are you;
   - усилить time examples, потому что `what time is it` и `который час` конфликтовали с python/disk в разных runs;
   - добавить hard positives/negatives для `get_current_time` vs `get_disk_usage` vs `get_python_version`;
   - проверить fallback calibration: fallback examples должны быть достаточно разнообразны и не только короткие chat-фразы.
5. Если параметры ещё крутить, стартовать от:
   - `hidden_dim=256`, `num_layers=4`, `num_heads=8`;
   - `batch_size=16`, `learning_rate=0.0005`, `epochs=10`;
   - не продолжать эпохи бесконечно, если holdout стоит на месте.
6. После финального приемлемого результата можно почистить data от временных probe artifacts, но не удалять используемые artifacts:
   - оставить `data/tools/tools.json`;
   - оставить `data/train/routing/routing.jsonl`;
   - оставить выбранный production tokenizer `.model` и `.vocab`;
   - оставить выбранный production `.pt`;
   - временный `data/tokenizers/proton_router_v1.corpus.txt` можно удалить, если он есть.

## Не повторять

- Не делать resume случайно. Для смены архитектуры всегда explicit null resume paths.
- Не оценивать качество только по training loss.
- Не запускать полный train-row eval внутри `/train/start`.
- Не чинить плохой smoke точечными exact phrase patches.
- Не возвращать pre-router.
- Не переименовывать v1 artifacts обратно в `routing_spm` или `custom_router_v1`.
- Не возвращаться к free-form tool name generation для новых checkpoints.
