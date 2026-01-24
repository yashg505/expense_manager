# Expense Manager

An intelligent expense management system that leverages OCR (RapidOCR/PaddleOCR) and LLMs (OpenAI/Gemini) to automate the extraction, classification, and organization of receipt data.

## 🚀 Overview

Expense Manager transforms messy receipt images into structured data. It uses advanced OCR to read text, employs Large Language Models to interpret and extract line items, and applies a vector-search-based taxonomy system to classify expenses accurately. Finally, it exports the processed data to Google Sheets for easy tracking.

### Key Features
- **Intelligent OCR**: Uses RapidOCR and PaddleOCR for high-accuracy text extraction from images.
- **LLM-Powered Parsing**: Extracts structured receipt data (vendor, date, total, line items) using GPT or Gemini .
- **Smart Classification**: Automatically assigns categories to items based on a taxonomy stored in PostgreSQL (using `pgvector` for native semantic search).
- **Deduplication**: Uses image fingerprinting (ImageHash) to prevent duplicate receipt uploads.
- **Streamlit UI**: A user-friendly, multi-page web interface for uploading, reviewing, and confirming expenses.
- **Google Sheets Integration**: Seamlessly syncs confirmed expenses to a centralized spreadsheet.
- **CI/CD Pipeline**: Automated testing and deployment to Google Cloud (GCE) using GitHub Actions and Docker.

## 🛠 Technology Stack
- **Frontend**: [Streamlit](https://streamlit.io/)
- **OCR**: [RapidOCR](https://github.com/RapidAI/RapidOCR), [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR)
- **LLM**: OpenAI, Google Gemini
- **Data Validation**: [Pydantic](https://docs.pydantic.dev/)
- **Database**: PostgreSQL with `pgvector` (Vector Search), SQLite (Metadata)
- **Embeddings**: Sentence-Transformers (`all-MiniLM-L6-v2`)
- **Dependency Management**: [uv](https://github.com/astral-sh/uv)
- **Cloud**: Google Cloud Platform (GCS, Secret Manager, Artifact Registry, GCE)

## 📁 Project Structure
```text
├── src/expense_manager/ # Core logic
│   ├── agents/          # LLM Parsing and Classification logic
│   ├── components/      # UI components (uploader, navbar, etc.)
│   ├── dbs/             # Database handlers (PostgreSQL, SQLite)
│   ├── integration/     # Google Sheets handler
│   ├── llm/             # OpenAI and Gemini client wrappers
│   ├── models/          # Pydantic data models
│   ├── sync/            # Taxonomy synchronization logic
│   └── utils/           # Logging, image fingerprinting, embeddings, etc.
├── pages/               # Streamlit multi-page application logic
├── scripts/             # Utility scripts (sync, setup, deployment)
├── data/                # SQLite databases and taxonomy files
├── artifacts/           # Uploaded images and metadata
├── tests/               # Pytest suite
├── .github/workflows/   # CI/CD Pipeline
└── Dockerfile           # Containerization setup
```

## ⚙️ Setup & Installation

### Prerequisites
- Python 3.10+
- [uv](https://github.com/astral-sh/uv) package manager
- PostgreSQL database with `pgvector` extension enabled.

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
2. Update `config.yaml` with your specific `sheet_id` and other preferences.

## 💻 Usage

### Running the Streamlit UI
```bash
uv run streamlit run main.py
```
This will launch the application in your browser:
1. **Upload**: Drop receipt images (detects duplicates automatically).
2. **Review**: Check extracted data and adjust classifications.
3. **Confirm**: Finalize and sync data to Google Sheets.

### Syncing Taxonomy
To sync the taxonomy from Google Sheets to the PostgreSQL database and update the vector embeddings:
```bash
uv run python scripts/build_taxonomy_index.py
```

## 🧪 Testing
Run the test suite using `pytest`:
```bash
uv run pytest
```

## 🚢 Deployment
The project is containerized using Docker and deployed via GitHub Actions.

- **Build Image**: `docker build -t expense-manager .`
- **Run Locally**: `docker run -p 8501:8501 --env-file .env expense-manager`
- **CI/CD**: Pushing to the `master` branch triggers the `.github/workflows/pipeline.yml`, which tests, builds, and deploys the app to Google Compute Engine.

## 📝 Development Conventions
- **Style**: Follow [PEP 8](https://peps.python.org/pep-0008/).
- **Typing**: Use Python type hints consistently.
- **Logging**: Use the internal `expense_manager.logger` for tracing.
- **Errors**: Use `expense_manager.exception.CustomException` for consistent error handling.
