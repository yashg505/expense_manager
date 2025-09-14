import sqlite3
from typing import Optional, List, Tuple

class mainDataDB:
    '''
    <docstring>
    '''
    def __init__(self, path=r'data/main_data.db'):
        self.path = path
        self._init_db()
    
    def __enter__(self):
        self.conn = sqlite3.connect(self.path)
        return self.conn
    
    def __exit__(self, exc_type, exc_value, traceback):
        if hasattr(self, 'conn'):
            self.conn.commit()
            self.conn.close()
    
    def _init_db(self):
        with self as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS main_data (
                    id INTEGER PRIMARY_KEY,
                    image_id INTEGER,
                    item_text TEXT,
                    taxonomy TEXT,
                    qty INTEGER,
                    price REAL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP(),
                    FOREIGN KEY (image_id) REFERENCE image_metadata(image_id)         
                )
            ''')
        
    def insert_item(self, image_id:int, item_text:str, taxonomy:Optional[str], qty:int=1,
                    price:Optional[float]=None) -> int:
        with self as conn:
            c = conn.cursor()
            c.execute('''
                INSERT INTO main_data (image_id, item_text, taxonomy, qty, price)
                VALUES (?,?,?,?,?)
            ''', (image_id, item_text, taxonomy, qty, price))
            return c.lastrowid
    
    def get_items_for_image(self, image_id:str)-> List[Tuple]:
        with self as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM main_data WHERE image_id=?", (image_id,))
            return c.fetchall
