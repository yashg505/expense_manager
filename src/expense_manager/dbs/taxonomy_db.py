"""
taxonomy_db.py

Domain layer for managing taxonomy data stored in taxonomy.db.

Responsibilities:
    - Provide read access to taxonomy table
    - Validate category IDs
    - Build FAISS index from taxonomy names
    - Load FAISS index + metadata
    - Perform vector search for nearest taxonomy categories

This module intentionally contains:
    - No Google Sheet syncing logic
    - No schema creation logic
    - No OpenAI or external API calls

All syncing, schema creation, and updates are handled by the taxonomy_sync module.
"""

import sqlite3
import json
from pathlib import Path

from expense_manager.utils.load_config import load_config_file
from expense_manager.utils.embed_texts import embed_texts
from expense_manager.dbs.faiss_store import FaissStore

from expense_manager.logger import get_logger
from expense_manager.exception import CustomException

logger = get_logger(__name__)



class TaxonomyDB:
    config = load_config_file()

    def __init__(self):
        try:
            paths = self.config["paths"]
            self.db_path = paths["taxonomy_db"]
            self.index_path = paths["taxonomy_index"]
            self.meta_path = paths["taxonomy_meta"]
            self.k = self.config["faiss"]["taxonomy_k"]

            self._ensure_db_exists()

            self.faiss = None
            self.row_ids = None  # FAISS index_pos -> taxonomy row_id

            logger.info("Initialized row-based TaxonomyDB.")

        except Exception as e:
            raise CustomException(e)

    def _get_connection(self):
        """Helper to create a thread-safe connection with Row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # ----------------------------------------------------------------------
    # DB EXISTS CHECK
    # ----------------------------------------------------------------------
    def _ensure_db_exists(self):
        """
        Ensure taxonomy.db file exists.
        Schema & data are added by taxonomy_sync, not this class.
        """
        if Path(self.db_path).exists():
            return

        # Create empty DB file
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        sqlite3.connect(self.db_path).close()

        msg = (
            "taxonomy.db created but empty. "
        )
        logger.error(msg)
        raise CustomException(msg)

    # ----------------------------------------------------------------------
    # BASIC QUERIES
    # ----------------------------------------------------------------------
    def get_all_rows(self):
        """Fetch all taxonomy rows."""
        try:
            with self._get_connection() as conn:
                cur = conn.execute("SELECT * FROM taxonomy;")
                return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            logger.error("Failed to fetch taxonomy rows.")
            raise CustomException(e)

    def get_row_by_id(self, row_id):
        """Fetch a row by taxonomy ID."""
        try:
            with self._get_connection() as conn:
                cur = conn.execute("SELECT * FROM taxonomy WHERE id = ?;", (row_id,))
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
                cur = conn.execute("SELECT 1 FROM taxonomy WHERE id = ?;", (row_id,))
                exists = cur.fetchone() is not None
                if not exists:
                    logger.warning(f"Unknown taxonomy row_id '{row_id}'.")
                return exists
        except Exception as e:
            raise CustomException(e)

    # ----------------------------------------------------------------------
    # EMBEDDING INPUT PREP
    # ----------------------------------------------------------------------
    def _fetch_full_paths(self):
        """
        Returns:
            row_ids     -> ["food_veg_fruits", ...]
            full_paths  -> ["Food Items > Fruits and Vegetables > Fruits", ...]
        """
        try:
            with self._get_connection() as conn:
                cur = conn.execute("SELECT id, full_path FROM taxonomy;")
                rows = cur.fetchall()

                if not rows:
                    msg = "taxonomy table is empty — cannot embed."
                    logger.error(msg)
                    raise CustomException(msg)

                ids = [row["id"] for row in rows]
                full_paths = [row["full_path"] for row in rows]
                return ids, full_paths

        except Exception as e:
            logger.error("Failed fetching full_path for embeddings.")
            raise CustomException(e)

    # ----------------------------------------------------------------------
    # FAISS BUILD
    # ----------------------------------------------------------------------
    def build_vector_index(self) -> int:
        """Build FAISS index from full_path embeddings."""
        try:
            row_ids, full_paths = self._fetch_full_paths()

            logger.info(f"Building taxonomy FAISS index with {len(row_ids)} rows.")

            vectors = embed_texts(full_paths)

            store = FaissStore(self.index_path)
            store.build_new_index(vectors)

            # Save FAISS index mapping
            with open(self.meta_path, "w") as f:
                json.dump({"ids": row_ids}, f)

            logger.info("taxonomy.index + taxonomy.meta.json saved.")

            return len(row_ids)

        except Exception as e:
            logger.error("Failed building taxonomy FAISS index.")
            raise CustomException(e)

    # ----------------------------------------------------------------------
    # FAISS LOAD
    # ----------------------------------------------------------------------
    def load_faiss(self):
        """Load FAISS index + metadata."""
        try:
            if not Path(self.index_path).exists():
                raise CustomException("taxonomy.index missing. Run build_vector_index().")

            if not Path(self.meta_path).exists():
                raise CustomException("taxonomy.meta.json missing.")

            with open(self.meta_path) as f:
                meta = json.load(f)

            self.row_ids = meta["ids"]

            self.faiss = FaissStore(self.index_path)
            self.faiss.load()

            logger.info("taxonomy FAISS index loaded.")

        except Exception as e:
            logger.error("Failed loading taxonomy FAISS index.")
            raise CustomException(e)

    # ----------------------------------------------------------------------
    # VECTOR SEARCH
    # ----------------------------------------------------------------------
    def search_vector(self, query_embedding, k=None):
        """Return nearest taxonomy rows to a given embedding."""
        try:
            if self.faiss is None:
                logger.info("FAISS not loaded — loading now.")
                self.load_faiss()

            if k is None:
                k = self.k

            idxs, scores = self.faiss.search(query_embedding, k=k)

            return [
                {"row_id": self.row_ids[i], "score": float(score)}
                for i, score in zip(idxs, scores)
            ]

        except Exception as e:
            logger.error("Failed FAISS search.")
            raise CustomException(e)
