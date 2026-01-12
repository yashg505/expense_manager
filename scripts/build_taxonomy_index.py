from expense_manager.sync.taxonomy_sync import TaxonomySync
from expense_manager.logger import get_logger
import sys
from dotenv import load_dotenv

# Load env vars (API key, DB conn)
load_dotenv()

# Configure logging
logger = get_logger(__name__)

def run_sync():
    try:
        logger.info("Starting Manual Taxonomy Sync (Sheet -> Postgres + Vector)...")
        
        # Initialize Sync Agent
        syncer = TaxonomySync()
        
        # Trigger Sync
        success = syncer.sync()
        
        if success:
            logger.info("Successfully synced taxonomy.")
            print("SUCCESS: Taxonomy synced to Postgres and Vector DB.")
        else:
            logger.error("Taxonomy sync returned False.")
            sys.exit(1)
        
    except Exception as e:
        logger.error(f"Failed to sync taxonomy: {e}")
        print(f"ERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_sync()
