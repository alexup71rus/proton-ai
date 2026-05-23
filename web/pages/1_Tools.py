import json

import streamlit as st

from client import post


st.title("Tools")

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

tools_text = st.text_area(
    "Registry JSON",
    json.dumps(default_tools, ensure_ascii=False, indent=2),
    height=260,
)

if st.button("Validate tools"):
    st.json(post("/tools/validate", {"tools": json.loads(tools_text)}))
