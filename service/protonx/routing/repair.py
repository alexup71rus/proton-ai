def repair_json_syntax(raw_output: str) -> str | None:
    trimmed = raw_output.strip()
    if not trimmed:
        return None
    if trimmed.count("{") > trimmed.count("}"):
        trimmed = trimmed + "}" * (trimmed.count("{") - trimmed.count("}"))
    if trimmed.count("[") > trimmed.count("]"):
        trimmed = trimmed + "]" * (trimmed.count("[") - trimmed.count("]"))
    return trimmed
