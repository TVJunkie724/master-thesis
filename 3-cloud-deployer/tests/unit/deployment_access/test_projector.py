from __future__ import annotations

from datetime import datetime, timezone
import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from src.api.models.deployment import DeploymentOperation, DeploymentStreamEvent
from src.deployment_access import (
    DeploymentAccessProjectionError,
    project_deployment_access_evidence,
)


FIXED_TIME = datetime(2026, 7, 31, 12, 0, tzinfo=timezone.utc)


class _Config:
    def __init__(self, l4: str, l5: str):
        self.providers = {"layer_4_provider": l4, "layer_5_provider": l5}

    def get_provider_for_layer(self, layer: str) -> str:
        return self.providers[f"layer_{layer}_provider"]


def _context(l4: str, l5: str, *, version: str = "2") -> SimpleNamespace:
    return SimpleNamespace(
        config=_Config(l4, l5),
        resolved_deployment_graph=SimpleNamespace(
            profile_ref={"id": "five-layer-baseline", "version": version}
        ),
    )


def _outputs() -> dict:
    return {
        "aws_component_twin_state_output": {
            "workspace_id": "aws-twin-workspace",
            "access_url": "https://eu-central-1.console.aws.amazon.com/iottwinmaker/home",
            "principal_label": "researcher@example.invalid",
        },
        "aws_component_visualization_output": {
            "workspace_id": "aws-grafana-workspace",
            "access_url": "https://g-example.grafana-workspace.eu-central-1.amazonaws.com/d/t2mc-raw-rollups/raw-rollups",
            "reader_url": "https://reader.lambda-url.eu-central-1.on.aws/",
            "principal_label": "researcher@example.invalid",
        },
        "azure_component_twin_state_output": {
            "instance_name": "azure-twin-instance",
            "endpoint": "https://azure-twin.api.weu.digitaltwins.azure.net",
            "access_url": "https://explorer.digitaltwins.azure.net/?eid=azure-twin.api.weu.digitaltwins.azure.net",
            "principal_label": "researcher@example.invalid",
            "access_role": "Azure Digital Twins Data Reader",
        },
        "azure_component_visualization_output": {
            "workspace_name": "azure-grafana-workspace",
            "access_url": "https://example.westeurope.grafana.azure.com/d/t2mc-raw-rollups/raw-rollups",
            "workspace_url": "https://example.westeurope.grafana.azure.com",
            "reader_url": "https://reader.azurewebsites.net/api/raw-history/v1",
            "reader_function_name": "reader",
            "principal_label": "researcher@example.invalid",
            "access_role": "Grafana Viewer",
        },
        "gcp_component_twin_state_output": {
            "service": "Cloud Run Twin API + read-only IAP Twin Explorer",
            "materializer_service_id": "projects/example/locations/europe-west1/services/materializer",
            "explorer_url": "https://twin-explorer-example-ew.a.run.app",
            "principal_label": "user:researcher@example.invalid",
            "authentication": "Google Identity-Aware Proxy",
            "capabilities": ["models", "twins"],
            "limitations": ["read-only"],
            "seed_revision": "gcp-l4-seed.v1",
            "seed_input_digest": "0" * 64,
        },
        "gcp_component_visualization_output": {
            "service": "Grafana OSS 12 on GKE",
            "endpoint": "https://grafana.example.invalid",
            "viewer_username": "researcher@example.invalid",
            "authentication": "Grafana local Viewer credential",
            "certificate_sha256": "1" * 64,
            "source_cidrs": ["203.0.113.0/24"],
            "dashboard_uid": "twin2multicloud-raw-rollups",
            "dashboard_title": "Twin2MultiCloud Raw & Rollups",
            "reader_service_id": "projects/example/locations/europe-west1/services/reader",
            "viewer_credential": "owner-scoped rotate-and-reveal operation required",
            "internal_secrets_output": False,
            "replica_count": 1,
            "persistent_disk_gib": 10,
        },
        "unrelated_password": "must-not-cross",
    }


@pytest.mark.parametrize("l4", ["aws", "azure", "gcp"])
@pytest.mark.parametrize("l5", ["aws", "azure", "gcp"])
def test_projects_exact_two_safe_surfaces_for_all_nine_placements(
    l4: str, l5: str
) -> None:
    outputs = _outputs()
    outputs[f"{l4}_component_twin_state_output"]["admin_password"] = "must-not-cross"

    evidence = project_deployment_access_evidence(
        _context(l4, l5), outputs, generated_at=FIXED_TIME
    )

    assert evidence is not None
    assert evidence["generated_at"] == "2026-07-31T12:00:00Z"
    assert [(item["layer"], item["provider"]) for item in evidence["surfaces"]] == [
        ("l4", l4),
        ("l5", l5),
    ]
    assert all(item["readiness"]["content"] == "pending" for item in evidence["surfaces"])
    serialized = json.dumps(evidence)
    assert "must-not-cross" not in serialized
    assert "reader_url" not in serialized
    assert "certificate_sha256" not in serialized


def test_historical_profile_has_no_deployer_access_evidence() -> None:
    assert (
        project_deployment_access_evidence(
            _context("aws", "aws", version="1"),
            _outputs(),
            generated_at=FIXED_TIME,
        )
        is None
    )


def test_selected_surface_requires_exact_safe_output_bundle() -> None:
    outputs = _outputs()
    del outputs["azure_component_twin_state_output"]["principal_label"]

    with pytest.raises(DeploymentAccessProjectionError, match="principal_label"):
        project_deployment_access_evidence(
            _context("azure", "aws"), outputs, generated_at=FIXED_TIME
        )


def test_gcp_surface_rejects_internal_secret_output_claim() -> None:
    outputs = _outputs()
    outputs["gcp_component_visualization_output"]["internal_secrets_output"] = True

    with pytest.raises(DeploymentAccessProjectionError, match="internal secrets"):
        project_deployment_access_evidence(
            _context("aws", "gcp"), outputs, generated_at=FIXED_TIME
        )


def test_stream_model_revalidates_evidence_before_serializing() -> None:
    evidence = project_deployment_access_evidence(
        _context("aws", "aws"), _outputs(), generated_at=FIXED_TIME
    )
    assert evidence is not None
    evidence["surfaces"][0]["access_token"] = "must-not-cross"

    with pytest.raises(ValidationError):
        DeploymentStreamEvent.complete(
            DeploymentOperation.deploy,
            deployment_access_evidence=evidence,
        )
