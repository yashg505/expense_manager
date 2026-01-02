import sqlite3
import sys
import json
from pathlib import Path
from typing import Optional, List, Dict, Any

from src.logger import get_logger
from src.exception import CustomException
from src.utils.load_config import load_config_file
from src.utils.embed_texts import embed_texts
from src.dbs.faiss_store import FaissStore

logger = get_logger(__name__)

class MainDB:
    """
    Main database layer for storing finalized expense items and managing
    the historical items vector index (Step 2 of classification).
    """

    def __init__(self):
        try:
            config = load_config_file()
            self.db_path = config["paths"]["main_db"]
            self.index_path = config["paths"]["main_index"]
            self.meta_path = str(Path(self.index_path).with_suffix('.json')) # e.g. main_data.index.json
            
            self._init_db()
            
            self.faiss = None
            self.historical_ids = [] # List of (item_text, taxonomy_id)
            
            logger.info(f"Initialized MainDB at {self.db_path}")
        except Exception as e:
            raise CustomException(e, sys)

    def _init_db(self):
        """Initializes the SQLite schema for processed items."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS processed_items (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        file_id TEXT NOT NULL,
                        item_text TEXT NOT NULL,
                        taxonomy_id TEXT NOT NULL,
                        quantity INTEGER,
                        price REAL,
                        total REAL,
                        shop_name TEXT,
                        receipt_date TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
            logger.debug("Main database schema verified.")
        except Exception as e:
            logger.error("Failed to initialize main database schema.")
            raise CustomException(e, sys)

    def _normalize(self, text: str) -> str:
        """
        Normalizes text for consistent lookup:
        - Lowercase
        - Strip whitespace
        - Collapse multiple spaces
        """
        import re
        if not text:
            return ""
        text = text.lower().strip()
        text = re.sub(r'\s+', ' ', text)
        return text

    def get_historical_exact_match(self, shop_name: str, item_text: str) -> Optional[str]:
        """
        Searches for an exact match in historical data (Step 2).
        """
        try:
            norm_shop = self._normalize(shop_name)
            norm_item = self._normalize(item_text)
            
            if not norm_item:
                return None

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                # We use LOWER() in SQL for safety if the data wasn't normalized on insertion
                cursor.execute("""
                    SELECT taxonomy_id 
                    FROM processed_items
                    WHERE LOWER(shop_name) = ? AND LOWER(item_text) = ?
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (norm_shop, norm_item))
                row = cursor.fetchone()
            
            if row:
                logger.debug(f"Historical exact match hit: [{norm_shop}] '{norm_item}' -> '{row[0]}'")
                return row[0]
            
            return None
        except Exception as e:
            logger.error(f"Failed to fetch historical exact match for {shop_name}/{item_text}: {e}")
            return None

    def insert_finalized_items(self, file_id: str, shop_name: str, receipt_date: str, items: List[Dict[str, Any]]):
        """
        Saves a list of finalized items to the database.
        Expected item format: {'item': str, 'taxonomy_id': str, 'item_count': int, 'price': float, ...}
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                for item in items:
                    price = item.get("price", {}).get("amount", 0) if isinstance(item.get("price"), dict) else item.get("price", 0)
                    qty = item.get("item_count", 1)
                    
                    conn.execute("""
                        INSERT INTO processed_items (
                            file_id, item_text, taxonomy_id, quantity, price, total, shop_name, receipt_date
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        file_id,
                        item["item"],
                        item["taxonomy_id"],
                        qty,
                        price,
                        qty * price,
                        shop_name,
                        receipt_date
                    ))
            logger.info(f"Saved {len(items)} items for file_id: {file_id}")
        except Exception as e:
            logger.error(f"Failed to save finalized items for {file_id}: {e}")
            raise CustomException(e, sys)

    # ----------------------------------------------------------------------
    # FAISS Operations (Historical Search)
    # ----------------------------------------------------------------------

    def load_index(self):
        """Loads the historical items FAISS index and metadata."""
        try:
            if not Path(self.index_path).exists():
                logger.warning("Historical FAISS index does not exist yet.")
                return False

            if not Path(self.meta_path).exists():
                logger.warning("Historical FAISS metadata missing.")
                return False

            with open(self.meta_path, 'r') as f:
                self.historical_ids = json.load(f)["mappings"]

            self.faiss = FaissStore(self.index_path)
            self.faiss.load()
            logger.info("Historical FAISS index loaded.")
            return True
        except Exception as e:
            logger.error(f"Failed to load historical index: {e}")
            return False

    def search_history(self, query_vector, threshold=0.1) -> Optional[str]:
        """
        Searches for a similar item in history.
        Returns the taxonomy_id if a high-confidence match is found.
        """
        try:
            if self.faiss is None:
                if not self.load_index():
                    return None

            idxs, scores = self.faiss.search(query_vector, k=1)
            
            if len(idxs) > 0 and idxs[0] != -1:
                score = scores[0]
                # Lower score means closer match in IndexFlatL2
                if score <= threshold:
                    match_data = self.historical_ids[idxs[0]]
                    logger.info(f"Historical hit: '{match_data['text']}' (Score: {score:.4f})")
                    return match_data["taxonomy_id"]
            
            return None
        except Exception as e:
            logger.error(f"Historical search failed: {e}")
            return None

    def rebuild_index(self):
        """
        Rebuilds the historical index from all items in processed_items table.
        This should be run periodically or after significant corrections.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("SELECT item_text, taxonomy_id FROM processed_items")
                rows = cursor.fetchall()

            if not rows:
                logger.info("No items to index.")
                return

            texts = [row["item_text"] for row in rows]
            mappings = [{"text": row["item_text"], "taxonomy_id": row["taxonomy_id"]} for row in rows]
            
            logger.info(f"Rebuilding historical index with {len(texts)} entries.")
            vectors = embed_texts(texts)
            
            store = FaissStore(self.index_path)
            store.build_new_index(vectors)
            
            with open(self.meta_path, 'w') as f:
                json.dump({"mappings": mappings}, f)
                
            logger.info("Historical index rebuilt successfully.")
            self.faiss = store
            self.historical_ids = mappings

        except Exception as e:
            logger.error(f"Failed to rebuild historical index: {e}")
            raise CustomException(e, sys)