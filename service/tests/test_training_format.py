import json

from protonx.training.format import OUTPUT_FORMAT_CALL
from protonx.training.format import parse_call_payload
from protonx.training.format import render_model_output
from protonx.training.format import serialize_training_parts


def test_serialize_training_parts_uses_compact_call_target_by_default() -> None:
    record = {
        "tools": [{"name": "get_node_version", "tags": ["node version"]}],
        "user": "node version",
        "assistant": {"tool_calls": [{"name": "get_node_version", "arguments": {}}]},
    }

    prompt, assistant = serialize_training_parts(record)

    assert prompt.startswith("TOOLS:\n")
    assert assistant == "CALL:get_node_version"


def test_parse_call_payload_supports_arguments() -> None:
    payload = parse_call_payload('CALL:search_files\nARGS:{"query":"package.json"}')

    assert payload == {
        "tool_calls": [{"name": "search_files", "arguments": {"query": "package.json"}}]
    }


def test_render_model_output_converts_compact_call_to_json_contract() -> None:
    rendered = render_model_output("CALL:get_python_version", OUTPUT_FORMAT_CALL)

    assert rendered is not None
    assert json.loads(rendered) == {
        "tool_calls": [{"name": "get_python_version", "arguments": {}}]
    }


def test_render_model_output_rejects_invalid_compact_call() -> None:
    assert render_model_output("get_python_version", OUTPUT_FORMAT_CALL) is None
