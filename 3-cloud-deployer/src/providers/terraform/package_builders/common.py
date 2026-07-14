"""Shared deterministic archive helpers for provider package builders."""

import glob
import hashlib
from pathlib import Path

def _compute_content_hash(data: bytes) -> str:
    """Compute a short SHA-256 hash for content-based package versioning."""
    return hashlib.sha256(data).hexdigest()[:16]


def _clean_old_versioned_zips(build_dir: Path, prefix: str) -> None:
    """Remove old versioned ZIPs with same prefix to avoid accumulation."""
    pattern = build_dir / f"{prefix}_*.zip"
    for old_zip in glob.glob(str(pattern)):
        try:
            Path(old_zip).unlink()
        except OSError:
            pass  # Ignore removal errors



def _should_include_file(file_path: Path) -> bool:
    """
    Check if a file should be included in the function ZIP.
    Excludes .zip files, .git*, .DS_Store, and __pycache__ directories.
    """
    if file_path.is_symlink():
        raise ValueError("Symbolic links are not allowed in function package sources")
    if '__pycache__' in str(file_path):
        return False
    if file_path.name.startswith('.git') or file_path.name == '.DS_Store':
        return False
    if file_path.suffix.lower() == '.zip':
        return False
    return True



def _merge_requirements(wrapper_req: Path, user_req: Path) -> str:
    """Merge wrapper and user requirements.txt files."""
    lines = set()
    
    if wrapper_req.exists():
        for line in wrapper_req.read_text().strip().splitlines():
            if line.strip() and not line.startswith('#'):
                lines.add(line.strip())
    
    if user_req.exists():
        for line in user_req.read_text().strip().splitlines():
            if line.strip() and not line.startswith('#'):
                lines.add(line.strip())
    
    return '\n'.join(sorted(lines)) if lines else ''



