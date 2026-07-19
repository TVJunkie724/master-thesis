"""Closed component-option construction for the five-layer baseline."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from itertools import product
from typing import Any, Mapping

from .diagnostics import ArchitectureResolutionError
from .strategy import ArchitectureResolutionContext


BASELINE_LAYER_COMPONENTS: tuple[tuple[str, str, str], ...] = (
    ("L1", "l1_ingestion", "component.ingestion"),
    ("L2", "l2_processing", "component.processing"),
    ("L3_hot", "l3_hot_storage", "component.hot-storage"),
    ("L3_cool", "l3_cool_storage", "component.cool-storage"),
    ("L3_archive", "l3_archive_storage", "component.archive-storage"),
    ("L4", "l4_twin_state", "component.twin-state"),
    ("L5", "l5_visualization", "component.visualization"),
)
_PROVIDER_ORDER = ("aws", "azure", "gcp")
_PROVIDER_LABELS = {
    "AWS": "aws",
    "Azure": "azure",
    "GCP": "gcp",
}


@dataclass(frozen=True)
class ComponentOption:
    layer_key: str
    slot_id: str
    logical_component_id: str
    responsibility_id: str
    provider: str
    region: str
    provider_profile: Mapping[str, Any]
    provider_mapping: Mapping[str, Any]
    catalog_component: Mapping[str, Any]
    cost: Decimal

    @property
    def deployment_component_id(self) -> str:
        return str(self.catalog_component["deployment_component_id"])

    @property
    def canonical_assignment_key(self) -> tuple[str, str, str]:
        return (
            self.logical_component_id,
            self.provider,
            self.deployment_component_id,
        )


@dataclass(frozen=True)
class ArchitectureCandidate:
    candidate_id: str
    components: tuple[ComponentOption, ...]

    @property
    def canonical_assignment_key(
        self,
    ) -> tuple[tuple[str, str, str], ...]:
        return tuple(
            sorted(
                option.canonical_assignment_key
                for option in self.components
            )
        )

    def component(self, logical_component_id: str) -> ComponentOption:
        for option in self.components:
            if option.logical_component_id == logical_component_id:
                return option
        raise KeyError(logical_component_id)


def enumerate_component_candidates(
    context: ArchitectureResolutionContext,
) -> tuple[ArchitectureCandidate, ...]:
    """Enumerate deterministic component-complete provider assignments."""

    if context.layer_options is None or context.provider_regions is None:
        raise RuntimeError(
            "Architecture execution inputs must be bound before enumeration"
        )
    expected_slots = tuple(
        slot_id for _, slot_id, _ in BASELINE_LAYER_COMPONENTS
    )
    if tuple(context.profile["optimization_slot_ids"]) != expected_slots:
        raise ArchitectureResolutionError(
            "ARCH_PROFILE_BUNDLE_INCOMPATIBLE",
            "optimization_slot_ids",
            "Profile optimization slots differ from the baseline adapter",
        )
    expected_layers = {
        layer_key for layer_key, _, _ in BASELINE_LAYER_COMPONENTS
    }
    if set(context.layer_options) != expected_layers:
        raise ArchitectureResolutionError(
            "ARCH_WORKLOAD_INCOMPATIBLE",
            "layerOptions",
            "Calculation results do not cover the baseline optimization slots",
        )

    profile_components = {
        str(item["component_id"]): item
        for item in context.profile["components"]
    }
    profile_slots = {
        str(item["slot_id"]): item
        for item in context.profile["extension_slots"]
    }
    catalog_components = {
        str(item["deployment_component_id"]): item
        for item in context.catalog["components"]
    }
    option_matrix: list[tuple[ComponentOption, ...]] = []
    for layer_key, slot_id, logical_component_id in BASELINE_LAYER_COMPONENTS:
        logical = profile_components.get(logical_component_id)
        if logical is None:
            raise ArchitectureResolutionError(
                "ARCH_COMPONENT_CANDIDATE_MISSING",
                logical_component_id,
                "Baseline logical component is missing from the profile",
            )
        costs = {
            _provider_key(label): cost
            for label, cost in context.layer_options[layer_key]
        }
        options = tuple(
            option
            for provider in _PROVIDER_ORDER
            if (
                option := _build_component_option(
                    context=context,
                    layer_key=layer_key,
                    slot_id=slot_id,
                    logical=logical,
                    provider=provider,
                    cost=costs.get(provider),
                    catalog_components=catalog_components,
                    profile_slots=profile_slots,
                )
            )
            is not None
        )
        if not options:
            raise ArchitectureResolutionError(
                "ARCH_COMPONENT_CANDIDATE_MISSING",
                logical_component_id,
                "No supported provider has a complete component mapping",
            )
        option_matrix.append(options)

    candidates = []
    for selected in product(*option_matrix):
        candidate_id = "|".join(option.provider for option in selected)
        candidates.append(
            ArchitectureCandidate(
                candidate_id=candidate_id,
                components=tuple(selected),
            )
        )
    return tuple(candidates)


def _build_component_option(
    *,
    context: ArchitectureResolutionContext,
    layer_key: str,
    slot_id: str,
    logical: Mapping[str, Any],
    provider: str,
    cost: Decimal | None,
    catalog_components: Mapping[str, Mapping[str, Any]],
    profile_slots: Mapping[str, Mapping[str, Any]],
) -> ComponentOption | None:
    profile = context.provider_profiles.get(provider)
    region = context.provider_regions.get(provider) if context.provider_regions else None
    if (
        cost is None
        or profile is None
        or profile["lifecycle_status"] != "active"
        or profile["supported"] is not True
        or not isinstance(region, str)
    ):
        return None
    mapping = next(
        (
            item
            for item in profile["component_mappings"]
            if item["component_id"] == logical["component_id"]
        ),
        None,
    )
    if mapping is None:
        return None
    if not _provider_profile_is_compatible(
        context=context,
        provider_profile=profile,
    ):
        return None
    required_capabilities = set(logical["required_capability_ids"])
    if not required_capabilities.issubset(
        set(mapping["provided_capability_ids"])
    ):
        return None
    expected_region_id = f"region.{provider}.{region}"
    if expected_region_id not in mapping["supported_region_ids"]:
        return None
    candidates = tuple(mapping["deployment_component_candidates"])
    if len(candidates) != 1:
        return None
    component = catalog_components.get(candidates[0])
    if not _component_is_complete(
        component=component,
        provider=provider,
        logical_component_id=str(logical["component_id"]),
        slot_id=slot_id,
        mapping=mapping,
        required_extension_slots={
            (
                extension_slot_id,
                str(profile_slots[extension_slot_id]["slot_version"]),
            )
            for extension_slot_id in logical["extension_slot_ids"]
            if extension_slot_id in profile_slots
        },
        architecture_profile_ref=(
            context.profile_ref.profile_id,
            context.profile_ref.profile_version,
        ),
        provider_profile_ref=(
            str(profile["implementation_profile_id"]),
            str(profile["implementation_profile_version"]),
        ),
    ):
        return None
    return ComponentOption(
        layer_key=layer_key,
        slot_id=slot_id,
        logical_component_id=str(logical["component_id"]),
        responsibility_id=str(logical["responsibility_id"]),
        provider=provider,
        region=region,
        provider_profile=profile,
        provider_mapping=mapping,
        catalog_component=component,
        cost=cost,
    )


def _component_is_complete(
    *,
    component: Mapping[str, Any] | None,
    provider: str,
    logical_component_id: str,
    slot_id: str,
    mapping: Mapping[str, Any],
    required_extension_slots: set[tuple[str, str]],
    architecture_profile_ref: tuple[str, str],
    provider_profile_ref: tuple[str, str],
) -> bool:
    if (
        component is None
        or component["provider"] != provider
        or logical_component_id not in component["logical_component_ids"]
        or not component["service_id"]
        or not component["formula_refs"]
        or not component["pricing_model_refs"]
        or not component["required_permission_capabilities"]
        or not component["package_artifact_ref"]
        or not mapping["formula_refs"]
        or not mapping["service_model_refs"]
    ):
        return False
    catalog_bindings = {
        binding["component_id"]
        for binding in component["deployment_specification_bindings"]
        if binding["slot_id"] in {slot_id, "transition_runtime"}
        and binding["specification_schema_version"]
        == "resolved-deployment-specification.v1"
    }
    mapped_bindings = set(mapping["deployment_specification_component_ids"])
    if not mapped_bindings or not mapped_bindings.issubset(catalog_bindings):
        return False
    if not set(mapping["formula_refs"]).issubset(
        set(component["formula_refs"])
    ):
        return False
    catalog_extension_slots = {
        (str(reference["id"]), str(reference["version"]))
        for reference in component["extension_slot_refs"]
    }
    if not required_extension_slots.issubset(catalog_extension_slots):
        return False
    compatibility = component["compatibility"]
    if (
        architecture_profile_ref
        not in {
            (str(item["id"]), str(item["version"]))
            for item in compatibility["architecture_profile_versions"]
        }
        or provider_profile_ref
        not in {
            (str(item["id"]), str(item["version"]))
            for item in compatibility["provider_profile_versions"]
        }
        or "resolved-deployment-specification.v1"
        not in compatibility["deployment_specification_versions"]
    ):
        return False
    return True


def _provider_profile_is_compatible(
    *,
    context: ArchitectureResolutionContext,
    provider_profile: Mapping[str, Any],
) -> bool:
    compatibility = provider_profile["compatibility"]
    return (
        (
            str(context.catalog["catalog_id"]),
            str(context.catalog["catalog_version"]),
        )
        in {
            (str(item["id"]), str(item["version"]))
            for item in compatibility["compatible_catalog_versions"]
        }
        and "resolved-deployment-specification.v1"
        in compatibility["compatible_deployment_specification_versions"]
        and "1" in compatibility["compatible_resolver_versions"]
        and "1" in compatibility["compatible_runtime_versions"]
    )


def _provider_key(label: str) -> str:
    try:
        return _PROVIDER_LABELS[label]
    except KeyError as exc:
        raise ArchitectureResolutionError(
            "ARCH_PROVIDER_IMPLEMENTATION_MISSING",
            "layerOptions",
            "Calculation result contains an unknown provider label",
        ) from exc
