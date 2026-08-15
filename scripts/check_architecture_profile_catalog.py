#!/usr/bin/env python3
"""Run the network-free Phase 8.3 catalog completeness and drift gate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "3-cloud-deployer"))

from src.architecture_profiles.completeness import (  # noqa: E402
    CatalogCheckError,
    check_catalog_completeness,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the deterministic full completeness report.",
    )
    args = parser.parse_args()
    try:
        report = check_catalog_completeness(ROOT)
    except CatalogCheckError as exc:
        print(f"architecture-profile-catalog: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        counts = report["catalog"]
        print(
            "architecture-profile-catalog: OK "
            f"(components={counts['deployment_components']}, "
            f"edges={counts['edge_implementations']}, "
            f"artifacts={counts['package_artifacts']}, "
            f"terraform_resources={counts['terraform_resources']})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
