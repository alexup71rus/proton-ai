# Tools Registry

Tool описывает разрешенное действие, которое tiny-router может выбрать. Модель не получает executor code. В prompt попадают только компактные routing-поля: `name`, `tags` и summary аргументов.

## Минимальный Tool Без Аргументов

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

## Tool С Enum-Аргументом

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
        "enum": [
          "node: версия Node.js через node --version",
          "npm: версия npm через npm --version"
        ]
      }
    },
    "required": ["target"]
  },
  "executor_path": "web_backend/executors/get_node_version.py"
}
```

Enum пишется в формате:

```text
value: описание для человека и модели
```

Модель должна вернуть только `value`:

```json
{"tool_calls":[{"name":"get_node_version","arguments":{"target":"npm"}}]}
```

## Ограничения Schema V1

- `arguments_schema.type` должен быть `object`.
- Поддерживаются string-аргументы.
- `enum`, если есть, должен быть списком строк.
- `__fallback__` зарезервирован системой.
- `name` должен быть уникальным.
- Executor должен быть доверенным локальным кодом.

## Tags

Tags - главный языковой материал для routing. Добавляй не только технические имена, но и реальные пользовательские варианты:

```json
["npm", "нпм", "энпм", "npm -v", "версия npm", "пакетный менеджер"]
```

Для похожих tools нужны контрастные tags:

- `версия npm` -> `get_node_version`
- `npm scripts` -> `inspect_package_json`
- `npm зависимости` -> `list_node_packages`
- `npm registry доступен` -> `check_http_head`

## Executor Safety

`executor_path` запускается backend-слоем после validation. Добавляй только безопасные и доверенные executors. Для локальных команд лучше начинать с readonly-действий: чтение версии, list, status, HEAD-проверки, без изменения файлов и внешнего состояния.

