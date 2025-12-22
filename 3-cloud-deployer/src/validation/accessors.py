"""
File Accessor implementations for different sources.

Provides concrete implementations of the FileAccessor protocol
for ZIP files and directories.
"""

import os
import zipfile
from pathlib import Path
from typing import List

import constants as CONSTANTS


class ZipFileAccessor:
    """FileAccessor implementation for ZIP files."""
    
    def __init__(self, zf: zipfile.ZipFile):
        self._zf = zf
        self._files = zf.namelist()
        self._project_root = self._find_project_root()
    
    def _find_project_root(self) -> str:
        """Find project root by locating config.json."""
        for f in self._files:
            if f.endswith(CONSTANTS.CONFIG_FILE):
                return f.replace(CONSTANTS.CONFIG_FILE, "")
        return ""
    
    def list_files(self) -> List[str]:
        return self._files
    
    def file_exists(self, path: str) -> bool:
        return path in self._files
    
    def read_text(self, path: str) -> str:
        with self._zf.open(path) as f:
            return f.read().decode('utf-8')
    
    def get_project_root(self) -> str:
        return self._project_root


class DirectoryAccessor:
    """FileAccessor implementation for directories."""
    
    def __init__(self, project_path: Path):
        self._path = Path(project_path)
        self._files = self._scan_files()
    
    def _scan_files(self) -> List[str]:
        """Scan all files in the directory."""
        files = []
        for root, dirs, filenames in os.walk(self._path):
            # Skip hidden directories and __pycache__
            dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__']
            for filename in filenames:
                full_path = os.path.join(root, filename)
                rel_path = os.path.relpath(full_path, self._path)
                # Normalize to forward slashes for consistency
                files.append(rel_path.replace('\\', '/'))
        return files
    
    def list_files(self) -> List[str]:
        return self._files
    
    def file_exists(self, path: str) -> bool:
        return (self._path / path).exists()
    
    def read_text(self, path: str) -> str:
        file_path = self._path / path
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        return file_path.read_text(encoding='utf-8')
    
    def get_project_root(self) -> str:
        return ""  # Directory is already the project root
