"""ResolvedTwinArchitecture v2 construction from complete Five-layer v2 evidence."""

from __future__ import annotations

from decimal import Decimal
import hashlib
from typing import Any, Mapping

from . import contracts
from .completeness import CompleteArchitectureCandidate, ResolvedEdgeOption
from .diagnostics import ArchitectureResolutionError
from .five_layer_v2_costing import FiveLayerV2CostEvaluation
from .strategy import ArchitectureResolutionContext


SCHEMA_VERSION = "resolved-twin-architecture.v2"


class FiveLayerV2ResolutionBuilder:
    """Build a v2 resolution only when topology, capacity, and cost agree."""

    def build(
        self,
        *,
        candidate: CompleteArchitectureCandidate,
        context: ArchitectureResolutionContext,
        deployment_specification: Mapping[str, Any],
        cost_evaluation: FiveLayerV2CostEvaluation,
        pricing_evidence_refs: Mapping[str, Mapping[str, str]],
    ) -> Mapping[str, Any]:
        try:
            return self._build(
                candidate=candidate,
                context=context,
                deployment_specification=deployment_specification,
                cost_evaluation=cost_evaluation,
                pricing_evidence_refs=pricing_evidence_refs,
            )
        except ArchitectureResolutionError:
            raise
        except contracts.ContractError as exc:
            raise ArchitectureResolutionError(
                "ARCH_RESOLUTION_BUILD_FAILED", exc.path, str(exc)
            ) from exc
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            raise ArchitectureResolutionError(
                "ARCH_RESOLUTION_BUILD_FAILED",
                "resolvedTwinArchitecture",
                "Five-layer v2 resolution inputs are inconsistent",
            ) from exc

    def _build(
        self,
        *,
        candidate: CompleteArchitectureCandidate,
        context: ArchitectureResolutionContext,
        deployment_specification: Mapping[str, Any],
        cost_evaluation: FiveLayerV2CostEvaluation,
        pricing_evidence_refs: Mapping[str, Mapping[str, str]],
    ) -> Mapping[str, Any]:
        self._validate_inputs(
            candidate,
            context,
            deployment_specification,
            cost_evaluation,
            pricing_evidence_refs,
        )
        selections_by_assignment: dict[str, list[str]] = {}
        for selection in deployment_specification["component_selections"]:
            selections_by_assignment.setdefault(
                str(selection["architecture_assignment_id"]), []
            ).append(str(selection["implementation_component_id"]))
        assignments = []
        for option in sorted(
            candidate.candidate.components,
            key=lambda item: item.logical_component_id,
        ):
            assignment_id = (
                f"assignment.{option.logical_component_id.removeprefix('component.')}"
            )
            assignments.append(
                {
                    "assignment_id": assignment_id,
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
                    "deployment_specification_component_ids": selections_by_assignment[
                        assignment_id
                    ],
                    "cost_contribution": {
                        "currency": cost_evaluation.currency,
                        "monthly_amount": _decimal_text(
                            cost_evaluation.component_totals[
                                option.logical_component_id
                            ]
                        ),
                    },
                    "required": True,
                }
            )
        edges = [
            self._edge(
                edge,
                cost_evaluation.edge_totals[str(edge.logical_edge["edge_id"])],
                cost_evaluation.currency,
                pricing_evidence_refs,
            )
            for edge in candidate.edges
        ]
        used_providers = sorted({item["provider"] for item in assignments})
        component_totals = [
            {
                "item_id": component_id,
                "monthly_amount": _decimal_text(amount),
            }
            for component_id, amount in sorted(
                cost_evaluation.component_totals.items()
            )
        ]
        edge_totals = [
            {"item_id": edge_id, "monthly_amount": _decimal_text(amount)}
            for edge_id, amount in sorted(cost_evaluation.edge_totals.items())
        ]
        responsibility_totals = []
        for responsibility in context.profile["responsibilities"]:
            amount = sum(
                (
                    cost_evaluation.component_totals[str(component["component_id"])]
                    for component in context.profile["components"]
                    if component["responsibility_id"]
                    == responsibility["responsibility_id"]
                ),
                Decimal(0),
            )
            responsibility_totals.append(
                {
                    "item_id": responsibility["responsibility_id"],
                    "monthly_amount": _decimal_text(amount),
                }
            )
        required_capabilities = candidate.completeness.required_capability_ids
        architecture = {
            "schema_version": SCHEMA_VERSION,
            "resolution_status": (
                "publishable"
                if deployment_specification["readiness"]["status"]
                == "deployment_ready"
                else "offline_contract_fixture"
            ),
            "resolution_id": "00000000-0000-0000-0000-000000000000",
            "calculation_run_id": context.calculation_run_id,
            "architecture_profile_ref": {
                "id": context.profile_ref.profile_id,
                "version": context.profile_ref.profile_version,
                "digest": context.profile_ref.content_digest,
            },
            "optimization_bundle_ref": context.bundle_ref.to_contract(),
            "provider_profile_refs": [
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
            ],
            "workload_contract_ref": dict(context.profile["workload_contract_ref"]),
            "pricing_evidence_refs": [
                dict(pricing_evidence_refs[provider])
                for provider in used_providers
            ],
            "component_assignments": assignments,
            "resolved_edges": edges,
            "extension_bindings": [
                binding.to_contract() for binding in context.extension_bindings
            ],
            "deployment_specification_ref": {
                "schema_version": deployment_specification["schema_version"],
                "calculation_run_id": deployment_specification[
                    "calculation_run_id"
                ],
                "digest": deployment_specification["digest"],
            },
            "cost_summary": {
                "currency": cost_evaluation.currency,
                "responsibility_totals": responsibility_totals,
                "component_totals": component_totals,
                "edge_totals": edge_totals,
                "monthly_total": _decimal_text(cost_evaluation.monthly_total),
            },
            "functional_completeness": {
                "status": "complete",
                "required_capability_ids": list(required_capabilities),
                "provided_capability_ids": list(
                    candidate.completeness.provided_capability_ids
                ),
                "provider_extra_capability_ids": list(
                    candidate.completeness.provider_extra_capability_ids
                ),
                "missing_capability_ids": [],
                "validator_version": "2",
                "validation_digest": self._completeness_digest(
                    required_capabilities, context
                ),
            },
            "content_digest": "",
        }
        architecture["resolution_id"] = contracts.calculate_document_resolution_id(
            architecture
        )
        architecture["content_digest"] = contracts.calculate_document_digest(
            architecture
        )
        return contracts.read_contract(
            architecture,
            linked_documents=context.linked_documents,
        ).as_dict()

    @staticmethod
    def _validate_inputs(
        candidate: CompleteArchitectureCandidate,
        context: ArchitectureResolutionContext,
        specification: Mapping[str, Any],
        costs: FiveLayerV2CostEvaluation,
        pricing_evidence_refs: Mapping[str, Mapping[str, str]],
    ) -> None:
        used_providers = {
            option.provider for option in candidate.candidate.components
        }
        specification_evidence = {
            item["provider"]: item["digest"]
            for item in specification["optimization_context"][
                "pricing_evidence_refs"
            ]
        }
        if (
            context.profile_ref.profile_version != "2"
            or not candidate.completeness.complete
            or specification.get("schema_version")
            != "resolved-deployment-specification.v2"
            or specification.get("calculation_run_id") != context.calculation_run_id
            or specification.get("architecture_profile_ref")
            != {
                "id": context.profile_ref.profile_id,
                "version": context.profile_ref.profile_version,
                "digest": context.profile_ref.content_digest,
            }
            or set(pricing_evidence_refs) != used_providers
            or {
                provider: reference["digest"]
                for provider, reference in pricing_evidence_refs.items()
            }
            != specification_evidence
        ):
            raise ArchitectureResolutionError(
                "ARCH_RESOLUTION_BUILD_FAILED",
                "winner",
                "Five-layer v2 resolution evidence does not describe one complete winner",
            )
        assignment_ids = {
            f"assignment.{option.logical_component_id.removeprefix('component.')}"
            for option in candidate.candidate.components
        }
        selected_assignment_ids = {
            item["architecture_assignment_id"]
            for item in specification["component_selections"]
        }
        if assignment_ids != selected_assignment_ids:
            raise ArchitectureResolutionError(
                "ARCH_RESOLUTION_BUILD_FAILED",
                "resolvedDeploymentSpecification.componentSelections",
                "Atomic selections do not cover every logical assignment",
            )
        if costs.monthly_total != sum(costs.component_totals.values(), Decimal(0)) + sum(
            costs.edge_totals.values(), Decimal(0)
        ):
            raise ArchitectureResolutionError(
                "ARCH_RESOLUTION_BUILD_FAILED",
                "costSummary",
                "Five-layer v2 winner cost does not reconcile",
            )

    @staticmethod
    def _edge(
        edge: ResolvedEdgeOption,
        monthly_cost: Decimal,
        currency: str,
        pricing_evidence_refs: Mapping[str, Mapping[str, str]],
    ) -> dict[str, Any]:
        edge_id = str(edge.logical_edge["edge_id"])
        suffix = edge_id.removeprefix("edge.")
        return {
            "resolved_edge_id": f"resolved.{suffix}",
            "edge_id": edge_id,
            "source_assignment_id": (
                f"assignment.{edge.source.logical_component_id.removeprefix('component.')}"
            ),
            "source_port_id": edge.catalog_edge["source_output_port_id"],
            "destination_assignment_id": (
                "assignment."
                f"{edge.destination.logical_component_id.removeprefix('component.')}"
            ),
            "destination_port_id": edge.catalog_edge["destination_input_port_id"],
            "edge_implementation_id": edge.catalog_edge["edge_implementation_id"],
            "mechanism": edge.catalog_edge["mechanism"],
            "delivery_semantics": dict(edge.catalog_edge["delivery_requirements"]),
            "transfer_route_class": edge.catalog_edge["transfer_route_class"],
            "transfer_evidence_refs": [
                pricing_evidence_refs[provider]["id"]
                for provider in sorted(
                    {edge.source.provider, edge.destination.provider}
                )
            ],
            "formula_refs": list(edge.catalog_edge["formula_refs"]),
            "cost_contribution": {
                "currency": currency,
                "monthly_amount": _decimal_text(monthly_cost),
            },
            "trust_contract_ref": dict(edge.catalog_edge["trust_contract_ref"]),
            "observability_contract_ref": dict(
                edge.catalog_edge["observability_contract_ref"]
            ),
            "deployment_input_binding_ids": [f"binding.input.{suffix}"],
            "deployment_output_binding_ids": [f"binding.output.{suffix}"],
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
    if not value.is_finite() or value < 0:
        raise ValueError("Architecture costs must be finite and non-negative")
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text in {"-0", ""} else text
