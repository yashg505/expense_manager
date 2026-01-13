import os
import streamlit as st
from PIL import Image

from expense_manager.models.receipt import ReceiptImage
from expense_manager.utils.image_fingerprint import get_image_fingerprint
from expense_manager.utils.artifacts_gcs import upload_artifact, ensure_local_artifact
from expense_manager.dbs.image_metadata import ImageMetadataDB
from expense_manager.logger import get_logger

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
    if 'metadata_db' not in st.session_state:
        st.session_state['metadata_db'] = ImageMetadataDB()

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
            local_path = getattr(old_obj, 'local_path', None)
            if local_path and os.path.exists(local_path):
                os.remove(local_path)
            logger.info("Removed file_id %s from session", fid)

        for f in uploaded_files:
            if f.file_id in st.session_state['images']:
                continue

            try:
                # 1. Open image briefly to get fingerprint
                image = Image.open(f).convert("RGB")
                fingerprint = get_image_fingerprint(image)

                # 2. Deduplication check
                # get fingerpints
                
                status = ['uploaded']
                images = ImageMetadataDB()
                uploaded_images = images.get_images_by_status(status)
                uploaded_fingerprints = {img['fingerprint'] for img in uploaded_images}
                st.session_state['fingerprints'].update(uploaded_fingerprints)
                
                if fingerprint in st.session_state['fingerprints']:
                    st.warning(f"Duplicate content skipped: {f.name}")
                    continue

                # 3. Save to Directory
                file_ext = os.path.splitext(f.name)[1]
                if not file_ext:
                    file_ext = ".png"
                
                temp_path = os.path.join(TEMP_DIR, f"{f.file_id}{file_ext}")
                file_bytes = bytes(f.getbuffer())
                with open(temp_path, "wb") as buf:
                    buf.write(file_bytes)

                gcs_path = upload_artifact(
                    file_bytes,
                    f"{f.file_id}{file_ext}",
                    content_type=f.type
                )

                # 4. Create Pydantic Model
                img_obj = ReceiptImage(
                    file_id=f.file_id,
                    file_name=f.name,
                    image_path=gcs_path,
                    local_path=temp_path,
                    fingerprint=fingerprint,
                    metadata={"size": f.size, "type": f.type}
                )

                # Persist to database
                st.session_state['metadata_db'].upsert_image(
                    file_id=img_obj.file_id,
                    file_name=img_obj.file_name,
                    fingerprint=img_obj.fingerprint,
                    image_path=img_obj.image_path,
                    state_dict=img_obj.model_dump()
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

                try:
                    local_path = ensure_local_artifact(
                        img_obj.image_path, existing_local=getattr(img_obj, 'local_path', None)
                    )
                    setattr(img_obj, 'local_path', local_path)
                    st.session_state['images'][fid] = img_obj
                    st.image(local_path, caption=img_obj.file_name, width="stretch")
                except FileNotFoundError:
                    st.error(f"Preview unavailable for {img_obj.file_name}")


    return st.session_state['images']
