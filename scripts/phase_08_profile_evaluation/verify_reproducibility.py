#!/usr/bin/env python3
"""Prove two clean Phase 8 evaluation regenerations are byte-identical."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import tempfile

from generate import DEFAULT_OUTPUT, generate
from validate import validate_package


def file_map(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file() and "schemas" not in path.relative_to(root).parts
    }


def compare(left: Path, right: Path, label: str) -> None:
    left_files = file_map(left)
    right_files = file_map(right)
    if left_files.keys() != right_files.keys():
        missing = sorted(left_files.keys() - right_files.keys())
        extra = sorted(right_files.keys() - left_files.keys())
        raise AssertionError(
            f"{label} file-set drift: missing={missing}, extra={extra}"
        )
    changed = [path for path in left_files if left_files[path] != right_files[path]]
    if changed:
        raise AssertionError(f"{label} byte drift: {changed}")


def verify(*, committed: Path, compare_committed: bool) -> None:
    with tempfile.TemporaryDirectory(prefix="phase8-evaluation-a-") as first_dir:
        with tempfile.TemporaryDirectory(prefix="phase8-evaluation-b-") as second_dir:
            first = Path(first_dir)
            second = Path(second_dir)
            generate(first)
            generate(second)
            validate_package(first)
            validate_package(second)
            compare(first, second, "clean regeneration")
            if compare_committed:
                compare(first, committed, "committed evidence")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--committed", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--skip-committed", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    verify(
        committed=args.committed.resolve(),
        compare_committed=not args.skip_committed,
    )
    print("Phase 8 evaluation regeneration: byte-identical")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"Phase 8 evaluation reproducibility failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
