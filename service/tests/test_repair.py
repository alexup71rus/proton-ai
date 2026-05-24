import json

from protonx.routing.repair import repair_json_syntax


def test_repair_json_syntax_normalizes_tool_specific_calls_key():
    repaired = repair_json_syntax(
        '{"tool_python_calls":[{"name":"get_python_version","arguments":{}}]}'
    )

    assert repaired is not None
    assert json.loads(repaired) == {
        "tool_calls": [{"name": "get_python_version", "arguments": {}}]
    }


def test_repair_json_syntax_keeps_unknown_structure_for_validator():
    raw = '{"tool_python_calls":{"name":"get_python_version"}}'

    assert repair_json_syntax(raw) == raw