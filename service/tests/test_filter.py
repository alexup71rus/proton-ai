from protonx.routing.filter import select_candidate_tools
from protonx.schemas import JsonSchema, ToolDefinition


def _tool(name: str, tags: list[str]) -> ToolDefinition:
    return ToolDefinition(
        name=name,
        description=name,
        tags=tags,
        arguments_schema=JsonSchema(type="object", properties={}, required=[]),
    )


def test_select_candidate_tools_returns_best_matches_first():
    tools = [
        _tool("light", ["light", "lamp", "brightness"]),
        _tool("window", ["window", "close", "draft"]),
        _tool("speaker", ["music", "volume", "sound"]),
    ]
    result = select_candidate_tools("turn on the lamp", tools, max_candidates=2)
    assert [tool.name for tool in result] == ["light", "speaker"]
