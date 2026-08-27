"""Tests for digest-bound bounded account preparation."""

from pathlib import Path

import pytest

from src.account_preparation import (
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
