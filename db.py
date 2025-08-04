import sqlite3
import os
from datetime import datetime
from typing import Optional

# Database path - matches your original logic
DATABASE_URL = os.getenv("DATABASE_URL", "file_integrity.db")
# Remove sqlite:/// prefix if present to get just the filename
if DATABASE_URL.startswith("sqlite:///"):
    DATABASE_URL = DATABASE_URL[10:]

class File:
    """File class that mimics SQLAlchemy model behavior"""
    def __init__(self, id=None, filename=None, path=None, hash=None, old_hash=None, last_modified=None):
        self.id = id
        self.filename = filename
        self.path = path
        self.hash = hash
        self.old_hash = old_hash
        self.last_modified = last_modified

def get_connection():
    """Get database connection"""
    return sqlite3.connect(DATABASE_URL)

def create_table():
    """Create the files table if it doesn't exist"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT,
            path TEXT,
            hash TEXT,
            old_hash TEXT DEFAULT NULL,
            last_modified TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

def insert_file(filename, path, hash_value):
    """Insert a new file record"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO files (filename, path, hash, last_modified)
        VALUES (?, ?, ?, ?)
    ''', (filename, path, hash_value, datetime.now()))
    
    conn.commit()
    conn.close()

def update_file(filename, path, hash_value):
    """Update file hash and set old_hash"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # First get the current hash to store as old_hash
    cursor.execute('SELECT hash FROM files WHERE filename = ? AND path = ?', (filename, path))
    result = cursor.fetchone()
    
    if result:
        old_hash = result[0]
        cursor.execute('''
            UPDATE files 
            SET hash = ?, old_hash = ?, last_modified = ?
            WHERE filename = ? AND path = ?
        ''', (hash_value, old_hash, datetime.now(), filename, path))
        
        conn.commit()
    
    conn.close()

def get_file(filename, path):
    """Get a specific file record - returns File object or None"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, filename, path, hash, old_hash, last_modified
        FROM files 
        WHERE filename = ? AND path = ?
    ''', (filename, path))
    
    result = cursor.fetchone()
    conn.close()
    
    if result:
        # Convert timestamp string back to datetime if needed
        last_modified = result[5]
        if isinstance(last_modified, str):
            try:
                last_modified = datetime.fromisoformat(last_modified.replace('Z', '+00:00'))
            except:
                last_modified = datetime.now()
        
        return File(
            id=result[0],
            filename=result[1],
            path=result[2],
            hash=result[3],
            old_hash=result[4],
            last_modified=last_modified
        )
    return None

def delete_file(path):
    """Delete a file record from database"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM files WHERE path = ?', (path,))
    conn.commit()
    conn.close()
    print(f"Removed file record: {path}")

def get_files():
    """Get all file records - returns list of File objects"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, filename, path, hash, old_hash, last_modified
        FROM files
        ORDER BY last_modified DESC
    ''')
    
    results = cursor.fetchall()
    conn.close()
    
    files = []
    for row in results:
        # Convert timestamp string back to datetime if needed
        last_modified = row[5]
        if isinstance(last_modified, str):
            try:
                last_modified = datetime.fromisoformat(last_modified.replace('Z', '+00:00'))
            except:
                last_modified = datetime.now()
        
        files.append(File(
            id=row[0],
            filename=row[1],
            path=row[2],
            hash=row[3],
            old_hash=row[4],
            last_modified=last_modified
        ))
    
    return files