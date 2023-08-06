import os
import hashlib
import uvicorn
import watchdog

from datetime import datetime
from watchdog.observers import Observer
from fastapi import FastAPI, HTTPException
from db import *
from notify import *

FILES_DIRECTORY = os.getenv("FILES_DIRECTORY", "./monito")

app = FastAPI()

def calculate_hash(file_path):
    with open(file_path, "rb") as file:
        sha256_hash = hashlib.sha256()
        while chunk := file.read(8192):
            sha256_hash.update(chunk)
        return sha256_hash.hexdigest()

def on_modified(event):
    if event.is_directory:
        return
    apobj.notify(
    body=f"""👀 Name: {event.src_path}
#️⃣ Hash: {calculate_hash(event.src_path)}
⏰ Date: {str(datetime.now())}""",
    title='⚠️ == File Modified == ⚠️'
    )

@app.get("/")
def read_root():
    return {"message": "Welcome to the file integrity monitoring system."}

@app.get("/files/{filename:path}")
def read_file(filename: str):
    path = os.path.join(FILES_DIRECTORY, filename)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="File not found.")
    hash_value = calculate_hash(path)
    file_info = get_file(filename, path)
    if not file_info:
        insert_file(filename, path, hash_value)

    if file_info[3] != hash_value:
        update_file(filename, path, hash_value)
        return {"status": "File Modified", "filename": filename, "path": path, "hash": hash_value}

    return {"status": "OK.","filename": filename, "path": path, "hash": hash_value}

if __name__ == "__main__":
    create_table()
    observer = Observer()
    event_handler = watchdog.events.FileSystemEventHandler()
    event_handler.on_modified = on_modified
    observer.schedule(event_handler, path=FILES_DIRECTORY, recursive=True)
    observer.start()

    try:
        uvicorn.run(app, host="0.0.0.0", port=8000)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
