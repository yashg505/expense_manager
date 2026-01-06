# Project Milestones: Expense Manager

This document outlines the development roadmap for the Expense Manager application.

## Milestone 1: Core Upload & Processing Engine (CURRENT)
*Goal: Successfully upload images, perform OCR, and parse into structured data.*
- [x] **Project Scaffolding**: Setup `src/`, `pages/`, and `tests/` directories.
- [x] **Data Modeling**: Implement Pydantic models for `ReceiptImage`, `OCRResult`, and `ParserResponse`.
- [x] **Image Uploader**: Build `page1_upload.py` with deduplication and local storage.
- [x] **OCR Integration**: Implement `OCRHandler` supporting RapidOCR and Tesseract.
- [x] **LLM Parser**: Build `src/agents/parser.py` to extract structured items via OpenAI.
- [x] **CLI Validation**: Verify the pipeline via `main.py`.

## Milestone 2: Interactive Review UI
*Goal: Allow users to review and correct parsed receipt data in the browser.*
- [x] **Review Page (Page 2)**: Implement `pages/page2_review.py` to process images in session state.
- [x] **Pipeline Execution**: Add a "Process" button to trigger OCR and LLM parsing for all pending images.
- [x] **Data Editor**: Use `st.data_editor` to allow users to manually correct prices, quantities, and dates.
- [x] **State Management**: Persist corrections back into the `ReceiptImage` model in session state.

## Milestone 3: Intelligent Classification & Taxonomy
*Goal: Automatically categorize items and remember user corrections.*
- [x] **Classification Agent**: Integrate `src/agents/classifier.py` to map items to categories.
- [x] **Taxonomy Search**: Implement FAISS/Vector search in `src/dbs/faiss_store.py` for semantic category matching.
- [x] **Corrections DB**: Wire up `src/dbs/corrections_db.py` to save user category overrides.
- [x] **Sync Logic**: Build `src/sync/taxonomy_sync.py` to update the classifier based on new corrections.

## Milestone 4: Persistence & Storage
*Goal: Save all processed expenses to a local database for historical tracking.*
- [x] **Main Database**: Implement `src/dbs/main_db.py` to store finalized receipts and items.
- [x] **Metadata Tracking**: Save image hashes and processing timestamps in `src/dbs/image_metadata.py`.
- [ ] **Dashboard (v2)**: Create a basic overview of expenses (totals by category/month).

## Milestone 5: External Integration & Export
*Goal: Export data to Google Sheets and other external formats.*
- [x] **Google Sheets Handler**: Implement `src/integration/gsheet_handler.py`.
- [x] **Confirmation Page (Page 3)**: Final summary and "Export" button.
- [x] **Export Validation**: Ensure data types match Google Sheets requirements.

## Milestone 6: Polish & Performance
- [ ] **Async Processing**: Use threading or background tasks for OCR/LLM calls to keep the UI responsive.
- [ ] **Error Resilience**: Implement better retry logic for API calls.
- [ ] **Theme/UX**: Add Material Design principles and custom styling via Streamlit.
