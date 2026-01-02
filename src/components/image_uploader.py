import os
import sys
from typing import Optional, Dict, Any
import streamlit as st
from PIL import Image

from src.models.receipt import ReceiptImage
from src.utils.image_fingerprint import get_image_fingerprint
from src.logger import get_logger
from src.exception import CustomException

logger = get_logger(__name__)

# --- Configuration ---
# Using artifacts/images to align with project structure
TEMP_DIR = "artifacts/images"
os.makedirs(TEMP_DIR, exist_ok=True)

def initialize_session():
    """Ensures session state keys exist."""
    if 'images' not in st.session_state:
        st.session_state['images'] = {}
    if 'fingerprints' not in st.session_state:
        st.session_state['fingerprints'] = set()

def upload_images():
    """
    Streamlit uploader that:
    1. Saves uploaded files to a persistent directory.
    2. Uses Pydantic for the ReceiptImage model.
    3. Prevents redundant re-processing of already uploaded files.
    """
    st.subheader("📤 Upload Receipt Images")
    initialize_session()

    uploaded_files = st.file_uploader(
        "Upload receipt images (JPEG, PNG)",
        type=["png", "jpg", "jpeg"],
        accept_multiple_files=True,
        key="receipt_uploader" # Unique key for persistence
    )

    if uploaded_files:
        # Sync state: Remove items from session_state that were removed from uploader
        current_file_ids = {f.file_id for f in uploaded_files}
        removed_ids = [fid for fid in st.session_state['images'] if fid not in current_file_ids]
        
        for fid in removed_ids:
            old_obj = st.session_state['images'].pop(fid)
            st.session_state['fingerprints'].discard(old_obj.fingerprint)
            logger.info("Removed file_id %s from session", fid)

        for f in uploaded_files:
            # SKIP if we already have this specific file_id processed
            if f.file_id in st.session_state['images']:
                continue

            try:
                # 1. Open image briefly to get fingerprint
                image = Image.open(f).convert("RGB")
                fingerprint = get_image_fingerprint(image)

                # 2. Deduplication check
                if fingerprint in st.session_state['fingerprints']:
                    st.warning(f"Duplicate content skipped: {f.name}")
                    continue

                # 3. Save to Directory
                file_ext = os.path.splitext(f.name)[1]
                if not file_ext:
                    file_ext = ".png"
                
                temp_path = os.path.join(TEMP_DIR, f"{f.file_id}{file_ext}")
                with open(temp_path, "wb") as buf:
                    buf.write(f.getbuffer())

                # 4. Create Pydantic Model
                img_obj = ReceiptImage(
                    file_id=f.file_id,
                    file_name=f.name,
                    image_path=temp_path, # Path instead of Object
                    fingerprint=fingerprint,
                    metadata={"size": f.size, "type": f.type}
                )

                st.session_state['images'][f.file_id] = img_obj
                st.session_state['fingerprints'].add(fingerprint)
                logger.info("Processed and saved: %s", f.name)

            except Exception as e:
                logger.error("Error processing %s: %s", f.name, e)
                st.error(f"Failed to process {f.name}")

    # --- Display Uploaded Images ---
    if st.session_state['images']:
        st.divider()
        st.markdown(f"### 🖼️ Uploaded Images ({len(st.session_state['images'])})")
        
        cols = st.columns(3)
        for idx, (fid, img_obj) in enumerate(st.session_state['images'].items()):
            with cols[idx % 3]:
                # We load the image from path ONLY when displaying
                st.image(img_obj.image_path, caption=img_obj.file_name, use_container_width=True)
        
        # A trigger for the next stage
        if st.button("🚀 Process All Receipts", type="primary"):
            st.session_state['trigger_ocr'] = True

    return st.session_state['images']
