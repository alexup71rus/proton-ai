# Tools Registry

Tool описывает одно разрешенное действие. Модель не получает executor code. В prompt попадает только routing metadata: `name`, `tags` и компактное описание arguments.

## Tool без arguments

```json
{
  "name": "get_current_time",
  "description": "Показать локальное время на машине.",
  "tags": ["время", "дата", "который час"],
  "arguments_schema": {
    "type": "object",
    "properties": {},
    "required": []
  },
  "executor_path": "web_backend/executors/get_current_time.py"
}
```

Ожидаемый model output:

```json
{"tool_calls":[{"name":"get_current_time","arguments":{}}]}
```

## Tool с enum argument

```json
{
  "name": "get_node_version",
  "description": "Показать установленную версию Node.js или npm.",
  "tags": ["node", "npm", "нода", "нпм", "версия npm"],
  "arguments_schema": {
    "type": "object",
    "properties": {
      "target": {
        "type": "string",
        "description": "Версию какого инструмента показать.",
        "enum": {
          "node": "версия Node.js через node --version",
          "npm": "версия npm через npm --version"
        }
      }
    },
    "required": ["target"]
  },
  "executor_path": "web_backend/executors/get_node_version.py"
}
```

Модель возвращает только enum key:

```json
{"tool_calls":[{"name":"get_node_version","arguments":{"target":"npm"}}]}
```

Для обратной совместимости `enum` может быть string list в формате `value: description`. Для новых tools лучше использовать key/value object.

## Schema V1 limits

- `arguments_schema.type` должен быть `object`.
- Поддерживаются string arguments.
- `enum` может быть object `value -> description` или list строк `value: description`.
- `__fallback__` зарезервирован системой.
- Tool names должны быть уникальными.
- Executor paths должны указывать на trusted local code.

## Tags

Tags - главный языковой сигнал для routing. Добавляй технические имена и реальные пользовательские формулировки:

```json
["npm", "нпм", "энпм", "npm -v", "версия npm", "пакетный менеджер"]
```

Для похожих tools нужны контрастные tags:

- `версия npm` -> `get_node_version`
- `npm scripts` -> `inspect_package_json`
- `npm зависимости` -> `list_node_packages`
- `npm registry доступен` -> `check_http_head`

## Executor safety

`executor_path` запускается UI backend после validation. Начинай с trusted read-only actions: version checks, directory lists, status calls и HTTP HEAD checks. Избегай изменения файлов и внешних side effects, пока tool и validation contract не описаны явно.
