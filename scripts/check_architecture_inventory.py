#!/usr/bin/env python3
"""CLI for generating or checking the Phase 8.0 architecture inventory."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from architecture_inventory.canonical import pretty_json
from architecture_inventory.checker import (
    InventoryCheckError,
    build_inventory,
    check_inventory,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check the code-backed current deployment graph inventory."
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Explicitly regenerate current-graph.json from audited sources.",
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    inventory_path = root / "contracts/architecture-inventory/v1/current-graph.json"
    try:
        if args.write:
            inventory_path.write_text(
                pretty_json(build_inventory(root)),
                encoding="utf-8",
            )
            print("architecture-inventory: regenerated current-graph.json")
        counts = check_inventory(root)
    except InventoryCheckError as exc:
        print(f"architecture-inventory: {exc.category} ({exc.total})", file=sys.stderr)
        for finding in exc.findings:
            print(f"- {finding}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(
            f"architecture-inventory: EVIDENCE_INCOMPLETE (1)\n"
            f"- {type(exc).__name__}: {str(exc)[:300]}",
            file=sys.stderr,
        )
        return 1
    summary = ", ".join(f"{key}={value}" for key, value in counts.items())
    print(f"architecture-inventory: OK ({summary})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
