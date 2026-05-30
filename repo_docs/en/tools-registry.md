# Tools Registry

A tool describes one allowed action. The model does not receive executor code. The prompt includes only routing metadata: `name`, `tags`, and a compact argument summary.

## Tool Without Arguments

```json
{
  "name": "get_current_time",
  "description": "Show local machine time.",
  "tags": ["time", "date", "clock"],
  "arguments_schema": {
    "type": "object",
    "properties": {},
    "required": []
  },
  "executor_path": "web_backend/executors/get_current_time.py"
}
```

Expected model output:

```json
{"tool_calls":[{"name":"get_current_time","arguments":{}}]}
```

## Tool With Enum Argument

```json
{
  "name": "get_node_version",
  "description": "Show installed Node.js or npm version.",
  "tags": ["node", "npm", "node version", "npm version"],
  "arguments_schema": {
    "type": "object",
    "properties": {
      "target": {
        "type": "string",
        "description": "Which tool version to show.",
        "enum": {
          "node": "Node.js version via node --version",
          "npm": "npm version via npm --version"
        }
      }
    },
    "required": ["target"]
  },
  "executor_path": "web_backend/executors/get_node_version.py"
}
```

The model returns only the enum key:

```json
{"tool_calls":[{"name":"get_node_version","arguments":{"target":"npm"}}]}
```

For backward compatibility, enum can also be a string list in `value: description` format. Prefer key/value objects in new tools.

## Schema V1 Limits

- `arguments_schema.type` must be `object`.
- String arguments are supported.
- `enum` can be an object of `value -> description` or a list of `value: description` strings.
- `__fallback__` is reserved by the system.
- Tool names must be unique.
- Executor paths must point to trusted local code.

## Tags

Tags are the main language signal for routing. Add technical names and realistic user wording:

```json
["npm", "npm -v", "npm version", "package manager"]
```

Use contrastive tags for related tools:

- `npm version` -> `get_node_version`
- `npm scripts` -> `inspect_package_json`
- `npm dependencies` -> `list_node_packages`
- `npm registry connectivity` -> `check_http_head`

## Executor Safety

`executor_path` runs in the UI backend after validation. Start with trusted read-only actions: version checks, directory lists, status calls, and HTTP HEAD checks. Avoid file mutation and external side effects until the tool and validation contract are explicit.
