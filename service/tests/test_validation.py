from protonx.routing.validate import validate_model_output
from protonx.contracts import build_fallback_tool
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
        available_tools=tools,
        raw_output='{"tool_calls":[{"name":"lamp","arguments":{"state":"on"}}]}',
    )
    assert result.valid is False
    assert result.error == "unknown tool outside available tools"


def test_validator_accepts_fallback_payload():
    tools = [build_fallback_tool()]
    result = validate_model_output(
        available_tools=tools,
        raw_output='{"tool_calls":[{"name":"__fallback__","arguments":{}}]}',
    )
    assert result.valid is True
    assert result.final_action == "fallback"


def test_validator_rejects_fallback_tool_combined_with_other_calls():
    tools = [
        build_fallback_tool(),
        ToolDefinition(
            name="light",
            description="Light control",
            tags=["light"],
            arguments_schema=JsonSchema(
                type="object",
                properties={"state": {"type": "string", "enum": ["on", "off"]}},
                required=["state"],
            ),
        ),
    ]
    result = validate_model_output(
        available_tools=tools,
        raw_output='{"tool_calls":[{"name":"__fallback__","arguments":{}},{"name":"light","arguments":{"state":"on"}}]}',
    )
    assert result.valid is False
    assert result.error == "fallback tool cannot be combined with other tool calls"


def test_validator_rejects_empty_tool_calls_without_fallback():
    tools = []
    result = validate_model_output(
        available_tools=tools,
        raw_output='{"tool_calls":[]}',
    )
    assert result.valid is False
    assert result.error == "empty tool_calls must use __fallback__"


def test_validator_rejects_unexpected_top_level_fields():
    tools = [build_fallback_tool()]
    result = validate_model_output(
        available_tools=tools,
        raw_output='{"tool_calls":[{"name":"__fallback__","arguments":{}}],"response":"nope"}',
    )

    assert result.valid is False
    assert result.error == "unexpected top-level fields"


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
        available_tools=tools,
        raw_output='{"tool_calls":[{"name":"light","arguments":{"state":"dim"}}]}',
    )
    assert result.valid is False
    assert result.error == "schema validation failed"


def test_validator_accepts_value_description_enum_object():
    tools = [
        ToolDefinition(
            name="list_directory",
            description="Directory listing",
            tags=["files"],
            arguments_schema=JsonSchema(
                type="object",
                properties={
                    "directory": {
                        "type": "string",
                        "enum": {
                            "downloads": "папка загрузок",
                            "project_root": "корень проекта",
                        },
                    }
                },
                required=["directory"],
            ),
        )
    ]

    result = validate_model_output(
        available_tools=tools,
        raw_output='{"tool_calls":[{"name":"list_directory","arguments":{"directory":"downloads"}}]}',
    )

    assert result.valid is True
