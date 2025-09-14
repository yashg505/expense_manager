import sqlite3
from typing import Optional, Tuple

class CorrectionsDB:
    '''
    <<docstring>>
    '''

    def __init__(self, path=r'data/corrections.db'):
        self.path = path
        self._init_db()
    
    def __enter__(self):
        self.conn = sqlite3.connect(self.path)
        return self.conn

    def __exit__(self, exc_type, exv_value, traceback):
        if hasattr(self, 'conn'):
            self.conn.commit()
            self.conn.close()
    
    def _init_db(self):
        with self as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS corrections(
                    id INTEGER PRIMARY KEY,
                    item_text TEXT,
                    corrected_taxonomy TEXT,
                    user_id TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
        ''')
    
    def insert_correction(self, item_text:str, corrected_taxonomy:str, user_id:str='system')-> int:
        with self as conn:
            c = conn.cursor()
            c.execute('SELECT corrected_taxonomy FROM corrections WHERE item_text=?', (item_text,))
            row = c.fetchone()
            return row[0] if row else None
    
    