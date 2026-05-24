from itertools import count

from protonx.contracts import build_fallback_response


_ids = count(1)


def to_openai_tool_calls(parsed_output: dict) -> dict:
    tool_calls = []
    for call in parsed_output["tool_calls"]:
        tool_calls.append(
            {
                "id": f"call_{next(_ids)}",
                "type": "function",
                "name": call["name"],
                "arguments": call["arguments"],
            }
        )

    payload = {"tool_calls": tool_calls, "answer": parsed_output["answer"]}
    if parsed_output.get("fallback") is True:
        payload["fallback"] = True
        response = build_fallback_response(bool(parsed_output["answer"]))
        if response is not None:
            payload["response"] = response
    return payload
