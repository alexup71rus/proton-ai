from protonx.model_contract import compact_tool_from_definition
from protonx.schemas import ToolDefinition


def build_routing_prompt(
    user_text: str, tools: list[ToolDefinition], answer_allowed: bool
) -> dict:
    return {
        "answer_allowed": answer_allowed,
        "tools": [
            compact_tool_from_definition(tool, variation_key=f"{user_text}|{index}")
            for index, tool in enumerate(tools)
        ],
        "user": user_text,
    }
