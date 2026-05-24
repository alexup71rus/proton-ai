import json


def generate_mock_output(prompt: dict) -> str:
    tools = prompt["tools"]
    if not tools:
        return json.dumps(
            {
                "tool_calls": [],
                "answer": True,
                "fallback": True,
            }
        )

    first_tool = tools[0]
    arguments = {}
    required = first_tool["arguments_schema"]["required"]
    if "state" in required:
        arguments["state"] = "on"

    return json.dumps(
        {
            "tool_calls": [{"name": first_tool["name"], "arguments": arguments}],
            "answer": False,
            "fallback": False,
        }
    )
