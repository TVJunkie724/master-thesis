"""Deterministic ResolvedTwinArchitecture v1 construction."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import hashlib
from typing import Any, Mapping

from backend.calculation_v2.path_optimizer import CompletePathEvaluation
from backend.pricing_catalog_models import PricingCatalogContext

from . import contracts
from .completeness import CompleteArchitectureCandidate, ResolvedEdgeOption
from .diagnostics import ArchitectureResolutionError
from .strategy import ArchitectureResolutionContext


SCHEMA_VERSION = "resolved-twin-architecture.v1"
EDGE_SEGMENTS = {
    "edge.ingestion-to-processing": "L1_to_L2",
    "edge.processing-to-hot-storage": "L2_to_L3_hot",
    "edge.hot-to-cool-storage": "L3_hot_to_L3_cool",
    "edge.cool-to-archive-storage": "L3_cool_to_L3_archive",
    "edge.hot-storage-to-twin-state": "L3_hot_to_L4",
    "edge.twin-state-to-visualization": "L4_to_L5",
}


@dataclass(frozen=True)
class ArchitectureResolutionWinner:
    candidate: CompleteArchitectureCandidate
    evaluation: CompletePathEvaluation
    deployment_specification: Mapping[str, Any]
    pricing_catalog_context: PricingCatalogContext
    currency: str
    currency_rate: Decimal


class ResolvedTwinArchitectureBuilder:
    """Build only from a complete winner and validate the shared contract."""

    def build(
        self,
        *,
        winner: ArchitectureResolutionWinner,
        context: ArchitectureResolutionContext,
    ) -> Mapping[str, Any]:
        try:
            return self._build(winner=winner, context=context)
        except ArchitectureResolutionError:
            raise
        except contracts.ContractError as exc:
            raise ArchitectureResolutionError(
                "ARCH_RESOLUTION_BUILD_FAILED",
                exc.path,
                str(exc),
            ) from exc
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            raise ArchitectureResolutionError(
                "ARCH_RESOLUTION_BUILD_FAILED",
                "resolvedTwinArchitecture",
                "Resolved architecture inputs are inconsistent",
            ) from exc

    def _build(
        self,
        *,
        winner: ArchitectureResolutionWinner,
        context: ArchitectureResolutionContext,
    ) -> Mapping[str, Any]:
        self._validate_winner(winner, context)
        component_costs = self._component_costs(winner)
        edge_costs = self._edge_costs(winner)
        assignments = [
            self._assignment(
                option=option,
                monthly_cost=component_costs[option.layer_key],
                currency=winner.currency,
                deployment_specification_component_ids=tuple(
                    component_id
                    for component_id in option.provider_mapping[
                        "deployment_specification_component_ids"
                    ]
                    if component_id
                    in {
                        item["component_id"]
                        for item in winner.deployment_specification[
                            "components"
                        ]
                    }
                ),
            )
            for option in sorted(
                winner.candidate.candidate.components,
                key=lambda item: item.logical_component_id,
            )
        ]
        edges = [
            self._edge(
                edge=edge,
                monthly_cost=edge_costs[str(edge.logical_edge["edge_id"])],
                currency=winner.currency,
                pricing_catalog_context=winner.pricing_catalog_context,
            )
            for edge in winner.candidate.edges
        ]
        used_providers = tuple(
            sorted({item["provider"] for item in assignments})
        )
        provider_refs = [
            {
                "id": context.provider_profiles[provider][
                    "implementation_profile_id"
                ],
                "version": context.provider_profiles[provider][
                    "implementation_profile_version"
                ],
                "digest": context.provider_profiles[provider][
                    "content_digest"
                ],
                "provider": provider,
            }
            for provider in used_providers
        ]
        required_capabilities = (
            winner.candidate.completeness.required_capability_ids
        )
        architecture = {
            "schema_version": SCHEMA_VERSION,
            "resolution_id": "00000000-0000-0000-0000-000000000000",
            "calculation_run_id": context.calculation_run_id,
            "architecture_profile_ref": {
                "id": context.profile_ref.profile_id,
                "version": context.profile_ref.profile_version,
                "digest": context.profile_ref.content_digest,
            },
            "optimization_bundle_ref": context.bundle_ref.to_contract(),
            "provider_profile_refs": provider_refs,
            "workload_contract_ref": dict(
                context.profile["workload_contract_ref"]
            ),
            "pricing_evidence_refs": [
                self._pricing_evidence(
                    provider,
                    winner.pricing_catalog_context,
                )
                for provider in used_providers
            ],
            "component_assignments": assignments,
            "resolved_edges": edges,
            "extension_bindings": [
                binding.to_contract()
                for binding in context.extension_bindings
            ],
            "deployment_specification_ref": {
                "schema_version": winner.deployment_specification[
                    "schema_version"
                ],
                "calculation_run_id": winner.deployment_specification[
                    "calculation_run_id"
                ],
                "digest": winner.deployment_specification["digest"],
            },
            "cost_summary": self._cost_summary(
                assignments=assignments,
                edges=edges,
                profile=context.profile,
                currency=winner.currency,
            ),
            "functional_completeness": {
                "status": "complete",
                "required_capability_ids": list(required_capabilities),
                "provided_capability_ids": list(
                    winner.candidate.completeness.provided_capability_ids
                ),
                "provider_extra_capability_ids": list(
                    winner.candidate.completeness.provider_extra_capability_ids
                ),
                "missing_capability_ids": [],
                "validator_version": "1",
                "validation_digest": self._completeness_digest(
                    required_capabilities,
                    context,
                ),
            },
        }
        architecture["resolution_id"] = contracts.calculate_resolution_id(
            architecture
        )
        architecture["content_digest"] = contracts.calculate_digest(
            architecture
        )
        validated = contracts.read_contract(
            architecture,
            linked_documents=context.linked_documents,
        )
        return validated.as_dict()

    @staticmethod
    def _validate_winner(
        winner: ArchitectureResolutionWinner,
        context: ArchitectureResolutionContext,
    ) -> None:
        if (
            winner.candidate.candidate_id
            != winner.evaluation.candidate_id
            or not winner.candidate.completeness.complete
            or winner.currency not in {"USD", "EUR"}
            or not winner.currency_rate.is_finite()
            or winner.currency_rate <= 0
        ):
            raise ArchitectureResolutionError(
                "ARCH_RESOLUTION_BUILD_FAILED",
                "winner",
                "Resolution winner is incomplete or inconsistent",
            )
        specification = winner.deployment_specification
        if (
            specification.get("schema_version")
            != "resolved-deployment-specification.v1"
            or specification.get("calculation_run_id")
            != context.calculation_run_id
            or specification.get("architecture_profile")
            != {
                "profile_id": context.profile_ref.profile_id,
                "profile_version": context.profile_ref.profile_version,
            }
        ):
            raise ArchitectureResolutionError(
                "ARCH_RESOLUTION_BUILD_FAILED",
                "resolvedDeploymentSpecification",
                "Deployment specification does not match the architecture context",
            )
        specification_components = {
            item["component_id"]
            for item in specification.get("components", ())
        }
        if any(
            not specification_components.intersection(
                option.provider_mapping[
                    "deployment_specification_component_ids"
                ]
            )
            for option in winner.candidate.candidate.components
        ):
            raise ArchitectureResolutionError(
                "ARCH_RESOLUTION_BUILD_FAILED",
                "resolvedDeploymentSpecification.components",
                "Deployment specification omits a logical component mapping",
            )

    @staticmethod
    def _component_costs(
        winner: ArchitectureResolutionWinner,
    ) -> dict[str, Decimal]:
        costs = {
            item.layer_key: item.cost * winner.currency_rate
            for item in winner.evaluation.assignments
        }
        if set(costs) != {
            option.layer_key
            for option in winner.candidate.candidate.components
        }:
            raise ArchitectureResolutionError(
                "ARCH_RESOLUTION_BUILD_FAILED",
                "componentAssignments",
                "Winner layer costs do not cover architecture components",
            )
        return costs

    @staticmethod
    def _edge_costs(
        winner: ArchitectureResolutionWinner,
    ) -> dict[str, Decimal]:
        transfer_costs = {
            charge.route.segment_id: charge.total_cost
            for charge in winner.evaluation.transfer_charges
        }
        runtime_costs = {
            charge.workload.transfer_segment_id: charge.total_cost
            for charge in winner.evaluation.transition_runtime_charges
        }
        result = {}
        for edge in winner.candidate.edges:
            edge_id = str(edge.logical_edge["edge_id"])
            segment = EDGE_SEGMENTS[edge_id]
            result[edge_id] = (
                transfer_costs[segment] + runtime_costs.get(segment, Decimal(0))
            ) * winner.currency_rate
        return result

    @staticmethod
    def _assignment(
        *,
        option: Any,
        monthly_cost: Decimal,
        currency: str,
        deployment_specification_component_ids: tuple[str, ...],
    ) -> dict[str, Any]:
        if not deployment_specification_component_ids:
            raise ArchitectureResolutionError(
                "ARCH_RESOLUTION_BUILD_FAILED",
                option.logical_component_id,
                "Assignment has no selected deployment specification component",
            )
        return {
            "assignment_id": (
                f"assignment.{option.logical_component_id.removeprefix('component.')}"
            ),
            "responsibility_id": option.responsibility_id,
            "logical_component_id": option.logical_component_id,
            "provider": option.provider,
            "provider_implementation_profile_ref": {
                "id": option.provider_profile["implementation_profile_id"],
                "version": option.provider_profile[
                    "implementation_profile_version"
                ],
                "digest": option.provider_profile["content_digest"],
            },
            "deployment_component_id": option.deployment_component_id,
            "deployment_component_version": option.catalog_component[
                "component_version"
            ],
            "service_id": option.catalog_component["service_id"],
            "region": option.region,
            "capability_evidence": list(
                option.provider_mapping["provided_capability_ids"]
            ),
            "pricing_model_refs": list(
                option.catalog_component["pricing_model_refs"]
            ),
            "formula_refs": list(option.catalog_component["formula_refs"]),
            "deployment_specification_component_ids": list(
                deployment_specification_component_ids
            ),
            "cost_contribution": {
                "currency": currency,
                "monthly_amount": _decimal_text(monthly_cost),
            },
            "required": True,
        }

    @staticmethod
    def _edge(
        *,
        edge: ResolvedEdgeOption,
        monthly_cost: Decimal,
        currency: str,
        pricing_catalog_context: PricingCatalogContext,
    ) -> dict[str, Any]:
        edge_id = str(edge.logical_edge["edge_id"])
        suffix = edge_id.removeprefix("edge.")
        evidence_providers = tuple(
            sorted({edge.source.provider, edge.destination.provider})
        )
        return {
            "resolved_edge_id": f"resolved.{suffix}",
            "edge_id": edge_id,
            "source_assignment_id": (
                "assignment."
                f"{edge.source.logical_component_id.removeprefix('component.')}"
            ),
            "source_port_id": edge.catalog_edge["source_output_port_id"],
            "destination_assignment_id": (
                "assignment."
                f"{edge.destination.logical_component_id.removeprefix('component.')}"
            ),
            "destination_port_id": edge.catalog_edge[
                "destination_input_port_id"
            ],
            "edge_implementation_id": edge.catalog_edge[
                "edge_implementation_id"
            ],
            "mechanism": edge.catalog_edge["mechanism"],
            "delivery_semantics": dict(
                edge.catalog_edge["delivery_requirements"]
            ),
            "transfer_route_class": edge.catalog_edge[
                "transfer_route_class"
            ],
            "transfer_evidence_refs": [
                pricing_catalog_context.catalogs[provider].snapshot_id
                for provider in evidence_providers
            ],
            "formula_refs": list(edge.catalog_edge["formula_refs"]),
            "cost_contribution": {
                "currency": currency,
                "monthly_amount": _decimal_text(monthly_cost),
            },
            "trust_contract_ref": dict(
                edge.catalog_edge["trust_contract_ref"]
            ),
            "observability_contract_ref": dict(
                edge.catalog_edge["observability_contract_ref"]
            ),
            "deployment_input_binding_ids": [f"binding.input.{suffix}"],
            "deployment_output_binding_ids": [f"binding.output.{suffix}"],
        }

    @staticmethod
    def _pricing_evidence(
        provider: str,
        context: PricingCatalogContext,
    ) -> dict[str, str]:
        reference = context.catalogs[provider]
        return {
            "id": reference.snapshot_id,
            "version": "1",
            "digest": reference.content_digest,
            "provider": provider,
            "currency": "USD",
        }

    @staticmethod
    def _cost_summary(
        *,
        assignments: list[dict[str, Any]],
        edges: list[dict[str, Any]],
        profile: Mapping[str, Any],
        currency: str,
    ) -> dict[str, Any]:
        assignment_costs = {
            item["logical_component_id"]: Decimal(
                item["cost_contribution"]["monthly_amount"]
            )
            for item in assignments
        }
        edge_costs = {
            item["edge_id"]: Decimal(
                item["cost_contribution"]["monthly_amount"]
            )
            for item in edges
        }
        component_totals = [
            {
                "item_id": component_id,
                "monthly_amount": _decimal_text(amount),
            }
            for component_id, amount in sorted(assignment_costs.items())
        ]
        edge_totals = [
            {
                "item_id": edge_id,
                "monthly_amount": _decimal_text(amount),
            }
            for edge_id, amount in sorted(edge_costs.items())
        ]
        responsibility_totals = []
        for responsibility in profile["responsibilities"]:
            responsibility_id = str(responsibility["responsibility_id"])
            amount = sum(
                (
                    assignment_costs[str(component["component_id"])]
                    for component in profile["components"]
                    if component["responsibility_id"] == responsibility_id
                ),
                Decimal(0),
            )
            responsibility_totals.append(
                {
                    "item_id": responsibility_id,
                    "monthly_amount": _decimal_text(amount),
                }
            )
        total = sum(assignment_costs.values(), Decimal(0)) + sum(
            edge_costs.values(),
            Decimal(0),
        )
        return {
            "currency": currency,
            "responsibility_totals": responsibility_totals,
            "component_totals": component_totals,
            "edge_totals": edge_totals,
            "monthly_total": _decimal_text(total),
        }

    @staticmethod
    def _completeness_digest(
        capabilities: tuple[str, ...],
        context: ArchitectureResolutionContext,
    ) -> str:
        payload = {
            "capabilities": sorted(capabilities),
            "profile_digest": context.profile["content_digest"],
            "catalog_digest": context.catalog["content_digest"],
        }
        encoded = contracts.canonical_json(payload).encode("utf-8")
        return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _decimal_text(value: Decimal) -> str:
    if not value.is_finite():
        raise ValueError("Architecture costs must be finite")
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text in {"-0", ""} else text
