import streamlit as st
import pandas as pd
from PIL import Image
import os
import sys
import sqlite3

from src.components.navbar import render_navbar
from src.components.ocr_handler import OCRHandler
from src.agents.parser import parse_receipt
from src.agents.classifier import ClassifierAgent
from src.llm.openai_client import OpenAIClient
from src.dbs.taxonomy_db import TaxonomyDB
from src.dbs.corrections_db import CorrectionsDB
from src.dbs.main_db import MainDB
from src.utils.load_config import load_config_file
from src.models.parsers import ParserResponse, ItemClassification, Price, ParsedItem
from src.integration.gsheet_handler import GSheetHandler
from src.logger import get_logger

logger = get_logger(__name__)

# --- Initialization ---
st.set_page_config(page_title="Review Receipts", layout="wide")
render_navbar(current_page=2)

config = load_config_file()

def initialize_agents():
    if 'ocr_handler' not in st.session_state:
        st.session_state['ocr_handler'] = OCRHandler(backend="rapidocr")
    if 'llm_client' not in st.session_state:
        st.session_state['llm_client'] = OpenAIClient(model_name=config['llm']['classification_model'])
    if 'classifier_agent' not in st.session_state:
        st.session_state['classifier_agent'] = ClassifierAgent(llm_client=st.session_state['llm_client'])
    if 'taxonomy_db' not in st.session_state:
        st.session_state['taxonomy_db'] = TaxonomyDB()
    if 'corrections_db' not in st.session_state:
        st.session_state['corrections_db'] = CorrectionsDB()
    if 'main_db' not in st.session_state:
        st.session_state['main_db'] = MainDB()

initialize_agents()

# --- Helper Functions ---

def get_taxonomy_options():
    """Returns a list of full_path strings from TaxonomyDB."""
    rows = st.session_state['taxonomy_db'].get_all_rows()
    paths = [row['full_path'] for row in rows]
    paths.append("Uncategorized")
    return sorted(list(set(paths)))

def process_receipt(file_id):
    """Runs the OCR -> Parser -> Classifier pipeline for a single image."""
    img_obj = st.session_state['images'][file_id]
    
    with st.spinner(f"Processing {img_obj.file_name}..."):
        try:
            # 1. OCR
            ocr_result = st.session_state['ocr_handler'].run(img_obj.image_path)
            if not ocr_result.success:
                st.error(f"OCR failed for {img_obj.file_name}")
                return
            img_obj.ocr_text = ocr_result.text

            # 2. Parse
            parser_response = parse_receipt(img_obj.ocr_text, st.session_state['llm_client'])
            img_obj.parser_response = parser_response

            # 3. Classify each item
            shop_name = parser_response.shop or "Unknown"
            for item in parser_response.parsed_items:
                classification = st.session_state['classifier_agent'].classify_item(
                    item_name=item.item,
                    shop_name=shop_name,
                    item_type=item.item_type
                )
                
                # Attach classification to item
                item.classification = ItemClassification(
                    item_type=item.item_type,
                    taxonomy_id=str(classification.taxonomy_id),
                    category=classification.category,
                    sub_category_i=classification.sub_category_i or "",
                    sub_category_ii=classification.sub_category_ii or ""
                )

            img_obj.processed = True
            st.session_state['images'][file_id] = img_obj
            
        except Exception as e:
            logger.error(f"Pipeline failed for {img_obj.file_name}: {e}")
            st.error(f"Failed to process {img_obj.file_name}")

def save_receipt_edits(file_id, edited_data, header_info):
    """Compares edits, saves to CorrectionsDB and MainDB."""
    img_obj = st.session_state['images'][file_id]
    original_parser = img_obj.parser_response
    
    # 1. Update Header Info
    original_parser.shop = header_info['shop']
    original_parser.date = header_info['date']
    
    # 2. Update Items and Check for Corrections
    new_items = []
    taxonomy_rows = st.session_state['taxonomy_db'].get_all_rows()
    path_to_id = {row['full_path']: str(row['id']) for row in taxonomy_rows}
    
    for row in edited_data:
        # Map selected path back to ID
        selected_path = row['Category Path']
        new_tax_id = path_to_id.get(selected_path, "UNCATEGORIZED")
        
        # Check if changed from original prediction (Step 1 correction logic)
        predicted_id = row.get('predicted_id', 'UNCATEGORIZED')
        
        if new_tax_id != predicted_id and new_tax_id != "UNCATEGORIZED":
            st.session_state['corrections_db'].add_correction(
                shop_name=header_info['shop'],
                item_text=row['Item Name'],
                taxonomy_id=new_tax_id
            )
            st.toast(f"Saved correction for {row['Item Name']}")

        # Build clean data structure for MainDB
        new_items.append({
            "item": row['Item Name'],
            "taxonomy_id": new_tax_id,
            "item_count": row['Qty'],
            "price": row['Price']
        })

    # 3. Save to MainDB (Historical persistence)
    st.session_state['main_db'].insert_finalized_items(
        file_id=file_id,
        shop_name=header_info['shop'],
        receipt_date=header_info['date'],
        items=new_items
    )
    
    img_obj.metadata['confirmed'] = True
    st.session_state['images'][file_id] = img_obj
    st.success(f"Receipt '{img_obj.file_name}' confirmed and saved!")

def export_to_gsheets(confirmed_fids):
    """Fetches confirmed items from MainDB and pushes to Google Sheets."""
    try:
        handler = GSheetHandler()
        all_data = []
        
        taxonomy_rows = st.session_state['taxonomy_db'].get_all_rows()
        tax_map = {str(r['id']): r for r in taxonomy_rows}
        
        with st.spinner("Preparing data for export..."):
            for fid in confirmed_fids:
                with sqlite3.connect(config["paths"]["main_db"]) as conn:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.execute("SELECT * FROM processed_items WHERE file_id = ?", (fid,))
                    rows = [dict(r) for r in cursor.fetchall()]
                
                for row in rows:
                    tax_info = tax_map.get(str(row['taxonomy_id']), {})
                    export_row = {
                        "Date": row['receipt_date'],
                        "Shop": row['shop_name'],
                        "Item": row['item_text'],
                        "Category": tax_info.get('category', 'Uncategorized'),
                        "Sub Category I": tax_info.get('sub_category_i', ''),
                        "Sub Category II": tax_info.get('sub_category_ii', ''),
                        "Quantity": row['quantity'],
                        "Price": row['price'],
                        "Total": row['total']
                    }
                    all_data.append(export_row)

        if not all_data:
            st.error("No data found to export.")
            return False

        df_export = pd.DataFrame(all_data)
        
        with st.spinner("Uploading to Google Sheets..."):
            handler.append_df_to_sheet(df_export)
            
        return True

    except Exception as e:
        logger.error(f"Export failed: {e}")
        st.error(f"Export failed: {e}")
        return False

# --- UI Layout ---

st.title("📋 Review & Categorize Receipts")

if not st.session_state.get('images'):
    st.warning("No images uploaded. Please go to the Upload page.")
    st.stop()

# 1. Batch Processing Trigger
unprocessed = [fid for fid, img in st.session_state['images'].items() if not img.processed]
if unprocessed:
    if st.button(f"⚡ Process {len(unprocessed)} New Receipts"):
        for fid in unprocessed:
            process_receipt(fid)
        st.rerun()

# 2. Review Section
taxonomy_options = get_taxonomy_options()
taxonomy_rows = st.session_state['taxonomy_db'].get_all_rows()
id_to_path = {str(row['id']): row['full_path'] for row in taxonomy_rows}

for fid, img_obj in st.session_state['images'].items():
    if not img_obj.processed:
        continue
    
    # Skip already exported items to keep UI clean
    if img_obj.metadata.get('exported'):
        continue

    status_label = "✅ Confirmed" if img_obj.metadata.get('confirmed') else "⏳ Pending Review"
    with st.expander(f"{status_label} | {img_obj.file_name} - {img_obj.parser_response.shop or 'Unknown'}"):
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.image(img_obj.image_path, use_container_width=True)
            
        with col2:
            # Header Edits
            h_col1, h_col2 = st.columns(2)
            with h_col1:
                new_shop = st.text_input("Shop Name", value=img_obj.parser_response.shop, key=f"shop_{fid}")
            with h_col2:
                new_date = st.text_input("Date (YYYY-MM-DD)", value=img_obj.parser_response.date, key=f"date_{fid}")
            
            # Prepare Table Data
            table_rows = []
            for item in img_obj.parser_response.parsed_items:
                current_tax_id = str(item.classification.taxonomy_id) if item.classification else "UNCATEGORIZED"
                current_path = id_to_path.get(current_tax_id, "Uncategorized")
                
                table_rows.append({
                    "Item Name": item.item,
                    "Qty": item.item_count,
                    "Price": item.price.amount,
                    "Category Path": current_path,
                    "predicted_id": current_tax_id 
                })
            
            df = pd.DataFrame(table_rows)
            
            # Highlights Uncategorized
            uncat_count = len(df[df['Category Path'] == "Uncategorized"])
            if uncat_count > 0:
                st.warning(f"⚠️ {uncat_count} items are Uncategorized.")

            edited_df = st.data_editor(
                df,
                column_config={
                    "Category Path": st.column_config.SelectboxColumn(
                        "Category Path",
                        help="Select the taxonomy category",
                        options=taxonomy_options,
                        required=True,
                    ),
                    "predicted_id": None # Hide tracking column
                },
                disabled=["predicted_id"],
                key=f"editor_{fid}",
                hide_index=True,
                use_container_width=True
            )
            
            if st.button("Confirm & Save Receipt", key=f"btn_{fid}", type="primary"):
                save_receipt_edits(
                    file_id=fid,
                    edited_data=edited_df.to_dict('records'),
                    header_info={'shop': new_shop, 'date': new_date}
                )
                st.rerun()

# 3. Export Section
confirmed_fids = [fid for fid, img in st.session_state['images'].items() 
                  if img.metadata.get('confirmed') and not img.metadata.get('exported')]

if confirmed_fids:
    st.divider()
    st.subheader(f"🚀 Ready to Export ({len(confirmed_fids)} receipts)")
    if st.button("Export All Confirmed to Google Sheets", type="primary", use_container_width=True):
        if export_to_gsheets(confirmed_fids):
            for fid in confirmed_fids:
                st.session_state['images'][fid].metadata['exported'] = True
            
            st.balloons()
            st.success("🎉 Data successfully uploaded to Google Sheets!")
            if st.button("Start New Batch"):
                st.session_state['images'] = {}
                st.session_state['fingerprints'] = set()
                st.switch_page("pages/page1_upload.py")
