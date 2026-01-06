"""
taxonomy_sync.py

Simple sync process:
    1. Load taxonomy sheet via GSheetHandler
    2. Rewrite taxonomy.db entirely
    3. Rebuild taxonomy FAISS index

No timestamps.
No metadata.
Always full refresh.

Run this manually whenever you update taxonomy in Google Sheet.
"""

import sqlite3
from expense_manager.logger import get_logger
from expense_manager.exception import CustomException
from expense_manager.utils.load_config import load_config_file

from expense_manager.dbs.taxonomy_db import TaxonomyDB
from expense_manager.integration.gsheet_handler import GSheetHandler

logger = get_logger(__name__)


class TaxonomySync:
    def __init__(self):
        try:
            self.config = load_config_file()
            self.db_path = self.config["paths"]["taxonomy_db"]

            # load sheet + taxonomy db handler
            self.sheet = GSheetHandler()
            self.taxonomy_db = TaxonomyDB()

            logger.info("Initialized simple TaxonomySync.")
        except Exception as e:
            raise CustomException(e)

    # ------------------------------------------------------
    # MAIN SYNC
    # ------------------------------------------------------
    def sync(self):
        """
        Full sync:
            → Fetch rows from Google Sheet
            → Rewrite taxonomy.db
            → Rebuild FAISS index
        """
        try:
            logger.info("Starting taxonomy SYNC...")

            rows, _ = self.sheet.fetch_taxonomy_rows()

            if not rows:
                raise CustomException("Google Sheet returned no taxonomy rows.")

            self._rewrite_taxonomy_db(rows)

            # Rebuild FAISS index
            count = self.taxonomy_db.build_vector_index()
            logger.info(f"Rebuilt FAISS index with {count} taxonomy entries!")

            logger.info("Taxonomy sync completed successfully.")
            return True

        except Exception as e:
            logger.error(f"Sync failed: {e}")
            raise CustomException(e)

    # ------------------------------------------------------
    # DB REWRITE
    # ------------------------------------------------------
    def _rewrite_taxonomy_db(self, rows: list[dict]):
        """Wipe taxonomy table and reinsert everything."""
        try:
            logger.info("Rewriting taxonomy.db with sheet content...")

            conn = sqlite3.connect(self.db_path)

            # Ensure schema exists
            conn.execute("""
                CREATE TABLE IF NOT EXISTS taxonomy (
                    id TEXT PRIMARY KEY,
                    category TEXT,
                    sub_category_i TEXT,
                    sub_category_ii TEXT,
                    full_path TEXT,
                    description TEXT
                );
            """)

            # wipe old data
            conn.execute("DELETE FROM taxonomy;")

            insert_sql = """
                INSERT INTO taxonomy (
                    id,
                    category,
                    sub_category_i,
                    sub_category_ii,
                    full_path,
                    description
                ) VALUES (?, ?, ?, ?, ?, ?);
            """

            for row in rows:
                conn.execute(
                    insert_sql,
                    (
                        row["id"],
                        row.get("category"),
                        row.get("sub_category_i"),
                        row.get("sub_category_ii"),
                        row.get("full_path"),
                        row.get("description"),
                    )
                )

            conn.commit()
            conn.close()

            logger.info(f"Inserted {len(rows)} rows into taxonomy.db.")

        except Exception as e:
            logger.error("Failed rewriting taxonomy.db.")
            raise CustomException(e)
