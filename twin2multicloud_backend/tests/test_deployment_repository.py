from datetime import datetime, timedelta, timezone

import pytest

from src.models.deployment import Deployment
from src.models.twin import DigitalTwin
from src.models.user import User
from src.repositories.deployment_repository import DeploymentRepository
from src.services.errors import DeploymentPackageBuildFailed


def _create_twin(db) -> DigitalTwin:
    user = User(email=f"user-{datetime.now(timezone.utc).timestamp()}@example.test")
    db.add(user)
    db.commit()
    db.refresh(user)
    twin = DigitalTwin(name="Factory Twin", user_id=user.id)
    db.add(twin)
    db.commit()
    db.refresh(twin)
    return twin


def _graph_evidence(digit: str = "1") -> dict:
    return {
        "graph_schema_version": "resolved-deployment-graph.v1",
        "graph_id": f"graph-{digit}",
        "calculation_run_id": f"run-{digit}",
        "graph_digest": "sha256:" + (digit * 64),
        "architecture_digest": "sha256:" + (digit * 64),
        "profile_id": "five-layer-baseline",
        "profile_version": "1",
        "catalog_id": "baseline-component-catalog",
        "catalog_version": "1",
        "catalog_digest": "sha256:" + (digit * 64),
        "specification_digest": "sha256:" + (digit * 64),
        "package_selection_digest": "sha256:" + (digit * 64),
        "node_count": 7,
        "edge_count": 6,
        "binding_count": 21,
        "stage_ids": ["package", "preplan", "terraform", "postapply"],
    }


def _create_deployment(
    db,
    twin_id: str,
    session_id: str,
    operation_type: str,
    status: str,
    started_at: datetime,
    completed_at: datetime | None = None,
    outputs: dict | None = None,
    operation_id: str | None = None,
    error_code: str | None = None,
) -> Deployment:
    deployment = Deployment(
        twin_id=twin_id,
        session_id=session_id,
        operation_type=operation_type,
        operation_id=operation_id,
        status=status,
        started_at=started_at,
        completed_at=completed_at,
        terraform_outputs=outputs,
        error_code=error_code,
    )
    db.add(deployment)
    db.commit()
    db.refresh(deployment)
    return deployment


def test_create_running_adds_running_deployment_record(db):
    twin = _create_twin(db)
    repository = DeploymentRepository(db)

    deployment = repository.create_running(
        twin_id=twin.id,
        session_id="session-1",
        operation_type="deploy",
        description="real deployment",
    )
    db.commit()
    db.refresh(deployment)

    assert deployment.twin_id == twin.id
    assert deployment.session_id == "session-1"
    assert deployment.operation_type == "deploy"
    assert deployment.status == "running"
    assert deployment.description == "real deployment"


def test_create_running_can_store_deployer_operation_id(db):
    twin = _create_twin(db)
    repository = DeploymentRepository(db)

    deployment = repository.create_running(
        twin_id=twin.id,
        session_id="session-with-op",
        operation_type="deploy",
        operation_id="op-123",
    )
    db.commit()
    db.refresh(deployment)

    assert deployment.operation_id == "op-123"


def test_graph_retry_accepts_identical_frozen_evidence(db):
    twin = _create_twin(db)
    repository = DeploymentRepository(db)
    evidence = _graph_evidence()
    deployment = repository.create_running(
        twin.id,
        "session-identical-graph",
        "deploy",
        graph_evidence=evidence,
    )

    repository.assert_graph_compatible(deployment, dict(evidence))


def test_graph_stage_progress_is_bounded_and_monotonic(db):
    twin = _create_twin(db)
    repository = DeploymentRepository(db)
    deployment = repository.create_running(
        twin.id,
        "session-stage-progress",
        "deploy",
        graph_evidence=_graph_evidence(),
    )

    assert deployment.completed_stage is None
    repository.mark_completed_stage(deployment, "package")
    repository.mark_completed_stage(deployment, "preplan")
    assert deployment.completed_stage == "preplan"
    with pytest.raises(ValueError, match="backwards"):
        repository.mark_completed_stage(deployment, "package")
    with pytest.raises(ValueError, match="Unknown"):
        repository.mark_completed_stage(deployment, "credentials")


def test_graph_retry_rejects_changed_package_selection_digest(db):
    twin = _create_twin(db)
    repository = DeploymentRepository(db)
    deployment = repository.create_running(
        twin.id,
        "session-changed-graph",
        "deploy",
        graph_evidence=_graph_evidence("1"),
    )

    with pytest.raises(DeploymentPackageBuildFailed) as raised:
        repository.assert_graph_compatible(
            deployment,
            _graph_evidence("2"),
        )

    assert raised.value.errors == [
        {
            "code": "DEPLOYMENT_GRAPH_RESUME_MISMATCH",
            "field": "graph_digest",
            "message": "DEPLOYMENT_GRAPH_RESUME_MISMATCH",
        }
    ]


def test_get_latest_successful_outputs_prefers_newest_successful_deploy_or_test(db):
    twin = _create_twin(db)
    now = datetime.now(timezone.utc)
    _create_deployment(
        db,
        twin.id,
        "old-success",
        "deploy",
        "success",
        started_at=now - timedelta(hours=3),
        completed_at=now - timedelta(hours=2),
        outputs={"old": True},
    )
    latest = _create_deployment(
        db,
        twin.id,
        "new-success",
        "test",
        "success",
        started_at=now - timedelta(hours=1),
        completed_at=now,
        outputs={"new": True},
    )
    _create_deployment(
        db,
        twin.id,
        "failed-newer",
        "deploy",
        "failed",
        started_at=now,
        completed_at=now + timedelta(minutes=1),
        outputs={"failed": True},
    )

    deployment = DeploymentRepository(db).get_latest_successful_outputs(twin.id)

    assert deployment.id == latest.id
    assert deployment.terraform_outputs == {"new": True}


def test_list_for_twin_orders_newest_first_and_applies_limit(db):
    twin = _create_twin(db)
    now = datetime.now(timezone.utc)
    oldest = _create_deployment(
        db, twin.id, "oldest", "deploy", "success", now - timedelta(days=2)
    )
    newest = _create_deployment(db, twin.id, "newest", "destroy", "failed", now)
    middle = _create_deployment(
        db, twin.id, "middle", "deploy", "success", now - timedelta(days=1)
    )

    deployments = DeploymentRepository(db).list_for_twin(twin.id, limit=2)

    assert [d.id for d in deployments] == [newest.id, middle.id]
    assert oldest.id not in [d.id for d in deployments]


def test_get_latest_for_twin_returns_newest_operation(db):
    twin = _create_twin(db)
    now = datetime.now(timezone.utc)
    _create_deployment(db, twin.id, "old", "deploy", "success", now - timedelta(days=1))
    latest = _create_deployment(
        db,
        twin.id,
        "new",
        "destroy",
        "failed",
        now,
        operation_id="op-new",
        error_code="DESTRUCTION_ERROR",
    )

    deployment = DeploymentRepository(db).get_latest_for_twin(twin.id)

    assert deployment.id == latest.id
    assert deployment.operation_id == "op-new"
    assert deployment.error_code == "DESTRUCTION_ERROR"


def test_mark_success_records_outputs_and_clears_error(db):
    twin = _create_twin(db)
    repository = DeploymentRepository(db)
    deployment = repository.create_running(twin.id, "session-success", "deploy")
    deployment.error_message = "old error"
    deployment.error_code = "OLD_ERROR"

    repository.mark_success(
        deployment,
        terraform_outputs={"endpoint": {"value": "ok"}},
        operation_id="op-success",
    )
    db.commit()
    db.refresh(deployment)

    assert deployment.status == "success"
    assert deployment.operation_id == "op-success"
    assert deployment.terraform_outputs == {"endpoint": {"value": "ok"}}
    assert deployment.error_code is None
    assert deployment.error_message is None
    assert deployment.completed_at is not None


def test_mark_failed_records_error_and_optional_outputs(db):
    twin = _create_twin(db)
    repository = DeploymentRepository(db)
    deployment = repository.create_running(twin.id, "session-failed", "deploy")

    repository.mark_failed(
        deployment,
        error_message="terraform failed",
        terraform_outputs={"partial": True},
        operation_id="op-failed",
        error_code="TERRAFORM_ERROR",
    )
    db.commit()
    db.refresh(deployment)

    assert deployment.status == "failed"
    assert deployment.operation_id == "op-failed"
    assert deployment.error_code == "TERRAFORM_ERROR"
    assert deployment.error_message == "terraform failed"
    assert deployment.terraform_outputs == {"partial": True}
    assert deployment.completed_at is not None
