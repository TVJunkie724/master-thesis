"""Default-off activation boundary for architecture profile resolution."""

from __future__ import annotations

import os


ARCHITECTURE_PROFILE_RESOLUTION_ENV = (
    "ARCHITECTURE_PROFILE_RESOLUTION_ENABLED"
)


def architecture_profile_resolution_enabled() -> bool:
    """Enable only through an explicit true environment value."""

    return (
        os.getenv(ARCHITECTURE_PROFILE_RESOLUTION_ENV, "false")
        .strip()
        .lower()
        == "true"
    )
