#!/usr/bin/env python3
"""CLI wrapper for the canonical Management policy materializer."""

from __future__ import annotations

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "twin2multicloud_backend"))

from src.services.deployment_policy_materializer import (  # noqa: E402,F401
    AWS_MANAGED_POLICY_CHARACTER_LIMIT,
    PolicyMaterializationError,
    aws_policy_character_count,
    load_gcp_phase8_api_baseline,
    main,
    materialize_aws_deployment_bundle,
    materialize_azure_custom_role,
    materialize_gcp_custom_role,
)


if __name__ == "__main__":
    raise SystemExit(main())
