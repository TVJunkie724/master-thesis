import os

def file_exists(file_path: str) -> bool:
    """Check if a file exists at the given path."""
    return os.path.isfile(file_path)