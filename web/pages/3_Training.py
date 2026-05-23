import streamlit as st

from client import get, post


st.title("Training")

dataset_path = st.text_input("Dataset path", "data/train/routing/routing.jsonl")

col_status, col_start = st.columns(2)

with col_status:
    if st.button("Refresh status"):
        st.json(get("/train/status"))

with col_start:
    if st.button("Start training"):
        st.json(post("/train/start", {"dataset_path": dataset_path}))
