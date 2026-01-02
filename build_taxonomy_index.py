from src.dbs.taxonomy_db import TaxonomyDB
from src.logger import get_logger
import sys
from dotenv import load_dotenv

# Load env vars (API key)
load_dotenv()

# Configure logging
logger = get_logger(__name__)

def build_index():
    try:
        logger.info("Starting Taxonomy FAISS Index Rebuild...")
        
        # Initialize DB Layer
        db = TaxonomyDB()
        
        # Trigger Index Build
        count = db.build_vector_index()
        
        logger.info(f"Successfully built FAISS index with {count} items.")
        print(f"SUCCESS: Built index for {count} taxonomy items.")
        
    except Exception as e:
        logger.error(f"Failed to build index: {e}")
        print(f"ERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    build_index()
