# Proton-X

Proton-X — экспериментальная платформа для обучения маленьких специализированных моделей. Сейчас это не чат-бот, а базовое ядро tool calling: модель должна выбрать функцию и вернуть структурированный `tool_call`.

Идея обратная обычному пути: не сначала учить модель говорить, а потом добавлять tool calling, а сначала научить её надёжно выбирать инструменты, валидировать результат, исполнять функцию и собирать логи. Ответы, цепочки действий и поведение универсального ассистента могут появиться позже поверх этого ядра.

## Текущий контракт v1

```text
candidate_tools + user_text -> tool_calls JSON
```

Модель получает только список кандидатов и текст пользователя. Она не генерирует обычный текст, объяснения, fallback-сообщения или ответы “из головы”. Человекочитаемый результат приходит от executor/template слоя после вызова инструмента.

Пайплайн:

```text
user -> pre-router -> top-k tools -> tiny model -> validator -> executor -> response
```

Fallback — тоже структурированный выбор: синтетический инструмент `__fallback__`.

## Структура

```text
service/      FastAPI сервис модели: routing, validation, training
web_backend/  FastAPI backend для UI: workspace, tools, datasets, execution
web_ui/       React + Vite интерфейс оператора
web/          legacy Streamlit UI
data/         локальные tools, datasets, weights, tokenizers, logs
```

Подробности по сервису модели: [service/README.md](service/README.md).

## Как запустить

```bash
cd service && pip install -r requirements.txt
cd ../web_backend && pip install -r requirements.txt
cd ../web_ui && npm install
```

Из корня репозитория:

```bash
make run-service
make run-ui-backend
make run-web-ui
```

Или все процессы сразу:

```bash
make run-dev
```

Адреса:

- `http://127.0.0.1:8000/health` — model service
- `http://127.0.0.1:8100/health` — UI backend
- `http://localhost:8501` — web UI

## Основной workflow

```text
create tools -> choose dataset -> train -> test -> inspect logs -> improve dataset
```

В UI есть страницы:

- **Tools** — редактирование registry инструментов.
- **Dataset + Training** — выбор dataset-файла и запуск обучения/дообучения.
- **Test** — проверка маршрутизации и executor output.
- **Logs** — fallback/error cases для улучшения dataset.

Состояние UI хранится на backend в [data/workspace/settings.json](data/workspace/settings.json).

## Проверка

```bash
pytest --import-mode=importlib service/tests web_backend/tests -q
cd web_ui && npm run build
```
