"""Atomic capacity and readiness coverage for Five-layer v2 RDS output."""

from __future__ import annotations

import json
from itertools import product

import pytest

from backend.architecture_profiles.diagnostics import ArchitectureResolutionError
from backend.architecture_profiles.five_layer_v2_workload import (
    CONTRACT_ROOT as WORKLOAD_ROOT,
    resolve_five_layer_v2_workload,
)
from backend.architecture_profiles.registry import ArchitectureProfileRegistry
from backend.deployment_specification.five_layer_v2_builder import (
    CONTRACT_ROOT as RDS_ROOT,
    LOGICAL_COMPONENTS,
    build_five_layer_v2_deployment_specification,
)


CASES = {
    "single-cloud-aws-small": (
        {logical: "aws" for logical in LOGICAL_COMPONENTS},
        "small",
    ),
    "two-cloud-azure-l3l5-gcp-l4-medium": (
        {
            logical: "gcp" if logical == "component.twin-state" else "azure"
            for logical in LOGICAL_COMPONENTS
        },
        "medium",
    ),
    "three-cloud-mixed-large": (
        {
            "component.ingestion": "aws",
            "component.processing": "azure",
            "component.hot-storage": "gcp",
            "component.cool-storage": "aws",
            "component.archive-storage": "azure",
            "component.twin-state": "aws",
            "component.visualization": "gcp",
        },
        "large",
    ),
}
EXPECTED_STORAGE_TASK_COUNTS = {
    "single-cloud-aws-small": ("aws.ecs-fargate-storage-mover", 1),
    "two-cloud-azure-l3l5-gcp-l4-medium": (
        "azure.container-apps-scheduled-storage-job",
        4,
    ),
    "three-cloud-mixed-large": ("gcp.cloud-run-storage-job", 3),
}


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _build(case_id, *, status="offline_contract_fixture", gates=frozenset(), ru=None):
    assignment, size = CASES[case_id]
    fixture = _read(RDS_ROOT / "fixtures" / "valid" / f"{case_id}.json")
    workload = resolve_five_layer_v2_workload(
        _read(WORKLOAD_ROOT / "fixtures" / "valid" / f"core-{size}.json")
    )
    registry = ArchitectureProfileRegistry(profile_version="2")
    return build_five_layer_v2_deployment_specification(
        calculation_run_id=fixture["calculation_run_id"],
        assignment=assignment,
        resolved_workload=workload,
        architecture_profile_ref={
            "id": registry.profile["profile_id"],
            "version": registry.profile["profile_version"],
            "digest": registry.profile["content_digest"],
        },
        component_catalog_ref={
            "id": registry.catalog["catalog_id"],
            "version": registry.catalog["catalog_version"],
            "digest": registry.catalog["content_digest"],
        },
        workload_contract_digest=registry.profile["workload_contract_ref"]["digest"],
        pricing_evidence_digests={
            item["provider"]: item["digest"]
            for item in fixture["optimization_context"]["pricing_evidence_refs"]
        },
        resolution_status=status,
        definition_lifecycle_statuses={
            "profile": registry.profile["lifecycle_status"],
            "catalog": registry.catalog["lifecycle_status"],
            **{
                f"provider:{provider}": registry.provider(provider)["lifecycle_status"]
                for provider in set(assignment.values())
            },
        },
        satisfied_live_gate_ids=gates,
        azure_large_autoscale_ru_per_second=ru,
    )


@pytest.mark.parametrize("case_id", tuple(CASES))
def test_builder_matches_frozen_atomic_selections_and_dimensions(case_id):
    actual = _build(case_id)
    expected = _read(RDS_ROOT / "fixtures" / "valid" / f"{case_id}.json")

    assert actual["component_selections"] == expected["component_selections"]
    assert actual["bindings"] == expected["bindings"]
    assert actual["fixed_dimensions"] == expected["fixed_dimensions"]
    assert set(actual["readiness"]["blocking_gate_ids"]) == set(
        expected["readiness"]["blocking_gate_ids"]
    )
    assert len(
        {
            selection["implementation_component_id"]
            for selection in actual["component_selections"]
        }
    ) == len(actual["component_selections"])


@pytest.mark.parametrize("case_id", tuple(CASES))
def test_builder_binds_exact_provider_storage_task_count(case_id):
    specification = _build(case_id)
    component_id, expected = EXPECTED_STORAGE_TASK_COUNTS[case_id]
    selection = next(
        item
        for item in specification["component_selections"]
        if item["implementation_component_id"] == component_id
    )
    task_count = next(
        dimension["value"]
        for dimension in selection["dimensions"]
        if dimension["dimension_id"].endswith(".task_count")
    )

    assert task_count == expected


def test_single_cloud_omits_remote_only_event_transport():
    specification = _build("single-cloud-aws-small")
    component_ids = {
        item["implementation_component_id"]
        for item in specification["component_selections"]
    }

    assert "aws.kinesis-only-for-reviewed-remote-telemetry-edge" not in component_ids
    assert "aws.sns-fifo-only-for-reviewed-remote-control-edge" not in component_ids
    assert "aws.sqs-fifo" in component_ids
    assert "aws.lambda-event-adapter" in component_ids


def test_large_gcp_uses_sixteen_firestore_timestamp_shards():
    specification = _build("three-cloud-mixed-large")
    shard_dimensions = [
        dimension
        for selection in specification["component_selections"]
        for dimension in selection["dimensions"]
        if dimension["dimension_id"].endswith(".timestamp_shards")
    ]

    assert shard_dimensions
    assert {item["value"] for item in shard_dimensions} == {16}


def test_large_azure_requires_measured_positive_autoscale_ru_before_ready():
    assignment = {logical: "azure" for logical in LOGICAL_COMPONENTS}
    source_fixture = _read(
        RDS_ROOT / "fixtures" / "valid" / "three-cloud-mixed-large.json"
    )
    workload = resolve_five_layer_v2_workload(
        _read(WORKLOAD_ROOT / "fixtures" / "valid" / "core-large.json")
    )
    registry = ArchitectureProfileRegistry(profile_version="2")
    kwargs = {
        "calculation_run_id": source_fixture["calculation_run_id"],
        "assignment": assignment,
        "resolved_workload": workload,
        "architecture_profile_ref": {
            "id": registry.profile["profile_id"],
            "version": registry.profile["profile_version"],
            "digest": registry.profile["content_digest"],
        },
        "component_catalog_ref": {
            "id": registry.catalog["catalog_id"],
            "version": registry.catalog["catalog_version"],
            "digest": registry.catalog["content_digest"],
        },
        "workload_contract_digest": registry.profile["workload_contract_ref"]["digest"],
        "pricing_evidence_digests": {"azure": "sha256:" + ("a" * 64)},
    }
    offline = build_five_layer_v2_deployment_specification(**kwargs)
    assert (
        "gate.live-capacity.azure.cosmos-autoscale-ru"
        in offline["readiness"]["blocking_gate_ids"]
    )
    offline_autoscale = next(
        dimension
        for selection in offline["component_selections"]
        for dimension in selection["dimensions"]
        if dimension["dimension_id"].endswith(".autoscale_max_ru_per_second")
    )
    assert offline_autoscale["value"] == 108000

    with pytest.raises(ArchitectureResolutionError) as raised:
        build_five_layer_v2_deployment_specification(
            **kwargs,
            resolution_status="deployment_ready",
        )
    assert raised.value.code == "ARCH_NO_ADMISSIBLE_CANDIDATE"

    with pytest.raises(ArchitectureResolutionError) as raised:
        build_five_layer_v2_deployment_specification(
            **kwargs,
            resolution_status="deployment_ready",
            definition_lifecycle_statuses={
                "profile": "active",
                "catalog": "active",
                "provider:azure": "active",
            },
            satisfied_live_gate_ids=frozenset(
                offline["readiness"]["blocking_gate_ids"]
            ),
        )
    assert raised.value.code == "ARCH_NO_ADMISSIBLE_CANDIDATE"

    ready = build_five_layer_v2_deployment_specification(
        **kwargs,
        resolution_status="deployment_ready",
        definition_lifecycle_statuses={
            "profile": "active",
            "catalog": "active",
            "provider:azure": "active",
        },
        satisfied_live_gate_ids=frozenset(offline["readiness"]["blocking_gate_ids"]),
        azure_large_autoscale_ru_per_second=108000,
        azure_large_autoscale_evidence_digest="sha256:" + ("b" * 64),
    )
    assert ready["readiness"] == {
        "status": "deployment_ready",
        "blocking_gate_ids": [],
    }
    autoscale = next(
        dimension
        for selection in ready["component_selections"]
        for dimension in selection["dimensions"]
        if dimension["dimension_id"].endswith(".autoscale_max_ru_per_second")
    )
    assert autoscale["value"] == 108000
    assert autoscale["evidence_reference"] == "sha256:" + ("b" * 64)
    mover = next(
        item
        for item in ready["component_selections"]
        if item["implementation_component_id"]
        == "azure.container-apps-scheduled-storage-job"
    )
    task_count = next(
        dimension["value"]
        for dimension in mover["dimensions"]
        if dimension["dimension_id"].endswith(".task_count")
    )
    assert task_count == 30


@pytest.mark.parametrize("size", ("small", "medium", "large"))
def test_all_729_assignments_build_for_each_core_size(size):
    workload = resolve_five_layer_v2_workload(
        _read(WORKLOAD_ROOT / "fixtures" / "valid" / f"core-{size}.json")
    )
    registry = ArchitectureProfileRegistry(profile_version="2")
    profile_ref = {
        "id": registry.profile["profile_id"],
        "version": registry.profile["profile_version"],
        "digest": registry.profile["content_digest"],
    }
    catalog_ref = {
        "id": registry.catalog["catalog_id"],
        "version": registry.catalog["catalog_version"],
        "digest": registry.catalog["content_digest"],
    }
    count = 0
    # L5 is fixed to L3 hot. The other six slots remain independent.
    for providers in product(("aws", "azure", "gcp"), repeat=6):
        assignment = dict(zip(LOGICAL_COMPONENTS[:-1], providers, strict=True))
        assignment["component.visualization"] = assignment["component.hot-storage"]
        selected = set(assignment.values())
        specification = build_five_layer_v2_deployment_specification(
            calculation_run_id="018f0f5e-7b5e-7b2d-9f0b-7f66c2a88a01",
            assignment=assignment,
            resolved_workload=workload,
            architecture_profile_ref=profile_ref,
            component_catalog_ref=catalog_ref,
            workload_contract_digest=registry.profile["workload_contract_ref"][
                "digest"
            ],
            pricing_evidence_digests={
                provider: "sha256:"
                + ({"aws": "a", "azure": "b", "gcp": "c"}[provider] * 64)
                for provider in selected
            },
        )
        assert specification["readiness"]["status"] == "offline_contract_fixture"
        count += 1

    assert count == 729
