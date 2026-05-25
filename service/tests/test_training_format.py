import pytest

from protonx.training.format import OUTPUT_FORMAT_JSON
from protonx.training.format import render_model_output
from protonx.training.format import serialize_training_parts


def test_serialize_training_parts_uses_full_json_target_by_default() -> None:
    record = {
        "tools": [{"name": "get_node_version", "tags": ["node version"]}],
        "user": "node version",
        "assistant": {"tool_calls": [{"name": "get_node_version", "arguments": {}}]},
    }

    prompt, assistant = serialize_training_parts(record)

    assert prompt.startswith("ИНСТРУМЕНТЫ:\n")
    assert assistant == '{"tool_calls":[{"name":"get_node_version","arguments":{}}]}'


def test_serialize_training_parts_rejects_non_json_targets() -> None:
    record = {
        "tools": [{"name": "get_node_version", "tags": ["node version"]}],
        "user": "node version",
        "assistant": {"tool_calls": [{"name": "get_node_version", "arguments": {}}]},
    }

    with pytest.raises(ValueError, match="unsupported output format"):
        serialize_training_parts(record, output_format="call-v1")


def test_render_model_output_keeps_json_contract_for_default_json_format() -> None:
    raw = '{"tool_calls":[{"name":"get_python_version","arguments":{}}]}'

    assert render_model_output(raw, OUTPUT_FORMAT_JSON) == raw


def test_render_model_output_keeps_raw_output_for_unknown_legacy_format() -> None:
    assert render_model_output("CALL:get_python_version", "call-v1") == "CALL:get_python_version"
