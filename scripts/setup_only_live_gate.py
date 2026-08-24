#!/usr/bin/env python3
"""Offline contract and safety boundary for the setup-only live gate.

This module deliberately contains no cloud SDK imports and cannot execute a
provider operation. Future supervised adapters must pass through these
manifest, operation-allowlist, confirmation, and cleanup-ledger guards.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
from collections.abc import Mapping, Sequence
from typing import Any
from uuid import UUID


REPO_ROOT = Path(__file__).resolve().parents[1]
PERMISSION_SET_ROOT = (
    REPO_ROOT / "3-cloud-deployer" / "docs" / "references" / "permission_sets"
)
SCHEMA_VERSION = "setup-only-live-gate.v2"
LEDGER_SCHEMA_VERSION = "setup-only-live-gate-ledger.v2"
PERMISSION_SET_VERSION = "thesis-demo-v2"
PROVIDERS = ("aws", "azure", "gcp")
MODES = ("plan_only", "setup_only")
RUN_ID_PATTERN = re.compile(r"^twin2mc-e2e-[a-z0-9][a-z0-9-]{6,15}$")
AWS_ACCOUNT_PATTERN = re.compile(r"^[0-9]{12}$")
GCP_PROJECT_PATTERN = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
REGION_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{1,31}$")
MAX_LEDGER_BYTES = 256 * 1024

BOOTSTRAP_PACK_PATHS = {
    "aws": PERMISSION_SET_ROOT / "aws_bootstrap_admin_v2.json",
    "azure": PERMISSION_SET_ROOT / "azure_bootstrap_admin_v2.json",
    "gcp": PERMISSION_SET_ROOT / "gcp_bootstrap_admin_v3.json",
}
DEPLOYMENT_PACK_PATHS = {
    provider: PERMISSION_SET_ROOT / f"{provider}_thesis_demo_v2.json"
    for provider in PROVIDERS
}
DEPLOYMENT_BINDING_PATHS = {
    provider: REPO_ROOT
    / "contracts"
    / "cloud-bootstrap"
    / "v1"
    / "deployment-identity-bindings"
    / f"{provider}.json"
    for provider in ("aws", "azure", "gcp")
}
GCP_API_BASELINE_PATH = (
    REPO_ROOT / "contracts" / "cloud-bootstrap" / "v1" / "gcp-phase8-api-baseline.json"
)

TARGET_KEYS = {
    "aws": frozenset({"provider", "account_id", "region"}),
    "azure": frozenset({"provider", "tenant_id", "subscription_id", "region"}),
    "gcp": frozenset({"provider", "mode", "project_id", "region"}),
}

ALLOWED_SETUP_OPERATIONS = {
    "aws": frozenset(
        {
            "sts.get_caller_identity",
            "iam.get_user",
            "iam.create_user",
            "iam.delete_user",
            "iam.tag_user",
            "iam.untag_user",
            "iam.create_policy",
            "iam.delete_policy",
            "iam.get_policy",
            "iam.get_policy_version",
            "iam.list_policy_versions",
            "iam.create_policy_version",
            "iam.delete_policy_version",
            "iam.attach_user_policy",
            "iam.detach_user_policy",
            "iam.list_attached_user_policies",
            "iam.list_entities_for_policy",
            "iam.tag_policy",
            "iam.untag_policy",
            "iam.create_access_key",
            "iam.delete_access_key",
            "iam.get_access_key_last_used",
            "iam.list_access_keys",
        }
    ),
    "azure": frozenset(
        {
            "arm.subscriptions.get",
            "arm.role_definitions.get",
            "arm.role_definitions.create_or_update",
            "arm.role_definitions.delete",
            "arm.role_assignments.list",
            "arm.role_assignments.create",
            "arm.role_assignments.delete",
            "graph.applications.get",
            "graph.applications.create",
            "graph.applications.delete",
            "graph.applications.add_password",
            "graph.applications.remove_password",
            "graph.service_principals.get",
            "graph.service_principals.create",
            "graph.service_principals.delete",
        }
    ),
    "gcp": frozenset(
        {
            "resourcemanager.projects.get",
            "resourcemanager.projects.get_iam_policy",
            "resourcemanager.projects.set_iam_policy",
            "resourcemanager.projects.test_iam_permissions",
            "cloudbilling.projects.get_billing_info",
            "serviceusage.services.get",
            "serviceusage.services.batch_enable",
            "serviceusage.operations.get",
            "iam.roles.get",
            "iam.roles.create",
            "iam.roles.delete",
            "iam.service_accounts.get",
            "iam.service_accounts.create",
            "iam.service_accounts.delete",
            "iam.service_account_keys.list",
            "iam.service_account_keys.get",
            "iam.service_account_keys.create",
            "iam.service_account_keys.delete",
        }
    ),
}

OPERATION_PERMISSIONS = {
    "aws": {
        "sts.get_caller_identity": "sts:GetCallerIdentity",
        "iam.get_user": "iam:GetUser",
        "iam.create_user": "iam:CreateUser",
        "iam.delete_user": "iam:DeleteUser",
        "iam.tag_user": "iam:TagUser",
        "iam.untag_user": "iam:UntagUser",
        "iam.create_policy": "iam:CreatePolicy",
        "iam.delete_policy": "iam:DeletePolicy",
        "iam.get_policy": "iam:GetPolicy",
        "iam.get_policy_version": "iam:GetPolicyVersion",
        "iam.list_policy_versions": "iam:ListPolicyVersions",
        "iam.create_policy_version": "iam:CreatePolicyVersion",
        "iam.delete_policy_version": "iam:DeletePolicyVersion",
        "iam.attach_user_policy": "iam:AttachUserPolicy",
        "iam.detach_user_policy": "iam:DetachUserPolicy",
        "iam.list_attached_user_policies": "iam:ListAttachedUserPolicies",
        "iam.list_entities_for_policy": "iam:ListEntitiesForPolicy",
        "iam.tag_policy": "iam:TagPolicy",
        "iam.untag_policy": "iam:UntagPolicy",
        "iam.create_access_key": "iam:CreateAccessKey",
        "iam.delete_access_key": "iam:DeleteAccessKey",
        "iam.get_access_key_last_used": "iam:GetAccessKeyLastUsed",
        "iam.list_access_keys": "iam:ListAccessKeys",
    },
    "azure": {
        "arm.subscriptions.get": "Microsoft.Resources/subscriptions/read",
        "arm.role_definitions.get": "Microsoft.Authorization/roleDefinitions/read",
        "arm.role_definitions.create_or_update": (
            "Microsoft.Authorization/roleDefinitions/write"
        ),
        "arm.role_definitions.delete": "Microsoft.Authorization/roleDefinitions/delete",
        "arm.role_assignments.list": "Microsoft.Authorization/roleAssignments/read",
        "arm.role_assignments.create": "Microsoft.Authorization/roleAssignments/write",
        "arm.role_assignments.delete": "Microsoft.Authorization/roleAssignments/delete",
        "graph.applications.get": "Application.ReadWrite.All",
        "graph.applications.create": "Application.ReadWrite.All",
        "graph.applications.delete": "Application.ReadWrite.All",
        "graph.applications.add_password": "Application.ReadWrite.All",
        "graph.applications.remove_password": "Application.ReadWrite.All",
        "graph.service_principals.get": "Application.ReadWrite.All",
        "graph.service_principals.create": "Application.ReadWrite.All",
        "graph.service_principals.delete": "Application.ReadWrite.All",
    },
    "gcp": {
        "resourcemanager.projects.get": "resourcemanager.projects.get",
        "resourcemanager.projects.get_iam_policy": (
            "resourcemanager.projects.getIamPolicy"
        ),
        "resourcemanager.projects.set_iam_policy": (
            "resourcemanager.projects.setIamPolicy"
        ),
        "resourcemanager.projects.test_iam_permissions": (
            "resourcemanager.projects.get"
        ),
        "cloudbilling.projects.get_billing_info": "resourcemanager.projects.get",
        "serviceusage.services.get": "serviceusage.services.get",
        "serviceusage.services.batch_enable": "serviceusage.services.enable",
        "serviceusage.operations.get": "serviceusage.operations.get",
        "iam.roles.get": "iam.roles.get",
        "iam.roles.create": "iam.roles.create",
        "iam.roles.delete": "iam.roles.delete",
        "iam.service_accounts.get": "iam.serviceAccounts.get",
        "iam.service_accounts.create": "iam.serviceAccounts.create",
        "iam.service_accounts.delete": "iam.serviceAccounts.delete",
        "iam.service_account_keys.list": "iam.serviceAccountKeys.list",
        "iam.service_account_keys.get": "iam.serviceAccountKeys.get",
        "iam.service_account_keys.create": "iam.serviceAccountKeys.create",
        "iam.service_account_keys.delete": "iam.serviceAccountKeys.delete",
    },
}

RESOURCE_KINDS = {
    "aws": frozenset({"iam_user", "managed_policy", "access_key"}),
    "azure": frozenset(
        {
            "application",
            "service_principal",
            "client_secret",
            "custom_role",
            "role_assignment",
        }
    ),
    "gcp": frozenset(
        {"service_account", "service_account_key", "custom_role", "project_binding"}
    ),
}

LEDGER_STATES = (
    "planned",
    "authority_validated",
    "identity_created",
    "credential_created",
    "connection_persisted",
    "preflight_passed",
    "cleanup_required",
    "cleanup_running",
    "clean",
)
STATE_TRANSITIONS = {
    "planned": frozenset({"authority_validated", "cleanup_required"}),
    "authority_validated": frozenset({"identity_created", "cleanup_required"}),
    "identity_created": frozenset({"credential_created", "cleanup_required"}),
    "credential_created": frozenset({"connection_persisted", "cleanup_required"}),
    "connection_persisted": frozenset({"preflight_passed", "cleanup_required"}),
    "preflight_passed": frozenset({"cleanup_required"}),
    "cleanup_required": frozenset({"cleanup_running"}),
    "cleanup_running": frozenset({"cleanup_required", "clean"}),
    "clean": frozenset(),
}

MANIFEST_KEYS = frozenset(
    {
        "schema_version",
        "run_id",
        "provider",
        "mode",
        "target",
        "bootstrap_authority_pack",
        "deployment_pack",
        "api_baseline",
        "cleanup_policy",
        "resource_prefix",
        "created_at",
    }
)
PACK_REFERENCE_KEYS = frozenset({"id", "version", "digest"})
API_BASELINE_REFERENCE_KEYS = frozenset({"id", "digest", "services", "retain_enabled"})
LEDGER_KEYS = frozenset(
    {
        "schema_version",
        "manifest_digest",
        "run_id",
        "provider",
        "target_scope",
        "resource_prefix",
        "current_state",
        "resources",
        "cloud_connection_id",
        "preflight_status",
        "updated_at",
    }
)
RESOURCE_KEYS = frozenset({"kind", "provider_id", "owner_marker"})


class SetupGateError(RuntimeError):
    """A secret-safe setup-gate validation or persistence failure."""


@dataclass(frozen=True)
class SetupGateManifest:
    document: dict[str, Any]

    @property
    def run_id(self) -> str:
        return str(self.document["run_id"])

    @property
    def provider(self) -> str:
        return str(self.document["provider"])

    @property
    def mode(self) -> str:
        return str(self.document["mode"])

    @property
    def digest(self) -> str:
        return _document_digest(self.document)


@dataclass(frozen=True)
class CleanupLedger:
    document: dict[str, Any]

    @property
    def state(self) -> str:
        return str(self.document["current_state"])

    @property
    def is_clean(self) -> bool:
        return self.state == "clean"


def create_manifest(
    *,
    run_id: str,
    provider: str,
    mode: str,
    target: Mapping[str, str],
    created_at: datetime | None = None,
) -> SetupGateManifest:
    provider = _provider(provider)
    if mode not in MODES:
        raise SetupGateError(f"Unsupported setup-gate mode: {mode}")
    _validate_run_id(run_id)
    normalized_target = dict(target)
    _validate_target(provider, normalized_target)
    timestamp = created_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        raise SetupGateError("created_at must include a timezone.")
    document: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "provider": provider,
        "mode": mode,
        "target": normalized_target,
        "bootstrap_authority_pack": _pack_reference(provider, authority=True),
        "deployment_pack": _pack_reference(provider, authority=False),
        "api_baseline": _api_baseline_reference(provider),
        "cleanup_policy": "mandatory",
        "resource_prefix": f"{run_id}-",
        "created_at": timestamp.astimezone(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z"),
    }
    return validate_manifest(document)


def validate_manifest(document: Mapping[str, Any]) -> SetupGateManifest:
    payload = dict(document)
    _exact_keys(payload, MANIFEST_KEYS, "manifest")
    if payload["schema_version"] != SCHEMA_VERSION:
        raise SetupGateError("Unsupported setup-gate manifest version.")
    provider = _provider(payload["provider"])
    mode = payload["mode"]
    if mode not in MODES:
        raise SetupGateError("Manifest mode must be plan_only or setup_only.")
    run_id = payload["run_id"]
    _validate_run_id(run_id)
    if payload["cleanup_policy"] != "mandatory":
        raise SetupGateError("Live setup cleanup must be mandatory.")
    if payload["resource_prefix"] != f"{run_id}-":
        raise SetupGateError("Resource prefix must be derived from the exact run ID.")
    _validate_target(provider, payload["target"])
    _validate_pack_reference(
        provider, payload["bootstrap_authority_pack"], authority=True
    )
    _validate_pack_reference(provider, payload["deployment_pack"], authority=False)
    _validate_api_baseline_reference(provider, payload["api_baseline"])
    _parse_timestamp(payload["created_at"], "created_at")
    _reject_secret_shaped_keys(payload)
    return SetupGateManifest(document=payload)


def authority_pack_gaps(provider: str) -> tuple[str, ...]:
    normalized = _provider(provider)
    pack = _load_json(BOOTSTRAP_PACK_PATHS[normalized])
    granted = {
        permission
        for group in pack["permission_groups"]
        for permission in group["permissions"]
    }
    required = set(OPERATION_PERMISSIONS[normalized].values())
    return tuple(sorted(required - granted))


def require_setup_only_admission(
    manifest: SetupGateManifest,
    *,
    environment: Mapping[str, str] | None = None,
) -> None:
    if manifest.mode != "setup_only":
        raise SetupGateError("Provider operations require a setup_only manifest.")
    env = os.environ if environment is None else environment
    if env.get("CI", "").strip().lower() in {"1", "true", "yes"}:
        raise SetupGateError("The setup-only live gate is forbidden in CI.")
    if env.get("TWIN2MC_SETUP_GATE_ENABLED") != "1":
        raise SetupGateError("The setup-only live gate is not explicitly enabled.")
    expected = f"{manifest.run_id}:{manifest.provider}:setup_only"
    if env.get("TWIN2MC_SETUP_GATE_CONFIRMATION") != expected:
        raise SetupGateError(
            "The setup-only live confirmation does not match the manifest."
        )
    gaps = authority_pack_gaps(manifest.provider)
    if gaps:
        raise SetupGateError(
            "The bootstrap authority pack does not admit every setup-only operation: "
            + ", ".join(gaps)
        )


def require_allowed_operation(manifest: SetupGateManifest, operation: str) -> None:
    if manifest.mode != "setup_only":
        raise SetupGateError("A plan-only manifest cannot execute provider operations.")
    if operation not in ALLOWED_SETUP_OPERATIONS[manifest.provider]:
        raise SetupGateError(
            f"Provider operation is outside the {manifest.provider} setup-only allowlist."
        )


def new_cleanup_ledger(manifest: SetupGateManifest) -> CleanupLedger:
    document = {
        "schema_version": LEDGER_SCHEMA_VERSION,
        "manifest_digest": manifest.digest,
        "run_id": manifest.run_id,
        "provider": manifest.provider,
        "target_scope": dict(manifest.document["target"]),
        "resource_prefix": manifest.document["resource_prefix"],
        "current_state": "planned",
        "resources": [],
        "cloud_connection_id": None,
        "preflight_status": "not_run",
        "updated_at": _utc_now(),
    }
    return validate_cleanup_ledger(document, manifest=manifest)


def validate_cleanup_ledger(
    document: Mapping[str, Any],
    *,
    manifest: SetupGateManifest | None = None,
) -> CleanupLedger:
    payload = dict(document)
    _exact_keys(payload, LEDGER_KEYS, "cleanup ledger")
    if payload["schema_version"] != LEDGER_SCHEMA_VERSION:
        raise SetupGateError("Unsupported cleanup-ledger version.")
    provider = _provider(payload["provider"])
    run_id = payload["run_id"]
    _validate_run_id(run_id)
    if payload["resource_prefix"] != f"{run_id}-":
        raise SetupGateError(
            "Cleanup ledger resource prefix does not match its run ID."
        )
    _validate_target(provider, payload["target_scope"])
    if payload["current_state"] not in LEDGER_STATES:
        raise SetupGateError("Cleanup ledger contains an unsupported state.")
    if not isinstance(payload["manifest_digest"], str) or not re.fullmatch(
        r"sha256:[a-f0-9]{64}", payload["manifest_digest"]
    ):
        raise SetupGateError("Cleanup ledger manifest digest is invalid.")
    if manifest is not None:
        if payload["manifest_digest"] != manifest.digest:
            raise SetupGateError("Cleanup ledger does not belong to this manifest.")
        if provider != manifest.provider or run_id != manifest.run_id:
            raise SetupGateError("Cleanup ledger scope does not match this manifest.")
    resources = payload["resources"]
    if not isinstance(resources, list):
        raise SetupGateError("Cleanup ledger resources must be a list.")
    for resource in resources:
        _validate_resource(provider, run_id, resource)
    connection_id = payload["cloud_connection_id"]
    if connection_id is not None:
        _safe_identifier(connection_id, "cloud_connection_id")
    if payload["preflight_status"] not in {"not_run", "passed", "failed", "error"}:
        raise SetupGateError("Cleanup ledger preflight status is invalid.")
    _parse_timestamp(payload["updated_at"], "updated_at")
    _reject_secret_shaped_keys(payload)
    return CleanupLedger(document=payload)


def transition_ledger(ledger: CleanupLedger, next_state: str) -> CleanupLedger:
    if next_state not in STATE_TRANSITIONS[ledger.state]:
        raise SetupGateError(
            f"Cleanup ledger cannot transition from {ledger.state} to {next_state}."
        )
    document = dict(ledger.document)
    document["current_state"] = next_state
    document["updated_at"] = _utc_now()
    return validate_cleanup_ledger(document)


def add_owned_resource(
    ledger: CleanupLedger,
    *,
    kind: str,
    provider_id: str,
    owner_marker: str,
) -> CleanupLedger:
    if ledger.state in {"planned", "clean"}:
        raise SetupGateError(
            f"Cleanup resources cannot be added while the ledger is {ledger.state}."
        )
    resource = {
        "kind": kind,
        "provider_id": provider_id,
        "owner_marker": owner_marker,
    }
    _validate_resource(ledger.document["provider"], ledger.document["run_id"], resource)
    if resource in ledger.document["resources"]:
        raise SetupGateError("Cleanup resource is already recorded.")
    document = dict(ledger.document)
    document["resources"] = [*ledger.document["resources"], resource]
    document["updated_at"] = _utc_now()
    return validate_cleanup_ledger(document)


def attach_cloud_connection(ledger: CleanupLedger, connection_id: str) -> CleanupLedger:
    if ledger.state not in {"credential_created", "cleanup_required"}:
        raise SetupGateError(
            "A CloudConnection can be attached only after credential creation."
        )
    if ledger.document["cloud_connection_id"] is not None:
        raise SetupGateError("Cleanup ledger already contains a CloudConnection ID.")
    _safe_identifier(connection_id, "cloud_connection_id")
    document = dict(ledger.document)
    document["cloud_connection_id"] = connection_id
    document["updated_at"] = _utc_now()
    return validate_cleanup_ledger(document)


def record_preflight_status(
    ledger: CleanupLedger,
    status: str,
) -> CleanupLedger:
    if ledger.state != "connection_persisted":
        raise SetupGateError(
            "Preflight status can be recorded only for a persisted test connection."
        )
    if status not in {"passed", "failed", "error"}:
        raise SetupGateError("Preflight status must be passed, failed, or error.")
    current = ledger.document["preflight_status"]
    if current != "not_run" and current != status:
        raise SetupGateError("Cleanup ledger already records another preflight result.")
    document = dict(ledger.document)
    document["preflight_status"] = status
    document["updated_at"] = _utc_now()
    return validate_cleanup_ledger(document)


class CleanupLedgerStore:
    """Private atomic storage for safe cleanup identifiers only."""

    def __init__(self, path: Path):
        self.path = path.expanduser().absolute()

    def create(self, ledger: CleanupLedger) -> None:
        self._ensure_private_parent()
        if _path_exists(self.path):
            raise SetupGateError("Cleanup ledger already exists; reconcile it first.")
        self._write(ledger, replace=False)

    def save(self, ledger: CleanupLedger) -> None:
        self._ensure_private_parent()
        self._require_private_file()
        self._write(ledger, replace=True)

    def load(self, *, manifest: SetupGateManifest | None = None) -> CleanupLedger:
        self._ensure_private_parent()
        metadata = self._require_private_file()
        if metadata.st_size > MAX_LEDGER_BYTES:
            raise SetupGateError("Cleanup ledger is unexpectedly large.")
        flags = os.O_RDONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(self.path, flags)
        try:
            chunks: list[bytes] = []
            total = 0
            while total <= MAX_LEDGER_BYTES:
                chunk = os.read(
                    descriptor,
                    min(8192, MAX_LEDGER_BYTES + 1 - total),
                )
                if not chunk:
                    break
                chunks.append(chunk)
                total += len(chunk)
            payload = b"".join(chunks)
        finally:
            os.close(descriptor)
        if len(payload) > MAX_LEDGER_BYTES:
            raise SetupGateError("Cleanup ledger is unexpectedly large.")
        try:
            document = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SetupGateError("Cleanup ledger is not valid UTF-8 JSON.") from exc
        if not isinstance(document, dict):
            raise SetupGateError("Cleanup ledger must contain one JSON object.")
        return validate_cleanup_ledger(document, manifest=manifest)

    def require_no_stale_ledger(self) -> None:
        if not _path_exists(self.path):
            return
        ledger = self.load()
        if not ledger.is_clean:
            raise SetupGateError(
                f"Cleanup ledger is still {ledger.state}; cleanup must finish first."
            )

    def _ensure_private_parent(self) -> None:
        parent = self.path.parent
        if _path_exists(parent):
            metadata = parent.lstat()
            if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
                raise SetupGateError("Cleanup-ledger parent must be a real directory.")
            if hasattr(os, "getuid") and metadata.st_uid != os.getuid():
                raise SetupGateError(
                    "Cleanup-ledger parent must be owned by the current user."
                )
            if stat.S_IMODE(metadata.st_mode) & 0o077:
                raise SetupGateError(
                    "Existing cleanup-ledger parent permissions must be 0700 or stricter."
                )
        else:
            parent.mkdir(parents=True, mode=0o700)

    def _require_private_file(self) -> os.stat_result:
        try:
            metadata = self.path.lstat()
        except OSError as exc:
            raise SetupGateError(
                "Cleanup ledger does not exist or cannot be inspected."
            ) from exc
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            raise SetupGateError("Cleanup ledger must be a regular file.")
        if metadata.st_nlink != 1:
            raise SetupGateError("Cleanup ledger must not be hard-linked.")
        if hasattr(os, "getuid") and metadata.st_uid != os.getuid():
            raise SetupGateError("Cleanup ledger must be owned by the current user.")
        if stat.S_IMODE(metadata.st_mode) & 0o077:
            raise SetupGateError("Cleanup ledger permissions must be 0600 or stricter.")
        return metadata

    def _write(self, ledger: CleanupLedger, *, replace: bool) -> None:
        validated = validate_cleanup_ledger(ledger.document)
        payload = (
            json.dumps(validated.document, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
        if len(payload) > MAX_LEDGER_BYTES:
            raise SetupGateError("Cleanup ledger is unexpectedly large.")
        descriptor, temporary = tempfile.mkstemp(
            prefix=f".{self.path.name}.", suffix=".tmp", dir=self.path.parent
        )
        temporary_path = Path(temporary)
        try:
            os.fchmod(descriptor, 0o600)
            offset = 0
            while offset < len(payload):
                written = os.write(descriptor, payload[offset:])
                if written <= 0:
                    raise OSError("Cleanup-ledger write made no progress")
                offset += written
            os.fsync(descriptor)
            os.close(descriptor)
            descriptor = -1
            if replace:
                self._require_private_file()
                os.replace(temporary_path, self.path)
            else:
                try:
                    os.link(temporary_path, self.path, follow_symlinks=False)
                except FileExistsError as exc:
                    raise SetupGateError(
                        "Cleanup ledger was created concurrently; reconcile it first."
                    ) from exc
                temporary_path.unlink()
            os.chmod(self.path, 0o600, follow_symlinks=False)
            directory_descriptor = os.open(self.path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_descriptor)
            finally:
                os.close(directory_descriptor)
        except SetupGateError:
            raise
        except OSError as exc:
            raise SetupGateError(
                "Cleanup ledger could not be persisted safely."
            ) from exc
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            temporary_path.unlink(missing_ok=True)


def write_manifest(path: Path, manifest: SetupGateManifest) -> None:
    target = path.expanduser().absolute()
    target.parent.mkdir(parents=True, exist_ok=True)
    parent_metadata = target.parent.lstat()
    if (
        stat.S_ISLNK(parent_metadata.st_mode)
        or not stat.S_ISDIR(parent_metadata.st_mode)
        or stat.S_IMODE(parent_metadata.st_mode) & 0o022
        or (
            hasattr(os, "getuid")
            and parent_metadata.st_uid != os.getuid()
        )
    ):
        raise SetupGateError(
            "Manifest parent must be an owner-controlled directory not writable by other users."
        )
    payload = (
        json.dumps(manifest.document, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = -1
    created = False
    succeeded = False
    try:
        descriptor = os.open(target, flags, 0o600)
        created = True
        offset = 0
        while offset < len(payload):
            written = os.write(descriptor, payload[offset:])
            if written <= 0:
                raise OSError("Manifest write made no progress")
            offset += written
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = -1
        os.chmod(target, 0o600, follow_symlinks=False)
        directory_descriptor = os.open(target.parent, os.O_RDONLY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
        succeeded = True
    except FileExistsError as exc:
        raise SetupGateError("Manifest output already exists.") from exc
    except OSError as exc:
        raise SetupGateError("Manifest could not be persisted safely.") from exc
    finally:
        if descriptor >= 0:
            try:
                os.close(descriptor)
            except OSError:
                pass
        if created and not succeeded:
            target.unlink(missing_ok=True)


def read_manifest(path: Path) -> SetupGateManifest:
    target = path.expanduser().absolute()
    try:
        metadata = target.lstat()
        parent_metadata = target.parent.lstat()
        if (
            stat.S_ISLNK(metadata.st_mode)
            or not stat.S_ISREG(metadata.st_mode)
            or metadata.st_nlink != 1
            or stat.S_IMODE(metadata.st_mode) & 0o077
        ):
            raise SetupGateError(
                "Manifest must be one private, non-linked regular file."
            )
        if (
            stat.S_ISLNK(parent_metadata.st_mode)
            or not stat.S_ISDIR(parent_metadata.st_mode)
            or stat.S_IMODE(parent_metadata.st_mode) & 0o022
        ):
            raise SetupGateError(
                "Manifest parent must be a real directory not writable by other users."
            )
        if hasattr(os, "getuid") and (
            metadata.st_uid != os.getuid()
            or parent_metadata.st_uid != os.getuid()
        ):
            raise SetupGateError("Manifest and parent must be owned by this user.")
        if metadata.st_size > MAX_LEDGER_BYTES:
            raise SetupGateError("Manifest is unexpectedly large.")
        flags = os.O_RDONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(target, flags)
        try:
            opened = os.fstat(descriptor)
            if (opened.st_dev, opened.st_ino) != (metadata.st_dev, metadata.st_ino):
                raise SetupGateError("Manifest changed while it was opened.")
            chunks: list[bytes] = []
            total = 0
            while total <= MAX_LEDGER_BYTES:
                chunk = os.read(
                    descriptor,
                    min(8192, MAX_LEDGER_BYTES + 1 - total),
                )
                if not chunk:
                    break
                chunks.append(chunk)
                total += len(chunk)
            payload = b"".join(chunks)
        finally:
            os.close(descriptor)
        if len(payload) > MAX_LEDGER_BYTES:
            raise SetupGateError("Manifest is unexpectedly large.")
        document = json.loads(payload.decode("utf-8"))
    except SetupGateError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SetupGateError("Manifest is not readable UTF-8 JSON.") from exc
    if not isinstance(document, dict):
        raise SetupGateError("Manifest must contain one JSON object.")
    return validate_manifest(document)


def _pack_reference(provider: str, *, authority: bool) -> dict[str, str]:
    path = (
        BOOTSTRAP_PACK_PATHS[provider] if authority else DEPLOYMENT_PACK_PATHS[provider]
    )
    document = _load_json(path)
    if authority:
        pack_id = document.get("contract_id")
        version = (
            pack_id.rsplit("-v", maxsplit=1)[-1] if isinstance(pack_id, str) else None
        )
    else:
        pack_id = f"{provider}.{document.get('permission_set_version')}"
        version = document.get("permission_set_version")
        if provider in DEPLOYMENT_BINDING_PATHS:
            base_digest = _document_digest(document)
            binding = _load_json(DEPLOYMENT_BINDING_PATHS[provider])
            if (
                binding.get("provider") != provider
                or binding.get("permission_set_version") != version
                or binding.get("base_pack_digest") != base_digest
                or not isinstance(binding.get("self_check_permissions"), list)
                or not binding["self_check_permissions"]
                or len(binding["self_check_permissions"])
                != len(set(binding["self_check_permissions"]))
                or (
                    provider == "gcp"
                    and not set(binding["self_check_permissions"]).issubset(
                        document.get("custom_role_inputs", [])
                    )
                )
            ):
                raise SetupGateError(
                    f"{provider.upper()} deployment identity binding does not "
                    "match the active pack."
                )
            expected_identity = {
                "aws": ("iam_user", "access_key", "customer_managed_policy"),
                "azure": (
                    "service_principal",
                    "client_secret",
                    "custom_role_assignment",
                ),
                "gcp": (
                    "service_account",
                    "service_account_key",
                    "project_custom_role_binding",
                ),
            }[provider]
            if (
                binding.get("identity_kind"),
                binding.get("connection_auth_type"),
                binding.get("policy_attachment_kind"),
            ) != expected_identity:
                raise SetupGateError(
                    f"{provider.upper()} deployment identity binding does not "
                    "match the implemented CloudConnection path."
                )
            pack_id = binding.get("binding_id")
            document = {
                "permission_set": document,
                "identity_binding": binding,
            }
    if not isinstance(pack_id, str) or not isinstance(version, str):
        raise SetupGateError("Permission-pack identity is malformed.")
    return {"id": pack_id, "version": version, "digest": _document_digest(document)}


def _api_baseline_reference(provider: str) -> dict[str, Any] | None:
    if provider != "gcp":
        return None
    document = _load_json(GCP_API_BASELINE_PATH)
    services = document.get("services")
    prerequisites = document.get("bootstrap_prerequisite_services")
    if (
        document.get("schema_version") != "gcp-phase8-api-baseline.v1"
        or document.get("baseline_id") != "gcp.phase8-api-baseline.v1"
        or document.get("provider") != "gcp"
        or document.get("status") != "frozen_offline_contract"
        or document.get("profiles")
        != ["five-layer-baseline@2", "six-layer-eventing@1"]
        or document.get("owner") != "bootstrap.gcp.admin-v3"
        or document.get("target_mode") != "existing_project"
        or document.get("region") != "europe-west1"
        or not isinstance(services, list)
        or not 1 <= len(services) <= 20
        or any(not isinstance(service, str) for service in services)
        or services != sorted(set(services))
        or any(
            re.fullmatch(r"[a-z0-9-]+\.googleapis\.com", service) is None
            for service in services
        )
        or not isinstance(prerequisites, list)
        or prerequisites
        != [
            "cloudresourcemanager.googleapis.com",
            "iam.googleapis.com",
            "serviceusage.googleapis.com",
        ]
        or document.get("retain_enabled") is not True
    ):
        raise SetupGateError(
            "GCP Phase 8 API baseline does not match the bootstrap authority pack."
        )
    return {
        "id": document["baseline_id"],
        "digest": _document_digest(document),
        "services": list(services),
        "retain_enabled": True,
    }


def _validate_pack_reference(provider: str, reference: Any, *, authority: bool) -> None:
    if not isinstance(reference, dict):
        raise SetupGateError("Permission-pack reference must be an object.")
    _exact_keys(reference, PACK_REFERENCE_KEYS, "permission-pack reference")
    if reference != _pack_reference(provider, authority=authority):
        raise SetupGateError("Permission-pack reference or digest is stale.")


def _validate_api_baseline_reference(provider: str, reference: Any) -> None:
    expected = _api_baseline_reference(provider)
    if reference is None:
        if expected is not None:
            raise SetupGateError("GCP setup manifest requires an API baseline.")
        return
    if not isinstance(reference, dict):
        raise SetupGateError("API-baseline reference must be an object or null.")
    _exact_keys(reference, API_BASELINE_REFERENCE_KEYS, "API-baseline reference")
    if reference != expected:
        raise SetupGateError("API-baseline reference or digest is stale.")


def _validate_target(provider: str, target: Any) -> None:
    if not isinstance(target, dict):
        raise SetupGateError("Provider target must be an object.")
    _exact_keys(target, TARGET_KEYS[provider], f"{provider} target")
    if target.get("provider") != provider:
        raise SetupGateError("Provider target does not match the manifest provider.")
    region = target.get("region")
    if not isinstance(region, str) or REGION_PATTERN.fullmatch(region) is None:
        raise SetupGateError("Provider region has an unsupported shape.")
    if provider == "aws":
        account_id = target.get("account_id")
        if (
            not isinstance(account_id, str)
            or AWS_ACCOUNT_PATTERN.fullmatch(account_id) is None
        ):
            raise SetupGateError("AWS account ID must contain exactly 12 digits.")
    elif provider == "azure":
        _uuid_text(target.get("tenant_id"), "Azure tenant ID")
        _uuid_text(target.get("subscription_id"), "Azure subscription ID")
    else:
        if target.get("mode") != "existing_project":
            raise SetupGateError(
                "The first setup-only GCP gate supports existing_project only."
            )
        project_id = target.get("project_id")
        if (
            not isinstance(project_id, str)
            or GCP_PROJECT_PATTERN.fullmatch(project_id) is None
        ):
            raise SetupGateError("GCP project ID has an unsupported shape.")


def _validate_resource(provider: str, run_id: str, resource: Any) -> None:
    if not isinstance(resource, dict):
        raise SetupGateError("Cleanup resource must be an object.")
    _exact_keys(resource, RESOURCE_KEYS, "cleanup resource")
    if resource["kind"] not in RESOURCE_KINDS[provider]:
        raise SetupGateError("Cleanup resource kind is not valid for this provider.")
    _safe_identifier(resource["provider_id"], "provider_id")
    owner_marker = resource["owner_marker"]
    if not isinstance(owner_marker, str) or not owner_marker.startswith(f"{run_id}-"):
        raise SetupGateError(
            "Cleanup resource is missing the exact gate ownership marker."
        )
    _safe_identifier(owner_marker, "owner_marker")


def _reject_secret_shaped_keys(value: Any, *, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).lower()
            if any(
                fragment in normalized
                for fragment in ("secret", "password", "private_key", "credential")
            ):
                raise SetupGateError(
                    f"Secret-shaped field is forbidden at {path}.{key}."
                )
            _reject_secret_shaped_keys(child, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_secret_shaped_keys(child, path=f"{path}[{index}]")


def _safe_identifier(value: Any, label: str) -> None:
    if not isinstance(value, str) or not value or len(value) > 512:
        raise SetupGateError(f"{label} must be a non-empty safe identifier.")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise SetupGateError(f"{label} contains control characters.")


def _uuid_text(value: Any, label: str) -> None:
    if not isinstance(value, str):
        raise SetupGateError(f"{label} must be a UUID string.")
    try:
        parsed = UUID(value)
    except ValueError as exc:
        raise SetupGateError(f"{label} must be a UUID string.") from exc
    if str(parsed) != value.lower():
        raise SetupGateError(f"{label} must use canonical UUID text.")


def _validate_run_id(value: Any) -> None:
    if not isinstance(value, str) or RUN_ID_PATTERN.fullmatch(value) is None:
        raise SetupGateError(
            "Run ID must use twin2mc-e2e- plus 7-16 lowercase letters, digits, or hyphens."
        )


def _provider(value: Any) -> str:
    if value not in PROVIDERS:
        raise SetupGateError("Provider must be exactly aws, azure, or gcp.")
    return str(value)


def _exact_keys(value: Mapping[str, Any], expected: frozenset[str], label: str) -> None:
    actual = frozenset(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        details = []
        if missing:
            details.append("missing=" + ",".join(missing))
        if extra:
            details.append("extra=" + ",".join(extra))
        raise SetupGateError(f"Invalid {label} fields ({'; '.join(details)}).")


def _load_json(path: Path) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SetupGateError(f"Permission pack cannot be read: {path.name}") from exc
    if not isinstance(document, dict):
        raise SetupGateError(f"Permission pack must be an object: {path.name}")
    return document


def _document_digest(document: Mapping[str, Any]) -> str:
    payload = json.dumps(
        document, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _parse_timestamp(value: Any, label: str) -> datetime:
    if not isinstance(value, str):
        raise SetupGateError(f"{label} must be an ISO-8601 timestamp.")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SetupGateError(f"{label} must be an ISO-8601 timestamp.") from exc
    if parsed.tzinfo is None:
        raise SetupGateError(f"{label} must include a timezone.")
    return parsed


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _path_exists(path: Path) -> bool:
    return path.exists() or path.is_symlink()


def _target_from_args(args: argparse.Namespace) -> dict[str, str]:
    target = {"provider": args.provider, "region": args.region}
    if args.provider == "aws":
        target["account_id"] = args.account_id or ""
    elif args.provider == "azure":
        target["tenant_id"] = args.tenant_id or ""
        target["subscription_id"] = args.subscription_id or ""
    else:
        target["mode"] = "existing_project"
        target["project_id"] = args.project_id or ""
    return target


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Create or validate a secret-free setup-only live-gate manifest. "
            "This command never contacts a cloud provider."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    create = subparsers.add_parser("create-manifest")
    create.add_argument("--provider", choices=PROVIDERS, required=True)
    create.add_argument("--mode", choices=MODES, required=True)
    create.add_argument("--run-id", required=True)
    create.add_argument("--region", required=True)
    create.add_argument("--account-id")
    create.add_argument("--tenant-id")
    create.add_argument("--subscription-id")
    create.add_argument("--project-id")
    create.add_argument("--output", type=Path, required=True)
    check_manifest = subparsers.add_parser("check-manifest")
    check_manifest.add_argument("--manifest", type=Path, required=True)
    check_ledger = subparsers.add_parser("check-ledger")
    check_ledger.add_argument("--ledger", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "create-manifest":
            manifest = create_manifest(
                run_id=args.run_id,
                provider=args.provider,
                mode=args.mode,
                target=_target_from_args(args),
            )
            write_manifest(args.output, manifest)
            print(
                "setup-only-live-gate: manifest created "
                f"(provider={manifest.provider}, mode={manifest.mode}, run_id={manifest.run_id})"
            )
        elif args.command == "check-manifest":
            manifest = read_manifest(args.manifest)
            gaps = authority_pack_gaps(manifest.provider)
            suffix = "ready" if not gaps else f"blocked_by_pack_gaps={len(gaps)}"
            print(
                "setup-only-live-gate: manifest valid "
                f"(provider={manifest.provider}, mode={manifest.mode}, {suffix})"
            )
        else:
            ledger = CleanupLedgerStore(args.ledger).load()
            print(
                "setup-only-live-gate: ledger valid "
                f"(provider={ledger.document['provider']}, state={ledger.state})"
            )
    except SetupGateError as exc:
        print(f"setup-only-live-gate: ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
