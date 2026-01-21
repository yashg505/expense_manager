import psycopg2
from psycopg2.extras import DictCursor
import os
import sys
from typing import Optional, List, Dict, Any

from expense_manager.logger import get_logger
from expense_manager.exception import CustomException
from expense_manager.utils.embed_texts import embed_texts

logger = get_logger(__name__)

class MainDB:
    """
    Main database layer for storing finalized expense items and managing
    the historical items vector index (Step 2 of classification).
    """

    def __init__(self):
        try:
            self.conn_str = os.getenv("NEON_CONN_STR")
            if not self.conn_str:
                raise CustomException("Database connection string (NEON_CONN_STR) not found.")
            
            self._init_db()
            
            logger.info("Initialized MainDB (Postgres).")
        except Exception as e:
            raise CustomException(e, sys)

    def _init_db(self):
        """Initializes the PostgreSQL schema for processed items."""
        try:
            with psycopg2.connect(self.conn_str) as conn:
                with conn.cursor() as cur:
                    cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                    cur.execute('''
                        CREATE TABLE IF NOT EXISTS processed_items (
                            id SERIAL PRIMARY KEY,
                            file_id TEXT NOT NULL,
                            shop_name TEXT,
                            receipt_date DATE,
                            receipt_time TIME,
                            item_text TEXT NOT NULL,
                            taxonomy_id TEXT NOT NULL,
                            item_type TEXT,
                            quantity INTEGER,
                            price REAL,
                            total REAL,
                            discount REAL,
                            embedding vector(384),
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
            logger.debug(f"Searching historical exact match for shop: '{norm_shop}', item: '{norm_item}'")
            with psycopg2.connect(self.conn_str) as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT taxonomy_id 
                        FROM processed_items
                        WHERE LOWER(shop_name) = %s AND LOWER(item_text) = %s
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
    
    def get_historical_exact_match_type(self, shop_name: str, item_type: str) -> Optional[str]:
        """
        Searches for an exact match in historical data (Step 2).
        """
        try:
            norm_shop = self._normalize(shop_name)
            norm_type = self._normalize(item_type)
            
            logger.debug(f"Searching historical exact match for shop: '{norm_shop}', type: '{norm_type}'")
            
            if not norm_type:
                return None

            with psycopg2.connect(self.conn_str) as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT taxonomy_id 
                        FROM processed_items
                        WHERE LOWER(shop_name) = %s AND LOWER(item_type) = %s
                        ORDER BY created_at DESC
                        LIMIT 1
                    """, (norm_shop, norm_type))
                    row = cursor.fetchone()
            
            if row:
                logger.debug(f"Historical exact match hit (type): [{norm_shop}] '{norm_type}' -> '{row[0]}'")
                return row[0]
            
            return None
        except Exception as e:
            logger.error(f"Failed to fetch historical exact match for {shop_name}/{item_type}: {e}")
            return None

    def insert_finalized_items(self, file_id: str, shop_name: str, receipt_date: str, receipt_time: str, items: List[Dict[str, Any]]):
        """
        Saves a list of finalized items to the database.
        Expected item format: {'item': str, 'taxonomy_id': str, 'item_count': int, 'price': float, 'discount': float, 'item_type': str, ...}
        """
        try:
            # Generate embeddings for all items at once
            item_texts = [item["item"] for item in items]
            embeddings = embed_texts(item_texts)

            with psycopg2.connect(self.conn_str) as conn:
                with conn.cursor() as cursor:
                    for i, item in enumerate(items):
                        # Handle potential dict or direct float for price/discount
                        price = item.get("price", 0)
                        if isinstance(price, dict):
                            price = price.get("amount", 0)
                        
                        discount = item.get("discount", 0)
                        if isinstance(discount, dict):
                            discount = discount.get("amount", 0) # Fallback to 0 if not specified
                        
                        qty = item.get("item_count", 1)
                        total = price - discount
                        embedding = embeddings[i].tolist() if i < len(embeddings) else None

                        cursor.execute("""
                        INSERT INTO processed_items (
                            file_id, item_text, taxonomy_id, item_type, quantity, price, discount, total, shop_name, receipt_date, receipt_time, embedding
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        file_id,
                        item["item"],
                        item["taxonomy_id"],
                        item.get("item_type"),
                        qty,
                        price,
                        discount,
                        total,
                        shop_name,
                        receipt_date,
                        receipt_time,
                        embedding
                    ))
            logger.info(f"Saved {len(items)} items for file_id: {file_id}")
        except Exception as e:
            logger.error(f"Failed to save finalized items for {file_id}: {e}")
            raise CustomException(e, sys)

    def get_items_by_file_id(self, file_id: str) -> List[Dict[str, Any]]:
        """Retrieves all processed items for a specific file_id."""
        try:
            with psycopg2.connect(self.conn_str) as conn:
                with conn.cursor(cursor_factory=DictCursor) as cur:
                    cur.execute("SELECT * FROM processed_items WHERE file_id = %s", (file_id,))
                    rows = cur.fetchall()
                    return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get items for file_id {file_id}: {e}")
            return []

    # ----------------------------------------------------------------------
    # Vector Search (Historical)
    # ----------------------------------------------------------------------

    def search_history(self, query_vector, threshold=0.1) -> Optional[str]:
        """
        Searches for a similar item in history using pgvector.
        Returns the taxonomy_id if a high-confidence match is found.
        """
        try:
            # Ensure query_vector is compatible list
            if hasattr(query_vector, "tolist"):
                query_vector = query_vector.tolist()
            
            if isinstance(query_vector, list) and len(query_vector) == 1 and isinstance(query_vector[0], list):
                query_vector = query_vector[0]

            with psycopg2.connect(self.conn_str) as conn:
                with conn.cursor(cursor_factory=DictCursor) as cur:
                    # <=> is cosine distance. 
                    # We want distance <= threshold.
                    # Order by distance ASC to get best match.
                    sql = """
                        SELECT taxonomy_id, item_text, (embedding <=> %s::vector) as distance
                        FROM processed_items
                        WHERE embedding IS NOT NULL
                        ORDER BY distance ASC
                        LIMIT 1;
                    """
                    cur.execute(sql, (query_vector,))
                    row = cur.fetchone()

            if row:
                score = float(row["distance"])
                if score <= threshold:
                    logger.info(f"Historical hit: '{row['item_text']}' (Score: {score:.4f})")
                    return row["taxonomy_id"]
            
            return None
        except Exception as e:
            logger.error(f"Historical search failed: {e}")
            return None

    def backfill_embeddings(self):
        """
        Backfills missing embeddings in processed_items table.
        """
        try:
            with psycopg2.connect(self.conn_str) as conn:
                # 1. Fetch items without embeddings
                with conn.cursor(cursor_factory=DictCursor) as cur:
                    cur.execute("SELECT id, item_text FROM processed_items WHERE embedding IS NULL")
                    rows = cur.fetchall()

            if not rows:
                logger.info("No items need embedding backfill.")
                return

            logger.info(f"Backfilling embeddings for {len(rows)} items...")
            
            texts = [row["item_text"] for row in rows]
            embeddings = embed_texts(texts)
            
            # 2. Update items
            with psycopg2.connect(self.conn_str) as conn:
                with conn.cursor() as cur:
                    for i, row in enumerate(rows):
                        emb = embeddings[i].tolist()
                        cur.execute(
                            "UPDATE processed_items SET embedding = %s WHERE id = %s",
                            (emb, row["id"])
                        )
            
            logger.info("Backfill completed.")

        except Exception as e:
            logger.error(f"Failed to backfill embeddings: {e}")
            raise CustomException(e, sys)