# Рабочие Сценарии

## 1. Подготовить Tools

1. Открой `http://localhost:8501`.
2. Перейди в `Tools`.
3. Добавь или отредактируй tool.
4. Заполни `name`, `description`, `tags`, `arguments_schema`, `executor_path`.
5. Нажми `Validate`.
6. Нажми `Save`.

Источник registry по умолчанию: `data/tools/tools.json`.

## 2. Подготовить Модель

В верхней панели UI:

- `Create model` создает draft новой модели и задает будущие пути артефактов.
- `Load model` загружает готовые `.pt`, `.model` и optional `.vocab`.

После успешного обучения backend сам обновляет workspace выбранной модели.

Workspace хранится в `data/workspace/settings.json`; пример структуры лежит в `data/workspace/settings.example.json`.

## 3. Выбрать Dataset И Обучить

1. Перейди в `Dataset + Training`.
2. Выбери dataset.
3. Проверь validation.
4. Задай `epochs` и `batch_size`.
5. Запусти training.

UI backend валидирует dataset перед стартом обучения. Прогресс приходит из `GET /api/training/status`, который проксирует состояние model service.

## 4. Проверить Роутер

1. Перейди в `Test`.
2. Введи пользовательский запрос.
3. Нажми run.
4. Смотри выбранный tool, arguments, execution output и debug.

Test доступен, когда у выбранной модели есть `model_path` и `tokenizer_path`.

## 5. Использовать Logs

`Logs` показывает routing incidents и позволяет экспортировать failed cases в draft dataset. Это основной цикл улучшения после ручных проверок:

```text
test -> inspect logs -> export failed cases -> extend dataset -> retrain
```

