import os
import sys
import psycopg2
from expense_manager.logger import get_logger

# Add src to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

logger = get_logger(__name__)

def setup_pgvector():
    """
    Connects to the Neon Postgres database and enables the 'vector' extension.
    Table creation is now handled by the respective DB classes (TaxonomySync, MainDB).
    """
    conn_str = os.getenv("NEON_CONN_STR")
    if not conn_str:
        logger.error("NEON_CONN_STR not found in environment variables.")
        return

    try:
        logger.info("Connecting to Neon Postgres...")
        with psycopg2.connect(conn_str) as conn:
            with conn.cursor() as cur:
                # 1. Enable pgvector extension
                logger.info("Enabling 'vector' extension...")
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                
            conn.commit()
        
        logger.info("pgvector setup completed successfully.")

    except Exception as e:
        logger.error(f"Failed to setup pgvector: {e}")

if __name__ == "__main__":
    setup_pgvector()
