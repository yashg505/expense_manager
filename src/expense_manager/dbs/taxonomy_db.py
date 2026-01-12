"""
taxonomy_db.py

Domain layer for managing taxonomy data stored in PostgreSQL.

Responsibilities:
    - Provide read access to taxonomy table
    - Validate category IDs
    - Perform vector search for nearest taxonomy categories using pgvector in 'taxonomy' table.

Refactored to remove FAISS dependency in favor of native Postgres vector search.
"""

import os
import psycopg2
from psycopg2.extras import DictCursor

from expense_manager.utils.load_config import load_config_file
from expense_manager.logger import get_logger
from expense_manager.exception import CustomException

logger = get_logger(__name__)


class TaxonomyDB:
    config = load_config_file()

    def __init__(self):
        try:
            self.conn_str = os.getenv("NEON_CONN_STR")            
            if not self.conn_str:
                raise CustomException("Database connection string (NEON_CONN_STR) not found.")

            self.k = self.config["taxonomy"]["taxonomy_k"] # Keep config key name for backward compat

            self._check_connection()

            logger.info("Initialized Postgres-based TaxonomyDB (Native Vector Search).")

        except Exception as e:
            raise CustomException(e)

    def _check_connection(self):
        """Verify database connectivity."""
        try:
            with psycopg2.connect(self.conn_str) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
        except Exception as e:
            msg = f"Failed to connect to taxonomy database: {e}"
            logger.error(msg)
            raise CustomException(msg)

    def _get_connection(self):
        """Create a new database connection."""
        return psycopg2.connect(self.conn_str)

    # ----------------------------------------------------------------------
    # BASIC QUERIES
    # ----------------------------------------------------------------------
    def get_all_rows(self):
        """Fetch all taxonomy rows."""
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=DictCursor) as cur:
                    cur.execute("SELECT * FROM taxonomy;")
                    return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            logger.error("Failed to fetch taxonomy rows.")
            raise CustomException(e)

    def get_all_df(self):
        """Fetch all taxonomy rows as a pandas DataFrame."""
        import pandas as pd
        try:
            rows = self.get_all_rows()
            if not rows:
                return pd.DataFrame()
            return pd.DataFrame(rows)
        except Exception as e:
            logger.error("Failed to fetch taxonomy rows as DataFrame.")
            raise CustomException(e)

    def get_row_by_id(self, row_id):
        """Fetch a row by taxonomy ID."""
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=DictCursor) as cur:
                    cur.execute("SELECT * FROM taxonomy WHERE id = %s;", (row_id,))
                    row = cur.fetchone()
                    return dict(row) if row else None
        except Exception as e:
            logger.error(f"Failed to fetch taxonomy row id={row_id}.")
            raise CustomException(e)

    # ----------------------------------------------------------------------
    # VALIDATION
    # ----------------------------------------------------------------------
    def validate_row_id(self, row_id) -> bool:
        """Check if a taxonomy row exists."""
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1 FROM taxonomy WHERE id = %s;", (row_id,))
                    exists = cur.fetchone() is not None
                    if not exists:
                        logger.warning(f"Unknown taxonomy row_id '{row_id}'.")
                    return exists
        except Exception as e:
            raise CustomException(e)

    # ----------------------------------------------------------------------
    # VECTOR SEARCH (PGVECTOR)
    # ----------------------------------------------------------------------
    def search_vector(self, query_embedding, k=None):
        """
        Return nearest taxonomy rows using pgvector <=> operator (cosine distance).
        query_embedding: list or numpy array
        """
        try:
            if k is None:
                k = self.k

            # Ensure embedding is a list for psycopg2 adaptation
            if hasattr(query_embedding, "tolist"):
                query_embedding = query_embedding.tolist()

            # Flatten if it's a 2D list with one row (e.g., [[0.1, 0.2, ...]])
            if isinstance(query_embedding, list) and len(query_embedding) == 1 and isinstance(query_embedding[0], list):
                query_embedding = query_embedding[0]

            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=DictCursor) as cur:
                    # <=> is cosine distance operator in pgvector
                    # We return the distance as 'score' (lower is better)
                    sql = """
                        SELECT id, (embedding <=> %s::vector) as distance
                        FROM taxonomy
                        ORDER BY distance ASC
                        LIMIT %s;
                    """
                    cur.execute(sql, (query_embedding, k))
                    rows = cur.fetchall()

            results = [
                {"row_id": row["id"], "score": float(row["distance"])}
                for row in rows
            ]
            
            return results

        except Exception as e:
            logger.error("Failed pgvector search.")
            raise CustomException(e)
