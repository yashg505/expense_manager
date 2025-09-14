import streamlit as st
from src.components.navbar import render_navbar
from src.components.uploader import upload_images

st.write("Upload the receipt")
render_navbar(current_page=1)

x = upload_images()

st.page_link("src/pages/page2_review.py", label='Process the data')

if 'images' in st.session_state.keys():
    print(f"printing session state : {st.session_state}")