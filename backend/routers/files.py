from fastapi import APIRouter, UploadFile, File, HTTPException
import shutil
import os
import uuid
from typing import List

router = APIRouter(prefix="/files", tags=["Files"])

STORAGE_PATH = os.getenv("STORAGE_PATH", "/tmp/storage")
os.makedirs(STORAGE_PATH, exist_ok=True)

@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    try:
        # Generate unique filename to avoid conflicts
        file_ext = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        file_location = os.path.join(STORAGE_PATH, unique_filename)
        
        with open(file_location, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        return {
            "filename": file.filename,
            "stored_filename": unique_filename,
            "path": file_location,
            "message": "File uploaded successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/")
def list_files():
    try:
        files = []
        if os.path.exists(STORAGE_PATH):
            for filename in os.listdir(STORAGE_PATH):
                file_path = os.path.join(STORAGE_PATH, filename)
                if os.path.isfile(file_path):
                    files.append({
                        "filename": filename,
                        "size": os.path.getsize(file_path)
                    })
        return files
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
