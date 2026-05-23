from protonx.schemas import ToolDefinition


def validate_unique_tool_names(tools: list[ToolDefinition]) -> None:
    names = [tool.name for tool in tools]
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
            if enum_values is not None and not isinstance(enum_values, list):
                raise ValueError(
                    f"unsupported enum definition for {tool.name}.{field_name}"
                )
