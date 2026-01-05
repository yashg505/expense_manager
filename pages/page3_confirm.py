import streamlit as st
from expense_manager.components.navbar import render_navbar


st.success("The data has been uploaded", icon="✅")

render_navbar(current_page=3)

st.balloons()
