import sqlite3
from typing import Optional

class ImageMetadataDB:
    '''
    '''

    def __init__(self, path='data/image_metadata.db'):
        self.path = path
        self._init_db()
    
    def __enter__(self):
        self.conn = sqlite3.connect(self.path)
        return self.conn

    def __exit__(self, exc_type, exc_value, traceback):
        if hasattr(self, "conn"):
            self.conn.commit()
            self.conn.close()
    
    def _init_db(self):
        with self as conn:
            conn.execute(
                '''
                CREATE TABLE IF NOT EXISTS image_metadata (
                    image_id INTEGER PRIMARY KEY,
                    file_name TEXT,
                    fingerpint TEXT UNIQUE,
                    image_path TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
    
    def insert_image(self, file_name:str, fingerprint:str, image_path:str)->int:
        '''insert new image metadata and return image_id'''
        with self as conn:
            c = conn.cursor()
            c.execute('''
                INSERT INTO image_metadata (file_name, fingerprint, image_path)
                    VALUE(?, ?, ?)
            ''', (file_name, fingerprint, image_path))

        return c.lastrowid

    def get_by_fingerprint(self, fingerprint:str)-> Optional[tuple]:
        '''return row if fingerprint exists for de-duplication'''
        with self as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM image_metadata WHERE fingerprint=?", (fingerprint,))
            return c.fetchone()

