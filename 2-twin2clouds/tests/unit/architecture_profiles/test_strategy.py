"""Strategy registry and immutable request-boundary tests."""

from __future__ import annotations

import copy
import json
from typing import Any

import pytest

from backend.architecture_profiles import contracts
from backend.architecture_profiles.diagnostics import (
    ArchitectureResolutionError,
    RejectionCollector,
)
from backend.architecture_profiles.registry import ArchitectureProfileRegistry
from backend.architecture_profiles.strategy import (
    ArchitectureProfileRef,
    ArchitectureStrategyRegistry,
    build_resolution_context,
)
from backend.architecture_profiles.five_layer_strategy import (
    FiveLayerCompletePathStrategy,
    validate_architecture_strategy_readiness,
)


RUN_ID = "018f0f5e-7b5e-7b2d-9f0b-7f66c2a88a01"


def _read(name: str) -> dict[str, Any]:
    return json.loads(
        (
            contracts.CONTRACT_ROOT
            / "fixtures"
            / "valid"
            / name
        ).read_text(encoding="utf-8")
    )


def _supported_fixture_registry() -> ArchitectureProfileRegistry:
    return ArchitectureProfileRegistry(
        profile=_read("five-layer-baseline-profile.json"),
        catalog=_read("baseline-component-catalog.json"),
        providers={
            "aws": _read("aws-baseline-provider-profile.json"),
            "azure": _read("azure-baseline-provider-profile.json"),
        },
    )


def _profile_ref(registry: ArchitectureProfileRegistry) -> dict[str, str]:
    return {
        "profileId": registry.profile["profile_id"],
        "profileVersion": registry.profile["profile_version"],
        "contentDigest": registry.profile["content_digest"],
    }


def _extension_binding() -> dict[str, str]:
    return {
        "slotId": "processor.telemetry",
        "slotVersion": "1",
        "artifactId": "018f0f5e-7b5e-7b2d-9f0b-7f66c2a88a02",
        "artifactDigest": "sha256:" + ("1" * 64),
        "configurationDigest": "sha256:" + ("2" * 64),
    }


class _Strategy:
    strategy_id = "test"

    def __init__(self, profile_ref: ArchitectureProfileRef):
        self.supported_profile_refs = frozenset({profile_ref})

    def validate_request(self, context):  # pragma: no cover - protocol shape
        return None

    def enumerate_candidates(self, context):  # pragma: no cover
        return ()

    def validate_functional_completeness(self, candidate, context):  # pragma: no cover
        return candidate

    def calculate_candidate(self, candidate, context):  # pragma: no cover
        return candidate

    def resolve_edges(self, candidate, context):  # pragma: no cover
        return candidate

    def build_resolution(self, winner, context):  # pragma: no cover
        return {}


def test_context_loads_only_exact_repository_references():
    registry = _supported_fixture_registry()

    context = build_resolution_context(
        registry=registry,
        calculation_run_id=RUN_ID,
        architecture_profile=_profile_ref(registry),
        extension_bindings=[_extension_binding()],
    )

    assert context.calculation_run_id == RUN_ID
    assert context.profile_ref.profile_id == "five-layer-baseline"
    assert tuple(context.provider_profiles) == ("aws", "azure")
    assert context.extension_bindings[0].logical_component_id == (
        "component.processing"
    )
    assert context.extension_bindings[0].validation_contract_version == "1"


@pytest.mark.parametrize(
    ("mutation", "code"),
    (
        ({"contentDigest": "sha256:" + ("0" * 64)}, "ARCH_PROFILE_DIGEST_MISMATCH"),
        ({"profileId": "unknown"}, "ARCH_PROFILE_NOT_FOUND"),
        ({"components": []}, "ARCH_PROFILE_NOT_FOUND"),
    ),
)
def test_context_rejects_non_exact_profile_references(mutation, code):
    registry = _supported_fixture_registry()
    reference = _profile_ref(registry)
    reference.update(mutation)

    with pytest.raises(ArchitectureResolutionError) as raised:
        build_resolution_context(
            registry=registry,
            calculation_run_id=RUN_ID,
            architecture_profile=reference,
            extension_bindings=[_extension_binding()],
        )

    assert raised.value.code == code


def test_context_rejects_missing_or_client_expanded_extension_bindings():
    registry = _supported_fixture_registry()

    for bindings in ([], [{**_extension_binding(), "source": "forbidden"}]):
        with pytest.raises(ArchitectureResolutionError) as raised:
            build_resolution_context(
                registry=registry,
                calculation_run_id=RUN_ID,
                architecture_profile=_profile_ref(registry),
                extension_bindings=bindings,
            )
        assert raised.value.code == "ARCH_EXTENSION_BINDING_INVALID"


def test_strategy_registry_is_exact_frozen_and_duplicate_safe():
    registry = _supported_fixture_registry()
    strategy = _Strategy(ArchitectureProfileRef.from_profile(registry.profile))
    strategies = ArchitectureStrategyRegistry()
    strategies.register(registry.profile, strategy)

    with pytest.raises(RuntimeError, match="Duplicate"):
        strategies.register(registry.profile, strategy)

    strategies.freeze()
    assert strategies.resolve(registry.profile) is strategy
    with pytest.raises(RuntimeError, match="frozen"):
        strategies.register(registry.profile, strategy)


def test_strategy_registry_rejects_bundle_drift():
    registry = _supported_fixture_registry()
    strategy = _Strategy(ArchitectureProfileRef.from_profile(registry.profile))
    strategies = ArchitectureStrategyRegistry()
    strategies.register(registry.profile, strategy)
    strategies.freeze()
    drifted = dict(registry.profile)
    drifted["optimization_bundle"] = dict(registry.profile["optimization_bundle"])
    drifted["optimization_bundle"]["formula_set_version"] = "2"

    with pytest.raises(ArchitectureResolutionError) as raised:
        strategies.resolve(drifted)

    assert raised.value.code == "ARCH_PROFILE_BUNDLE_INCOMPATIBLE"


def test_rejection_diagnostics_are_bounded_and_code_only():
    collector = RejectionCollector()
    for index in range(40):
        collector.record(
            "ARCH_EDGE_IMPLEMENTATION_MISSING",
            f"candidate:{index:02d}",
        )

    diagnostics = collector.freeze()
    assert diagnostics.rejected_candidate_count == 40
    assert len(diagnostics.representative_candidate_ids) == 25
    assert diagnostics.to_dict()["rejectedByErrorCode"] == {
        "ARCH_EDGE_IMPLEMENTATION_MISSING": 40
    }


def test_startup_readiness_resolves_only_the_reviewed_strategy_bundle():
    strategies = validate_architecture_strategy_readiness(
        _supported_fixture_registry()
    )

    assert strategies.resolve(
        _supported_fixture_registry().profile
    ).strategy_id == "five-layer-complete-path.v1"


@pytest.mark.parametrize(
    "mutation",
    (
        lambda profile: profile.update(
            {"content_digest": "sha256:" + ("0" * 64)}
        ),
        lambda profile: profile["optimization_bundle"].update(
            {"formula_set_version": "2"}
        ),
    ),
)
def test_five_layer_strategy_rejects_unreviewed_startup_drift(mutation):
    profile = copy.deepcopy(_read("five-layer-baseline-profile.json"))
    mutation(profile)

    with pytest.raises(RuntimeError, match="drifted"):
        FiveLayerCompletePathStrategy(profile)
