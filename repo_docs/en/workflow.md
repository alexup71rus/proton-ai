# Workflow

## 1. Define Tools

1. Open `http://localhost:8501`.
2. Go to **Tools**.
3. Add or edit a tool.
4. Fill `name`, `description`, `tags`, `arguments_schema`, and `executor_path`.
5. Validate the registry.
6. Save changes.

Default registry path: `data/tools/tools.json`.

## 2. Prepare A Model Slot

Use the header controls:

- **Configure** creates a model draft and sets artifact paths.
- **Import** loads existing `.pt`, `.model`, and optional `.vocab` files.

After training completes, the UI backend updates the selected model in workspace settings.

Workspace path: `data/workspace/settings.json`.

## 3. Choose Dataset Storage And Train

1. Open **Training**.
2. Choose the dataset storage folder.
3. Import or generate a dataset.
4. Validate the selected dataset.
5. Set `epochs`, `batch_size`, and `learning_rate`.
6. Start training.

The UI backend validates the dataset before sending `/train/start` to the model service.

## 4. Test Routing

1. Open **Test**.
2. Enter user text.
3. Run the request.
4. Inspect selected tool, arguments, validation output, executor output, and debug details.

Testing requires a selected model with `model_path` and `tokenizer_path`.

## 5. Improve From Logs

**Logs** shows routing incidents. Use it to collect missed phrases, aliases, argument values, and fallback cases.

Improvement loop:

```text
test -> inspect logs -> export failed cases -> extend dataset -> retrain
```
