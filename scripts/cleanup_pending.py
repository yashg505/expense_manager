import sys
import os

# Ensure the src directory is in the path so we can import modules
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from expense_manager.dbs.image_metadata import ImageMetadataDB
from expense_manager.logger import get_logger

logger = get_logger(__name__)

def main():
    """
    Cleans up images and metadata for receipts that are still in 'pending' status.
    This is useful for resetting the workspace or removing abandoned uploads.
    """
    try:
        db = ImageMetadataDB()
        
        print("Searching for 'pending' images to clean up...")
        result = db.cleanup_images_by_status(["pending"])
        
        print("-" * 40)
        print(f"Cleanup Complete:")
        print(f"  Deleted Files: {result['deleted_files']}")
        print(f"  Missing Files: {result['missing_files']}")
        print(f"  Deleted DB Rows: {result['deleted_rows']}")
        print("-" * 40)
        
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
