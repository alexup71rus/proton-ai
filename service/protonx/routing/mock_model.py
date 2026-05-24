import json

from protonx.contracts import build_fallback_payload


def generate_mock_output(prompt: dict) -> str:
    tools = prompt["tools"]
    if not tools:
        return json.dumps(build_fallback_payload())

    first_tool = tools[0]
    arguments = {}
    required = first_tool.get("arguments_schema", {}).get("required", [])
    if "state" in required:
        arguments["state"] = "on"

    return json.dumps(
        {
            "tool_calls": [{"name": first_tool["name"], "arguments": arguments}],
        }
    )
