"""Closed candidate enumeration and completeness-gate coverage."""

from __future__ import annotations

import copy
import json
from typing import Any

import pytest

from backend.architecture_profiles import contracts
from backend.architecture_profiles.diagnostics import ArchitectureResolutionError
from backend.architecture_profiles.five_layer_strategy import (
    FiveLayerCompletePathStrategy,
)
from backend.architecture_profiles.registry import ArchitectureProfileRegistry
from backend.architecture_profiles.strategy import build_resolution_context


RUN_ID = "018f0f5e-7b5e-7b2d-9f0b-7f66c2a88a01"
LAYER_KEYS = (
    "L1",
    "L2",
    "L3_hot",
    "L3_cool",
    "L3_archive",
    "L4",
    "L5",
)


def _read(name: str) -> dict[str, Any]:
    return json.loads(
        (
            contracts.CONTRACT_ROOT
            / "fixtures"
            / "valid"
            / name
        ).read_text(encoding="utf-8")
    )


def _registry() -> ArchitectureProfileRegistry:
    return ArchitectureProfileRegistry(
        profile=_read("five-layer-baseline-profile.json"),
        catalog=_read("baseline-component-catalog.json"),
        providers={
            "aws": _read("aws-baseline-provider-profile.json"),
            "azure": _read("azure-baseline-provider-profile.json"),
        },
    )


def _context(
    registry: ArchitectureProfileRegistry,
    *,
    aws_region: str = "eu-central-1",
):
    context = build_resolution_context(
        registry=registry,
        calculation_run_id=RUN_ID,
        architecture_profile={
            "profileId": registry.profile["profile_id"],
            "profileVersion": registry.profile["profile_version"],
            "contentDigest": registry.profile["content_digest"],
        },
        extension_bindings=[
            {
                "slotId": "processor.telemetry",
                "slotVersion": "1",
                "artifactId": "artifact.user.processor.example",
                "artifactDigest": "sha256:" + ("1" * 64),
                "configurationDigest": "sha256:" + ("2" * 64),
            }
        ],
    )
    return context.with_execution_inputs(
        layer_options={
            layer: (("AWS", 1.0), ("Azure", 1.0))
            for layer in LAYER_KEYS
        },
        provider_regions={
            "aws": aws_region,
            "azure": "westeurope",
            "gcp": "europe-west1",
        },
    )


def test_enumeration_is_deterministic_and_component_complete():
    registry = _registry()
    context = _context(registry)
    strategy = FiveLayerCompletePathStrategy(registry.profile)
    strategy.validate_request(context)

    candidates = strategy.enumerate_candidates(context)

    assert len(candidates) == 128
    assert candidates[0].candidate_id == "aws|aws|aws|aws|aws|aws|aws"
    assert candidates[-1].candidate_id == (
        "azure|azure|azure|azure|azure|azure|azure"
    )
    assert all(len(candidate.components) == 7 for candidate in candidates)


def test_completeness_rejects_unmapped_edges_before_ranking():
    registry = _registry()
    context = _context(registry)
    strategy = FiveLayerCompletePathStrategy(registry.profile)
    candidates = strategy.enumerate_candidates(context)
    complete = []
    rejected = []

    for candidate in candidates:
        try:
            complete.append(
                strategy.validate_functional_completeness(
                    candidate,
                    context,
                )
            )
        except ArchitectureResolutionError as exc:
            rejected.append((candidate.candidate_id, exc.code))

    assert [candidate.candidate_id for candidate in complete] == [
        "aws|aws|aws|aws|aws|aws|aws",
        "aws|azure|azure|azure|azure|azure|azure",
        "azure|azure|azure|azure|azure|azure|azure",
    ]
    assert len(rejected) == 125
    assert {code for _, code in rejected} == {
        "ARCH_EDGE_IMPLEMENTATION_MISSING"
    }
    assert all(len(candidate.edges) == 6 for candidate in complete)


def test_region_mismatch_removes_provider_options_fail_closed():
    registry = _registry()
    context = _context(registry, aws_region="us-east-1")
    strategy = FiveLayerCompletePathStrategy(registry.profile)

    candidates = strategy.enumerate_candidates(context)

    assert [candidate.candidate_id for candidate in candidates] == [
        "azure|azure|azure|azure|azure|azure|azure"
    ]


def test_component_without_required_extension_slot_is_not_admissible():
    catalog = copy.deepcopy(_read("baseline-component-catalog.json"))
    for component in catalog["components"]:
        if component["logical_component_ids"] == ["component.processing"]:
            component["extension_slot_refs"] = []
    catalog["content_digest"] = contracts.calculate_digest(catalog)
    registry = ArchitectureProfileRegistry(
        profile=_read("five-layer-baseline-profile.json"),
        catalog=catalog,
        providers={
            "aws": _read("aws-baseline-provider-profile.json"),
            "azure": _read("azure-baseline-provider-profile.json"),
        },
    )
    strategy = FiveLayerCompletePathStrategy(registry.profile)

    with pytest.raises(ArchitectureResolutionError) as raised:
        strategy.enumerate_candidates(_context(registry))

    assert raised.value.code == "ARCH_COMPONENT_CANDIDATE_MISSING"


def test_repository_profiles_cannot_bypass_unsupported_state():
    registry = ArchitectureProfileRegistry()
    context = build_resolution_context(
        registry=registry,
        calculation_run_id=RUN_ID,
        architecture_profile={
            "profileId": registry.profile["profile_id"],
            "profileVersion": registry.profile["profile_version"],
            "contentDigest": registry.profile["content_digest"],
        },
        extension_bindings=[
            {
                "slotId": "processor.telemetry",
                "slotVersion": "1",
                "artifactId": "artifact.user.processor.example",
                "artifactDigest": "sha256:" + ("1" * 64),
                "configurationDigest": "sha256:" + ("2" * 64),
            }
        ],
    )
    strategy = FiveLayerCompletePathStrategy(registry.profile)

    with pytest.raises(ArchitectureResolutionError) as raised:
        strategy.validate_request(context)

    assert raised.value.code == "ARCH_PROVIDER_IMPLEMENTATION_MISSING"
