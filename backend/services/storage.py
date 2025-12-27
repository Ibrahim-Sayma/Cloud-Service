import os
from typing import List

STORAGE_PATH = os.getenv("STORAGE_PATH", "/tmp/storage")

def ensure_storage_dir() -> str:
    """
    Ensure storage directory exists and return its path.
    Safe to call multiple times.
    """
    os.makedirs(STORAGE_PATH, exist_ok=True)
    return STORAGE_PATH

def get_file_path(filename: str) -> str:
    ensure_storage_dir()
    return os.path.join(STORAGE_PATH, filename)

def list_files() -> List[str]:
    ensure_storage_dir()
    try:
        return [
            f for f in os.listdir(STORAGE_PATH)
            if os.path.isfile(os.path.join(STORAGE_PATH, f))
        ]
    except FileNotFoundError:
        return []

def file_exists(filename: str) -> bool:
    return os.path.isfile(get_file_path(filename))
