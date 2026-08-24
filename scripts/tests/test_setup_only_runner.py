"""Credential-free tests for the two-step setup-only runner."""

from __future__ import annotations

import io
import json
import stat
from urllib.parse import parse_qs, urlparse

import pytest

from scripts.setup_only_live_gate import (
    CleanupLedgerStore,
    SetupGateError,
    create_manifest,
)
from scripts.setup_only_runner import (
    _read_stdin_credential,
    _run_id,
    execute,
    prepare,
)


SESSION_ID = "11111111-1111-4111-8111-111111111111"
TARGETS = {
    "aws": {
        "provider": "aws",
        "account_id": "123456789012",
        "region": "eu-central-1",
    },
    "azure": {
        "provider": "azure",
        "tenant_id": "22222222-2222-4222-8222-222222222222",
        "subscription_id": "33333333-3333-4333-8333-333333333333",
        "region": "westeurope",
    },
    "gcp": {
        "provider": "gcp",
        "mode": "existing_project",
        "project_id": "twin2mc-test-project",
        "region": "europe-west1",
    },
}
RESOURCE_IDS = {
    "aws": {"user_name": f"{_run_id(SESSION_ID)}-deployer"},
    "azure": {"application_object_id": "44444444-4444-4444-8444-444444444444"},
    "gcp": {
        "service_account_email": (
            f"{_run_id(SESSION_ID)}@twin2mc-test-project.iam.gserviceaccount.com"
        )
    },
}


class FakeManagementClient:
    def __init__(
        self,
        provider: str,
        *,
        preflight_ready: bool = True,
        preflight_raises: bool = False,
        cleanup_complete: bool = True,
        execution_mode: str = "supervised_live",
    ):
        self.provider = provider
        self.target = TARGETS[provider]
        self.preflight_ready = preflight_ready
        self.preflight_raises = preflight_raises
        self.cleanup_complete = cleanup_complete
        self.execution_mode = execution_mode
        self.calls: list[str] = []
        self.session = self._session("draft", revision=1, connection=None)
        self.secret_seen_only_in_request = False

    def request(
        self,
        method,
        path,
        *,
        payload=None,
        confirmation=None,
        expected_statuses=(200,),
    ):
        del expected_statuses
        route = urlparse(path).path
        self.calls.append(f"{method} {route}")
        if route == f"/cloud-bootstrap/{self.provider}/guide":
            reference = create_manifest(
                run_id=_run_id(SESSION_ID),
                provider=self.provider,
                mode="setup_only",
                target=self.target,
            ).document
            return 200, {
                "provider": self.provider,
                "target": self.target,
                "execution_mode": self.execution_mode,
                "guide_digest": "sha256:" + ("1" * 64),
                "bootstrap_authority_pack": reference["bootstrap_authority_pack"],
                "generated_deployment_pack": reference["deployment_pack"],
                "api_baseline": reference["api_baseline"],
                "known_blockers": (
                    []
                    if self.execution_mode == "supervised_live"
                    else [{"blocking": True}]
                ),
            }
        if method == "POST" and route == "/cloud-bootstrap/sessions":
            assert payload["execution_kind"] == "setup_only_validation"
            return 200, dict(self.session)
        if method == "GET" and route == "/cloud-bootstrap/sessions":
            assert parse_qs(urlparse(path).query) == {"provider": [self.provider]}
            return 200, {"items": [dict(self.session)]}
        if route.endswith("/execute"):
            assert confirmation == f"{_run_id(SESSION_ID)}:{self.provider}:setup_only"
            serialized = json.dumps(payload)
            assert "submitted-bootstrap-secret" in serialized
            self.secret_seen_only_in_request = True
            connection = {"id": "connection-test-001"}
            self.session = self._session(
                "generated_connection_ready",
                revision=2,
                connection=connection,
            )
            return 200, dict(self.session)
        if route.endswith("/setup-gate-receipt"):
            return 200, {
                "schema_version": "cloud-bootstrap-setup-receipt.v1",
                "session_id": SESSION_ID,
                "provider": self.provider,
                "run_id": _run_id(SESSION_ID),
                "resource_ids": RESOURCE_IDS[self.provider],
                "connection_id": (
                    self.session.get("connection") or {}
                ).get("id"),
            }
        if route == "/cloud-connections/connection-test-001/preflight":
            if self.preflight_raises:
                raise SetupGateError("safe simulated preflight outage")
            return 200, {
                "id": "connection-test-001",
                "provider": self.provider,
                "ready": self.preflight_ready,
            }
        if route.endswith("/setup-gate-cleanup"):
            assert "submitted-bootstrap-secret" in json.dumps(payload)
            if self.cleanup_complete:
                self.session = self._session("cancelled", revision=4, connection=None)
            else:
                self.session = self._session(
                    "manual_revocation_required",
                    revision=4,
                    connection={"id": "connection-test-001"},
                )
            return 200, {
                "schema_version": "cloud-bootstrap-setup-cleanup.v1",
                "session_id": SESSION_ID,
                "provider": self.provider,
                "run_id": _run_id(SESSION_ID),
                "generated_access_clean": self.cleanup_complete,
                "local_connection_clean": self.cleanup_complete,
                "bootstrap_authority_disposal_status": (
                    "revoked" if self.cleanup_complete else "manual_revocation_required"
                ),
                "cleanup_complete": self.cleanup_complete,
                "manual_action_required": not self.cleanup_complete,
            }
        if method == "GET" and route == "/cloud-connections/connection-test-001":
            return 404, {"detail": "not found"}
        if method == "GET" and route == f"/cloud-bootstrap/sessions/{SESSION_ID}":
            return 200, dict(self.session)
        if route.endswith("/cancel"):
            self.session = self._session("cancelled", revision=2, connection=None)
            return 200, dict(self.session)
        raise AssertionError(f"Unexpected fake Management request: {method} {path}")

    def _session(self, state: str, *, revision: int, connection):
        return {
            "id": SESSION_ID,
            "provider": self.provider,
            "revision": revision,
            "state": state,
            "connection": connection,
        }


@pytest.mark.parametrize("provider", ["aws", "azure", "gcp"])
def test_runner_prepares_executes_preflights_and_cleans_without_secret_artifacts(
    tmp_path,
    provider,
):
    client = FakeManagementClient(provider)
    manifest_path = tmp_path / "manifest.json"
    ledger_path = tmp_path / "private" / "ledger.json"
    manifest = prepare(
        client=client,
        provider=provider,
        mode="setup_only",
        target=TARGETS[provider],
        manifest_path=manifest_path,
        ledger_path=ledger_path,
    )
    confirmation = f"{manifest.run_id}:{provider}:setup_only"
    credential = {
        "provider": provider,
        "secret": "submitted-bootstrap-secret",
    }

    ledger = execute(
        client=client,
        manifest_path=manifest_path,
        ledger_path=ledger_path,
        confirmation=confirmation,
        credential_origin="dedicated_disposable",
        credential=credential,
        admission_environment={"TWIN2MC_SETUP_GATE_ENABLED": "1"},
    )

    assert ledger.is_clean
    assert stat.S_IMODE(manifest_path.stat().st_mode) == 0o600
    assert stat.S_IMODE(ledger_path.stat().st_mode) == 0o600
    assert client.secret_seen_only_in_request is True
    assert client.calls.index("POST /cloud-connections/connection-test-001/preflight") < client.calls.index(
        f"POST /cloud-bootstrap/sessions/{SESSION_ID}/setup-gate-cleanup"
    )
    evidence = manifest_path.read_text() + ledger_path.read_text()
    assert "submitted-bootstrap-secret" not in evidence
    assert CleanupLedgerStore(ledger_path).load(manifest=manifest).is_clean


@pytest.mark.parametrize("preflight_raises", [False, True])
def test_preflight_failure_still_cleans_and_records_clean_evidence(
    tmp_path,
    preflight_raises,
):
    client = FakeManagementClient(
        "aws",
        preflight_ready=False,
        preflight_raises=preflight_raises,
    )
    manifest_path = tmp_path / "manifest.json"
    ledger_path = tmp_path / "private" / "ledger.json"
    manifest = prepare(
        client=client,
        provider="aws",
        mode="setup_only",
        target=TARGETS["aws"],
        manifest_path=manifest_path,
        ledger_path=ledger_path,
    )

    with pytest.raises(SetupGateError, match="cleanup succeeded"):
        execute(
            client=client,
            manifest_path=manifest_path,
            ledger_path=ledger_path,
            confirmation=f"{manifest.run_id}:aws:setup_only",
            credential_origin="dedicated_disposable",
            credential={
                "provider": "aws",
                "secret": "submitted-bootstrap-secret",
            },
            admission_environment={"TWIN2MC_SETUP_GATE_ENABLED": "1"},
        )

    assert CleanupLedgerStore(ledger_path).load(manifest=manifest).is_clean
    assert any(call.endswith("/setup-gate-cleanup") for call in client.calls)


def test_cleanup_failure_remains_resumable_and_blocks_clean_claim(tmp_path):
    client = FakeManagementClient("aws", cleanup_complete=False)
    manifest_path = tmp_path / "manifest.json"
    ledger_path = tmp_path / "private" / "ledger.json"
    manifest = prepare(
        client=client,
        provider="aws",
        mode="setup_only",
        target=TARGETS["aws"],
        manifest_path=manifest_path,
        ledger_path=ledger_path,
    )

    with pytest.raises(SetupGateError, match="remains incomplete"):
        execute(
            client=client,
            manifest_path=manifest_path,
            ledger_path=ledger_path,
            confirmation=f"{manifest.run_id}:aws:setup_only",
            credential_origin="dedicated_disposable",
            credential={
                "provider": "aws",
                "secret": "submitted-bootstrap-secret",
            },
            admission_environment={"TWIN2MC_SETUP_GATE_ENABLED": "1"},
        )

    ledger = CleanupLedgerStore(ledger_path).load(manifest=manifest)
    assert ledger.state == "cleanup_required"
    assert ledger.document["cloud_connection_id"] == "connection-test-001"


def test_plan_only_cancels_session_and_never_calls_execute_or_preflight(tmp_path):
    client = FakeManagementClient("gcp")
    manifest_path = tmp_path / "manifest.json"
    ledger_path = tmp_path / "private" / "ledger.json"
    manifest = prepare(
        client=client,
        provider="gcp",
        mode="plan_only",
        target=TARGETS["gcp"],
        manifest_path=manifest_path,
        ledger_path=ledger_path,
    )

    assert manifest.mode == "plan_only"
    assert CleanupLedgerStore(ledger_path).load(manifest=manifest).is_clean
    assert not any(call.endswith("/execute") for call in client.calls)
    assert not any(call.endswith("/preflight") for call in client.calls)
    assert any(call.endswith("/cancel") for call in client.calls)


def test_setup_prepare_rejects_non_live_or_blocked_management_and_cancels(tmp_path):
    client = FakeManagementClient("aws", execution_mode="deterministic_fake")
    manifest_path = tmp_path / "manifest.json"
    ledger_path = tmp_path / "private" / "ledger.json"

    with pytest.raises(SetupGateError, match="frozen packs"):
        prepare(
            client=client,
            provider="aws",
            mode="setup_only",
            target=TARGETS["aws"],
            manifest_path=manifest_path,
            ledger_path=ledger_path,
        )

    assert not manifest_path.exists()
    assert not ledger_path.exists()
    assert any(call.endswith("/cancel") for call in client.calls)


def test_stdin_reader_rejects_tty_and_clears_no_command_line_path():
    class PipedInput:
        buffer = io.BytesIO(b'{"provider":"aws","secret":"sentinel"}')

        @staticmethod
        def isatty():
            return False

    class TtyInput(PipedInput):
        @staticmethod
        def isatty():
            return True

    assert _read_stdin_credential(PipedInput())["provider"] == "aws"
    with pytest.raises(SetupGateError, match="piped through stdin"):
        _read_stdin_credential(TtyInput())
