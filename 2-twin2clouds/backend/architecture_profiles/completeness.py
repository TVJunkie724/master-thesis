"""Functional-completeness and edge coverage for architecture candidates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .candidate_factory import ArchitectureCandidate, ComponentOption
from .diagnostics import ArchitectureResolutionError
from .strategy import ArchitectureResolutionContext


@dataclass(frozen=True)
class ResolvedEdgeOption:
    logical_edge: Mapping[str, Any]
    catalog_edge: Mapping[str, Any]
    source: ComponentOption
    destination: ComponentOption


@dataclass(frozen=True)
class FunctionalCompletenessEvidence:
    required_capability_ids: tuple[str, ...]
    provided_capability_ids: tuple[str, ...]
    provider_extra_capability_ids: tuple[str, ...]
    missing_capability_ids: tuple[str, ...]

    @property
    def complete(self) -> bool:
        return not self.missing_capability_ids


@dataclass(frozen=True)
class CompleteArchitectureCandidate:
    candidate: ArchitectureCandidate
    edges: tuple[ResolvedEdgeOption, ...]
    completeness: FunctionalCompletenessEvidence

    @property
    def candidate_id(self) -> str:
        return self.candidate.candidate_id

    @property
    def canonical_assignment_key(
        self,
    ) -> tuple[tuple[str, str, str], ...]:
        return self.candidate.canonical_assignment_key


def validate_candidate_completeness(
    candidate: ArchitectureCandidate,
    context: ArchitectureResolutionContext,
) -> CompleteArchitectureCandidate:
    """Reject incomplete candidates before cost evaluation or ranking."""

    expected_components = {
        str(item["component_id"]) for item in context.profile["components"]
    }
    actual_components = {
        option.logical_component_id for option in candidate.components
    }
    if actual_components != expected_components:
        raise ArchitectureResolutionError(
            "ARCH_FUNCTIONAL_INCOMPLETE",
            candidate.candidate_id,
            "Candidate does not assign every profile component exactly once",
        )
    expected_responsibilities = {
        str(item["responsibility_id"])
        for item in context.profile["responsibilities"]
        if item["required"]
    }
    actual_responsibilities = {
        option.responsibility_id for option in candidate.components
    }
    if not expected_responsibilities.issubset(actual_responsibilities):
        raise ArchitectureResolutionError(
            "ARCH_FUNCTIONAL_INCOMPLETE",
            candidate.candidate_id,
            "Candidate does not cover every required responsibility",
        )
    required = {
        str(capability)
        for component in context.profile["components"]
        for capability in component["required_capability_ids"]
    }
    provided = {
        str(capability)
        for option in candidate.components
        for capability in option.provider_mapping["provided_capability_ids"]
    }
    extra = {
        str(capability)
        for option in candidate.components
        for capability in option.provider_profile["capability_claims"][
            "extra_capability_ids"
        ]
    }
    evidence = FunctionalCompletenessEvidence(
        required_capability_ids=tuple(sorted(required)),
        provided_capability_ids=tuple(sorted(required & provided)),
        provider_extra_capability_ids=tuple(sorted(extra)),
        missing_capability_ids=tuple(sorted(required - provided)),
    )
    if not evidence.complete:
        raise ArchitectureResolutionError(
            "ARCH_FUNCTIONAL_INCOMPLETE",
            candidate.candidate_id,
            "Candidate lacks one or more mandatory capabilities",
        )
    return CompleteArchitectureCandidate(
        candidate=candidate,
        edges=resolve_candidate_edges(candidate, context),
        completeness=evidence,
    )


def resolve_candidate_edges(
    candidate: ArchitectureCandidate,
    context: ArchitectureResolutionContext,
) -> tuple[ResolvedEdgeOption, ...]:
    """Resolve exactly one compatible catalog edge per logical edge."""

    catalog_edges = {
        str(item["edge_implementation_id"]): item
        for item in context.catalog["edge_implementations"]
    }
    resolved = []
    for logical_edge in context.profile["edges"]:
        source = candidate.component(str(logical_edge["source_component_id"]))
        destination = candidate.component(
            str(logical_edge["destination_component_id"])
        )
        implementation = _select_edge_implementation(
            logical_edge=logical_edge,
            source=source,
            destination=destination,
            catalog_edges=catalog_edges,
        )
        if implementation is None or not _edge_is_complete(
            logical_edge=logical_edge,
            source=source,
            destination=destination,
            implementation=implementation,
            context=context,
        ):
            raise ArchitectureResolutionError(
                "ARCH_EDGE_IMPLEMENTATION_MISSING",
                candidate.candidate_id,
                f"No complete implementation exists for {logical_edge['edge_id']}",
            )
        resolved.append(
            ResolvedEdgeOption(
                logical_edge=logical_edge,
                catalog_edge=implementation,
                source=source,
                destination=destination,
            )
        )
    return tuple(resolved)


def _select_edge_implementation(
    *,
    logical_edge: Mapping[str, Any],
    source: ComponentOption,
    destination: ComponentOption,
    catalog_edges: Mapping[str, Mapping[str, Any]],
) -> Mapping[str, Any] | None:
    if source.provider == destination.provider:
        provider_mapping = next(
            (
                item
                for item in source.provider_profile["edge_mappings"]
                if item["edge_id"] == logical_edge["edge_id"]
                and source.deployment_component_id
                in item["source_deployment_component_ids"]
                and destination.deployment_component_id
                in item["destination_deployment_component_ids"]
            ),
            None,
        )
        if provider_mapping is None:
            return None
        return catalog_edges.get(provider_mapping["edge_implementation_id"])
    matches = [
        implementation
        for implementation in catalog_edges.values()
        if logical_edge["edge_id"] in implementation["logical_edge_ids"]
        and source.deployment_component_id
        in implementation["source_component_ids"]
        and destination.deployment_component_id
        in implementation["destination_component_ids"]
        and implementation["transfer_route_class"] == "cross_provider"
    ]
    return matches[0] if len(matches) == 1 else None


def _edge_is_complete(
    *,
    logical_edge: Mapping[str, Any],
    source: ComponentOption,
    destination: ComponentOption,
    implementation: Mapping[str, Any],
    context: ArchitectureResolutionContext,
) -> bool:
    cross_provider = source.provider != destination.provider
    expected_route = (
        "cross_provider" if cross_provider else "same_provider_same_region"
    )
    if (
        logical_edge["edge_id"] not in implementation["logical_edge_ids"]
        or source.deployment_component_id
        not in implementation["source_component_ids"]
        or destination.deployment_component_id
        not in implementation["destination_component_ids"]
        or implementation["delivery_requirements"]
        != logical_edge["delivery_requirements"]
        or implementation["transfer_route_class"] != expected_route
        or not implementation["formula_refs"]
        or not implementation["pricing_model_refs"]
        or not implementation["required_permission_capabilities"]
        or not implementation["trust_contract_ref"]
        or not implementation["observability_contract_ref"]
        or not logical_edge["cost_owner_ids"]
    ):
        return False
    compatibility = implementation["compatibility"]
    compatible_profiles = {
        (str(item["id"]), str(item["version"]))
        for item in compatibility["provider_profile_versions"]
    }
    required_profiles = {
        (
            str(option.provider_profile["implementation_profile_id"]),
            str(option.provider_profile["implementation_profile_version"]),
        )
        for option in (source, destination)
    }
    if (
        (
            context.profile_ref.profile_id,
            context.profile_ref.profile_version,
        )
        not in {
            (str(item["id"]), str(item["version"]))
            for item in compatibility["architecture_profile_versions"]
        }
        or not required_profiles.issubset(compatible_profiles)
        or "resolved-deployment-specification.v1"
        not in compatibility["deployment_specification_versions"]
    ):
        return False
    if cross_provider:
        return (
            implementation["mechanism"] == "cross_provider_adapter"
            and bool(
                implementation["glue_component_ids"]
                or implementation["terraform_binding"]["dependency_keys"]
            )
        )
    return not implementation["glue_component_ids"]
