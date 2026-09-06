"""Deterministic Layer Access fixtures for local UI integration tests only.

This module is imported exclusively when ``ENABLE_TEST_ENDPOINTS=true``.  It
creates no cloud resources and accepts no cloud credentials.
"""

from __future__ import annotations

from datetime import datetime, timezone
import uuid
from typing import Any

from sqlalchemy.orm import Session

from src.models.deployment import Deployment
from src.models.twin import DigitalTwin, TwinState
from src.models.user import User


_PROVIDERS = ("aws", "azure", "gcp")
_SURFACE_MATRIX = {
    ("l4", "aws"): (
        "aws_iot_twinmaker",
        "AWS IoT TwinMaker",
        "aws_identity_center",
        "none",
    ),
    ("l4", "azure"): (
        "azure_digital_twins",
        "Azure Digital Twins Explorer",
        "azure_entra",
        "none",
    ),
    ("l4", "gcp"): (
        "gcp_twin_explorer",
        "GCP Twin Explorer",
        "gcp_iap",
        "none",
    ),
    ("l5", "aws"): (
        "aws_raw_history_reader",
        "AWS Raw-history Reader",
        "aws_sigv4",
        "none",
    ),
    ("l5", "azure"): (
        "azure_raw_history_reader",
        "Azure Raw-history Reader",
        "azure_function_key",
        "none",
    ),
    ("l5", "gcp"): (
        "gcp_raw_history_reader",
        "GCP Raw-history Reader",
        "gcp_identity_token",
        "none",
    ),
}


def _surface(
    run_id: str,
    layer: str,
    provider: str,
    *,
    blocked: bool = False,
) -> dict[str, Any]:
    service_id, display_name, auth_mode, credential_action = _SURFACE_MATRIX[
        (layer, provider)
    ]
    limitations = ["Browser sign-in remains a supervised PoC check."]
    if blocked:
        limitations = [
            "ACCESS_BINDING_BLOCKED",
            "Grant the thesis researcher access, then retry Layer Access.",
        ]
    return {
        "layer": layer,
        "provider": provider,
        "service_id": service_id,
        "display_name": display_name,
        "url": (f"https://{provider}-{layer}-{run_id}.example.invalid/access"),
        "auth": {
            "mode": auth_mode,
            "principal_label": "researcher@example.invalid",
            "credential_action": credential_action,
        },
        "readiness": {
            "resource": "ready",
            "access_binding": "blocked" if blocked else "ready",
            "content": "ready",
            "data_probe": "ready",
            "browser_sign_in": "unverified",
        },
        "capabilities": [
            (
                "Inspect semantic models, state, and relationships."
                if layer == "l4"
                else "Inspect raw history and rollups."
            )
        ],
        "limitations": limitations,
    }


def _evidence(
    run_id: str,
    l4_provider: str,
    l5_provider: str,
    *,
    block_l4: bool = False,
) -> dict[str, Any]:
    return {
        "schema_version": "deployment-access-evidence.v1",
        "profile_id": "six-layer-eventing",
        "profile_version": "1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "surfaces": [
            _surface(run_id, "l4", l4_provider, blocked=block_l4),
            _surface(run_id, "l5", l5_provider),
        ],
    }


def _seed_twin(
    db: Session,
    *,
    owner: User,
    run_id: str,
    label: str,
    l4_provider: str = "aws",
    l5_provider: str = "aws",
    profile_version: str = "1",
    state: TwinState = TwinState.DEPLOYED,
    block_l4: bool = False,
    terraform_outputs: dict[str, Any] | None = None,
) -> DigitalTwin:
    now = datetime.now(timezone.utc)
    twin = DigitalTwin(
        name=f"Layer Access {label} {run_id}",
        user_id=owner.id,
        state=state,
        deployed_at=now if state == TwinState.DEPLOYED else None,
        destroyed_at=now if state == TwinState.DESTROYED else None,
    )
    db.add(twin)
    db.flush()
    deployment = Deployment(
        twin_id=twin.id,
        session_id=f"layer-access-{label}-{run_id}",
        operation_type="test",
        status="success",
        started_at=now,
        completed_at=now,
        profile_id="six-layer-eventing",
        profile_version=profile_version,
        graph_validation={
            "schema_version": "layer-access-test-graph.v1",
            "twin_id": twin.id,
        },
        deployment_access_evidence=(
            _evidence(
                run_id,
                l4_provider,
                l5_provider,
                block_l4=block_l4,
            )
            if profile_version == "1"
            else None
        ),
        terraform_outputs=terraform_outputs
        or {"safe_endpoint": f"https://outputs-{run_id}.example.invalid"},
    )
    db.add(deployment)
    return twin


def seed_layer_access_fixtures(
    db: Session,
    *,
    owner: User,
) -> dict[str, Any]:
    """Seed an isolated complete placement matrix for one authenticated owner."""

    run_id = uuid.uuid4().hex[:12]
    placements: dict[str, str] = {}
    for l4_provider in _PROVIDERS:
        for l5_provider in _PROVIDERS:
            key = f"{l4_provider}-{l5_provider}"
            twin = _seed_twin(
                db,
                owner=owner,
                run_id=run_id,
                label=key,
                l4_provider=l4_provider,
                l5_provider=l5_provider,
                terraform_outputs=(
                    {
                        "safe_endpoint": (f"https://outputs-{run_id}.example.invalid"),
                        # Test-only sentinels prove sensitive Terraform outputs stay redacted.
                        "admin_password": "test-admin-value-must-not-cross-api",  # nosec B105
                        "reader_token": "test-reader-value-must-not-cross-api",  # nosec B105
                    }
                    if key == "aws-aws"
                    else None
                ),
            )
            placements[key] = twin.id

    unsupported = _seed_twin(
        db,
        owner=owner,
        run_id=run_id,
        label="removed-profile-v2",
        profile_version="2",
    )
    destroyed = _seed_twin(
        db,
        owner=owner,
        run_id=run_id,
        label="destroyed",
        state=TwinState.DESTROYED,
    )
    blocked = _seed_twin(
        db,
        owner=owner,
        run_id=run_id,
        label="blocked",
        l4_provider="aws",
        l5_provider="azure",
        block_l4=True,
    )
    foreign_owner = User(
        email=f"foreign-layer-access-{run_id}@example.invalid",
        name="Foreign Layer Access Owner",
    )
    db.add(foreign_owner)
    db.flush()
    foreign = _seed_twin(
        db,
        owner=foreign_owner,
        run_id=run_id,
        label="foreign",
        l4_provider="azure",
        l5_provider="gcp",
    )
    db.commit()

    return {
        "schema_version": "layer-access-test-fixtures.v1",
        "placements": placements,
        "unsupported_twin_id": unsupported.id,
        "destroyed_twin_id": destroyed.id,
        "blocked_twin_id": blocked.id,
        "foreign_owner_twin_id": foreign.id,
        "outputs_twin_id": placements["aws-aws"],
    }
