import os

STORAGE_PATH = os.getenv("STORAGE_PATH", "/tmp/storage")

os.makedirs(STORAGE_PATH, exist_ok=True)

def get_file_path(filename: str) -> str:
    return os.path.join(STORAGE_PATH, filename)

def list_files() -> list:
    if not os.path.exists(STORAGE_PATH):
        return []
    return [
        f for f in os.listdir(STORAGE_PATH)
        if os.path.isfile(os.path.join(STORAGE_PATH, f))
    ]

def file_exists(filename: str) -> bool:
    return os.path.isfile(get_file_path(filename))
