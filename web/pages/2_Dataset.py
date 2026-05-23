import json

import streamlit as st

from client import post


st.title("Dataset")

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
    },
    {
        "name": "window",
        "description": "Window control",
        "tags": ["window", "close"],
        "arguments_schema": {
            "type": "object",
            "properties": {"state": {"type": "string", "enum": ["open", "close"]}},
            "required": ["state"],
        },
    },
]

tools_text = st.text_area(
    "Tools JSON",
    json.dumps(default_tools, ensure_ascii=False, indent=2),
    height=320,
)

if st.button("Build dataset"):
    st.json(post("/train/dataset/build", {"tools": json.loads(tools_text)}))
