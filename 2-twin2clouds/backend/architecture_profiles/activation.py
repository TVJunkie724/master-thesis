"""Default-on activation boundary for architecture profile resolution."""

from __future__ import annotations

import os


ARCHITECTURE_PROFILE_RESOLUTION_ENV = "ARCHITECTURE_PROFILE_RESOLUTION_ENABLED"


def architecture_profile_resolution_enabled() -> bool:
    """Enable by default while preserving an explicit false rollback."""

    return (
        os.getenv(ARCHITECTURE_PROFILE_RESOLUTION_ENV, "true").strip().lower() == "true"
    )
