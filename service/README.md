# Proton AI Model Service

`service/` is the FastAPI model service for Proton AI. It owns model-facing behavior: tool registry validation, prompt construction, model runtime, output validation, dataset bootstrap, training, and training status.

Product logic stays outside this service. The UI backend owns workspace settings, tools storage, dataset files, executor paths, execution output, and logs.

## Contract

```text
tools registry + user_text -> tool_calls JSON
```

Regular output:

```json
{"tool_calls":[{"name":"get_current_time","arguments":{}}]}
```

Fallback output:

```json
{"tool_calls":[{"name":"__fallback__","arguments":{}}]}
```

The v1 model does not produce user-facing prose. The outer layer can turn a validated tool call into a response after execution.

## Responsibilities

The model service does:

- validate the supported tool schema subset;
- build the compact routing prompt;
- run `ModelRuntime.generate()`;
- validate JSON output and arguments;
- return canonical fallback on invalid output;
- generate bootstrap datasets from a tools registry;
- train and save checkpoint/tokenizer artifacts;
- expose public training status with downsampled loss history.

The model service does not:

- execute user scripts;
- store UI workspace settings;
- edit the tools registry;
- format final user responses;
- manage a tool marketplace or authoring layer.

## Runtime Path

```text
user_text
  -> tools registry
  -> compact prompt
  -> ModelRuntime.generate()
  -> validator
  -> final_output
```

Invalid JSON, unknown tools, missing required arguments, unsupported enum values, and strict-mode extra arguments are converted to canonical fallback. Raw model output remains available in debug responses.

`/route/preview` returns the same path with debug data: prompt, raw model output, validation result, final action, and final output.

`/chat/completions` is an OpenAI-style adapter on top of the router path.

## Prompt Inputs

The prompt includes:

- `name`
- `tags`
- compact `args` summary

The prompt does not include:

- executor code;
- executor path;
- full backend config;
- response templates;
- fallback prose.

Current prompt/checkpoint compatibility: `compact-ru-v1`.

## Training Data

Recommended compact JSONL row:

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

Legacy chat-shaped rows are accepted for compatibility, but new data should use the compact format.

The dataset must teach two behaviors:

- select the correct tool from the provided candidates;
- fill only valid arguments from the compact schema summary.

Fallback rows are required. They teach the model not to call a random tool when the request is outside the registry.

## API

- `GET /health`
- `POST /tools/validate`
- `POST /route/preview`
- `POST /chat/completions`
- `POST /train/dataset/build`
- `POST /train/start`
- `GET /train/status`

## Run

From the repository root:

```bash
make run-service
```

Manual run:

```bash
(cd service && uvicorn main:app --reload --port 8000)
```

## Test

From the repository root:

```bash
python -m pytest --import-mode=importlib service/tests -q
```
