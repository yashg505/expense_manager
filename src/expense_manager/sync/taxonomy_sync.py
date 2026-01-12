"""
taxonomy_sync.py

Sync process:
    1. Load taxonomy sheet via GSheetHandler
    2. Process data: generate IDs and full_paths
    3. Generate embeddings
    4. Sync to Postgres table 'taxonomy' (metadata + embeddings)

Always full refresh.
"""

import os
import re
import psycopg2
from expense_manager.logger import get_logger
from expense_manager.exception import CustomException
from expense_manager.utils.load_config import load_config_file
from expense_manager.utils.embed_texts import embed_texts

from expense_manager.integration.gsheet_handler import GSheetHandler

logger = get_logger(__name__)

SHEET_TYPE='taxonomy'

class TaxonomySync:
    def __init__(self):
        try:
            self.config = load_config_file()
            self.conn_str = os.getenv("NEON_CONN_STR")
            
            if not self.conn_str:
                raise CustomException("Database connection string (NEON_CONN_STR) not found.")

            # load sheet handler
            self.sheet = GSheetHandler(sheet_type=SHEET_TYPE)

            logger.info("Initialized TaxonomySync (Postgres + Vector).")
        except Exception as e:
            raise CustomException(e)

    # ------------------------------------------------------
    # MAIN SYNC
    # ------------------------------------------------------
    def sync(self):
        """
        Full sync:
            → Fetch rows from Google Sheet
            → Process (add id, full_path)
            → Generate embeddings
            → Rewrite main taxonomy table (with embeddings)
        """
        try:
            logger.info("Starting taxonomy SYNC...")

            # 1. Fetch
            rows, _ = self.sheet.fetch_taxonomy_rows()
            if not rows:
                raise CustomException("Google Sheet returned no taxonomy rows.")

            # 2. Process
            processed_rows = self._process_rows(rows)

            # 3. Generate Embeddings
            texts = [r["full_path"] for r in processed_rows]
            embeddings = embed_texts(texts) # returns numpy array
            
            if len(embeddings) != len(processed_rows):
                raise CustomException("Mismatch between rows and embeddings count.")
            
            # Add embeddings to rows
            for i, row in enumerate(processed_rows):
                row["embedding"] = embeddings[i].tolist()

            # 4. Rewrite main taxonomy table
            self._rewrite_taxonomy_db(processed_rows)

            logger.info("Taxonomy sync completed successfully.")
            return True

        except Exception as e:
            logger.error(f"Sync failed: {e}")
            raise CustomException(e)

    # ------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------
    def _process_rows(self, rows: list[dict]) -> list[dict]:
        """
        Add 'id' and 'full_path' to each row.
        full_path: Category > Sub I > Sub II
        id: slugified full_path
        """
        processed = []
        seen_ids = set()

        for i, row in enumerate(rows):
            # Keys from Google Sheet: Category, Sub Category-I, Sub Category II, Description
            cat = str(row.get("Category", "")).strip()
            sub1 = str(row.get("Sub Category-I", "")).strip()
            sub2 = str(row.get("Sub Category II", "")).strip()
            desc = str(row.get("Description", "")).strip()

            # Construct full path
            parts = [p for p in [cat, sub1, sub2] if p]
            
            # Skip empty rows
            if not parts:
                logger.warning(f"Row {i} has no category data. Skipping.")
                continue

            full_path = " > ".join(parts)

            # Construct ID (slug)
            # e.g. "Food & Drink" -> "food_drink"
            slug_source = "_".join(parts).lower()
            row_id = re.sub(r'[^a-z0-9_]+', '_', slug_source).strip('_')

            if not row_id:
                logger.warning(f"Row {i} generated empty ID from path '{full_path}'. Skipping.")
                continue

            if row_id in seen_ids:
                logger.warning(f"Duplicate ID '{row_id}' generated for row {i} ({full_path}). Skipping.")
                continue

            seen_ids.add(row_id)

            row["id"] = row_id
            row["full_path"] = full_path
            
            # Normalize fields for DB
            row["category"] = cat
            row["sub_category_i"] = sub1
            row["sub_category_ii"] = sub2
            row["description"] = desc
            
            processed.append(row)
        
        logger.info(f"Processed {len(processed)} valid rows (added IDs and paths).")
        return processed

    # ------------------------------------------------------
    # DB REWRITE (Main Table)
    # ------------------------------------------------------
    def _rewrite_taxonomy_db(self, rows: list[dict]):
        """Wipe taxonomy table and reinsert everything."""
        try:
            logger.info("Rewriting 'taxonomy' table...")

            with psycopg2.connect(self.conn_str) as conn:
                with conn.cursor() as cur:
                    # Ensure extension
                    cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")

                    # Ensure schema exists
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS taxonomy (
                            id TEXT PRIMARY KEY,
                            category TEXT,
                            sub_category_i TEXT,
                            sub_category_ii TEXT,
                            full_path TEXT,
                            description TEXT,
                            embedding vector(384)
                        );
                    """)

                    # wipe old data
                    cur.execute("TRUNCATE TABLE taxonomy;")

                    insert_sql = """
                        INSERT INTO taxonomy (
                            id,
                            category,
                            sub_category_i,
                            sub_category_ii,
                            full_path,
                            description,
                            embedding
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s);
                    """

                    for row in rows:
                        cur.execute(
                            insert_sql,
                            (
                                row["id"],
                                row["category"],
                                row["sub_category_i"],
                                row["sub_category_ii"],
                                row["full_path"],
                                row.get("description"),
                                row.get("embedding"),
                            )
                        )
                conn.commit()

            logger.info(f"Inserted {len(rows)} rows into 'taxonomy' table.")

        except Exception as e:
            logger.error("Failed rewriting taxonomy table.")
            raise CustomException(e)
