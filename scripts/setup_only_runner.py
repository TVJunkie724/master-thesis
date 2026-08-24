#!/usr/bin/env python3
"""Two-step Management client for the supervised setup-only thesis gate.

This runner never imports a cloud SDK. ``prepare`` is provider-credential free;
``execute`` reads exactly one bootstrap credential JSON object from stdin and
keeps it in process memory through preflight and mandatory cleanup.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import (
    HTTPRedirectHandler,
    ProxyHandler,
    Request,
    build_opener,
)
import uuid

try:
    from scripts.setup_only_live_gate import (
        CleanupLedger,
        CleanupLedgerStore,
        SetupGateError,
        SetupGateManifest,
        add_owned_resource,
        attach_cloud_connection,
        create_manifest,
        new_cleanup_ledger,
        read_manifest,
        record_preflight_status,
        require_setup_only_admission,
        transition_ledger,
        write_manifest,
    )
except ModuleNotFoundError:  # Direct ``python scripts/setup_only_runner.py``.
    from setup_only_live_gate import (  # type: ignore[no-redef]
        CleanupLedger,
        CleanupLedgerStore,
        SetupGateError,
        SetupGateManifest,
        add_owned_resource,
        attach_cloud_connection,
        create_manifest,
        new_cleanup_ledger,
        read_manifest,
        record_preflight_status,
        require_setup_only_admission,
        transition_ledger,
        write_manifest,
    )


MAX_API_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_STDIN_CREDENTIAL_BYTES = 64 * 1024
MANAGEMENT_TOKEN_ENV = "TWIN2MC_MANAGEMENT_BEARER_TOKEN"
CONFIRMATION_HEADER = "X-Twin2MC-Setup-Confirmation"
SAFE_CODE = re.compile(r"^[A-Z0-9_]{3,96}$")

RESOURCE_KIND_BY_RECEIPT_KEY = {
    "aws": {
        "user_name": ("iam_user",),
        "policy_arn": ("managed_policy",),
        "access_key_id": ("access_key",),
    },
    "azure": {
        "application_object_id": ("application",),
        "service_principal_object_id": ("service_principal",),
        "credential_key_id": ("client_secret",),
        "role_definition_id": ("custom_role",),
        "role_assignment_id": ("role_assignment",),
    },
    "gcp": {
        "service_account_email": ("service_account",),
        "key_id": ("service_account_key",),
        "role_name": ("custom_role", "project_binding"),
    },
}


class ManagementApiError(SetupGateError):
    def __init__(self, status: int, code: str | None = None):
        self.status = status
        self.code = code
        suffix = f", code={code}" if code else ""
        super().__init__(f"Management API rejected the setup request (status={status}{suffix}).")


class ManagementClient(Protocol):
    def request(
        self,
        method: str,
        path: str,
        *,
        payload: Mapping[str, Any] | None = None,
        confirmation: str | None = None,
        expected_statuses: tuple[int, ...] = (200,),
    ) -> tuple[int, dict[str, Any] | None]: ...


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        del req, fp, code, msg, headers, newurl
        return None


class UrlManagementClient:
    """Minimal no-proxy, no-redirect JSON client for one Management origin."""

    def __init__(self, base_url: str, bearer_token: str):
        parsed = urlparse(base_url)
        local_http = parsed.scheme == "http" and parsed.hostname in {
            "127.0.0.1",
            "localhost",
            "::1",
        }
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or (parsed.scheme != "https" and not local_http)
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise SetupGateError(
                "Management URL must be HTTPS, or HTTP on an explicit loopback host."
            )
        if (
            not bearer_token
            or len(bearer_token) > 8192
            or any(ord(character) < 32 for character in bearer_token)
        ):
            raise SetupGateError("Management bearer token is missing or invalid.")
        self._base_url = base_url.rstrip("/")
        self._token = bearer_token
        self._opener = build_opener(ProxyHandler({}), _NoRedirect())

    def request(
        self,
        method: str,
        path: str,
        *,
        payload: Mapping[str, Any] | None = None,
        confirmation: str | None = None,
        expected_statuses: tuple[int, ...] = (200,),
    ) -> tuple[int, dict[str, Any] | None]:
        if not path.startswith("/") or "//" in path:
            raise SetupGateError("Management API path is invalid.")
        data = None
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._token}",
        }
        if payload is not None:
            data = json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if confirmation is not None:
            headers[CONFIRMATION_HEADER] = confirmation
        request = Request(
            f"{self._base_url}{path}",
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with self._opener.open(request, timeout=60) as response:
                status = response.status
                body = response.read(MAX_API_RESPONSE_BYTES + 1)
        except HTTPError as exc:
            body = exc.read(MAX_API_RESPONSE_BYTES + 1)
            if exc.code not in expected_statuses:
                raise ManagementApiError(exc.code, _safe_error_code(body)) from exc
            status = exc.code
        except (OSError, URLError) as exc:
            raise SetupGateError("Management API could not be reached safely.") from exc
        if len(body) > MAX_API_RESPONSE_BYTES:
            raise SetupGateError("Management API response exceeded the safe size limit.")
        if status not in expected_statuses:
            raise ManagementApiError(status, _safe_error_code(body))
        if not body:
            return status, None
        try:
            document = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SetupGateError("Management API returned invalid JSON.") from exc
        if not isinstance(document, dict):
            raise SetupGateError("Management API response must be a JSON object.")
        return status, document


def prepare(
    *,
    client: ManagementClient,
    provider: str,
    mode: str,
    target: Mapping[str, str],
    manifest_path: Path,
    ledger_path: Path,
) -> SetupGateManifest:
    """Create guide/session and local evidence without provider credentials."""

    if _path_exists(manifest_path) or _path_exists(ledger_path):
        raise SetupGateError(
            "Manifest and ledger outputs must be new paths; reconcile prior evidence first."
        )
    _, guide = client.request(
        "POST",
        f"/cloud-bootstrap/{provider}/guide",
        payload={"target": dict(target)},
    )
    if guide is None or guide.get("provider") != provider or guide.get("target") != dict(target):
        raise SetupGateError("Management guide does not match the requested provider scope.")
    authority = guide.get("bootstrap_authority_pack")
    deployment = guide.get("generated_deployment_pack")
    if (
        not isinstance(guide.get("guide_digest"), str)
        or not isinstance(authority, dict)
        or not isinstance(authority.get("digest"), str)
        or not isinstance(deployment, dict)
        or not isinstance(deployment.get("digest"), str)
    ):
        raise SetupGateError("Management guide is missing frozen pack references.")
    _, session = client.request(
        "POST",
        "/cloud-bootstrap/sessions",
        payload={
            "provider": provider,
            "target": dict(target),
            "entry_point": "settings",
            "twin_id": None,
            "execution_kind": "setup_only_validation",
            "display_name": f"{provider.upper()} setup-only validation",
            "guide_digest": guide["guide_digest"],
            "bootstrap_authority_pack_digest": authority["digest"],
            "generated_deployment_pack_digest": deployment["digest"],
            "idempotency_key": f"prepare-{provider}-{uuid.uuid4().hex}",
        },
    )
    if session is None:
        raise SetupGateError("Management did not return a setup-only session.")
    session_id = _safe_session_id(session)
    manifest_created = False
    try:
        manifest = create_manifest(
            run_id=_run_id(session_id),
            provider=provider,
            mode=mode,
            target=target,
        )
        _require_guide_matches_manifest(guide, manifest)
        ledger = new_cleanup_ledger(manifest)
        write_manifest(manifest_path, manifest)
        manifest_created = True
        store = CleanupLedgerStore(ledger_path)
        store.create(ledger)
    except (OSError, SetupGateError):
        _best_effort_cancel(client, session_id, session)
        if manifest_created and not _path_exists(ledger_path):
            manifest_path.unlink(missing_ok=True)
        raise

    if mode == "plan_only":
        try:
            client.request(
                "POST",
                f"/cloud-bootstrap/sessions/{session_id}/cancel",
                payload={"expected_revision": _revision(session)},
            )
            ledger = transition_ledger(ledger, "cleanup_required")
            store.save(ledger)
            ledger = transition_ledger(ledger, "cleanup_running")
            store.save(ledger)
            ledger = transition_ledger(ledger, "clean")
            store.save(ledger)
        except SetupGateError:
            if ledger.state == "planned":
                ledger = transition_ledger(ledger, "cleanup_required")
                store.save(ledger)
            raise
    return manifest


def _best_effort_cancel(
    client: ManagementClient,
    session_id: str,
    session: Mapping[str, Any],
) -> None:
    try:
        client.request(
            "POST",
            f"/cloud-bootstrap/sessions/{session_id}/cancel",
            payload={"expected_revision": _revision(session)},
        )
    except SetupGateError:
        return


def execute(
    *,
    client: ManagementClient,
    manifest_path: Path,
    ledger_path: Path,
    confirmation: str,
    credential_origin: str,
    credential: dict[str, Any],
    admission_environment: Mapping[str, str] | None = None,
) -> CleanupLedger:
    """Execute, preflight, and mandatorily clean one setup-only transaction."""

    manifest = read_manifest(manifest_path)
    environment = dict(
        os.environ if admission_environment is None else admission_environment
    )
    environment["TWIN2MC_SETUP_GATE_CONFIRMATION"] = confirmation
    require_setup_only_admission(manifest, environment=environment)
    if credential_origin not in {"dedicated_disposable", "existing_user_owned"}:
        raise SetupGateError("Credential origin is unsupported.")
    if credential.get("provider") != manifest.provider:
        raise SetupGateError("Credential provider does not match the manifest.")

    store = CleanupLedgerStore(ledger_path)
    ledger = store.load(manifest=manifest)
    if ledger.is_clean:
        raise SetupGateError("This setup-only ledger is already clean.")
    session = _find_session(client, manifest)
    session_id = _safe_session_id(session)
    preflight_ready: bool | None = None
    preflight_error = False

    if session.get("state") == "cancelled" and ledger.state in {
        "cleanup_required",
        "cleanup_running",
    }:
        return _reconcile_terminal_cleanup(client, store, ledger, session)

    if session.get("state") in {"draft", "credential_reentry_required"}:
        _, session = client.request(
            "POST",
            f"/cloud-bootstrap/sessions/{session_id}/execute",
            confirmation=confirmation,
            payload={
                "expected_revision": _revision(session),
                "idempotency_key": f"execute-{manifest.provider}-{manifest.run_id}",
                "credential_origin": credential_origin,
                "credential": credential,
            },
        )
        if session is None:
            raise SetupGateError("Management did not return the executed session.")

    if session.get("state") not in {
        "generated_connection_ready",
        "manual_revocation_required",
    }:
        raise SetupGateError("Setup-only session is not recoverable for mandatory cleanup.")

    _, receipt = client.request(
        "GET",
        f"/cloud-bootstrap/sessions/{session_id}/setup-gate-receipt",
        confirmation=confirmation,
    )
    if receipt is None:
        raise SetupGateError("Management did not return a cleanup receipt.")
    if (
        receipt.get("connection_id") is None
        and isinstance(ledger.document["cloud_connection_id"], str)
    ):
        receipt = dict(receipt)
        receipt["connection_id"] = ledger.document["cloud_connection_id"]
    _validate_receipt(receipt, manifest, session_id)
    ledger = _record_receipt(store, ledger, receipt, manifest)

    if ledger.state == "connection_persisted":
        try:
            _, preflight = client.request(
                "POST",
                f"/cloud-connections/{receipt['connection_id']}/preflight",
            )
            if (
                preflight is None
                or preflight.get("id") != receipt["connection_id"]
                or preflight.get("provider") != manifest.provider
                or not isinstance(preflight.get("ready"), bool)
            ):
                raise SetupGateError("Management preflight response is invalid.")
            preflight_ready = bool(preflight and preflight.get("ready") is True)
            ledger = record_preflight_status(
                ledger,
                "passed" if preflight_ready else "failed",
            )
            store.save(ledger)
        except SetupGateError:
            preflight_error = True
            preflight_ready = False
            ledger = record_preflight_status(ledger, "error")
            store.save(ledger)
        if preflight_ready:
            ledger = transition_ledger(ledger, "preflight_passed")
            store.save(ledger)
    if ledger.state == "preflight_passed":
        ledger = transition_ledger(ledger, "cleanup_required")
        store.save(ledger)
    elif ledger.state == "connection_persisted":
        ledger = transition_ledger(ledger, "cleanup_required")
        store.save(ledger)
    elif ledger.state == "cleanup_running":
        ledger = transition_ledger(ledger, "cleanup_required")
        store.save(ledger)
    if ledger.state != "cleanup_required":
        raise SetupGateError(f"Cleanup cannot resume from ledger state {ledger.state}.")

    ledger = transition_ledger(ledger, "cleanup_running")
    store.save(ledger)
    session = _find_session(client, manifest)
    _, cleanup = client.request(
        "POST",
        f"/cloud-bootstrap/sessions/{session_id}/setup-gate-cleanup",
        confirmation=confirmation,
        payload={
            "expected_revision": _revision(session),
            "credential": credential,
        },
    )
    if not _cleanup_is_complete(cleanup, manifest, session_id):
        ledger = transition_ledger(ledger, "cleanup_required")
        store.save(ledger)
        raise SetupGateError(
            "Mandatory setup cleanup remains incomplete; retain the ledger and retry."
        )

    status, _ = client.request(
        "GET",
        f"/cloud-connections/{receipt['connection_id']}",
        expected_statuses=(404,),
    )
    if status != 404:
        ledger = transition_ledger(ledger, "cleanup_required")
        store.save(ledger)
        raise SetupGateError("Local test CloudConnection still exists after cleanup.")
    _, terminal = client.request(
        "GET",
        f"/cloud-bootstrap/sessions/{session_id}",
    )
    if terminal is None or terminal.get("state") != "cancelled" or terminal.get("connection") is not None:
        ledger = transition_ledger(ledger, "cleanup_required")
        store.save(ledger)
        raise SetupGateError("Setup-only session did not reach its clean terminal state.")

    ledger = transition_ledger(ledger, "clean")
    store.save(ledger)
    if ledger.document["preflight_status"] == "error" or preflight_error:
        raise SetupGateError("Generated identity preflight failed safely; mandatory cleanup succeeded.")
    if ledger.document["preflight_status"] == "failed" or preflight_ready is False:
        raise SetupGateError("Generated identity preflight failed; mandatory cleanup succeeded.")
    return ledger


def acknowledge_manual_bootstrap_revocation(
    *,
    client: ManagementClient,
    manifest_path: Path,
    ledger_path: Path,
    confirmation: str,
    admission_environment: Mapping[str, str] | None = None,
) -> CleanupLedger:
    """Close a setup run after an operator manually revoked bootstrap authority."""

    manifest = read_manifest(manifest_path)
    environment = dict(
        os.environ if admission_environment is None else admission_environment
    )
    environment["TWIN2MC_SETUP_GATE_CONFIRMATION"] = confirmation
    require_setup_only_admission(manifest, environment=environment)
    store = CleanupLedgerStore(ledger_path)
    ledger = store.load(manifest=manifest)
    if ledger.is_clean:
        raise SetupGateError("This setup-only ledger is already clean.")
    if ledger.state not in {"cleanup_required", "cleanup_running"}:
        raise SetupGateError(
            "Manual bootstrap revocation can only reconcile an incomplete cleanup."
        )

    session = _find_session(client, manifest)
    if session.get("state") == "cancelled":
        return _reconcile_terminal_cleanup(client, store, ledger, session)
    if (
        session.get("state") != "manual_revocation_required"
        or session.get("connection") is not None
    ):
        raise SetupGateError(
            "Management has not proven provider-generated and local access clean."
        )

    if ledger.state == "cleanup_required":
        ledger = transition_ledger(ledger, "cleanup_running")
        store.save(ledger)
    try:
        _, terminal = client.request(
            "POST",
            f"/cloud-bootstrap/sessions/{_safe_session_id(session)}/"
            "acknowledge-manual-revocation",
            confirmation=confirmation,
            payload={"expected_revision": _revision(session)},
        )
        if (
            terminal is None
            or terminal.get("state") != "cancelled"
            or terminal.get("connection") is not None
        ):
            raise SetupGateError(
                "Manual bootstrap revocation did not reach a clean terminal session."
            )
        connection_id = ledger.document["cloud_connection_id"]
        if not isinstance(connection_id, str):
            raise SetupGateError("Cleanup ledger has no local connection evidence.")
        status, _ = client.request(
            "GET",
            f"/cloud-connections/{connection_id}",
            expected_statuses=(404,),
        )
        if status != 404:
            raise SetupGateError(
                "Local test CloudConnection still exists after manual reconciliation."
            )
    except SetupGateError:
        ledger = transition_ledger(ledger, "cleanup_required")
        store.save(ledger)
        raise

    ledger = transition_ledger(ledger, "clean")
    store.save(ledger)
    if ledger.document["preflight_status"] == "failed":
        raise SetupGateError(
            "Generated identity preflight failed; mandatory cleanup succeeded."
        )
    if ledger.document["preflight_status"] == "error":
        raise SetupGateError(
            "Generated identity preflight failed safely; mandatory cleanup succeeded."
        )
    return ledger


def _reconcile_terminal_cleanup(
    client: ManagementClient,
    store: CleanupLedgerStore,
    ledger: CleanupLedger,
    session: Mapping[str, Any],
) -> CleanupLedger:
    connection_id = ledger.document["cloud_connection_id"]
    if not isinstance(connection_id, str) or session.get("connection") is not None:
        raise SetupGateError("Terminal setup session does not match cleanup evidence.")
    status, _ = client.request(
        "GET",
        f"/cloud-connections/{connection_id}",
        expected_statuses=(404,),
    )
    if status != 404:
        raise SetupGateError("Local test CloudConnection still exists after cleanup.")
    if ledger.state == "cleanup_required":
        ledger = transition_ledger(ledger, "cleanup_running")
        store.save(ledger)
    ledger = transition_ledger(ledger, "clean")
    store.save(ledger)
    if ledger.document["preflight_status"] == "failed":
        raise SetupGateError("Generated identity preflight failed; mandatory cleanup succeeded.")
    if ledger.document["preflight_status"] == "error":
        raise SetupGateError("Generated identity preflight failed safely; mandatory cleanup succeeded.")
    return ledger


def _record_receipt(
    store: CleanupLedgerStore,
    ledger: CleanupLedger,
    receipt: Mapping[str, Any],
    manifest: SetupGateManifest,
) -> CleanupLedger:
    if ledger.state == "planned":
        ledger = transition_ledger(ledger, "authority_validated")
        store.save(ledger)
        for key, provider_id in sorted(receipt["resource_ids"].items()):
            for kind in RESOURCE_KIND_BY_RECEIPT_KEY[manifest.provider][key]:
                ledger = add_owned_resource(
                    ledger,
                    kind=kind,
                    provider_id=provider_id,
                    owner_marker=f"{manifest.run_id}-{kind}",
                )
                store.save(ledger)
        ledger = transition_ledger(ledger, "identity_created")
        store.save(ledger)
        ledger = transition_ledger(ledger, "credential_created")
        store.save(ledger)
        ledger = attach_cloud_connection(ledger, receipt["connection_id"])
        store.save(ledger)
        ledger = transition_ledger(ledger, "connection_persisted")
        store.save(ledger)
    elif ledger.document["cloud_connection_id"] != receipt["connection_id"]:
        raise SetupGateError("Cleanup receipt does not match the durable ledger.")
    return ledger


def _find_session(
    client: ManagementClient,
    manifest: SetupGateManifest,
) -> dict[str, Any]:
    query = urlencode({"provider": manifest.provider})
    _, response = client.request("GET", f"/cloud-bootstrap/sessions?{query}")
    items = response.get("items") if response else None
    if not isinstance(items, list):
        raise SetupGateError("Management session list is invalid.")
    matches = [
        item
        for item in items
        if isinstance(item, dict)
        and isinstance(item.get("id"), str)
        and _run_id(item["id"]) == manifest.run_id
    ]
    if len(matches) != 1:
        raise SetupGateError("Exactly one Management session must match the setup run.")
    return matches[0]


def _validate_receipt(
    receipt: Mapping[str, Any],
    manifest: SetupGateManifest,
    session_id: str,
) -> None:
    if (
        receipt.get("schema_version") != "cloud-bootstrap-setup-receipt.v1"
        or receipt.get("session_id") != session_id
        or receipt.get("provider") != manifest.provider
        or receipt.get("run_id") != manifest.run_id
        or not isinstance(receipt.get("connection_id"), str)
        or not receipt["connection_id"]
        or not isinstance(receipt.get("resource_ids"), dict)
        or not receipt["resource_ids"]
        or not set(receipt["resource_ids"]).issubset(
            RESOURCE_KIND_BY_RECEIPT_KEY[manifest.provider]
        )
        or any(
            not isinstance(value, str)
            or not value
            or len(value) > 512
            or any(ord(character) < 32 for character in value)
            for value in receipt["resource_ids"].values()
        )
    ):
        raise SetupGateError("Management cleanup receipt is invalid or out of scope.")


def _cleanup_is_complete(
    cleanup: Mapping[str, Any] | None,
    manifest: SetupGateManifest,
    session_id: str,
) -> bool:
    if cleanup is None:
        return False
    return (
        cleanup.get("schema_version") == "cloud-bootstrap-setup-cleanup.v1"
        and cleanup.get("session_id") == session_id
        and cleanup.get("provider") == manifest.provider
        and cleanup.get("run_id") == manifest.run_id
        and cleanup.get("generated_access_clean") is True
        and cleanup.get("local_connection_clean") is True
        and cleanup.get("bootstrap_authority_disposal_status")
        in {"revoked", "expires_at_provider", "not_retained_user_managed"}
        and cleanup.get("cleanup_complete") is True
        and cleanup.get("manual_action_required") is False
    )


def _require_guide_matches_manifest(
    guide: Mapping[str, Any],
    manifest: SetupGateManifest,
) -> None:
    authority = guide.get("bootstrap_authority_pack")
    deployment = guide.get("generated_deployment_pack")
    blockers = guide.get("known_blockers")
    expected_api = manifest.document["api_baseline"]
    actual_api = guide.get("api_baseline")
    if (
        not isinstance(authority, dict)
        or not isinstance(deployment, dict)
        or authority.get("id")
        != manifest.document["bootstrap_authority_pack"]["id"]
        or authority.get("digest")
        != manifest.document["bootstrap_authority_pack"]["digest"]
        or deployment.get("id") != manifest.document["deployment_pack"]["id"]
        or deployment.get("digest")
        != manifest.document["deployment_pack"]["digest"]
        or not isinstance(blockers, list)
        or (
            manifest.mode == "setup_only"
            and (
                guide.get("execution_mode") != "supervised_live"
                or any(
                    not isinstance(item, dict) or item.get("blocking") is True
                    for item in blockers
                )
            )
        )
        or (
            expected_api is None
            and actual_api is not None
        )
        or (
            expected_api is not None
            and (
                not isinstance(actual_api, dict)
                or any(
                    actual_api.get(key) != value
                    for key, value in expected_api.items()
                )
            )
        )
    ):
        raise SetupGateError("Management guide does not match the local frozen packs.")


def _safe_session_id(session: Mapping[str, Any]) -> str:
    value = session.get("id")
    if not isinstance(value, str):
        raise SetupGateError("Management session ID is missing.")
    try:
        parsed = uuid.UUID(value)
    except ValueError as exc:
        raise SetupGateError("Management session ID is invalid.") from exc
    if str(parsed) != value.lower():
        raise SetupGateError("Management session ID must use canonical UUID text.")
    return value


def _revision(session: Mapping[str, Any]) -> int:
    value = session.get("revision")
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise SetupGateError("Management session revision is invalid.")
    return value


def _run_id(session_id: str) -> str:
    import hashlib

    return f"twin2mc-e2e-{hashlib.sha256(session_id.encode('utf-8')).hexdigest()[:12]}"


def _read_stdin_credential(stream) -> dict[str, Any]:
    if stream.isatty():
        raise SetupGateError("Bootstrap credential JSON must be piped through stdin.")
    payload = stream.buffer.read(MAX_STDIN_CREDENTIAL_BYTES + 1)
    if len(payload) > MAX_STDIN_CREDENTIAL_BYTES:
        raise SetupGateError("Bootstrap credential JSON exceeds the safe size limit.")
    try:
        document = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SetupGateError("stdin must contain one valid credential JSON object.") from exc
    if not isinstance(document, dict):
        raise SetupGateError("stdin must contain one credential JSON object.")
    return document


def _safe_error_code(body: bytes) -> str | None:
    if len(body) > MAX_API_RESPONSE_BYTES:
        return None
    try:
        document = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    candidates = []
    if isinstance(document, dict):
        candidates.append(document.get("code"))
        detail = document.get("detail")
        if isinstance(detail, dict):
            candidates.append(detail.get("code"))
    return next(
        (
            value
            for value in candidates
            if isinstance(value, str) and SAFE_CODE.fullmatch(value)
        ),
        None,
    )


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
    parser = argparse.ArgumentParser(description="Run the thesis setup-only identity gate.")
    parser.add_argument("--api-url", default="http://127.0.0.1:5005")
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--provider", choices=("aws", "azure", "gcp"), required=True)
    prepare_parser.add_argument("--mode", choices=("plan_only", "setup_only"), required=True)
    prepare_parser.add_argument("--region", required=True)
    prepare_parser.add_argument("--account-id")
    prepare_parser.add_argument("--tenant-id")
    prepare_parser.add_argument("--subscription-id")
    prepare_parser.add_argument("--project-id")
    prepare_parser.add_argument("--manifest", type=Path, required=True)
    prepare_parser.add_argument("--ledger", type=Path, required=True)
    execute_parser = subparsers.add_parser("execute")
    execute_parser.add_argument("--manifest", type=Path, required=True)
    execute_parser.add_argument("--ledger", type=Path, required=True)
    execute_parser.add_argument("--confirm", required=True)
    execute_parser.add_argument(
        "--credential-origin",
        choices=("dedicated_disposable", "existing_user_owned"),
        required=True,
    )
    acknowledge_parser = subparsers.add_parser("acknowledge")
    acknowledge_parser.add_argument("--manifest", type=Path, required=True)
    acknowledge_parser.add_argument("--ledger", type=Path, required=True)
    acknowledge_parser.add_argument("--confirm", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        token = os.environ.get(MANAGEMENT_TOKEN_ENV, "")
        client = UrlManagementClient(args.api_url, token)
        if args.command == "prepare":
            manifest = prepare(
                client=client,
                provider=args.provider,
                mode=args.mode,
                target=_target_from_args(args),
                manifest_path=args.manifest,
                ledger_path=args.ledger,
            )
            print(
                "setup-only-runner: prepared "
                f"(provider={manifest.provider}, mode={manifest.mode}, run_id={manifest.run_id})"
            )
            if manifest.mode == "setup_only":
                print(
                    "setup-only-runner: confirmation "
                    f"{manifest.run_id}:{manifest.provider}:setup_only"
                )
        elif args.command == "execute":
            credential = _read_stdin_credential(sys.stdin)
            try:
                ledger = execute(
                    client=client,
                    manifest_path=args.manifest,
                    ledger_path=args.ledger,
                    confirmation=args.confirm,
                    credential_origin=args.credential_origin,
                    credential=credential,
                )
            finally:
                credential.clear()
            print(
                "setup-only-runner: complete "
                f"(provider={ledger.document['provider']}, state={ledger.state})"
            )
        else:
            ledger = acknowledge_manual_bootstrap_revocation(
                client=client,
                manifest_path=args.manifest,
                ledger_path=args.ledger,
                confirmation=args.confirm,
            )
            print(
                "setup-only-runner: manual cleanup reconciled "
                f"(provider={ledger.document['provider']}, state={ledger.state})"
            )
    except SetupGateError as exc:
        print(f"setup-only-runner: ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
