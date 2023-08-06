import sqlite3, os
from datetime import datetime

DATABASE_NAME = os.getenv("DATABASE_NAME", "file_integrity.db")

def create_table():
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS files
                      (id INTEGER PRIMARY KEY AUTOINCREMENT,
                       filename TEXT,
                       path TEXT,
                       hash TEXT,
                       old_hash TEXT DEFAULT NULL,
                       last_modified TIMESTAMP)''')
    conn.commit()
    conn.close()

def insert_file(filename, path, hash_value):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO files (filename, path, hash, last_modified) VALUES (?, ?, ?, ?)",
                   (filename, path, hash_value, datetime.now()))
    conn.commit()
    conn.close()

def update_file(filename, path, hash_value):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    old_hash = cursor.execute("SELECT hash FROM files WHERE filename = ? AND path = ?", (filename, path)).fetchone()[0]
    cursor.execute("UPDATE files SET hash = ?, last_modified = ?, old_hash = ? WHERE filename = ? AND path = ?",
                   (hash_value, datetime.now(), old_hash, filename, path))
    conn.commit()
    conn.close()

def get_file(filename, path):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM files WHERE filename = ? AND path = ?", (filename, path))
    result = cursor.fetchone()
    conn.close()
    return result

def get_files():
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM files")
    result = cursor.fetchall()
    conn.close()
    return result