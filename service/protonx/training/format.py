import json


def serialize_training_record(record: dict) -> str:
    system = json.dumps(record["system"], ensure_ascii=False, sort_keys=True)
    tools = json.dumps(record["tools"], ensure_ascii=False, sort_keys=True)
    user = record["messages"][0]["content"]
    assistant = record["messages"][1]["content"]
    return (
        "<system>\n"
        f"{system}\n"
        "<tools>\n"
        f"{tools}\n"
        "<user>\n"
        f"{user}\n"
        "<assistant>\n"
        f"{assistant}"
    )


def serialize_inference_prompt(prompt: dict) -> str:
    system = json.dumps(prompt["system"], ensure_ascii=False, sort_keys=True)
    tools = json.dumps(prompt["tools"], ensure_ascii=False, sort_keys=True)
    return (
        "<system>\n"
        f"{system}\n"
        "<tools>\n"
        f"{tools}\n"
        "<user>\n"
        f"{prompt['user']}\n"
        "<assistant>\n"
    )
