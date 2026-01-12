# Expense Manager

An intelligent expense management system that leverages OCR (RapidOCR/PaddleOCR) and LLMs (OpenAI/Gemini) to automate the extraction, classification, and organization of receipt data.

## 🚀 Overview

Expense Manager transforms messy receipt images into structured data. It uses advanced OCR to read text, employs Large Language Models to interpret and extract line items, and applies a vector-search-based taxonomy system to classify expenses accurately. Finally, it exports the processed data to Google Sheets for easy tracking.

### Key Features
- **Intelligent OCR**: Uses RapidOCR and PaddleOCR for high-accuracy text extraction from images.
- **LLM-Powered Parsing**: Extracts structured receipt data (vendor, date, total, line items) using GPT-4 or Gemini.
- **Smart Classification**: Automatically assigns categories to items based on a taxonomy stored in PostgreSQL (using pgvector for semantic search) and SQLite.
- **Deduplication**: Uses image fingerprinting (ImageHash) to prevent duplicate receipt uploads.
- **Streamlit UI**: A user-friendly, multi-page web interface for uploading, reviewing, and confirming expenses.
- **Google Sheets Integration**: Seamlessly syncs confirmed expenses to a centralized spreadsheet.

## 🛠 Technology Stack
- **Frontend**: [Streamlit](https://streamlit.io/)
- **OCR**: [RapidOCR](https://github.com/RapidAI/RapidOCR), [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR)
- **LLM**: OpenAI (GPT-4), Google Gemini
- **Data Validation**: [Pydantic](https://docs.pydantic.dev/)
- **Database**: PostgreSQL (Metadata, Taxonomy, Vector Search via pgvector)
- **Image Processing**: OpenCV, Pillow, ImageHash
- **Dependency Management**: [uv](https://github.com/astral-sh/uv)

## 📁 Project Structure
```text
├── src/
│   ├── agents/          # Parsing (LLM) and Classification logic
│   ├── components/      # UI components (uploader, navbar, etc.)
│   ├── dbs/             # Database handlers (Postgres)
│   ├── integration/     # Google Sheets handler
│   ├── llm/             # OpenAI and Gemini client wrappers
│   ├── models/          # Pydantic data models
│   └── utils/           # Logging, image fingerprinting, prompt builders
├── pages/               # Streamlit multi-page application logic
├── data/                # SQLite databases (Legacy/Migrating)
├── artifacts/           # Uploaded images and temporary assets
└── tests/               # Pytest suite
```

## ⚙️ Setup & Installation

### Prerequisites
- Python 3.10+
- [uv](https://github.com/astral-sh/uv) package manager
- PostgreSQL database with `pgvector` extension enabled (e.g., Neon).

### Installation
1. Clone the repository.
2. Install dependencies using `uv`:
   ```bash
   uv sync
   ```

### Configuration
1. Create a `.env` file in the root directory and add your API keys:
   ```env
   OPENAI_API_KEY=your_openai_key
   GEMINI_API_KEY=your_gemini_key
   NEON_CONN_STR=postgresql://user:password@host/dbname
   ```
2. Update `config.yaml` with your specific `sheet_id` and other preferences if necessary.

## 💻 Usage

### Running the Streamlit UI (Primary Interface)
```bash
uv run streamlit run pages/page1_upload.py
```
This will launch the application in your browser, where you can:
1. **Upload**: Drop receipt images (detects duplicates automatically).
2. **Review**: Check LLM-extracted data and adjust classifications.
3. **Confirm**: Finalize and sync data to Google Sheets.

### CLI Pipeline (Debug/Test)
```bash
uv run python main.py
```

### Building the Taxonomy Index
If you update the taxonomy in the database or JSON, rebuild the FAISS index:
```bash
uv run python scripts/build_taxonomy_index.py
```

## 🧪 Testing
Run the test suite using `pytest`:
```bash
uv run pytest
```

## 📝 Development Conventions
- **Style**: Follow [PEP 8](https://peps.python.org/pep-0008/).
- **Typing**: Use Python type hints consistently.
- **Logging**: Use the internal `expense_manager.logger` for tracing.
- **Errors**: Use `expense_manager.exception.CustomException` for consistent error handling.
