"""HTTP contract tests for pure graph-requirement inspection."""

from fastapi.testclient import TestClient

import rest_api
from src.account_preparation import AccountPreparationResult
from src.operation_packages import DeploymentRequirementsInspection


client = TestClient(rest_api.app)


def test_inspection_returns_only_digest_bound_requirement_contract(monkeypatch):
    seen = {}

    def inspect(project_name, content):
        seen.update(project_name=project_name, content=content)
        return DeploymentRequirementsInspection(
            project_name=project_name,
            warnings=("review",),
            graph_evidence={
                "graph_schema_version": "resolved-deployment-graph.v1",
                "graph_digest": "sha256:" + "1" * 64,
                "requirements_digest": "sha256:" + "2" * 64,
                "requirement_count": 1,
            },
            requirements=(
                {
                    "requirement_id": "requirement.provider-scope.aws",
                    "requirement_type": "provider_scope",
                    "provider": "aws",
                    "capability_id": "aws.target-scope",
                    "scope": "account",
                    "preparation_mode": "none",
                    "mandatory": True,
                    "source_node_ids": ["node.aws"],
                    "source_edge_ids": [],
                    "region": "",
                    "attributes": {"target_type": "account"},
                },
            ),
            preparation_plan={
                "schema_version": "graph-account-preparation.v1",
                "graph_digest": "sha256:" + "1" * 64,
                "requirements_digest": "sha256:" + "2" * 64,
                "plan_digest": "sha256:" + "3" * 64,
                "actions": [],
                "manual_requirements": [],
            },
        )

    monkeypatch.setattr(
        "src.api.validation_requirements.inspect_deployment_requirements",
        inspect,
    )

    response = client.post(
        "/validate/deployment-requirements?project_name=factory",
        files={"file": ("deployment.zip", b"archive", "application/zip")},
    )

    assert response.status_code == 200
    assert seen == {"project_name": "factory", "content": b"archive"}
    assert response.json() == {
        "project_name": "factory",
        "warnings": ["review"],
        "graph_evidence": {
            "graph_schema_version": "resolved-deployment-graph.v1",
            "graph_digest": "sha256:" + "1" * 64,
            "requirements_digest": "sha256:" + "2" * 64,
            "requirement_count": 1,
        },
        "requirements": [
            {
                "requirement_id": "requirement.provider-scope.aws",
                "requirement_type": "provider_scope",
                "provider": "aws",
                "capability_id": "aws.target-scope",
                "scope": "account",
                "preparation_mode": "none",
                "mandatory": True,
                "source_node_ids": ["node.aws"],
                "source_edge_ids": [],
                "region": "",
                "attributes": {"target_type": "account"},
            }
        ],
        "preparation_plan": {
            "schema_version": "graph-account-preparation.v1",
            "graph_digest": "sha256:" + "1" * 64,
            "requirements_digest": "sha256:" + "2" * 64,
            "plan_digest": "sha256:" + "3" * 64,
            "actions": [],
            "manual_requirements": [],
        },
    }


def test_inspection_rejects_invalid_package(monkeypatch):
    def reject(_project_name, _content):
        raise ValueError("DEPLOYMENT_MANIFEST_REQUIRED")

    monkeypatch.setattr(
        "src.api.validation_requirements.inspect_deployment_requirements",
        reject,
    )

    response = client.post(
        "/validate/deployment-requirements?project_name=factory",
        files={"file": ("deployment.zip", b"invalid", "application/zip")},
    )

    assert response.status_code == 400
    assert "DEPLOYMENT_MANIFEST_REQUIRED" in response.json()["detail"]


def test_account_preparation_requires_and_forwards_confirmation(monkeypatch):
    seen = {}
    plan_digest = "sha256:" + "3" * 64

    def prepare(project_name, content, **kwargs):
        seen.update(project_name=project_name, content=content, **kwargs)
        return AccountPreparationResult(
            project_name=project_name,
            plan_digest=plan_digest,
            requirements_digest="sha256:" + "2" * 64,
            status="ready",
            completed_actions=(),
            failed_actions=(),
            remaining_actions=(),
        )

    monkeypatch.setattr(
        "src.api.validation_requirements.execute_account_preparation",
        prepare,
    )

    response = client.post(
        "/infrastructure/account-preparation?project_name=factory",
        data={"expected_plan_digest": plan_digest, "confirmed": "true"},
        files={"file": ("deployment.zip", b"archive", "application/zip")},
    )

    assert response.status_code == 200
    assert seen == {
        "project_name": "factory",
        "content": b"archive",
        "expected_plan_digest": plan_digest,
        "confirmed": True,
    }
    assert response.json()["retry_safe"] is True
