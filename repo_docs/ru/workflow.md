# Workflow

## 1. Описать tools

1. Открой `http://localhost:8501`.
2. Перейди в **Tools**.
3. Добавь или измени tool.
4. Заполни `name`, `description`, `tags`, `arguments_schema` и `executor_path`.
5. Провалидируй registry.
6. Сохрани изменения.

Default registry path: `data/tools/tools.json`.

## 2. Подготовить model slot

Controls в header:

- **Configure** создает model draft и задает artifact paths.
- **Import** загружает существующие `.pt`, `.model` и optional `.vocab` files.

После успешного training UI backend обновляет выбранную модель в workspace settings.

Workspace path: `data/workspace/settings.json`.

## 3. Выбрать dataset storage и запустить training

1. Открой **Training**.
2. Выбери dataset storage folder.
3. Импортируй или сгенерируй dataset.
4. Провалидируй выбранный dataset.
5. Задай `epochs`, `batch_size` и `learning_rate`.
6. Запусти training.

UI backend проверяет dataset перед отправкой `/train/start` в model service.

## 4. Проверить routing

1. Открой **Test**.
2. Введи user text.
3. Запусти request.
4. Проверь selected tool, arguments, validation output, executor output и debug details.

Testing требует выбранную модель с `model_path` и `tokenizer_path`.

## 5. Улучшать через logs

**Logs** показывает routing incidents. Используй их, чтобы добавлять missed phrases, aliases, argument values и fallback cases.

Improvement loop:

```text
test -> inspect logs -> export failed cases -> extend dataset -> retrain
```
