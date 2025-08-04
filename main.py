import os
import hashlib
import uvicorn
import watchdog
import werkzeug

from datetime import datetime
from watchdog.observers import Observer
from fastapi import FastAPI, HTTPException, Request
from fastapi.templating import Jinja2Templates
from db import *
from notify import apobj

# Support multiple directories - can be comma-separated or use a list
FILES_DIRECTORIES = os.getenv("FILES_DIRECTORIES", "./test_dir")

app = FastAPI()
templates = Jinja2Templates(directory="templates")

def get_directories_list():
    """Parse the directories from environment variable or return default"""
    if isinstance(FILES_DIRECTORIES, str):
        # Split by comma and strip whitespace
        dirs = [d.strip() for d in FILES_DIRECTORIES.split(',') if d.strip()]
    else:
        dirs = FILES_DIRECTORIES
    
    # Validate that all directories exist
    valid_dirs = []
    for directory in dirs:
        if os.path.exists(directory) and os.path.isdir(directory):
            valid_dirs.append(os.path.abspath(directory))
        else:
            print(f"Warning: Directory '{directory}' does not exist or is not a directory")
    
    return valid_dirs

def get_relative_path(full_path):
    """Convert full path to relative path for display"""
    directories = get_directories_list()
    
    for directory in directories:
        if full_path.startswith(directory):
            rel_path = os.path.relpath(full_path, directory)
            # Get the directory name (last part of the path)
            dir_name = os.path.basename(directory)
            return f"{dir_name}/{rel_path}" if rel_path != "." else dir_name
    
    # Fallback to just the filename if no match
    return os.path.basename(full_path)

def calculate_hash(file_path):
    try:
        with open(file_path, "rb") as file:
            sha256_hash = hashlib.sha256()
            while chunk := file.read(8192):
                sha256_hash.update(chunk)
            return sha256_hash.hexdigest()
    except Exception as e:
        print(f"Error calculating hash for {file_path}: {e}")
        return None

def on_modified(event):
    """Handle file modification events"""
    if event.is_directory:
        return

    try:
        hash_value = calculate_hash(event.src_path)
        if not hash_value:
            return
            
        path = event.src_path
        filename = os.path.basename(path)
        file_info = get_file(filename, path)
        
        if not file_info:
            insert_file(filename, path, hash_value)
            print(f"Added new file to monitoring: {filename}")
        else:
            if file_info.hash != hash_value:
                update_file(filename, path, hash_value)
                print(f"Updated hash for modified file: {filename}")
                
                apobj.notify(
                    body=f"👀 Name: {get_relative_path(path)}\n🔄 Old Hash: {file_info.hash[:8]}...{file_info.hash[-8:]}\n#️⃣ New Hash: {hash_value[:8]}...{hash_value[-8:]}\n⏰ Date: {str(datetime.now())}",
                    title='⚠️ == File Modified == ⚠️'
                )
    except Exception as e:
        print(f"Error in on_modified for {event.src_path}: {e}")

def on_created(event):
    """Handle file creation events"""
    if event.is_directory:
        return

    try:
        hash_value = calculate_hash(event.src_path)
        if not hash_value:
            return
            
        path = event.src_path
        filename = os.path.basename(path)
        
        # Add to database
        insert_file(filename, path, hash_value)
        print(f"🆕 New file detected: {get_relative_path(path)}")
        
        apobj.notify(
            body=f"📁 Name: {get_relative_path(path)}\n#️⃣ Hash: {hash_value[:8]}...{hash_value[-8:]}\n📏 Size: {os.path.getsize(path)} bytes\n⏰ Date: {str(datetime.now())}",
            title='🆕 == New File Created == 🆕'
        )
    except Exception as e:
        print(f"Error in on_created for {event.src_path}: {e}")

def on_deleted(event):
    """Handle file deletion events"""
    if event.is_directory:
        return

    try:
        path = event.src_path
        filename = os.path.basename(path)
        
        # Check if file was in our database
        file_info = get_file(filename, path)
        if file_info:
            # Mark as deleted or remove from database
            delete_file(path)  # We'll need to add this function to db.py
            print(f"🗑️ File deleted: {get_relative_path(path)}")
            
            apobj.notify(
                body=f"📁 Name: {get_relative_path(path)}\n🔄 Last Hash: {file_info.hash[:8]}...{file_info.hash[-8:]}\n⏰ Date: {str(datetime.now())}",
                title='🗑️ == File Deleted == 🗑️'
            )
    except Exception as e:
        print(f"Error in on_deleted for {event.src_path}: {e}")

def on_moved(event):
    """Handle file move/rename events"""
    if event.is_directory:
        return

    try:
        old_path = event.src_path
        new_path = event.dest_path
        old_filename = os.path.basename(old_path)
        new_filename = os.path.basename(new_path)
        
        # Check if file was in our database
        file_info = get_file(old_filename, old_path)
        if file_info:
            # Update database with new path
            delete_file(old_path)
            
            # Calculate hash for moved file
            hash_value = calculate_hash(new_path)
            if hash_value:
                insert_file(new_filename, new_path, hash_value)
                print(f"📦 File moved: {get_relative_path(old_path)} → {get_relative_path(new_path)}")
                
                apobj.notify(
                    body=f"📁 From: {get_relative_path(old_path)}\n📁 To: {get_relative_path(new_path)}\n#️⃣ Hash: {hash_value[:8]}...{hash_value[-8:]}\n⏰ Date: {str(datetime.now())}",
                    title='📦 == File Moved/Renamed == 📦'
                )
    except Exception as e:
        print(f"Error in on_moved for {event.src_path}: {e}")

def first_run():
    """Scan all configured directories on startup"""
    directories = get_directories_list()
    print(f"Scanning directories: {directories}")
    
    for directory in directories:
        print(f"Processing directory: {directory}")
        for root, dirs, files in os.walk(directory):
            for file in files:
                path = os.path.join(root, file)
                try:
                    hash_value = calculate_hash(path)
                    if not hash_value:
                        continue
                        
                    file_info = get_file(file, path)
                    
                    if not file_info:
                        # New file - add to database
                        insert_file(file, path, hash_value)
                        print(f"Added new file: {file}")
                    else:
                        # Existing file - check if hash changed
                        if file_info.hash != hash_value:
                            update_file(file, path, hash_value)
                            print(f"Hash changed for: {file}")
                            
                            # Send notification for changed file
                            apobj.notify(
                                body=f"👀 Name: {path}\n#️⃣ New Hash: {hash_value}\n🔄 Old Hash: {file_info.hash}\n⏰ Date: {str(datetime.now())}",
                                title='⚠️ == File Changed During Startup == ⚠️'
                            )
                        else:
                            print(f"No change detected for: {file}")
                            
                except Exception as e:
                    print(f"Error processing file {path}: {e}")

def find_file_in_directories(filename):
    """Find a file across all monitored directories"""
    directories = get_directories_list()
    secure_filename = werkzeug.utils.secure_filename(filename)
    
    for directory in directories:
        potential_path = os.path.join(directory, secure_filename)
        if os.path.isfile(potential_path):
            return potential_path
    
    # Also check subdirectories
    for directory in directories:
        for root, dirs, files in os.walk(directory):
            if secure_filename in files:
                return os.path.join(root, secure_filename)
    
    return None

@app.get("/")
def json_data():
    files = get_files()
    files_final = []
    for i in files:
        files_final.append({
            "filename": i.filename, 
            "path": i.path,
            "relative_path": get_relative_path(i.path),
            "hash": i.hash, 
            "old_hash": i.old_hash,
            "last_modified": i.last_modified
        })
    return {"files": files_final, "monitored_directories": get_directories_list()}

@app.get("/dash")
def dashboard(request: Request):
    files = get_files()
    files_final = []
    for i in files:
        files_final.append({
            "filename": i.filename, 
            "path": i.path,
            "relative_path": get_relative_path(i.path),
            "hash": i.hash, 
            "old_hash": i.old_hash,
            "last_modified": i.last_modified
        })
    return templates.TemplateResponse("dashboard.html", {
        "request": request, 
        "files_data": files_final,
        "monitored_directories": get_directories_list()
    })

@app.get("/directories")
def get_monitored_directories():
    """Return list of currently monitored directories"""
    return {"directories": get_directories_list()}

@app.get("/stats")
def get_stats():
    """Return statistics about monitored files"""
    files = get_files()
    total_files = len(files)
    modified_files = len([f for f in files if f.old_hash and f.hash != f.old_hash])
    new_files = len([f for f in files if not f.old_hash])
    
    return {
        "total_files": total_files,
        "modified_files": modified_files,
        "new_files": new_files,
        "unchanged_files": total_files - modified_files - new_files,
        "monitored_directories": len(get_directories_list())
    }
    
@app.get("/files/{filename:path}")
def read_file(filename: str):
    # Find the file across all monitored directories
    file_path = find_file_in_directories(filename)
    
    if not file_path:
        raise HTTPException(status_code=404, detail="File not found in any monitored directory.")
    
    secure_filename = werkzeug.utils.secure_filename(os.path.basename(filename))
    hash_value = calculate_hash(file_path)
    
    if not hash_value:
        raise HTTPException(status_code=500, detail="Could not calculate file hash.")
    
    file_info = get_file(secure_filename, file_path)
    
    if not file_info:
        insert_file(secure_filename, file_path, hash_value)
        return {
            "status": "File Added to Monitoring", 
            "filename": secure_filename, 
            "path": file_path,
            "relative_path": get_relative_path(file_path),
            "hash": hash_value, 
            "old_hash": None, 
            "last_modified": None
        }

    if file_info.hash != hash_value:
        update_file(secure_filename, file_path, hash_value)
        return {
            "status": "File Modified", 
            "filename": secure_filename, 
            "path": file_path,
            "relative_path": get_relative_path(file_path),
            "hash": hash_value, 
            "old_hash": file_info.old_hash, 
            "last_modified": file_info.last_modified
        }

    return {
        "status": "OK.",
        "filename": secure_filename, 
        "path": file_path,
        "relative_path": get_relative_path(file_path),
        "hash": hash_value, 
        "old_hash": file_info.old_hash, 
        "last_modified": file_info.last_modified
    }

@app.get("/files")
def read_files():
    files = get_files()
    files_final = []
    for i in files:
        files_final.append({
            "filename": i.filename, 
            "path": i.path,
            "relative_path": get_relative_path(i.path),
            "hash": i.hash, 
            "old_hash": i.old_hash,
            "last_modified": i.last_modified
        })
    return {"files": files_final}

if __name__ == "__main__":
    create_table()
    
    # Get list of directories to monitor
    directories = get_directories_list()
    
    if not directories:
        print("No valid directories found to monitor. Please check FILES_DIRECTORIES environment variable.")
        exit(1)
    
    print(f"Starting File Integrity Guardian for directories: {directories}")
    
    # Create observer and set up monitoring for all directories
    observer = Observer()
    event_handler = watchdog.events.FileSystemEventHandler()
    
    # Set up all event handlers
    event_handler.on_modified = on_modified
    event_handler.on_created = on_created
    event_handler.on_deleted = on_deleted
    event_handler.on_moved = on_moved
    
    # Schedule monitoring for each directory
    for directory in directories:
        observer.schedule(event_handler, path=directory, recursive=True)
        print(f"Monitoring: {directory}")
    
    observer.start()

    try:
        first_run()
        uvicorn.run(app, host="0.0.0.0", port=8000)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()