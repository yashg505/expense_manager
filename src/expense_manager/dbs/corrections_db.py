"""
corrections_db.py

Manages user-provided category overrides (Step 1 of the classification waterfall).
Stores exact string matches for (shop_name, item_text) to ensure consistent re-classification.
"""

import psycopg2
import sys
import os
from typing import Optional
import re

from expense_manager.logger import get_logger
from expense_manager.exception import CustomException

logger = get_logger(__name__)

class CorrectionsDB:
    def __init__(self):
        try:
            self.conn_str = os.getenv("NEON_CONN_STR")
            if not self.conn_str:
                raise CustomException("Database connection string (NEON_CONN_STR) not found.")

            self._init_db()
            logger.info("Initialized CorrectionsDB (Postgres).")
        except Exception as e:
            raise CustomException(e, sys)

    def _init_db(self):
        """Creates the corrections table if it doesn't exist."""
        try:
            with psycopg2.connect(self.conn_str) as conn:
                with conn.cursor() as cur:
                    # Using a composite primary key for shop + item
                    cur.execute('''
                        CREATE TABLE IF NOT EXISTS corrections (
                            shop_name TEXT NOT NULL,
                            item_text TEXT NOT NULL,
                            corrected_taxonomy_id TEXT NOT NULL,
                            user_id TEXT DEFAULT 'system',
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            corrected_item_type TEXT,
                            PRIMARY KEY (shop_name, item_text)
                        )
                    ''')
            logger.debug("Corrections database schema verified with shop_name.")
        except Exception as e:
            logger.error("Failed to initialize corrections database schema.")
            raise CustomException(e, sys)

    def _normalize(self, text: str) -> str:
        """
        Normalizes text for consistent lookup:
        - Lowercase
        - Strip whitespace
        - Collapse multiple spaces
        """
        if not text:
            return ""
        text = text.lower().strip()
        text = re.sub(r'\s+', ' ', text)
        return text

    def add_correction(self, shop_name: str, item_text: str, taxonomy_id: str, corrected_item_type: Optional[str] = None, user_id: str = 'system'):
        """
        Adds or updates a correction for a specific shop + item combo.
        Uses ON CONFLICT for Postgres upsert.
        """
        try:
            norm_shop = self._normalize(shop_name)
            norm_item = self._normalize(item_text)
            
            if not norm_item:
                return

            with psycopg2.connect(self.conn_str) as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO corrections (shop_name, item_text, corrected_taxonomy_id, user_id, corrected_item_type, updated_at)
                        VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                        ON CONFLICT (shop_name, item_text) 
                        DO UPDATE SET
                            corrected_taxonomy_id = EXCLUDED.corrected_taxonomy_id,
                            user_id = EXCLUDED.user_id,
                            corrected_item_type = EXCLUDED.corrected_item_type,
                            updated_at = CURRENT_TIMESTAMP;
                    """, (norm_shop, norm_item, taxonomy_id, user_id, corrected_item_type))
            
            logger.info(f"Correction saved: [{norm_shop}] '{norm_item}' -> '{taxonomy_id}' (Type: {corrected_item_type})")
        except Exception as e:
            logger.error(f"Failed to save correction for {shop_name}/{item_text}: {e}")
            raise CustomException(e, sys)

    def get_correction(self, shop_name: str, item_text: str) -> Optional[tuple[str, Optional[str]]]:
        """
        Retrieves the taxonomy ID and corrected item type for a given shop + item if it exists.
        Returns: (taxonomy_id, corrected_item_type) or None
        """
        try:
            norm_shop = self._normalize(shop_name)
            norm_item = self._normalize(item_text)
            
            if not norm_item:
                return None

            with psycopg2.connect(self.conn_str) as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT corrected_taxonomy_id, corrected_item_type
                        FROM corrections
                        WHERE shop_name = %s AND item_text = %s
                    """, (norm_shop, norm_item))
                    row = cur.fetchone()
                
            if row:
                logger.debug(f"Correction hit: [{norm_shop}] '{norm_item}' -> '{row[0]}' (Type: {row[1]})")
                return (row[0], row[1])
            
            return None
        except Exception as e:
            logger.error(f"Failed to fetch correction for {shop_name}/{item_text}: {e}")
            raise CustomException(e, sys)
