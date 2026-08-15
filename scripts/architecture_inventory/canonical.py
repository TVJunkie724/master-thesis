"""Deterministic JSON and audited-source digest helpers."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


_IGNORED_PARTS = frozenset(
    {
        ".build",
        ".dart_tool",
        ".git",
        ".idea",
        ".pytest_cache",
        ".terraform",
        ".venv",
        "__pycache__",
        "build",
        "coverage",
        "data",
        "node_modules",
        "runtime",
        "tmp",
        "uploads",
    }
)
_IGNORED_NAMES = frozenset(
    {
        ".env",
        "config_credentials.json",
        "terraform.tfstate",
        "terraform.tfstate.backup",
    }
)


def canonical_bytes(value: Any) -> bytes:
    """Return the compact canonical representation used for digests."""

    return json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def pretty_json(value: Any) -> str:
    """Return the committed deterministic representation."""

    return json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n"


def content_digest(inventory: dict[str, Any]) -> str:
    """Digest semantic content while excluding audit-only metadata."""

    content = {
        key: value
        for key, value in inventory.items()
        if key not in {"generated_at", "content_digest"}
    }
    return f"sha256:{hashlib.sha256(canonical_bytes(content)).hexdigest()}"


def _safe_files(root: Path, declared_paths: Iterable[str]) -> list[Path]:
    files: set[Path] = set()
    for relative in declared_paths:
        candidate = (root / relative).resolve()
        try:
            candidate.relative_to(root.resolve())
        except ValueError as exc:
            raise ValueError(f"Audited path escapes repository: {relative}") from exc
        if not candidate.exists():
            raise ValueError(f"Audited path does not exist: {relative}")
        candidates = [candidate] if candidate.is_file() else candidate.rglob("*")
        for path in candidates:
            if not path.is_file() or path.is_symlink():
                continue
            relative_path = path.relative_to(root)
            if any(part in _IGNORED_PARTS for part in relative_path.parts):
                continue
            if path.name in _IGNORED_NAMES or path.name.endswith((".tfstate", ".zip")):
                continue
            files.add(path)
    return sorted(files, key=lambda item: item.relative_to(root).as_posix())


def source_tree_digest(root: Path, declared_paths: Iterable[str]) -> str:
    """Hash sorted repository path/content-digest pairs without exposing content."""

    pairs = [
        {
            "path": path.relative_to(root).as_posix(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        for path in _safe_files(root, declared_paths)
    ]
    return f"sha256:{hashlib.sha256(canonical_bytes(pairs)).hexdigest()}"
