"""Tests for digest-bound bounded account preparation."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.account_preparation import (
    _enable_gcp_api,
    build_account_preparation_plan,
    execute_account_preparation,
)
from src.core.project_storage import ProjectStorage
from src.operation_packages import inspect_deployment_requirements
from tests.unit.test_operation_packages import _six_layer_archive


def _inspection(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        "file_manager.validator.validate_project_zip",
        lambda _archive, **_kwargs: [],
    )
    return inspect_deployment_requirements(
        "factory",
        _six_layer_archive(),
        project_storage=ProjectStorage(project_root=tmp_path / "projects"),
    )


def test_plan_is_deterministic_bounded_and_explains_persistent_scope(
    monkeypatch,
    tmp_path,
):
    inspection = _inspection(monkeypatch, tmp_path)

    first = build_account_preparation_plan(inspection)
    second = build_account_preparation_plan(inspection)

    assert first == second
    assert first["plan_digest"].startswith("sha256:")
    assert first["requirements_digest"] == inspection.graph_evidence[
        "requirements_digest"
    ]
    assert first["actions"]
    assert {item["provider"] for item in first["actions"]} == {"azure"}
    assert {item["action_type"] for item in first["actions"]} == {
        "register_resource_provider"
    }
    assert all(item["persistent_after_destroy"] for item in first["actions"])
    assert all(not item["destructive"] for item in first["actions"])
    assert any(
        item["capability_id"] == "aws.outbound-identity-federation"
        for item in first["manual_requirements"]
    )


def test_execution_is_digest_bound_and_returns_honest_partial_evidence(
    monkeypatch,
    tmp_path,
):
    inspection = _inspection(monkeypatch, tmp_path)
    plan = build_account_preparation_plan(inspection)
    calls = []
    first_action_id = plan["actions"][0]["action_id"]

    def executor(provider, capability, credentials):
        assert credentials["azure_client_secret"] == "operation-secret"
        calls.append((provider, capability))
        if f"prepare.{provider}.register_resource_provider.{capability}" == first_action_id:
            raise RuntimeError("provider registration temporarily unavailable")
        return {"message": f"{capability} is registered."}

    result = execute_account_preparation(
        "factory",
        _six_layer_archive(),
        expected_plan_digest=plan["plan_digest"],
        confirmed=True,
        executor=executor,
        project_storage=ProjectStorage(project_root=tmp_path / "projects"),
    )

    assert result.status == "partial"
    assert result.retry_safe is True
    assert len(calls) == len(plan["actions"])
    assert [item["action_id"] for item in result.remaining_actions] == [
        first_action_id
    ]
    assert len(result.failed_actions) == 1
    assert "operation-secret" not in str(result)


def test_execution_rejects_missing_confirmation_and_stale_digest(
    monkeypatch,
    tmp_path,
):
    _inspection(monkeypatch, tmp_path)
    archive = _six_layer_archive()
    storage = ProjectStorage(project_root=tmp_path / "projects")

    with pytest.raises(ValueError, match="confirmation"):
        execute_account_preparation(
            "factory",
            archive,
            expected_plan_digest="sha256:" + "0" * 64,
            confirmed=False,
            project_storage=storage,
        )
    with pytest.raises(ValueError, match="stale"):
        execute_account_preparation(
            "factory",
            archive,
            expected_plan_digest="sha256:" + "0" * 64,
            confirmed=True,
            project_storage=storage,
        )


def test_gcp_api_preparation_uses_request_objects_and_waits_for_enable(
    monkeypatch,
):
    calls = []

    class Operation:
        def result(self, *, timeout):
            calls.append(("wait", timeout))

    class ServiceUsageClient:
        def __init__(self, *, credentials):
            calls.append(("client", credentials))

        def get_service(self, *, request):
            calls.append(("get", request))
            return SimpleNamespace(state=SimpleNamespace(name="DISABLED"))

        def enable_service(self, *, request):
            calls.append(("enable", request))
            return Operation()

    credential = object()
    monkeypatch.setattr(
        "google.cloud.service_usage_v1.ServiceUsageClient",
        ServiceUsageClient,
    )
    monkeypatch.setattr(
        "google.oauth2.service_account.Credentials.from_service_account_info",
        lambda _info: credential,
    )

    result = _enable_gcp_api(
        "cloudresourcemanager.googleapis.com",
        {
            "gcp_project_id": "thesis-project",
            "gcp_credentials_file": json.dumps({"type": "service_account"}),
        },
    )

    name = (
        "projects/thesis-project/services/"
        "cloudresourcemanager.googleapis.com"
    )
    assert calls == [
        ("client", credential),
        ("get", {"name": name}),
        ("enable", {"name": name}),
        ("wait", 120),
    ]
    assert result == {
        "message": "cloudresourcemanager.googleapis.com is enabled."
    }


def test_gcp_api_preparation_is_idempotent(monkeypatch):
    calls = []

    class ServiceUsageClient:
        def __init__(self, *, credentials):
            calls.append(("client", credentials))

        def get_service(self, *, request):
            calls.append(("get", request))
            return SimpleNamespace(state=SimpleNamespace(name="ENABLED"))

        def enable_service(self, *, request):  # pragma: no cover - safety guard
            raise AssertionError(f"Unexpected enable request: {request}")

    credential = object()
    monkeypatch.setattr(
        "google.cloud.service_usage_v1.ServiceUsageClient",
        ServiceUsageClient,
    )
    monkeypatch.setattr(
        "google.oauth2.service_account.Credentials.from_service_account_info",
        lambda _info: credential,
    )

    result = _enable_gcp_api(
        "cloudresourcemanager.googleapis.com",
        {
            "gcp_project_id": "thesis-project",
            "gcp_credentials_file": json.dumps({"type": "service_account"}),
        },
    )

    assert len(calls) == 2
    assert calls[1][0] == "get"
    assert result == {
        "message": "cloudresourcemanager.googleapis.com is already enabled."
    }
