import streamlit as st


st.title("Test")
st.warning("This Streamlit page is legacy and has been retired.")
st.markdown("Use the new SPA Test screen instead of the old Streamlit sandbox.")
st.code("cd web_ui && npm run dev", language="bash")
st.stop()
