# Expense Manager

An intelligent expense management system that uses OCR (RapidOCR) and LLMs (OpenAI) to extract structured data from receipt images, classify items using a taxonomy, and export results to Google Sheets. The application provides a Streamlit-based UI for uploading, reviewing, and confirming expense data.

## Project Structure

- **`src/`**: Core source code.
    - **`agents/`**: Logic for parsing (`parser.py`) and classification (`classifier.py`).
    - **`components/`**: UI components (e.g., `image_uploader.py`, `ocr_handler.py`).
    - **`dbs/`**: Database interactions (SQLite, FAISS) for taxonomy and storage.
    - **`integration/`**: External service handlers (e.g., `gsheet_handler.py`).
    - **`llm/`**: OpenAI/LLM client wrappers.
    - **`models/`**: Pydantic data models (`receipt.py`, `ocr_result.py`).
    - **`utils/`**: Helper utilities (`logger.py`, `image_fingerprint.py`).
- **`pages/`**: Streamlit application pages (multi-page app structure).
    - `page1_upload.py`: Receipt upload and deduplication.
    - `page2_review.py`: Data review and processing.
    - `page3_confirm.py`: Final confirmation.
- **`data/`**: Storage for SQLite databases (`main_data.db`, `taxonomy.db`) and FAISS indexes.
- **`artifacts/`**: storage for uploaded images and other temporary assets.
- **`tests/`**: Pytest test suite.

## Development Setup

This project uses `uv` for dependency management.

### Prerequisites
- Python 3.10+
- `uv` package manager

### Installation
```bash
uv sync
```

### Running the Application

**Streamlit UI (Primary Interface):**
```bash
uv run streamlit run pages/page1_upload.py
```

**CLI Pipeline (Test/Debug):**
```bash
uv run python main.py
```

### Testing
Run the test suite using `pytest`:
```bash
uv run pytest
```
To run specific tests:
```bash
uv run pytest tests/test_end_to_end.py
```

## Key Technologies

- **Frontend**: Streamlit
- **OCR**: RapidOCR (via `rapidocr-onnxruntime`)
- **LLM**: OpenAI (GPT models)
- **Data Validation**: Pydantic
- **Database**: SQLite (metadata, structured data), FAISS (vector search for taxonomy)
- **Image Processing**: Pillow, OpenCV

## Development Conventions

- **Code Style**: Follow PEP 8. Use `snake_case` for functions/variables, `PascalCase` for classes.
- **Type Hinting**: Use Python type hints (`str`, `List`, `Optional`, etc.) consistently.
- **Error Handling**: Use `src.exception.CustomException` and `src.logger` for tracing.
- **State Management**: Use `streamlit.session_state` for persisting data between pages.
- **File Storage**: Uploaded images are stored in `artifacts/images/` and referenced by path in `ReceiptImage` models.
