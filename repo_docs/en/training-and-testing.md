# Training And Testing

## Compact JSONL

Recommended row format:

```json
{
  "tools": [
    {"name":"get_current_time","tags":["time","date"]},
    {"name":"__fallback__","tags":["no tool","unsupported request"]}
  ],
  "user": "what time is it",
  "assistant": {
    "tool_calls": [{"name":"get_current_time","arguments":{}}]
  }
}
```

Fallback is a normal supervised row:

```json
{
  "tools": [
    {"name":"get_current_time","tags":["time"]},
    {"name":"__fallback__","tags":["no tool"]}
  ],
  "user": "write a poem",
  "assistant": {
    "tool_calls": [{"name":"__fallback__","arguments":{}}]
  }
}
```

## Generate Bootstrap Dataset

From the repository root:

```bash
PYTHONPATH=service python -m protonx.training.bootstrap_dataset_mixer_for_tools \
  --tools data/tools/tools.json \
  --output data/train/routing/routing.jsonl \
  --target-rows 50000
```

The internal package name is `protonx`; the public project name is Proton AI.

## Train Through API

Use the UI or the API so progress is visible in the web UI. Direct model service call:

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

A new model is created when `resume_model_path` and `resume_tokenizer_path` are omitted.

## Artifacts

For `artifact_name: "router"`:

```text
data/weights/router.pt
data/tokenizers/router.model
data/tokenizers/router.vocab
data/tokenizers/router.corpus.txt
```

## Evaluation

After training, the model service builds a holdout set from rows that are not used for training. Main metrics:

- `Exact match` - tool call and arguments match exactly.
- `Valid output` - model output is valid JSON under the contract.
- `Positive rows` - accuracy on normal tool calls.
- `Fallback rows` - accuracy on fallback rows.
- `Invalid outputs` - JSON, schema, or tool membership errors.

For a small router, `Valid output` and `Fallback rows` matter as much as `Exact match`. They show whether the model keeps the contract and avoids random tool calls.

## Test And Logs

**Test** sends user text to the selected model and shows final action, arguments, validation error, executor output, and debug data.

**Logs** stores routing incidents and can export failed cases into a dataset draft. This is usually more useful than adding epochs without changing data: real misses show which phrases, aliases, and argument values are missing from the corpus.
