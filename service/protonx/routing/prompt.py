from protonx.model_contract import compact_tool_from_definition
from protonx.schemas import ToolDefinition


def build_routing_prompt(
    user_text: str, tools: list[ToolDefinition], answer_allowed: bool
) -> dict:
    compact_tools = [
        compact_tool_from_definition(tool, variation_key=f"{user_text}|{index}")
        for index, tool in enumerate(tools)
    ]
    return {
        "answer_allowed": answer_allowed,
        "tools": compact_tools,
        "user": user_text,
    }
