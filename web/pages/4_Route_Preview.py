import json

import streamlit as st

from client import post


st.title("Route Preview")

default_tools = [
    {
        "name": "light",
        "description": "Light control",
        "tags": ["light", "lamp"],
        "arguments_schema": {
            "type": "object",
            "properties": {"state": {"type": "string", "enum": ["on", "off"]}},
            "required": ["state"],
        },
    }
]

user_text = st.text_input("User text", "turn on the lamp")
tools_text = st.text_area(
    "Tools JSON",
    json.dumps(default_tools, ensure_ascii=False, indent=2),
    height=240,
)

if st.button("Preview route"):
    payload = {
        "user_text": user_text,
        "tools": json.loads(tools_text),
        "answer_allowed": False,
    }
    st.json(post("/route/preview", payload))
