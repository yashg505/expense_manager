import streamlit as st
from src.components.navbar import render_navbar


st.write("Check the data please", icon="✅")

render_navbar(current_page=2)

