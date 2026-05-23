from itertools import count


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
    if "response" in parsed_output:
        payload["response"] = parsed_output["response"]
    if parsed_output.get("fallback") is True:
        payload["fallback"] = True
    return payload
