import streamlit as st
from src.components.navbar import render_navbar
from src.components.image_uploader import upload_images

# Set page config once at the entry point
st.set_page_config(page_title="Expense Manager - Upload", layout="wide")

st.title("💸 Expense Manager")
st.write("Upload your receipts to get started.")

render_navbar(current_page=1)

# Image uploader component handles session state and display
images = upload_images()

if images:
    st.divider()
    st.info(f"Loaded {len(images)} images. Ready to process?")
    if st.button("Go to Review & Categorize", type="primary", use_container_width=True):
        st.switch_page("pages/page2_review.py")

# Debugging session state (optional, can be removed)
if 'images' in st.session_state and st.session_state['images']:
    with st.expander("Session Debug Info"):
        st.write(st.session_state)
