import json


def repair_json_syntax(raw_output: str) -> str | None:
    trimmed = raw_output.strip()
    if not trimmed:
        return None
    if trimmed.count("{") > trimmed.count("}"):
        trimmed = trimmed + "}" * (trimmed.count("{") - trimmed.count("}"))
    if trimmed.count("[") > trimmed.count("]"):
        trimmed = trimmed + "]" * (trimmed.count("[") - trimmed.count("]"))
    try:
        payload = json.loads(trimmed)
    except json.JSONDecodeError:
        return trimmed
    if isinstance(payload, dict) and "tool_calls" not in payload and len(payload) == 1:
        key, value = next(iter(payload.items()))
        if key.startswith("tool_") and key.endswith("_calls") and isinstance(value, list):
            return json.dumps({"tool_calls": value}, separators=(",", ":"))
    return trimmed
