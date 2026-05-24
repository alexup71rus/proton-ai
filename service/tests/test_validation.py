from protonx.routing.validate import validate_model_output
from protonx.schemas import JsonSchema, ToolDefinition


def test_validator_rejects_unknown_tool():
    tools = [
        ToolDefinition(
            name="light",
            description="Light control",
            tags=["light"],
            arguments_schema=JsonSchema(
                type="object",
                properties={"state": {"type": "string", "enum": ["on", "off"]}},
                required=["state"],
            ),
        )
    ]
    result = validate_model_output(
        candidate_tools=tools,
        raw_output='{"tool_calls":[{"name":"lamp","arguments":{"state":"on"}}],"answer":false}',
        answer_allowed=False,
    )
    assert result.valid is False
    assert result.error == "unknown tool outside candidate set"


def test_validator_accepts_fallback_payload():
    tools = []
    result = validate_model_output(
        candidate_tools=tools,
        raw_output='{"tool_calls":[],"answer":true,"fallback":true}',
        answer_allowed=True,
    )
    assert result.valid is True
    assert result.final_action == "fallback"


def test_validator_accepts_no_answer_fallback_when_answer_is_not_allowed():
    tools = []
    result = validate_model_output(
        candidate_tools=tools,
        raw_output='{"tool_calls":[],"answer":false,"fallback":true}',
        answer_allowed=False,
    )
    assert result.valid is True
    assert result.final_action == "fallback"


def test_validator_rejects_empty_tool_calls_without_fallback():
    tools = []
    result = validate_model_output(
        candidate_tools=tools,
        raw_output='{"tool_calls":[],"answer":false}',
        answer_allowed=False,
    )
    assert result.valid is False
    assert result.error == "empty tool_calls must use fallback"


def test_validator_rejects_argument_outside_enum():
    tools = [
        ToolDefinition(
            name="light",
            description="Light control",
            tags=["light"],
            arguments_schema=JsonSchema(
                type="object",
                properties={"state": {"type": "string", "enum": ["on", "off"]}},
                required=["state"],
            ),
        )
    ]
    result = validate_model_output(
        candidate_tools=tools,
        raw_output='{"tool_calls":[{"name":"light","arguments":{"state":"dim"}}],"answer":false}',
        answer_allowed=False,
    )
    assert result.valid is False
    assert result.error == "schema validation failed"
