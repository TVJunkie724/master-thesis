"""Small local configuration readers for the deterministic Optimizer."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import backend.constants as CONSTANTS
from backend.logger import logger


def load_json_file(file_path: str | Path) -> dict[str, Any]:
    path = Path(file_path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        logger.error("Error loading JSON file %s: %s", path, exc)
        raise
    if not isinstance(payload, dict):
        raise ValueError(f"JSON document must be an object: {path}")
    return payload


def load_config_file() -> dict[str, Any]:
    """Load optional non-secret runtime settings."""
    path = Path(CONSTANTS.CONFIG_FILE_PATH)
    if not path.exists():
        logger.warning("Optional config file not found: %s", path)
        return {"mode": os.getenv("TWIN2CLOUDS_MODE", "INFO")}
    return load_json_file(path)
