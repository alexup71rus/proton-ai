from protonx.schemas import ToolDefinition


def _normalize(text: str) -> list[str]:
    return text.lower().replace(",", " ").replace(".", " ").split()


def _score(user_text: str, tool: ToolDefinition) -> int:
    tokens = _normalize(user_text)
    score = 0
    for tag in tool.tags:
        tag_tokens = _normalize(tag)
        if any(token in tokens for token in tag_tokens):
            score += 2
        if tag in user_text.lower():
            score += 3
    if tool.name in user_text.lower():
        score += 5
    return score


def score_candidate_tools(
    user_text: str, tools: list[ToolDefinition]
) -> list[tuple[ToolDefinition, int]]:
    return sorted(
        ((tool, _score(user_text, tool)) for tool in tools),
        key=lambda item: (-item[1], item[0].name),
    )


def select_candidate_tools(
    user_text: str, tools: list[ToolDefinition], max_candidates: int
) -> list[ToolDefinition]:
    if not tools or max_candidates <= 0:
        return []
    ranked = score_candidate_tools(user_text, tools)
    if ranked[0][1] <= 0:
        return []
    return [tool for tool, _score_value in ranked[:max_candidates]]
