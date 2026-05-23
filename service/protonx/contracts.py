FALLBACK_MESSAGE = (
    "I work only with available tools."
)


def build_system_contract(answer_allowed: bool) -> dict:
    return {
        "answer_allowed": answer_allowed,
        "fallback_message": FALLBACK_MESSAGE,
        "instruction": "Choose only from candidate tools. Return JSON. Use fallback when unsure.",
    }


def build_fallback_payload(answer_allowed: bool) -> dict:
    payload = {
        "tool_calls": [],
        "answer": answer_allowed,
        "fallback": True,
    }
    if answer_allowed:
        payload["response"] = FALLBACK_MESSAGE
    return payload
