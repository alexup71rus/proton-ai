import streamlit as st

st.set_page_config(page_title="Proton-X", layout="wide")

st.title("Proton-X")
st.caption("Validator-driven tool router")
st.page_link("pages/1_Tools.py", label="Tools")
st.page_link("pages/2_Dataset.py", label="Dataset")
st.page_link("pages/3_Training.py", label="Training")
st.page_link("pages/4_Route_Preview.py", label="Route Preview")
st.page_link("pages/5_Logs.py", label="Logs")
