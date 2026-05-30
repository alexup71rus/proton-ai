import streamlit as st


st.set_page_config(page_title="Proton AI Legacy UI", layout="centered")

st.title("Proton AI Legacy UI")
st.warning("This Streamlit interface is retired and should no longer be used as the primary UI.")
st.markdown(
	"""
Use the new workflow instead:

- start the UI backend on `http://127.0.0.1:8100`
- start the SPA frontend from `web_ui` on `http://localhost:8501`
- use the new routes `Tools`, `Training`, `Test`, and `Logs`
"""
)
st.info("If you are still seeing old Streamlit pages, stop the old Streamlit process before launching the new frontend.")
