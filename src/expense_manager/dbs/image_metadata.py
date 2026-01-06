import os
import sqlite3
import json
import sys
from typing import Optional, Dict, Any

from expense_manager.logger import get_logger
from expense_manager.exception import CustomException
from expense_manager.utils.load_config import load_config_file

logger = get_logger(__name__)

class ImageMetadataDB:
    """
    Manages image metadata and persistent state tracking.
    Stores the full JSON representation of ReceiptImage for debugging and persistence.
    """

    def __init__(self):
        try:
            config = load_config_file()
            self.path = config["paths"]["image_metadata_db"]
            self._init_db()
            logger.info(f"Initialized ImageMetadataDB at {self.path}")
        except Exception as e:
            raise CustomException(e, sys)

    def _init_db(self):
        """Initializes the database schema and performs simple migrations."""
        try:
            with sqlite3.connect(self.path) as conn:
                # 1. Create table if not exists
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS image_metadata (
                        file_id TEXT PRIMARY KEY,
                        file_name TEXT,
                        fingerprint TEXT UNIQUE,
                        image_path TEXT,
                        json_state TEXT,
                        status TEXT DEFAULT 'pending',
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # 2. Migration: Add 'status' column if it's missing (for existing databases)
                cursor = conn.execute("PRAGMA table_info(image_metadata)")
                columns = [row[1] for row in cursor.fetchall()]
                if 'status' not in columns:
                    logger.info("Migrating database: Adding 'status' column to image_metadata")
                    conn.execute("ALTER TABLE image_metadata ADD COLUMN status TEXT DEFAULT 'pending'")

            logger.debug("Image metadata schema verified and migrated.")
        except Exception as e:
            logger.error("Failed to initialize or migrate image metadata schema.")
            raise CustomException(e, sys)

    def upsert_image(self, file_id: str, file_name: str, fingerprint: str, image_path: str, state_dict: Dict[str, Any]):
        """
        Inserts or updates image metadata along with its current full state.
        If an image with the same fingerprint is already 'uploaded', it prevents modification.
        """
        try:
            json_state = json.dumps(state_dict)
            
            with sqlite3.connect(self.path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Check for existing image by fingerprint
                cursor.execute("SELECT file_id, status FROM image_metadata WHERE fingerprint = ?", (fingerprint,))
                existing = cursor.fetchone()
                
                if existing:
                    if existing['status'] == 'uploaded':
                        logger.warning(f"Attempted to modify already uploaded image: {fingerprint}")
                        return # Skip update for finalized data
                    
                    # If file_id changed but fingerprint is same (re-upload), 
                    # we should remove the old file_id entry to avoid unique constraint issues
                    if existing['file_id'] != file_id:
                        conn.execute("DELETE FROM image_metadata WHERE file_id = ?", (existing['file_id'],))

                # Now safe to perform the upsert
                conn.execute('''
                    INSERT INTO image_metadata (file_id, file_name, fingerprint, image_path, json_state, updated_at)
                    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(file_id) DO UPDATE SET
                        json_state = excluded.json_state,
                        updated_at = CURRENT_TIMESTAMP
                ''', (file_id, file_name, fingerprint, image_path, json_state))
            
            logger.debug(f"Metadata and state persisted for file_id: {file_id}")
        except Exception as e:
            logger.error(f"Failed to upsert metadata for {file_id}: {e}")
            raise CustomException(e, sys)

    def update_status(self, file_id: str, status: str):
        """Updates the status of a receipt (e.g., to 'uploaded')."""
        try:
            with sqlite3.connect(self.path) as conn:
                conn.execute('''
                    UPDATE image_metadata 
                    SET status = ?, updated_at = CURRENT_TIMESTAMP 
                    WHERE file_id = ?
                ''', (status, file_id))
            logger.info(f"Status for {file_id} updated to '{status}'")
        except Exception as e:
            logger.error(f"Failed to update status for {file_id}: {e}")
            raise CustomException(e, sys)

    def get_by_fingerprint(self, fingerprint: str) -> Optional[dict]:
        """Check if an image with this fingerprint already exists."""
        try:
            with sqlite3.connect(self.path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM image_metadata WHERE fingerprint = ?", (fingerprint,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Error fetching by fingerprint: {e}")
            raise CustomException(e, sys)

    def get_all_states(self) -> Dict[str, Dict[str, Any]]:
        """Retrieves all saved states, keyed by file_id."""
        try:
            states = {}
            with sqlite3.connect(self.path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("SELECT file_id, json_state FROM image_metadata")
                for row in cursor.fetchall():
                    states[row['file_id']] = json.loads(row['json_state'])
            return states
        except Exception as e:
            logger.error(f"Error fetching all states: {e}")
            raise CustomException(e, sys)

    def get_images_by_status(self, statuses: list[str]) -> list[dict]:
        """Returns file_id and image_path for rows matching the given status list."""
        if not statuses:
            return []

        try:
            placeholders = ",".join("?" * len(statuses))
            query = f"""
                SELECT file_id, image_path, status
                FROM image_metadata
                WHERE status IN ({placeholders})
            """
            with sqlite3.connect(self.path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(query, tuple(statuses))
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error fetching images by status: {e}")
            raise CustomException(e, sys)

    def cleanup_images_by_status(self, statuses: list[str]) -> Dict[str, int]:
        """Deletes image files and DB rows for matching statuses."""
        rows = self.get_images_by_status(statuses)
        return self._delete_images_and_rows(rows, reason=f"status cleanup: {statuses}")

    def _delete_images_and_rows(self, rows: list[dict], reason: str) -> Dict[str, int]:
        deleted_files = 0
        missing_files = 0
        file_ids = []

        for row in rows:
            file_id = row.get("file_id")
            image_path = row.get("image_path")
            if file_id:
                file_ids.append(file_id)
            if image_path and os.path.exists(image_path):
                try:
                    os.remove(image_path)
                    deleted_files += 1
                except OSError as exc:
                    logger.error(f"Failed to delete image {image_path}: {exc}")
            else:
                missing_files += 1

        if file_ids:
            placeholders = ",".join("?" * len(file_ids))
            query = f"DELETE FROM image_metadata WHERE file_id IN ({placeholders})"
            with sqlite3.connect(self.path) as conn:
                conn.execute(query, tuple(file_ids))

        logger.info(
            "Cleanup %s: removed %s files, %s missing, %s rows",
            reason,
            deleted_files,
            missing_files,
            len(file_ids),
        )
        return {
            "deleted_files": deleted_files,
            "missing_files": missing_files,
            "deleted_rows": len(file_ids),
        }
