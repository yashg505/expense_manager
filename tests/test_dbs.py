import pytest
from unittest.mock import MagicMock, patch
import os
import numpy as np
from expense_manager.dbs.main_db import MainDB
from expense_manager.dbs.taxonomy_db import TaxonomyDB
from expense_manager.exception import CustomException

# Mock environment variables
@pytest.fixture
def mock_env():
    with patch.dict(os.environ, {"NEON_CONN_STR": "postgres://user:pass@host/db"}):
        yield

# --- TaxonomyDB Tests ---

def test_taxonomy_db_init(mock_env):
    with patch("expense_manager.dbs.taxonomy_db.psycopg2.connect") as mock_connect:
        db = TaxonomyDB()
        assert db is not None
        mock_connect.assert_called()

def test_taxonomy_db_init_fail_no_env():
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(CustomException):
            TaxonomyDB()

def test_taxonomy_db_get_row_by_id(mock_env):
    with patch("expense_manager.dbs.taxonomy_db.psycopg2.connect") as mock_connect:
        mock_conn = mock_connect.return_value
        mock_conn.__enter__.return_value = mock_conn
        mock_cur = mock_conn.cursor.return_value
        mock_cur.__enter__.return_value = mock_cur
        
        # Mock fetchone return
        mock_cur.fetchone.return_value = {"id": "123", "category": "Test"}
        
        db = TaxonomyDB()
        row = db.get_row_by_id("123")
        
        assert row == {"id": "123", "category": "Test"}
        mock_cur.execute.assert_called_with("SELECT * FROM taxonomy WHERE id = %s;", ("123",))

def test_taxonomy_db_search_vector(mock_env):
    with patch("expense_manager.dbs.taxonomy_db.psycopg2.connect") as mock_connect:
        mock_conn = mock_connect.return_value
        mock_conn.__enter__.return_value = mock_conn
        mock_cur = mock_conn.cursor.return_value
        mock_cur.__enter__.return_value = mock_cur
        
        # Mock fetchall return for vector search
        mock_cur.fetchall.return_value = [
            {"id": "A", "distance": 0.1},
            {"id": "B", "distance": 0.2}
        ]
        
        db = TaxonomyDB()
        results = db.search_vector([0.1, 0.2, 0.3], k=2)
        
        assert len(results) == 2
        assert results[0]["row_id"] == "A"
        assert results[0]["score"] == 0.1

# --- MainDB Tests ---

def test_main_db_init(mock_env):
    with patch("expense_manager.dbs.main_db.psycopg2.connect") as mock_connect:
        db = MainDB()
        assert db is not None

def test_main_db_insert_finalized_items(mock_env):
    with patch("expense_manager.dbs.main_db.psycopg2.connect") as mock_connect, \
         patch("expense_manager.dbs.main_db.embed_texts") as mock_embed:
        
        mock_conn = mock_connect.return_value
        mock_conn.__enter__.return_value = mock_conn
        mock_cur = mock_conn.cursor.return_value
        mock_cur.__enter__.return_value = mock_cur
        
        # Mock embeddings
        mock_embed.return_value = np.array([[0.1]*384, [0.2]*384])
        
        db = MainDB()
        
        items = [
            {"item": "Milk", "taxonomy_id": "DAIRY", "price": 1.0},
            {"item": "Bread", "taxonomy_id": "BAKERY", "price": 2.0}
        ]
        
        db.insert_finalized_items("file_123", "Tesco", "2025-01-01", "12:00", items)
        
        # Expected calls:
        # 2 calls in _init_db (CREATE EXTENSION, CREATE TABLE)
        # 2 calls in insert_finalized_items (INSERT x 2)
        assert mock_cur.execute.call_count == 4

def test_main_db_get_historical_exact_match(mock_env):
    with patch("expense_manager.dbs.main_db.psycopg2.connect") as mock_connect:
        mock_conn = mock_connect.return_value
        mock_conn.__enter__.return_value = mock_conn
        mock_cur = mock_conn.cursor.return_value
        mock_cur.__enter__.return_value = mock_cur
        
        # Mock fetchone return
        mock_cur.fetchone.return_value = ["GROCERY_ID"]
        
        db = MainDB()
        result = db.get_historical_exact_match("Tesco", "Milk")
        
        assert result == "GROCERY_ID"
        args, _ = mock_cur.execute.call_args
        assert "LOWER(item_text) = %s" in args[0]
        assert args[1] == ("tesco", "milk")

def test_main_db_get_historical_exact_match_type(mock_env):
    with patch("expense_manager.dbs.main_db.psycopg2.connect") as mock_connect:
        mock_conn = mock_connect.return_value
        mock_conn.__enter__.return_value = mock_conn
        mock_cur = mock_conn.cursor.return_value
        mock_cur.__enter__.return_value = mock_cur
        
        # Mock fetchone return
        mock_cur.fetchone.return_value = ["DAIRY_ID"]
        
        db = MainDB()
        result = db.get_historical_exact_match_type("Tesco", "Dairy Product")
        
        assert result == "DAIRY_ID"
        args, _ = mock_cur.execute.call_args
        # Verifying it now matches against item_type column
        assert "LOWER(item_type) = %s" in args[0]
        assert args[1] == ("tesco", "dairy product")

def test_main_db_get_items_by_file_id(mock_env):
    with patch("expense_manager.dbs.main_db.psycopg2.connect") as mock_connect:
        mock_conn = mock_connect.return_value
        mock_conn.__enter__.return_value = mock_conn
        mock_cur = mock_conn.cursor.return_value
        mock_cur.__enter__.return_value = mock_cur
        
        mock_cur.fetchall.return_value = [
            {"id": 1, "file_id": "F1", "item_text": "Item 1"},
            {"id": 2, "file_id": "F1", "item_text": "Item 2"}
        ]
        
        db = MainDB()
        items = db.get_items_by_file_id("F1")
        
        assert len(items) == 2
        assert items[0]["item_text"] == "Item 1"
        mock_cur.execute.assert_called_with("SELECT * FROM processed_items WHERE file_id = %s", ("F1",))

def test_main_db_search_history(mock_env):
    with patch("expense_manager.dbs.main_db.psycopg2.connect") as mock_connect:
        mock_conn = mock_connect.return_value
        mock_conn.__enter__.return_value = mock_conn
        mock_cur = mock_conn.cursor.return_value
        mock_cur.__enter__.return_value = mock_cur
        
        # Mock vector search result
        mock_cur.fetchone.return_value = {"taxonomy_id": "HIST_ID", "item_text": "Similar Item", "distance": 0.05}
        
        db = MainDB()
        res = db.search_history([0.1]*384, threshold=0.1)
        
        assert res == "HIST_ID"
        assert mock_cur.execute.called