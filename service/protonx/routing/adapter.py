from itertools import count

from protonx.contracts import build_fallback_response
from protonx.contracts import is_fallback_tool_name


_ids = count(1)


def to_openai_tool_calls(parsed_output: dict, answer_allowed: bool) -> dict:
    fallback_selected = any(
        is_fallback_tool_name(call["name"])
        for call in parsed_output["tool_calls"]
    )
    tool_calls = []
    for call in parsed_output["tool_calls"]:
        if is_fallback_tool_name(call["name"]):
            continue
        tool_calls.append(
            {
                "id": f"call_{next(_ids)}",
                "type": "function",
                "name": call["name"],
                "arguments": call["arguments"],
            }
        )

    payload = {"tool_calls": tool_calls}
    if fallback_selected:
        payload["fallback"] = True
        response = build_fallback_response(answer_allowed)
        if response is not None:
            payload["response"] = response
    return payload
