from protonx.contracts import build_system_contract
from protonx.schemas import ToolDefinition


def build_routing_prompt(
    user_text: str, tools: list[ToolDefinition], answer_allowed: bool
) -> dict:
    return {
        "system": build_system_contract(answer_allowed),
        "tools": [tool.model_dump() for tool in tools],
        "user": user_text,
    }
