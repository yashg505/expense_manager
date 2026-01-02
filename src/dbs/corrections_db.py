import sqlite3
import sys
from typing import Optional
import re

from src.logger import get_logger
from src.exception import CustomException
from src.utils.load_config import load_config_file

logger = get_logger(__name__)

class CorrectionsDB:
    """
    Manages user-provided category overrides (Step 1 of the classification waterfall).
    Stores exact string matches for (shop_name, item_text) to ensure consistent re-classification.
    """

    def __init__(self):
        try:
            config = load_config_file()
            self.path = config["paths"]["corrections_db"]
            self._init_db()
            logger.info(f"Initialized CorrectionsDB at {self.path}")
        except Exception as e:
            raise CustomException(e, sys)

    def _init_db(self):
        """Creates the corrections table if it doesn't exist."""
        try:
            with sqlite3.connect(self.path) as conn:
                # Using a composite primary key for shop + item
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS corrections (
                        shop_name TEXT NOT NULL,
                        item_text TEXT NOT NULL,
                        corrected_taxonomy_id TEXT NOT NULL,
                        user_id TEXT DEFAULT 'system',
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
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

    def add_correction(self, shop_name: str, item_text: str, taxonomy_id: str, user_id: str = 'system'):
        """
        Adds or updates a correction for a specific shop + item combo.
        """
        try:
            norm_shop = self._normalize(shop_name)
            norm_item = self._normalize(item_text)
            
            if not norm_item:
                return

            with sqlite3.connect(self.path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO corrections (shop_name, item_text, corrected_taxonomy_id, user_id, updated_at)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (norm_shop, norm_item, taxonomy_id, user_id))
            
            logger.info(f"Correction saved: [{norm_shop}] '{norm_item}' -> '{taxonomy_id}'")
        except Exception as e:
            logger.error(f"Failed to save correction for {shop_name}/{item_text}: {e}")
            raise CustomException(e, sys)

    def get_correction(self, shop_name: str, item_text: str) -> Optional[str]:
        """
        Retrieves the taxonomy ID for a given shop + item if it exists.
        """
        try:
            norm_shop = self._normalize(shop_name)
            norm_item = self._normalize(item_text)
            
            if not norm_item:
                return None

            with sqlite3.connect(self.path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT corrected_taxonomy_id 
                    FROM corrections
                    WHERE shop_name = ? AND item_text = ?
                """, (norm_shop, norm_item))
                row = cursor.fetchone()
                
            if row:
                logger.debug(f"Correction hit: [{norm_shop}] '{norm_item}' -> '{row[0]}'")
                return row[0]
            
            return None
        except Exception as e:
            logger.error(f"Failed to fetch correction for {shop_name}/{item_text}: {e}")
            raise CustomException(e, sys)
