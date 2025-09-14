import os

# Relative folder structure (since you're already in the project root)
STRUCTURE = {
    "data": [
        "main_data.db", "corrections.db",
        "main_data.index", "taxonomy.index", "taxonomy.json"
    ],
    "src": {
        "components": ["image_uploader.py", "ocr_handler.py"],
        "dbs": ["main_db.py", "corrections_db.py", "taxonomy_db.py", "faiss_store.py"],
        "llm": ["openai_client.py"],
        "agents": ["parser.py", "classifier.py"],
        "integration": ["gsheet_handler.py"],
        "utils": ["prompt_builder.py", "logger.py", "config.py", "validators.py"],
    },
    "pages": ["page1_upload.py", "page2_review.py", "page3_dashboard.py"],
    "tests": ["test_parser.py", "test_classifier.py", "test_dbs.py", "test_end_to_end.py"],
    "notebooks": ["experiments.ipynb"],
}

EXTRA_FILES = ["src/background.py", "src/datamodels.py"]

def create_structure(base, structure):
    for name, content in structure.items():
        folder = os.path.join(base, name)
        os.makedirs(folder, exist_ok=True)

        # Add __init__.py to every Python package folder inside src
        if folder.startswith(os.path.join("src")):
            init_file = os.path.join(folder, "__init__.py")
            open(init_file, "w").close()

        if isinstance(content, list):  # files
            for file in content:
                path = os.path.join(folder, file)
                open(path, "w").close()
        elif isinstance(content, dict):  # subfolders
            create_structure(folder, content)

def main():
    create_structure(".", STRUCTURE)
    for file in EXTRA_FILES:
        path = os.path.join(".", file)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "w").close()
    print("✅ Project scaffold created in current folder")

if __name__ == "__main__":
    main()
