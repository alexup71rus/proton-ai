from protonx.contracts import FALLBACK_TOOL_NAME
from protonx.enum_values import enum_is_supported
from protonx.schemas import ToolDefinition


def validate_unique_tool_names(tools: list[ToolDefinition]) -> None:
    names = [tool.name for tool in tools]
    if FALLBACK_TOOL_NAME in names:
        raise ValueError(f"tool name {FALLBACK_TOOL_NAME} is reserved")
    if len(names) != len(set(names)):
        raise ValueError("tool names must be unique")


def validate_supported_schema_subset(tools: list[ToolDefinition]) -> None:
    for tool in tools:
        schema = tool.arguments_schema
        if schema.type != "object":
            raise ValueError("only object schemas are supported")
        for field_name, property_schema in schema.properties.items():
            if property_schema.get("type") != "string":
                raise ValueError(
                    f"unsupported schema type for {tool.name}.{field_name}"
                )
            enum_values = property_schema.get("enum")
            if not enum_is_supported(enum_values):
                raise ValueError(
                    f"unsupported enum definition for {tool.name}.{field_name}"
                )
