from __future__ import annotations

from datetime import datetime, timezone
import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from src.api.models.deployment import (
    DeploymentOperation,
    DeploymentResult,
    DeploymentStreamEvent,
)
from src.deployment_access import (
    DeploymentAccessProjectionError,
    collect_deployment_access_runtime_evidence,
    project_deployment_access_evidence,
)


FIXED_TIME = datetime(2026, 7, 31, 12, 0, tzinfo=timezone.utc)


class _Config:
    def __init__(self, l4: str, l5: str):
        self.providers = {"layer_4_provider": l4, "layer_5_provider": l5}

    def get_provider_for_layer(self, layer: str) -> str:
        return self.providers[f"layer_{layer}_provider"]


def _context(
    l4: str,
    l5: str,
    *,
    profile_id: str = "six-layer-eventing",
    version: str = "1",
) -> SimpleNamespace:
    return SimpleNamespace(
        config=_Config(l4, l5),
        resolved_deployment_graph=SimpleNamespace(
            profile_ref={"id": profile_id, "version": version}
        ),
    )


def _internal(
    resource: str,
    binding: str,
    artifact: str,
    content: str,
    probe: str,
) -> dict:
    return {
        "resource_ref": resource,
        "access_binding_refs": [binding],
        "artifact_refs": [artifact],
        "content_revision": content,
        "data_probe_revision": probe,
    }


def _outputs() -> dict:
    return {
        "aws_component_twin_state_output": {
            "workspace_id": "aws-twin-workspace",
            "access_url": "https://eu-central-1.console.aws.amazon.com/iottwinmaker/home",
            "principal_label": "researcher@example.invalid",
            "internal_evidence": _internal(
                "aws-twin-workspace",
                "aws-account-assignment",
                "Twin2MultiCloudPoCDevice",
                "aws-l4-seed.v1",
                "aws-twinmaker-readback.v1",
            ),
        },
        "aws_component_visualization_output": {
            "access_url": "https://reader.lambda-url.eu-central-1.on.aws/",
            "reader_function_name": "factory-six-layer-raw-history-reader",
            "principal_label": "arn:aws:iam::123456789012:user/researcher",
            "access_role": "AWS IAM signed read-only invocation",
            "internal_evidence": _internal(
                "arn:aws:lambda:eu-central-1:123456789012:function:reader",
                "https://reader.lambda-url.eu-central-1.on.aws/",
                "aws-six-layer-runtime.zip",
                "raw-history-query.v1",
                "aws-raw-history-readback.v1",
            ),
        },
        "azure_component_twin_state_output": {
            "instance_name": "azure-twin-instance",
            "endpoint": "https://azure-twin.api.weu.digitaltwins.azure.net",
            "access_url": "https://explorer.digitaltwins.azure.net/?eid=azure-twin.api.weu.digitaltwins.azure.net",
            "principal_label": "researcher@example.invalid",
            "access_role": "Azure Digital Twins Data Reader",
            "internal_evidence": _internal(
                "azure-twin-instance",
                "azure-twin-role-assignment",
                "dtmi:twin2multicloud:poc:TwinNode;1",
                "azure-l4-seed.v1",
                "azure-adt-readback.v1",
            ),
        },
        "azure_component_visualization_output": {
            "access_url": "https://reader.azurewebsites.net/api/raw-history/v1",
            "reader_function_name": "reader",
            "principal_label": "00000000-0000-4000-8000-000000000002",
            "access_role": "Function key resolved by the deployment principal",
            "internal_evidence": _internal(
                "/subscriptions/example/resourceGroups/example/providers/Microsoft.Web/sites/reader",
                "/subscriptions/example/resourceGroups/example/providers/Microsoft.Web/sites/reader",
                "azure-six-layer-runtime.zip",
                "raw-history-query.v1",
                "azure-raw-history-readback.v1",
            ),
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
            "internal_evidence": _internal(
                "gcp-twin-explorer",
                "gcp-iap-binding",
                "platform-image@sha256:abc",
                "gcp-l4-seed.v1",
                "gcp-twin-explorer-readback.v1",
            ),
        },
        "gcp_component_visualization_output": {
            "service": "Cloud Run bounded raw-history reader",
            "access_url": "https://reader-example-ew.a.run.app/raw-history/v1",
            "principal_label": "deployer@example.iam.gserviceaccount.com",
            "authentication": "Google identity token",
            "access_role": "Cloud Run Invoker",
            "reader_service_id": "projects/example/locations/europe-west1/services/reader",
            "internal_evidence": _internal(
                "projects/example/locations/europe-west1/services/reader",
                "projects/example/locations/europe-west1/services/reader roles/run.invoker",
                "platform@sha256:abc",
                "raw-history-query.v1",
                "gcp-raw-history-readback.v1",
            ),
        },
        "unrelated_password": "must-not-cross",
    }


@pytest.mark.parametrize("l4", ["aws", "azure", "gcp"])
@pytest.mark.parametrize("l5", ["aws", "azure", "gcp"])
@pytest.mark.parametrize(
    ("profile_id", "version"),
    [("six-layer-eventing", "1")],
)
def test_projects_exact_two_safe_surfaces_for_all_nine_placements(
    l4: str, l5: str, profile_id: str, version: str
) -> None:
    outputs = _outputs()
    outputs[f"{l4}_component_twin_state_output"]["admin_password"] = "must-not-cross"

    evidence = project_deployment_access_evidence(
        _context(l4, l5, profile_id=profile_id, version=version),
        outputs,
        generated_at=FIXED_TIME,
    )

    assert evidence is not None
    assert (evidence["profile_id"], evidence["profile_version"]) == (
        profile_id,
        version,
    )
    assert evidence["generated_at"] == "2026-07-31T12:00:00Z"
    assert [(item["layer"], item["provider"]) for item in evidence["surfaces"]] == [
        ("l4", l4),
        ("l5", l5),
    ]
    assert all(
        item["readiness"]["content"] == "pending" for item in evidence["surfaces"]
    )
    serialized = json.dumps(evidence)
    assert "must-not-cross" not in serialized
    assert "reader_url" not in serialized
    assert "certificate_sha256" not in serialized
    assert "internal_evidence" not in serialized


@pytest.mark.parametrize("l4", ["aws", "azure", "gcp"])
@pytest.mark.parametrize("l5", ["aws", "azure", "gcp"])
@pytest.mark.parametrize(
    ("profile_id", "version"),
    [("six-layer-eventing", "1")],
)
def test_successful_runtime_gates_mark_all_nine_placements_content_ready(
    l4: str, l5: str, profile_id: str, version: str
) -> None:
    context = _context(l4, l5, profile_id=profile_id, version=version)
    outputs = _outputs()
    context.deployment_access_runtime_evidence = (
        collect_deployment_access_runtime_evidence(context, outputs)
    )

    evidence = project_deployment_access_evidence(
        context,
        outputs,
        generated_at=FIXED_TIME,
    )

    assert evidence is not None
    assert all(
        surface["readiness"]["content"] == "ready"
        and surface["readiness"]["data_probe"] == "ready"
        for surface in evidence["surfaces"]
    )


def test_unknown_profile_has_no_deployer_access_evidence() -> None:
    assert (
        project_deployment_access_evidence(
            _context("aws", "aws", profile_id="unknown-profile", version="1"),
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


def test_gcp_surface_does_not_project_unrelated_internal_fields() -> None:
    outputs = _outputs()
    outputs["gcp_component_visualization_output"]["internal_secrets_output"] = True

    evidence = project_deployment_access_evidence(
        _context("aws", "gcp"), outputs, generated_at=FIXED_TIME
    )
    assert evidence is not None
    assert "internal_secrets_output" not in json.dumps(evidence)


def test_projection_rejects_stale_runtime_evidence() -> None:
    context = _context("aws", "azure")
    outputs = _outputs()
    context.deployment_access_runtime_evidence = (
        collect_deployment_access_runtime_evidence(context, outputs)
    )
    outputs["azure_component_visualization_output"]["internal_evidence"][
        "content_revision"
    ] = "tampered.v2"

    with pytest.raises(DeploymentAccessProjectionError, match="does not match"):
        project_deployment_access_evidence(context, outputs, generated_at=FIXED_TIME)


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


def test_synchronous_result_redacts_internal_rotation_secret() -> None:
    result = DeploymentResult(
        project_name="factory",
        provider="terraform",
        operation_id="operation-1",
        terraform_outputs={
            "gcp_grafana_rotation_secret": {"admin_password": "must-not-cross"},
            "gcp_component_visualization_output": {
                "endpoint": "https://grafana.example.invalid"
            },
        },
    )

    assert result.terraform_outputs == {
        "gcp_grafana_rotation_secret": "[REDACTED]",
        "gcp_component_visualization_output": {
            "endpoint": "https://grafana.example.invalid"
        },
    }
