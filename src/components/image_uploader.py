from dataclasses import dataclass, field
from typing import Optional, Dict, Any
import streamlit as st
from PIL import Image
from src.utils.image_fingerprint import get_image_fingerprint
from src.logger import get_logger
from src.exception import CustomException
import sys

logger = get_logger(__name__)

@dataclass
class ReceiptImage:
    file_id:str
    file_name:str
    image:Image.Image
    fingerprint:str
    processed:bool=False
    oct_text:Optional[str] = None
    category: Optional[str]=None
    df: Optional[str]=None
    metadata: Dict[str, Any] = field(default_factory=dict)

def clear_image_session():
    st.session_state['images'] = {}
    st.session_state['fingerprints'] = set()
    logger.info("Image session state cleared.")

st.session_state.setdefault('images', {})
st.session_state.setdefault('fingerprints', set())


def upload_images():
    '''
    Stearmlit uploader that supports:
    - Drag and Drop
    - File Selection
    - Optiona: image URL upload
    
    Deduplicates images using perceptual hashing (pHash).
    Stores accepted image objects and fingerprints in session_state.
    
    '''

    st.subheader("📤 Upload Receipt Images")


    st.session_state['images'] 

    uploaded_files = st.file_uploader(
        "Upload receipt images (JPEG, PNG)",
        type=["png", "jpg", "jpeg"],
        accept_multiple_files=True,
        on_change=clear_image_session
    )

    if uploaded_files:
        logger.info("%s file(s) uploaded by the user", len(uploaded_files))
        for f in uploaded_files:
            try:    
                image = Image.open(f).convert("RGB")
                fingerprint = get_image_fingerprint(image)
                logger.info("Image %s processed. Fingerprint: %s", f.name, fingerprint)

            
                if fingerprint in st.session_state['fingerprints']:
                    st.warning(f'Duplicate images skipped: {f.name}')
                    logger.warning("Duplicate detected and skipped: %s", f.name)
                    continue

            
            
                img_obj = ReceiptImage(
                    file_id=f.file_id,
                    file_name=f.name,
                    image=image,
                    fingerprint=fingerprint
                )
            
                st.session_state['images'][f.file_id] = img_obj
                st.session_state['fingerprints'].add(fingerprint)
                
                logger.info("Image %s added to session state", f.name)
            
            except Exception as e:
                logger.error("Error processing file %s:%s", f.name, e)
                raise CustomException(e, sys)
      
    # Display Uploaded Images
    if st.session_state['images']:
        st.markdown("### 🖼️ Uploaded Images")
        cols = st.columns(3)
        for idx, img in enumerate(st.session_state['images'].values()):
            with cols[idx % 3]:
                st.image(img.image, caption=img.file_name, use_container_width=True)
        logger.info("Uploaded images displayed.")

    return st.session_state['images']