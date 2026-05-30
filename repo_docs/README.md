# Proton-X Docs

Эти документы описывают текущий рабочий контур Proton-X: локальный model service, UI backend, React UI, tools registry, datasets, обучение и проверку tiny-router модели.

`repo_docs/` - единственный каталог пользовательской документации под git. Каталог `docs/` зарезервирован как локальная scratch-зона для планов и временных заметок агентов и игнорируется git.

## Навигация

- [Быстрый старт](getting-started.md) - установка, запуск сервисов и health checks.
- [Рабочие сценарии](workflows.md) - путь от tools registry до проверки модели.
- [Tools registry](tools-registry.md) - формат tools, аргументы, enum-значения и executors.
- [Datasets, обучение и проверка](training-and-testing.md) - JSONL формат, запуск обучения, артефакты, Test и Logs.

## Компоненты

```text
service/      FastAPI model service: routing, validation, training
web_backend/  FastAPI backend для UI: workspace, tools, datasets, execution
web_ui/       React/Vite интерфейс оператора
data/         локальные tools, datasets, weights, tokenizers, logs
```

`web/` остается legacy Streamlit-интерфейсом. Для нового использования нужен `web_ui`.
