# Proton-X

Proton-X — экспериментальная платформа для создания персональных маленьких моделей автоматизации. Идея похожа на macOS/iOS Shortcuts: команды заранее описаны человеком или внешней системой, но выбирать нужную команду и подставлять аргументы должна нейронная модель.

Сейчас Proton-X не является чат-ботом и не пытается отвечать "из головы". Текущая задача уже: взять набор пользовательских инструментов, сгенерировать под них обучающий датасет, обучить tiny-router модель и проверить, что она стабильно выбирает правильный tool call с аргументами.

Долгосрочно это может стать конструктором локальных автоматизаций: человек скачивает проект, добавляет свои tools/executors, обучает модель под свой набор сценариев и получает маленький специализированный роутер. Более умная облачная модель в будущем может помогать писать tools, расширять датасеты или подбирать примеры, а маленькая локальная модель будет быстро и контролируемо вызывать уже разрешённые команды.

Подробнее о концепции: [PROJECT_CONCEPT.md](PROJECT_CONCEPT.md).

## Текущий контракт v1

```text
tools registry + user_text -> tool_calls JSON
```

Модель получает registry инструментов и текст пользователя. Она смотрит на `name`, `tags` и компактное описание аргументов, затем возвращает структурированный вызов:

```json
{"tool_calls":[{"name":"get_current_time","arguments":{}}]}
```

Если подходящего инструмента нет, модель тоже делает структурированный выбор через синтетический tool:

```json
{"tool_calls":[{"name":"__fallback__","arguments":{}}]}
```

Человекочитаемый результат приходит от executor/template слоя после вызова инструмента. Это сознательное разделение: модель выбирает действие и аргументы, а реальное выполнение остаётся в контролируемом коде.

Пайплайн:

```text
user -> tools registry -> tiny model -> validator -> executor -> response
```

## Для чего это нужно

Базовый сценарий:

1. Пользователь описывает свои tools: имя, теги, JSON schema аргументов и executor script.
2. Proton-X генерирует или принимает JSONL dataset для обучения маршрутизации.
3. Пользователь обучает tiny-router модель под свой набор команд.
4. В UI пользователь тестирует запросы, смотрит debug, fallback и ошибки.
5. Неудачные случаи превращаются в новые dataset rows, после чего модель можно дообучить.

Это подходит не только для автоматизации компьютера. Такой же подход можно использовать для классификации, выбора внутренних операций, управления локальными скриптами, интеграций с API или более сложных сценариев, где важно получить не свободный текст, а валидное структурированное действие.

## Почему tools с аргументами

Можно было бы завести отдельный tool на каждое действие без аргументов: `turn_light_on`, `turn_light_off`, `set_warm_light`, `set_cold_light` и так далее. Это проще для модели, но плохо масштабируется.

Proton-X идёт в сторону нормального разделения:

```text
tool name + structured arguments
```

Например один tool `set_light` с аргументами `state`, `temperature` или `room` лучше, чем десятки почти одинаковых tools. Модель становится сложнее, зато registry остаётся компактнее, а будущий marketplace/tools authoring слой может описывать команды в более естественном виде.

## Структура

```text
service/      FastAPI сервис модели: routing, validation, training
web_backend/  FastAPI backend для UI: workspace, tools, datasets, execution
web_ui/       React + Vite интерфейс оператора
web/          legacy Streamlit UI
data/         локальные tools, datasets, weights, tokenizers, logs
```

Подробности по сервису модели: [service/README.md](service/README.md).

## Документация

Карта пользовательских гайдов лежит в [repo_docs/README.md](repo_docs/README.md):

- быстрый старт и запуск сервисов;
- рабочий цикл tools -> dataset -> training -> test -> logs;
- формат tools registry и аргументов;
- datasets, обучение, артефакты и evaluation.

## Как сделать модель под себя

Минимальный путь:

1. Описать tools в UI или в `data/tools/tools.json`.
2. Для каждого tool указать безопасный `executor_path`.
3. Сгенерировать bootstrap dataset на странице Dataset + Training.
4. При необходимости добавить ручные examples или импортировать свой JSONL.
5. Запустить обучение.
6. Проверить модель на странице Test.
7. Разобрать Logs и добавить новые failed/fallback cases в dataset.

Текущий compact JSONL формат строки:

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

## Запуск

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

В UI есть страницы:

- **Tools** — редактирование registry инструментов и executor paths.
- **Dataset + Training** — генерация, импорт, проверка dataset и запуск обучения/дообучения.
- **Test** — проверка маршрутизации, аргументов, validator output и executor output.
- **Logs** — fallback/error cases для улучшения dataset.

Состояние UI хранится на backend в локальном `data/workspace/settings.json`.
Этот файл не коммитится; пример структуры лежит в [data/workspace/settings.example.json](data/workspace/settings.example.json).

## Проверка

```bash
pytest --import-mode=importlib service/tests web_backend/tests -q
cd web_ui && npm run build
```
