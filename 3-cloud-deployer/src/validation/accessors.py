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
from src.project_archive.policy import MAX_MEMBER_BYTES, validate_archive


class ZipFileAccessor:
    """FileAccessor implementation for ZIP files."""
    
    def __init__(self, zf: zipfile.ZipFile):
        validate_archive(zf)
        self._zf = zf
        self._files = zf.namelist()
        self._project_root = self._find_project_root()
        self._validate_project_boundary()
    
    def _find_project_root(self) -> str:
        """Resolve one unambiguous root from an exact ``config.json`` entry."""
        roots = set()
        for filename in self._files:
            path = Path(filename)
            if path.name != CONSTANTS.CONFIG_FILE:
                continue
            parent = path.parent.as_posix()
            roots.add("" if parent == "." else parent.strip("/"))
        if len(roots) > 1:
            raise ValueError("ZIP contains multiple project roots")
        if not roots:
            return ""
        root = roots.pop()
        return f"{root}/" if root else ""

    def _validate_project_boundary(self) -> None:
        """Reject sibling files when the project uses a wrapper directory."""
        if not self._project_root:
            return
        root_entry = self._project_root.rstrip("/")
        for filename in self._files:
            if filename.rstrip("/") == root_entry:
                continue
            if not filename.startswith(self._project_root):
                raise ValueError("ZIP contains files outside the canonical project root")
    
    def list_files(self) -> List[str]:
        return self._files
    
    def file_exists(self, path: str) -> bool:
        return path in self._files
    
    def read_text(self, path: str) -> str:
        return self._read_bounded(path).decode("utf-8")
    
    def read_binary(self, path: str) -> bytes:
        """Read file contents as bytes."""
        if path not in self._files:
            raise FileNotFoundError(f"File not found in ZIP: {path}")
        return self._read_bounded(path)

    def _read_bounded(self, path: str) -> bytes:
        with self._zf.open(path) as file_handle:
            content = file_handle.read(MAX_MEMBER_BYTES + 1)
        if len(content) > MAX_MEMBER_BYTES:
            raise ValueError("ZIP entry exceeds the per-file read limit")
        return content
    
    def get_project_root(self) -> str:
        return self._project_root


class DirectoryAccessor:
    """FileAccessor implementation for directories."""
    
    def __init__(self, project_path: Path):
        self._path = Path(project_path)
        if self._path.is_symlink() or not self._path.is_dir():
            raise ValueError("Project validation root must be a regular directory")
        self._files = self._scan_files()
    
    def _scan_files(self) -> List[str]:
        """Scan all files in the directory."""
        files = []
        for root, dirs, filenames in os.walk(self._path):
            root_path = Path(root)
            if any((root_path / directory).is_symlink() for directory in dirs):
                raise ValueError("Project validation does not allow symbolic links")
            # Skip hidden directories and __pycache__
            dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__']
            for filename in filenames:
                full_path = os.path.join(root, filename)
                if Path(full_path).is_symlink():
                    raise ValueError("Project validation does not allow symbolic links")
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
    
    def read_binary(self, path: str) -> bytes:
        """Read file contents as bytes."""
        file_path = self._path / path
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        return file_path.read_bytes()
    
    def get_project_root(self) -> str:
        return ""  # Directory is already the project root
