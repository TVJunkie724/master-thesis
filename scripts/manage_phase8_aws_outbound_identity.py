#!/usr/bin/env python3
"""Manage the one approved AWS outbound-identity prerequisite for Phase 8.

This is a narrow thesis-evaluation helper. It never prints the account-specific
issuer URL or credential values. Enablement remains inventoried until the last
AWS-to-Azure Twin scenario; disablement is a separate final-cleanup action.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import ClientError


APPROVED_RUN_ID = "26083001"
APPROVED_PLAN_DIGEST = (
    "sha256:29d1024d5180e79b86ff198da4c21c61c83f89c703753b850efe3686c0505754"
)


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(value).encode()).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_aws_credentials(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    aws = dict(value["aws"])
    required = {"aws_access_key_id", "aws_secret_access_key", "aws_region"}
    if not required.issubset(aws):
        raise ValueError("AWS credential schema is incomplete")
    return aws


def _client(credentials: dict[str, Any]) -> Any:
    values: dict[str, Any] = {
        "aws_access_key_id": credentials["aws_access_key_id"],
        "aws_secret_access_key": credentials["aws_secret_access_key"],
        "region_name": credentials["aws_region"],
    }
    if credentials.get("aws_session_token"):
        values["aws_session_token"] = credentials["aws_session_token"]
    return boto3.client("iam", **values)


def _status(client: Any) -> str:
    try:
        response = client.get_outbound_web_identity_federation_info()
    except ClientError as exc:
        code = str(exc.response.get("Error", {}).get("Code") or "")
        if code in {"FeatureDisabled", "FeatureDisabledException"}:
            return "disabled"
        raise
    enabled = response.get("JwtVendingEnabled")
    if isinstance(enabled, bool):
        return "enabled" if enabled else "disabled"
    return "unknown"


def manage(client: Any, action: str) -> dict[str, Any]:
    before = _status(client)
    mutation_performed = False
    if action == "enable":
        if before == "unknown":
            raise RuntimeError("AWS_OUTBOUND_IDENTITY_STATUS_UNKNOWN")
        if before == "disabled":
            client.enable_outbound_web_identity_federation()
            mutation_performed = True
        expected = "enabled"
    elif action == "disable":
        if before == "unknown":
            raise RuntimeError("AWS_OUTBOUND_IDENTITY_STATUS_UNKNOWN")
        if before == "enabled":
            client.disable_outbound_web_identity_federation()
            mutation_performed = True
        expected = "disabled"
    else:
        raise ValueError("unsupported action")

    after = before
    for _ in range(12):
        after = _status(client)
        if after == expected:
            break
        time.sleep(5)
    if after != expected:
        raise RuntimeError("AWS_OUTBOUND_IDENTITY_TRANSITION_INCOMPLETE")

    record: dict[str, Any] = {
        "schema_version": "six-layer-phase8-aws-outbound-identity.v1",
        "run_id": APPROVED_RUN_ID,
        "plan_record_digest": APPROVED_PLAN_DIGEST,
        "checked_at": _utc_now(),
        "action": action,
        "status_before": before,
        "status_after": after,
        "mutation_performed": mutation_performed,
        "issuer_url_included": False,
        "credential_values_included": False,
        "provider_scope_values_included": False,
        "direct_cost_cap_usd": "0.000000",
        "cleanup_requirement": (
            "disable_after_final_aws_to_azure_twin_scenario"
            if action == "enable"
            else "complete"
        ),
    }
    record["record_digest"] = _digest(record)
    return record


def _safe_error_code(exc: Exception) -> str:
    if isinstance(exc, ClientError):
        raw = str(exc.response.get("Error", {}).get("Code") or "AWS_CLIENT_ERROR")
    else:
        raw = type(exc).__name__
    return re.sub(r"[^A-Z0-9_]+", "_", raw.upper()).strip("_")[:80]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--enable", action="store_true")
    actions.add_argument("--disable-final-cleanup", action="store_true")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--approved-plan-digest", required=True)
    parser.add_argument("--credentials", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if args.run_id != APPROVED_RUN_ID:
        raise ValueError("run ID is not approved")
    if args.approved_plan_digest != APPROVED_PLAN_DIGEST:
        raise ValueError("plan digest is not approved")
    if args.output.exists():
        raise FileExistsError("result output already exists")

    credentials = _load_aws_credentials(args.credentials.resolve())
    action = "enable" if args.enable else "disable"
    try:
        record = manage(_client(credentials), action)
    except Exception as exc:
        print(f"AWS outbound identity prerequisite: BLOCKED_{_safe_error_code(exc)}")
        return 2
    serialized = _canonical_json(record)
    for key in ("aws_access_key_id", "aws_secret_access_key", "aws_session_token"):
        value = credentials.get(key)
        if isinstance(value, str) and len(value) >= 4 and value in serialized:
            raise ValueError("credential value escaped redaction")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "AWS outbound identity prerequisite: "
        f"{record['status_after']}; mutation={record['mutation_performed']}; "
        "direct_cost_cap_usd=0.000000"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
