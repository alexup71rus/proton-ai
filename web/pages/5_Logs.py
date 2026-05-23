import json
from pathlib import Path

import streamlit as st


st.title("Logs")

log_path = Path(__file__).resolve().parents[2] / "data" / "logs" / "router.jsonl"
if not log_path.exists():
    st.info("No router logs yet.")
else:
    rows = [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    st.json(rows[-50:])
