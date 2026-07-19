"""Deterministic Phase 8.1 five-layer baseline decision contract."""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
from typing import Any, Callable, Iterable

from .canonical import content_digest, pretty_json


SCHEMA_VERSION = "five-layer-baseline-decision.v1"
PROFILE_ID = "five-layer-baseline"
PROFILE_VERSION = "1"
DECISION_PATH = Path(
    "contracts/architecture-inventory/v1/five-layer-baseline-v1-decision.json"
)
SCHEMA_PATH = Path(
    "contracts/architecture-inventory/v1/baseline-decision.schema.json"
)
RESEARCH_PATH = Path("docs/research/five_layer_baseline_target_decision.md")
DOCS_PATH = Path("docs-site/docs/architecture/five-layer-baseline.md")
DIAGRAM_MANIFEST_START = "<!-- five-layer-baseline-decision-ids:"
DIAGRAM_MANIFEST_END = "-->"
MAX_FINDINGS = 100

REQUIRED_RESPONSIBILITIES = (
    {
        "responsibility_id": "responsibility.ingestion",
        "paper_layer": "L1",
        "purpose": "Receive and normalize device telemetry.",
    },
    {
        "responsibility_id": "responsibility.processing",
        "paper_layer": "L2",
        "purpose": "Apply user and domain transformation.",
    },
    {
        "responsibility_id": "responsibility.storage",
        "paper_layer": "L3",
        "purpose": "Persist hot, cool, and archive data with explicit retention.",
    },
    {
        "responsibility_id": "responsibility.twin-state",
        "paper_layer": "L4",
        "purpose": "Maintain and query operational or semantic Twin state.",
    },
    {
        "responsibility_id": "responsibility.visualization",
        "paper_layer": "L5",
        "purpose": "Expose Twin state through a visualization interface.",
    },
)
OPTIMIZATION_SLOTS = (
    "l1_ingestion",
    "l2_processing",
    "l3_hot_storage",
    "l3_cool_storage",
    "l3_archive_storage",
    "l4_twin_state",
    "l5_visualization",
)
ALLOWED_ACTIONS = frozenset({"retain", "internalize", "replace", "remove"})
ALLOWED_MECHANISMS = frozenset(
    {
        "in_process_port",
        "typed_synchronous_api",
        "provider_native_trigger",
        "provider_workflow",
        "storage_lifecycle",
        "source_owned_transition_runtime",
        "cross_provider_adapter",
        "remove",
    }
)
ALLOWED_BINDINGS = frozenset(
    {
        "declared_component_output",
        "platform_binding",
        "profile_constant",
        "none",
    }
)
ALLOWED_TARGET_RESPONSIBILITIES = frozenset(
    {
        *(item["responsibility_id"] for item in REQUIRED_RESPONSIBILITIES),
        "responsibility.platform.orchestration",
    }
)
NON_RETAIN_ACTIONS = frozenset({"internalize", "replace", "remove"})
STORAGE_TRANSITIONS = frozenset(
    {
        "l3-hot-to-l3-cool",
        "l3-cool-to-l3-archive",
    }
)


class BaselineDecisionError(RuntimeError):
    """Stable bounded decision-check failure."""

    def __init__(self, category: str, findings: Iterable[str]):
        values = sorted({str(item)[:500] for item in findings})
        self.category = category
        self.total = len(values)
        self.findings = tuple(values[:MAX_FINDINGS])
        super().__init__(f"{category}: {self.total} finding(s)")


def _target_responsibility(component: dict[str, Any]) -> str:
    current = component["responsibility_id"]
    implementation_id = component["implementation_id"]
    if current == "responsibility.l1.ingestion":
        return "responsibility.ingestion"
    if current in {"responsibility.l2.processing", "responsibility.user-extension"}:
        return "responsibility.processing"
    if current.startswith("responsibility.l3.") or current == (
        "responsibility.storage-transition"
    ):
        return "responsibility.storage"
    if current == "responsibility.l4.twin-state":
        return "responsibility.twin-state"
    if current == "responsibility.l5.visualization":
        return "responsibility.visualization"
    if current == "responsibility.cross-cloud-glue":
        if any(
            token in implementation_id
            for token in (
                "hot-writer",
                "cold-writer",
                "archive-writer",
            )
        ):
            return "responsibility.storage"
        if "hot-reader" in implementation_id:
            return "responsibility.twin-state"
        if any(token in implementation_id for token in ("connector", "ingestion")):
            return "responsibility.processing"
    return "responsibility.platform.orchestration"


def _is_removed_component(component: dict[str, Any]) -> bool:
    implementation_id = component["implementation_id"]
    return (
        ".registry-excluded." in implementation_id
        or ".function.event-checker" in implementation_id
        or ".function.event-feedback" in implementation_id
        or ".user-template.event-actions-" in implementation_id
    )


def _owner_phase(component: dict[str, Any]) -> str:
    implementation_id = component["implementation_id"]
    if ".user-" in implementation_id or "processor-wrapper" in implementation_id:
        return "Phase 8.3 after #113"
    if implementation_id.startswith("implementation.platform.optimizer"):
        return "Phase 8.5"
    if implementation_id.startswith("implementation.platform.flutter"):
        return "Phase 8.7"
    if implementation_id.startswith("implementation.platform.management-api"):
        return "Phase 8.4"
    if (
        implementation_id.startswith("implementation.platform.deployer")
        or ".terraform-root" in implementation_id
        or ".function." in implementation_id
    ):
        return "Phase 8.6"
    return "Phase 8.3"


def _component_decision(component: dict[str, Any]) -> dict[str, Any]:
    implementation_id = component["implementation_id"]
    action = "remove" if _is_removed_component(component) else "retain"
    target_responsibility = _target_responsibility(component)
    target_component_id = (
        None if action == "remove" else component["component_id"]
    )
    target_implementation_id = None if action == "remove" else implementation_id
    if action == "remove":
        after = (
            "The implementation is excluded from the executable baseline and "
            "remains visible only as compatibility evidence."
        )
        functional_proof = (
            "The current graph provides no approved executable topology that "
            "requires this optional or registry-excluded implementation."
        )
        cost_proof = (
            "No mandatory baseline cost is deleted; the existing scientific "
            "slot formula remains owned by its retained responsibility."
        )
        package_effect = (
            "Phase 8.6 omits this implementation and its package binding from "
            "the resolved baseline graph without deleting historical source."
        )
    else:
        after = (
            "The implementation remains as evidence for the named target "
            "responsibility or as platform support for compiling that graph."
        )
        functional_proof = "Retain action preserves the current observable behavior."
        cost_proof = "Retain action preserves current formula and cost evidence."
        package_effect = (
            "The current package and Terraform ownership remain compatibility "
            "inputs until the profile compiler replaces fixed selection logic."
        )
    has_package = bool(component["package_artifact_ids"])
    has_terraform = bool(component["terraform_object_ids"])
    has_permission_scope = bool(component["required_permission_capabilities"])
    owns_user_fields = bool(component["user_owned_fields"])
    scales_independently = component["kind"] in {
        "api",
        "bridge",
        "function",
        "scheduler",
        "storage",
        "twin-service",
        "visualization",
        "workflow",
    }
    has_failure_boundary = component["kind"] not in {"user-extension"}
    has_independent_consumer = component["kind"] in {
        "api",
        "bridge",
        "storage",
        "twin-service",
        "visualization",
    }
    has_lifecycle = (
        has_package
        or has_terraform
        or component["deployment_lifecycle"] == "always"
    )
    has_trust_boundary = has_permission_scope or owns_user_fields
    if action == "retain":
        reasons = []
        if has_package:
            reasons.append("content-addressed package ownership")
        if has_terraform:
            reasons.append("explicit Terraform ownership")
        if has_permission_scope:
            reasons.append("provider permission scope")
        if owns_user_fields:
            reasons.append("user-code trust ownership")
        if scales_independently:
            reasons.append("independent runtime or service scaling")
        if component["deployment_lifecycle"] == "always":
            reasons.append("always-on platform lifecycle")
        rationale = (
            "Retained because evidence records "
            + ", ".join(reasons)
            + "."
        )
    else:
        rationale = (
            "No mandatory trust, scaling, lifecycle, failure-isolation, or "
            "independent-consumer boundary depends on this excluded path."
        )
    return {
        "action": action,
        "behavior_after": after,
        "behavior_before": (
            f"{component['kind']} at {component['runtime_entrypoint']} under "
            f"{component['responsibility_id']}."
        ),
        "boundary_rationale": {
            "failure_isolation": action == "retain" and has_failure_boundary,
            "independent_consumer": (
                action == "retain" and has_independent_consumer
            ),
            "lifecycle": action == "retain" and has_lifecycle,
            "ownership": (
                (
                    f"{component['provider']} implementation ownership with "
                    f"{len(component['package_artifact_ids'])} package and "
                    f"{len(component['terraform_object_ids'])} Terraform records."
                )
                if action == "retain"
                else "No executable baseline owner is assigned."
            ),
            "scaling": action == "retain" and scales_independently,
            "summary": rationale,
            "trust": action == "retain" and has_trust_boundary,
        },
        "cost_formula_effect": (
            "Existing optimizer-slot, transition, transfer, extension, or "
            "platform cost ownership is preserved explicitly."
        ),
        "cost_proof": cost_proof,
        "current_implementation_id": implementation_id,
        "current_logical_component_id": component["component_id"],
        "decision_evidence": [
            "docs/research/five_layer_baseline_target_decision.md#component-decisions",
            "docs/plans/phase_08_architecture_profiles_eventing/phase_08_1_five_layer_baseline.md#7-decision-procedure",
        ],
        "functional_proof": functional_proof,
        "implementation_owner_phase": _owner_phase(component),
        "migration_compatibility_effect": (
            "The current resolved-deployment specification remains readable; "
            "the target profile is not executable until Phases 8.2-8.7 finish."
        ),
        "package_terraform_effect": package_effect,
        "provider_applicability": [component["provider"]],
        "source_evidence": component["source_references"],
        "target_implementation_id": target_implementation_id,
        "target_logical_component_id": target_component_id,
        "target_responsibility_id": target_responsibility,
    }


def _edge_mechanism(
    edge: dict[str, Any],
    components: dict[str, dict[str, Any]],
) -> str:
    edge_id = edge["edge_id"]
    if (
        _is_removed_component(components[edge["source_implementation_id"]])
        or _is_removed_component(components[edge["destination_implementation_id"]])
        or edge_id.endswith(".l3-hot-to-l5-reader")
    ):
        return "remove"
    if edge_id.startswith("edge.binding.") and ".package-" in edge_id:
        return "in_process_port"
    if edge_id == "edge.binding.management-to-deployer":
        return "typed_synchronous_api"
    if edge_id in {
        "edge.runtime.flutter-to-management",
        "edge.runtime.management-to-optimizer",
    }:
        return "typed_synchronous_api"
    if ".function-hot-to-cold-mover-to-cold-writer" in edge_id or (
        ".function-cold-to-archive-mover-to-archive-writer" in edge_id
    ):
        return "source_owned_transition_runtime"
    if edge_id.startswith("edge.runtime.mixed."):
        token = edge_id.removeprefix("edge.runtime.mixed.")
        source_provider = components[edge["source_implementation_id"]]["provider"]
        destination_provider = components[
            edge["destination_implementation_id"]
        ]["provider"]
        if source_provider != destination_provider:
            return "cross_provider_adapter"
        if token in STORAGE_TRANSITIONS:
            return "source_owned_transition_runtime"
    if edge_id.endswith(".l4-to-l5"):
        return "typed_synchronous_api"
    if any(edge_id.endswith(f".{token}") for token in STORAGE_TRANSITIONS):
        return "source_owned_transition_runtime"
    if edge["edge_kind"] in {"provider_trigger", "schedule", "http"}:
        return "provider_native_trigger"
    return "in_process_port"


def _target_endpoint(
    decision_by_implementation: dict[str, dict[str, Any]],
    implementation_id: str,
) -> tuple[str | None, str | None]:
    decision = decision_by_implementation[implementation_id]
    return (
        decision["target_logical_component_id"],
        decision["target_implementation_id"],
    )


def _edge_decision(
    edge: dict[str, Any],
    components: dict[str, dict[str, Any]],
    component_decisions: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    mechanism = _edge_mechanism(edge, components)
    source_component, source_implementation = _target_endpoint(
        component_decisions, edge["source_implementation_id"]
    )
    destination_component, destination_implementation = _target_endpoint(
        component_decisions, edge["destination_implementation_id"]
    )
    removed = mechanism == "remove"
    edge_id = edge["edge_id"]
    is_l4_to_l5 = edge_id.endswith(".l4-to-l5")
    is_l3_to_l4 = edge_id.endswith(".l3-hot-to-l4")
    is_transition = any(
        edge_id.endswith(f".{token}") for token in STORAGE_TRANSITIONS
    ) or "mover-to-" in edge_id
    if removed:
        target_edge_id = None
        source_component = None
        source_implementation = None
        destination_component = None
        destination_implementation = None
        payload = {"schema_id": "none", "version": "none"}
        binding = "none"
        functional_proof = (
            "The removed edge either targets an excluded optional component or "
            "is the unsafe L3-hot-to-L5 shortcut replaced by the required "
            "typed L4-to-L5 contract."
        )
    else:
        target_edge_id = f"target.{edge['edge_id']}"
        if edge["phase"] == "deployment":
            schema_id = "deployment-binding.v1"
        elif is_l4_to_l5:
            schema_id = "twin-query-result.v1"
        elif is_l3_to_l4:
            schema_id = "telemetry-to-twin-state.v1"
        elif is_transition:
            schema_id = "storage-transition-record.v1"
        else:
            schema_id = "telemetry-envelope.v1"
        payload = {"schema_id": schema_id, "version": "1"}
        binding = (
            "platform_binding"
            if edge["phase"] == "deployment"
            else "declared_component_output"
        )
        functional_proof = (
            "The selected mechanism preserves the current required payload flow "
            "while making ownership and binding explicit."
        )
    if mechanism == "typed_synchronous_api" or is_l4_to_l5:
        invocation = "synchronous request/response with immediate response required"
        timeout = "contract-defined bounded timeout"
        retry = "bounded retry for idempotent operations only"
    elif mechanism == "remove":
        invocation = "none"
        timeout = "none"
        retry = "none"
    else:
        invocation = "asynchronous or deployment-time invocation"
        timeout = "provider or compiler bounded timeout"
        retry = "bounded provider or source-owned retry"
    rejected = [
        (
            "A general event broker or queue was rejected because the baseline "
            "has no fan-out, replay, or independent event-consumer requirement."
        ),
        (
            "Constructed resource names were rejected in favor of declared "
            "component outputs or platform-owned bindings."
        ),
    ]
    if edge["edge_id"].endswith(".l3-hot-to-l5-reader"):
        rejected.append(
            "Retaining the direct L3 reader binding would contradict the "
            "scientific L4-to-L5 flow and fail for mixed L4/L5 selections."
        )
    if removed:
        rationale = (
            "Remove this edge from the executable target because one endpoint "
            "is excluded or because the edge bypasses the required L4 boundary."
        )
    elif edge["phase"] == "deployment":
        rationale = (
            "Compile the package or operation binding inside the platform from "
            "a content-addressed artifact and an explicit component declaration."
        )
    elif is_l4_to_l5:
        rationale = (
            "Visualization requires an immediate typed query result from L4; "
            "the boundary therefore has a bounded synchronous contract even "
            "when a cross-provider adapter realizes it."
        )
    elif mechanism == "cross_provider_adapter":
        rationale = (
            "The selected providers differ, so a declared source/destination "
            "adapter owns authentication, transfer, and destination binding."
        )
    elif mechanism == "source_owned_transition_runtime":
        rationale = (
            "The source storage owner preserves modeled timing, destination "
            "semantics, observability, and transition cost across providers."
        )
    else:
        rationale = (
            "An intrinsic provider trigger preserves the asynchronous boundary "
            "and independent scaling without introducing a general broker."
        )
    if removed:
        authentication = "none"
        delivery_semantics = "none"
    elif edge["phase"] == "deployment":
        authentication = (
            "platform service identity scoped to the declared deployment operation"
        )
        delivery_semantics = "one deterministic binding compilation or explicit failure"
    elif mechanism in {"typed_synchronous_api", "cross_provider_adapter"}:
        authentication = (
            "platform-provisioned workload identity scoped to the declared "
            "destination interface"
        )
        delivery_semantics = (
            "one correlated response or explicit bounded failure"
            if is_l4_to_l5 or mechanism == "typed_synchronous_api"
            else "at-least-once delivery with contract-owned idempotency"
        )
    else:
        authentication = (
            "provider workload identity scoped to the destination component"
        )
        delivery_semantics = "at-least-once delivery with contract-owned idempotency"
    return {
        "authentication": authentication,
        "compatibility_fixture_ids": [
            f"fixture.compatibility.{edge['edge_id'].removeprefix('edge.')}",
        ],
        "correlation_observability": (
            "A deployment-operation or telemetry correlation identifier crosses "
            "the boundary and is recorded by both owners."
            if not removed
            else "not applicable"
        ),
        "cost_owner_ids": edge["cost_owner_ids"],
        "cost_proof": (
            "Existing workload, transfer, transition-runtime, or platform cost "
            "ownership remains assigned; removed compatibility edges add no "
            "mandatory cost."
        ),
        "current_edge_id": edge["edge_id"],
        "dead_letter_behavior": (
            "none"
            if removed or mechanism == "typed_synchronous_api"
            else "provider capability required only for approved asynchronous flow"
        ),
        "delivery_semantics": delivery_semantics,
        "destination_target_implementation_id": destination_implementation,
        "destination_target_logical_component_id": destination_component,
        "functional_proof": functional_proof,
        "idempotency_behavior": (
            "none"
            if removed
            else (
                edge["idempotency_scope"]
                if edge["idempotency_scope"] != "none"
                else "contract-owned operation or telemetry identifier"
            )
        ),
        "implementation_owner_phase": (
            "Phase 8.6"
            if edge["phase"] == "deployment"
            or edge["edge_id"].endswith((".l4-to-l5", ".l3-hot-to-l5-reader"))
            else "Phase 8.3"
        ),
        "invocation_semantics": invocation,
        "mechanism": mechanism,
        "ordering_behavior": (
            "none" if removed else edge["ordering_scope"]
        ),
        "payload_envelope": payload,
        "rationale": rationale,
        "rejected_alternatives": rejected,
        "resource_binding_source": binding,
        "retry_behavior": retry,
        "source_target_implementation_id": source_implementation,
        "source_target_logical_component_id": source_component,
        "target_edge_id": target_edge_id,
        "timeout_behavior": timeout,
        "transfer_route_id": edge["transfer_route_id"],
        "trust_boundary_id": edge["trust_boundary_id"],
        "verification_fixture_ids": [
            f"fixture.verification.{edge['edge_id'].removeprefix('edge.')}",
        ],
    }


def _provider_admissibility(
    components: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    ids_by_provider = {
        provider: sorted(
            item["implementation_id"]
            for item in components
            if item["provider"] == provider and not _is_removed_component(item)
        )
        for provider in ("aws", "azure", "gcp")
    }
    required = [
        "capability.ingestion",
        "capability.processing",
        "capability.hot-storage",
        "capability.cool-storage",
        "capability.archive-storage",
        "capability.twin-state",
        "capability.visualization",
        "capability.six-baseline-flows",
    ]
    return [
        {
            "candidate_id": "candidate.all-aws",
            "deployment_support_status": "incomplete",
            "evidence_support_status": "complete",
            "formula_evidence_complete": True,
            "implementation_component_bundle": ids_by_provider["aws"],
            "known_extra_functionality": [
                "Intrinsic provider triggers and optional orchestration choices"
            ],
            "mandatory_capabilities": required,
            "missing_functionality": [
                "Typed L4-to-L5 datasource binding is not implemented until Phase 8.6"
            ],
            "pricing_evidence_complete": True,
            "status": "blocked_until_target_implementation",
            "unsupported_error_code": "PROFILE_TARGET_NOT_IMPLEMENTED",
            "unsupported_reason": (
                "The target decision is complete, but the current Deployer still "
                "binds Grafana to the L3 hot reader."
            ),
        },
        {
            "candidate_id": "candidate.all-azure",
            "deployment_support_status": "incomplete",
            "evidence_support_status": "complete",
            "formula_evidence_complete": True,
            "implementation_component_bundle": ids_by_provider["azure"],
            "known_extra_functionality": [
                "Intrinsic provider triggers and optional orchestration choices"
            ],
            "mandatory_capabilities": required,
            "missing_functionality": [
                "Typed L4-to-L5 datasource binding is not implemented until Phase 8.6"
            ],
            "pricing_evidence_complete": True,
            "status": "blocked_until_target_implementation",
            "unsupported_error_code": "PROFILE_TARGET_NOT_IMPLEMENTED",
            "unsupported_reason": (
                "The target decision is complete, but the current Deployer still "
                "binds Grafana to the L3 hot reader."
            ),
        },
        {
            "candidate_id": "candidate.all-gcp",
            "deployment_support_status": "unsupported",
            "evidence_support_status": "complete",
            "formula_evidence_complete": False,
            "implementation_component_bundle": ids_by_provider["gcp"],
            "known_extra_functionality": [
                "GCP implements L1 through L3 and storage transitions"
            ],
            "mandatory_capabilities": required,
            "missing_functionality": [
                "Deployable L4 Twin-state capability",
                "Deployable L5 visualization capability",
                "L3-hot-to-L4 and L4-to-L5 formula and deployment evidence",
            ],
            "pricing_evidence_complete": False,
            "status": "unsupported",
            "unsupported_error_code": "PROFILE_PROVIDER_CAPABILITY_INCOMPLETE",
            "unsupported_reason": (
                "GCP has no approved deployable L4/L5 bundle in the current evidence."
            ),
        },
        {
            "candidate_id": "candidate.mixed-provider",
            "deployment_support_status": "incomplete",
            "evidence_support_status": "complete",
            "formula_evidence_complete": True,
            "implementation_component_bundle": sorted(
                {
                    *ids_by_provider["aws"],
                    *ids_by_provider["azure"],
                    *ids_by_provider["gcp"],
                }
            ),
            "known_extra_functionality": [
                "Explicit adapters exist for the currently modeled L1-L4 boundaries"
            ],
            "mandatory_capabilities": required,
            "missing_functionality": [
                "Cross-provider typed L4-to-L5 datasource binding"
            ],
            "pricing_evidence_complete": True,
            "status": "blocked_until_target_implementation",
            "unsupported_error_code": "PROFILE_TARGET_NOT_IMPLEMENTED",
            "unsupported_reason": (
                "Phase 8.6 must compile declared outputs for every selected "
                "source/destination pair before mixed deployment is admissible."
            ),
        },
    ]


def _cost_rules(inventory: dict[str, Any]) -> list[dict[str, Any]]:
    target_by_current = {
        "responsibility.l1.ingestion": "responsibility.ingestion",
        "responsibility.l2.processing": "responsibility.processing",
        "responsibility.user-extension": "responsibility.processing",
        "responsibility.l3.hot-storage": "responsibility.storage",
        "responsibility.l3.cool-storage": "responsibility.storage",
        "responsibility.l3.archive-storage": "responsibility.storage",
        "responsibility.storage-transition": "responsibility.storage",
        "responsibility.l4.twin-state": "responsibility.twin-state",
        "responsibility.l5.visualization": "responsibility.visualization",
    }
    rules = []
    for current in inventory["cost_owners"]:
        target_responsibilities = sorted(
            {
                target_by_current[item]
                for item in current["responsibility_ids"]
                if item in target_by_current
            }
        )
        if target_responsibilities:
            scope = "scientific_responsibility"
        elif current["cost_kind"] == "transfer":
            scope = "edge"
        elif current["cost_owner_id"] == "cost.platform.orchestration":
            scope = "platform"
        else:
            scope = "extension"
        rules.append(
            {
                "current_cost_owner_id": current["cost_owner_id"],
                "evidence_references": current["source_references"],
                "formula_effect": (
                    "The existing pricing intents and formulas remain traceable; "
                    "scientific layer count does not collapse distinct L3 slots."
                ),
                "pricing_intent_ids": current["pricing_intent_ids"],
                "target_cost_owner_id": current["cost_owner_id"],
                "target_responsibility_ids": target_responsibilities,
                "target_scope": scope,
            }
        )
    return sorted(rules, key=lambda item: item["current_cost_owner_id"])


def _required_scenarios() -> list[dict[str, Any]]:
    return [
        {
            "scenario_id": "scenario.all-aws",
            "status": "blocked_until_target_implementation",
            "reason_code": "PROFILE_TARGET_NOT_IMPLEMENTED",
            "required_edge_ids": [
                "edge.runtime.aws.l1-to-l2",
                "edge.runtime.aws.l2-to-l3-hot",
                "edge.runtime.aws.l3-hot-to-l3-cool",
                "edge.runtime.aws.l3-cool-to-l3-archive",
                "edge.runtime.aws.l3-hot-to-l4",
                "edge.runtime.aws.l4-to-l5",
            ],
        },
        {
            "scenario_id": "scenario.all-azure",
            "status": "blocked_until_target_implementation",
            "reason_code": "PROFILE_TARGET_NOT_IMPLEMENTED",
            "required_edge_ids": [
                "edge.runtime.azure.l1-to-l2",
                "edge.runtime.azure.l2-to-l3-hot",
                "edge.runtime.azure.l3-hot-to-l3-cool",
                "edge.runtime.azure.l3-cool-to-l3-archive",
                "edge.runtime.azure.l3-hot-to-l4",
                "edge.runtime.azure.l4-to-l5",
            ],
        },
        {
            "scenario_id": "scenario.all-gcp",
            "status": "unsupported",
            "reason_code": "PROFILE_PROVIDER_CAPABILITY_INCOMPLETE",
            "required_edge_ids": [
                "edge.runtime.gcp.l1-to-l2",
                "edge.runtime.gcp.l2-to-l3-hot",
                "edge.runtime.gcp.l3-hot-to-l3-cool",
                "edge.runtime.gcp.l3-cool-to-l3-archive",
            ],
        },
        {
            "scenario_id": "scenario.mixed-provider",
            "status": "blocked_until_target_implementation",
            "reason_code": "PROFILE_TARGET_NOT_IMPLEMENTED",
            "required_edge_ids": [
                "edge.runtime.mixed.l1-to-l2",
                "edge.runtime.mixed.l2-to-l3-hot",
                "edge.runtime.mixed.l3-hot-to-l3-cool",
                "edge.runtime.mixed.l3-cool-to-l3-archive",
                "edge.runtime.mixed.l3-hot-to-l4",
                "edge.runtime.mixed.l4-to-l5",
            ],
        },
        {
            "scenario_id": "scenario.user-processor",
            "status": "supported",
            "reason_code": "EXTENSION_BINDING_COMPLETE",
            "required_edge_ids": [
                "edge.runtime.aws.function-dispatcher-to-processor-wrapper",
                "edge.runtime.azure.function-dispatcher-to-processor-wrapper",
                "edge.runtime.gcp.function-dispatcher-to-processor-wrapper",
            ],
        },
        {
            "scenario_id": "scenario.optional-event-check-feedback",
            "status": "unsupported",
            "reason_code": "PROFILE_OPTIONAL_TOPOLOGY_UNSUPPORTED",
            "required_edge_ids": [],
        },
    ]


def build_baseline_decision(inventory: dict[str, Any]) -> dict[str, Any]:
    """Build the deterministic target decision from the verified Phase 8.0 graph."""

    components = {
        item["implementation_id"]: item for item in inventory["components"]
    }
    component_decisions = [
        _component_decision(item)
        for item in sorted(
            inventory["components"],
            key=lambda item: (
                item["component_id"],
                item["implementation_id"],
            ),
        )
    ]
    decision_by_implementation = {
        item["current_implementation_id"]: item for item in component_decisions
    }
    edge_decisions = [
        _edge_decision(item, components, decision_by_implementation)
        for item in sorted(inventory["edges"], key=lambda item: item["edge_id"])
    ]
    decision: dict[str, Any] = {
        "compatibility_rules": [
            {
                "compatibility_id": "compatibility.current-resolved-specification",
                "rule": (
                    "Current seven provider keys and selected cheapest fields "
                    "remain readable until profile-aware persistence migrates them."
                ),
                "owner_phase": "Phases 8.2-8.7",
            },
            {
                "compatibility_id": "compatibility.no-silent-decision-change",
                "rule": (
                    "A later implementation change must update this decision, "
                    "its digest, affected plan, and issue evidence."
                ),
                "owner_phase": "Phases 8.2-8.7",
            },
            {
                "compatibility_id": "compatibility.extension-prerequisite",
                "rule": (
                    "No user extension slot becomes executable before GitHub "
                    "issue #113 is complete."
                ),
                "owner_phase": "Phase 8.3 after #113",
            },
        ],
        "component_decisions": component_decisions,
        "cost_ownership_rules": _cost_rules(inventory),
        "edge_decisions": edge_decisions,
        "functional_completeness_rules": [
            {
                "capability_id": "capability.ingestion",
                "required": True,
                "evidence": "responsibility.ingestion and target L1-to-L2 edge",
            },
            {
                "capability_id": "capability.processing",
                "required": True,
                "evidence": "responsibility.processing and target L2-to-L3-hot edge",
            },
            {
                "capability_id": "capability.hot-storage",
                "required": True,
                "evidence": "l3_hot_storage optimization slot",
            },
            {
                "capability_id": "capability.cool-storage",
                "required": True,
                "evidence": "l3_cool_storage optimization slot",
            },
            {
                "capability_id": "capability.archive-storage",
                "required": True,
                "evidence": "l3_archive_storage optimization slot",
            },
            {
                "capability_id": "capability.twin-state",
                "required": True,
                "evidence": "responsibility.twin-state and target L3-hot-to-L4 edge",
            },
            {
                "capability_id": "capability.visualization",
                "required": True,
                "evidence": "responsibility.visualization and target L4-to-L5 edge",
            },
            {
                "capability_id": "capability.five-scientific-responsibilities",
                "required": True,
                "evidence": "required_responsibilities",
            },
            {
                "capability_id": "capability.seven-costed-optimization-slots",
                "required": True,
                "evidence": "optimization_slots",
            },
            {
                "capability_id": "capability.six-baseline-flows",
                "required": True,
                "evidence": "required_scenarios",
            },
            {
                "capability_id": "capability.explicit-component-bindings",
                "required": True,
                "evidence": "edge_decisions.resource_binding_source",
            },
            {
                "capability_id": "capability.fail-closed-provider-admissibility",
                "required": True,
                "evidence": "provider_admissibility",
            },
        ],
        "optimization_slots": list(OPTIMIZATION_SLOTS),
        "profile_id": PROFILE_ID,
        "profile_version": PROFILE_VERSION,
        "provider_admissibility": _provider_admissibility(inventory["components"]),
        "required_responsibilities": list(REQUIRED_RESPONSIBILITIES),
        "required_scenarios": _required_scenarios(),
        "residual_limitations": [
            {
                "limitation_id": "limitation.target-not-yet-executable",
                "statement": (
                    "This artifact is a target decision. Phases 8.2-8.7 must "
                    "implement it before any provider candidate becomes supported."
                ),
                "owner_phase": "Phases 8.2-8.7",
            },
            {
                "limitation_id": "limitation.gcp-l4-l5",
                "statement": (
                    "GCP has no approved L4/L5 implementation and therefore "
                    "remains explicitly unsupported for a complete baseline path."
                ),
                "owner_phase": "Future work",
            },
            {
                "limitation_id": "limitation.optional-error-topology",
                "statement": (
                    "Optional event-check and feedback behavior remains outside "
                    "the executable baseline; provider-native triggers are only "
                    "intrinsic component details."
                ),
                "owner_phase": "Phase 8.8 evaluation",
            },
        ],
        "schema_version": SCHEMA_VERSION,
        "source_inventory_digest": inventory["content_digest"],
    }
    decision["content_digest"] = content_digest(decision)
    return decision


def write_baseline_decision(root: Path, inventory: dict[str, Any]) -> None:
    """Write the canonical generated decision artifact."""

    (root / DECISION_PATH).write_text(
        pretty_json(build_baseline_decision(inventory)),
        encoding="utf-8",
    )


def _duplicates(values: Iterable[str]) -> list[str]:
    counts = Counter(values)
    return sorted(value for value, count in counts.items() if count > 1)


def _extract_manifest(text: str) -> set[str]:
    start = text.find(DIAGRAM_MANIFEST_START)
    if start < 0:
        return set()
    start += len(DIAGRAM_MANIFEST_START)
    end = text.find(DIAGRAM_MANIFEST_END, start)
    if end < 0:
        return set()
    return {
        line.strip()
        for line in text[start:end].splitlines()
        if line.strip()
    }


def _check_coverage(
    inventory: dict[str, Any], decision: dict[str, Any]
) -> None:
    expected_components = {
        item["implementation_id"] for item in inventory["components"]
    }
    actual_components = [
        item["current_implementation_id"]
        for item in decision["component_decisions"]
    ]
    duplicates = _duplicates(actual_components)
    missing = expected_components - set(actual_components)
    stale = set(actual_components) - expected_components
    if duplicates or missing or stale:
        raise BaselineDecisionError(
            "COMPONENT_DECISION_MISSING",
            [
                *(f"duplicate:{item}" for item in duplicates),
                *(f"missing:{item}" for item in missing),
                *(f"stale:{item}" for item in stale),
            ],
        )
    expected_edges = {item["edge_id"] for item in inventory["edges"]}
    actual_edges = [item["current_edge_id"] for item in decision["edge_decisions"]]
    duplicates = _duplicates(actual_edges)
    missing = expected_edges - set(actual_edges)
    stale = set(actual_edges) - expected_edges
    if duplicates or missing or stale:
        raise BaselineDecisionError(
            "EDGE_DECISION_MISSING",
            [
                *(f"duplicate:{item}" for item in duplicates),
                *(f"missing:{item}" for item in missing),
                *(f"stale:{item}" for item in stale),
            ],
        )


def _check_enums(decision: dict[str, Any]) -> None:
    findings = [
        item["current_implementation_id"]
        for item in decision["component_decisions"]
        if item["action"] not in ALLOWED_ACTIONS
    ]
    findings.extend(
        item["current_edge_id"]
        for item in decision["edge_decisions"]
        if item["mechanism"] not in ALLOWED_MECHANISMS
    )
    findings.extend(
        item["current_implementation_id"]
        for item in decision["component_decisions"]
        if item["target_responsibility_id"] not in ALLOWED_TARGET_RESPONSIBILITIES
    )
    if findings:
        raise BaselineDecisionError("FUNCTIONAL_PROOF_MISSING", findings)


def _check_component_consistency(
    inventory: dict[str, Any], decision: dict[str, Any]
) -> None:
    current = {
        item["implementation_id"]: item for item in inventory["components"]
    }
    findings = []
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in decision["component_decisions"]:
        grouped.setdefault(item["current_logical_component_id"], []).append(item)
        source = current[item["current_implementation_id"]]
        if item["current_logical_component_id"] != source["component_id"]:
            findings.append(f"{item['current_implementation_id']}:logical")
        if item["provider_applicability"] != [source["provider"]]:
            findings.append(f"{item['current_implementation_id']}:provider")
        target_ids = (
            item["target_logical_component_id"],
            item["target_implementation_id"],
        )
        if item["action"] == "remove" and any(
            value is not None for value in target_ids
        ):
            findings.append(f"{item['current_implementation_id']}:removed-target")
        if item["action"] != "remove" and any(
            value is None for value in target_ids
        ):
            findings.append(f"{item['current_implementation_id']}:missing-target")
    for component_id, variants in grouped.items():
        unqualified_decisions = {
            (
                item["action"],
                item["target_logical_component_id"],
                item["target_responsibility_id"],
            )
            for item in variants
        }
        if len(unqualified_decisions) != 1:
            findings.append(f"{component_id}:provider-divergence")
    if findings:
        raise BaselineDecisionError("TARGET_REFERENCE_UNRESOLVED", findings)


def _check_targets(
    inventory: dict[str, Any], decision: dict[str, Any]
) -> None:
    target_components = {
        item["target_logical_component_id"]
        for item in decision["component_decisions"]
        if item["target_logical_component_id"] is not None
    }
    target_implementations = {
        item["target_implementation_id"]
        for item in decision["component_decisions"]
        if item["target_implementation_id"] is not None
    }
    findings = []
    decision_by_implementation = {
        item["current_implementation_id"]: item
        for item in decision["component_decisions"]
    }
    current_edges = {item["edge_id"]: item for item in inventory["edges"]}
    target_edge_ids = [
        item["target_edge_id"]
        for item in decision["edge_decisions"]
        if item["target_edge_id"] is not None
    ]
    findings.extend(
        f"duplicate:{item}" for item in _duplicates(target_edge_ids)
    )
    for edge in decision["edge_decisions"]:
        current_edge = current_edges[edge["current_edge_id"]]
        if edge["mechanism"] == "remove":
            target_fields = (
                edge["target_edge_id"],
                edge["source_target_logical_component_id"],
                edge["source_target_implementation_id"],
                edge["destination_target_logical_component_id"],
                edge["destination_target_implementation_id"],
            )
            if any(value is not None for value in target_fields):
                findings.append(f"{edge['current_edge_id']}:removed-target")
            if edge["resource_binding_source"] != "none":
                findings.append(f"{edge['current_edge_id']}:removed-binding")
            continue
        source_decision = decision_by_implementation[
            current_edge["source_implementation_id"]
        ]
        destination_decision = decision_by_implementation[
            current_edge["destination_implementation_id"]
        ]
        expected = {
            "source_target_logical_component_id": source_decision[
                "target_logical_component_id"
            ],
            "source_target_implementation_id": source_decision[
                "target_implementation_id"
            ],
            "destination_target_logical_component_id": destination_decision[
                "target_logical_component_id"
            ],
            "destination_target_implementation_id": destination_decision[
                "target_implementation_id"
            ],
        }
        for key, known in (
            ("source_target_logical_component_id", target_components),
            ("destination_target_logical_component_id", target_components),
            ("source_target_implementation_id", target_implementations),
            ("destination_target_implementation_id", target_implementations),
        ):
            if edge[key] not in known:
                findings.append(f"{edge['current_edge_id']}->{edge[key]}")
            elif edge[key] != expected[key]:
                findings.append(f"{edge['current_edge_id']}:{key}-mismatch")
        if edge["target_edge_id"] is None:
            findings.append(f"{edge['current_edge_id']}:missing-target-edge")
    if findings:
        raise BaselineDecisionError("TARGET_REFERENCE_UNRESOLVED", findings)


def _check_proofs(decision: dict[str, Any]) -> None:
    findings = []
    for item in decision["component_decisions"]:
        if item["action"] in NON_RETAIN_ACTIONS and (
            not item["functional_proof"].strip() or not item["cost_proof"].strip()
        ):
            findings.append(item["current_implementation_id"])
        if not item["implementation_owner_phase"].strip():
            findings.append(f"owner:{item['current_implementation_id']}")
    for item in decision["edge_decisions"]:
        if not item["functional_proof"].strip() or not item["cost_proof"].strip():
            findings.append(item["current_edge_id"])
        if not item["implementation_owner_phase"].strip():
            findings.append(f"owner:{item['current_edge_id']}")
    if findings:
        raise BaselineDecisionError("FUNCTIONAL_PROOF_MISSING", findings)


def _check_cost_owners(
    inventory: dict[str, Any], decision: dict[str, Any]
) -> None:
    expected = {item["cost_owner_id"] for item in inventory["cost_owners"]}
    actual = [
        item["current_cost_owner_id"]
        for item in decision["cost_ownership_rules"]
    ]
    findings = [
        *(f"missing:{item}" for item in expected - set(actual)),
        *(f"stale:{item}" for item in set(actual) - expected),
        *(f"duplicate:{item}" for item in _duplicates(actual)),
    ]
    if findings:
        raise BaselineDecisionError("COST_OWNER_MISSING", findings)


def _check_provider_bundles(decision: dict[str, Any]) -> None:
    findings = []
    allowed_components = {
        item["current_implementation_id"]
        for item in decision["component_decisions"]
        if item["action"] != "remove"
    }
    known_capabilities = {
        item["capability_id"]
        for item in decision["functional_completeness_rules"]
    }
    candidate_ids = [item["candidate_id"] for item in decision["provider_admissibility"]]
    findings.extend(f"duplicate:{item}" for item in _duplicates(candidate_ids))
    for item in decision["provider_admissibility"]:
        if not item["mandatory_capabilities"]:
            findings.append(f"{item['candidate_id']}:capabilities")
        if not item["implementation_component_bundle"]:
            findings.append(f"{item['candidate_id']}:bundle")
        findings.extend(
            f"{item['candidate_id']}->{component_id}"
            for component_id in item["implementation_component_bundle"]
            if component_id not in allowed_components
        )
        findings.extend(
            f"{item['candidate_id']}->{capability_id}"
            for capability_id in item["mandatory_capabilities"]
            if capability_id not in known_capabilities
        )
        if item["status"] == "supported" and (
            item["deployment_support_status"] != "complete"
            or item["evidence_support_status"] != "complete"
            or not item["formula_evidence_complete"]
            or not item["pricing_evidence_complete"]
            or item["missing_functionality"]
        ):
            findings.append(f"{item['candidate_id']}:supported-incomplete")
        if item["status"] != "supported" and (
            not item["unsupported_error_code"].strip()
            or not item["unsupported_reason"].strip()
        ):
            findings.append(f"{item['candidate_id']}:rejection")
    if findings:
        raise BaselineDecisionError("PROVIDER_BUNDLE_INCOMPLETE", findings)


def _check_bindings(decision: dict[str, Any]) -> None:
    findings = []
    forbidden = ("constructed", "derived_name", "string_convention", "suffix_lookup")
    for item in decision["edge_decisions"]:
        binding = item["resource_binding_source"]
        if binding not in ALLOWED_BINDINGS or any(
            token in binding for token in forbidden
        ):
            findings.append(item["current_edge_id"])
        if item["mechanism"] != "remove" and binding == "none":
            findings.append(f"{item['current_edge_id']}:none")
    if findings:
        raise BaselineDecisionError("RESOURCE_BINDING_IMPLICIT", findings)


def _check_eventing_scope(decision: dict[str, Any]) -> None:
    findings = []
    for item in decision["required_responsibilities"]:
        if "eventing" in item["responsibility_id"].lower():
            findings.append(item["responsibility_id"])
    for item in decision["component_decisions"]:
        target_ids = (
            item["target_logical_component_id"],
            item["target_implementation_id"],
            item["target_responsibility_id"],
        )
        if any(value and "eventing" in value.lower() for value in target_ids):
            findings.append(item["current_implementation_id"])
        if any(
            token in item["current_implementation_id"]
            for token in (".event-checker", ".event-feedback")
        ) and item["action"] != "remove":
            findings.append(item["current_implementation_id"])
    for item in decision["cost_ownership_rules"]:
        if "eventing" in item["target_cost_owner_id"].lower():
            findings.append(item["target_cost_owner_id"])
    if findings:
        raise BaselineDecisionError("EVENTING_SCOPE_LEAK", findings)


def _check_sensitive_material(decision: dict[str, Any]) -> None:
    serialized = json.dumps(decision, sort_keys=True).lower()
    forbidden = (
        "config_credentials.json",
        "terraform.tfstate",
        "aws_access_key_id=",
        "aws_secret_access_key=",
        "-----begin private key-----",
    )
    findings = [f"forbidden:{item}" for item in forbidden if item in serialized]
    if findings:
        raise BaselineDecisionError("FUNCTIONAL_PROOF_MISSING", findings)


def _check_evidence_paths(root: Path, decision: dict[str, Any]) -> None:
    references = []
    for item in decision["component_decisions"]:
        references.extend(
            (item["current_implementation_id"], reference)
            for reference in (
                *item["source_evidence"],
                *item["decision_evidence"],
            )
        )
    for item in decision["cost_ownership_rules"]:
        references.extend(
            (item["current_cost_owner_id"], reference)
            for reference in item["evidence_references"]
        )
    findings = []
    for owner, reference in references:
        relative = Path(reference.split("#", 1)[0])
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or not (root / relative).exists()
        ):
            findings.append(f"{owner}->{relative.as_posix()}")
    if findings:
        raise BaselineDecisionError("FUNCTIONAL_PROOF_MISSING", findings)


def _check_fixed_invariants(decision: dict[str, Any]) -> None:
    responsibility_ids = tuple(
        item["responsibility_id"]
        for item in decision["required_responsibilities"]
    )
    expected_ids = tuple(
        item["responsibility_id"] for item in REQUIRED_RESPONSIBILITIES
    )
    findings = []
    if responsibility_ids != expected_ids:
        findings.append("required_responsibilities")
    if tuple(decision["optimization_slots"]) != OPTIMIZATION_SLOTS:
        findings.append("optimization_slots")
    if findings:
        raise BaselineDecisionError("FUNCTIONAL_PROOF_MISSING", findings)


def _check_scenarios(
    inventory: dict[str, Any], decision: dict[str, Any]
) -> None:
    expected = {
        "scenario.all-aws",
        "scenario.all-azure",
        "scenario.all-gcp",
        "scenario.mixed-provider",
        "scenario.user-processor",
        "scenario.optional-event-check-feedback",
    }
    actual = {item["scenario_id"] for item in decision["required_scenarios"]}
    known_edges = {item["edge_id"] for item in inventory["edges"]}
    findings = [
        *(f"missing:{item}" for item in expected - actual),
        *(f"stale:{item}" for item in actual - expected),
    ]
    for item in decision["required_scenarios"]:
        if item["status"] != "supported" and not item["reason_code"].strip():
            findings.append(f"{item['scenario_id']}:reason")
        findings.extend(
            f"{item['scenario_id']}->{edge_id}"
            for edge_id in item["required_edge_ids"]
            if edge_id not in known_edges
        )
    if findings:
        raise BaselineDecisionError("PROVIDER_BUNDLE_INCOMPLETE", findings)


def _check_document_manifests(
    root: Path, decision: dict[str, Any]
) -> None:
    expected = {
        *(item["responsibility_id"] for item in REQUIRED_RESPONSIBILITIES),
        *(
            item["target_edge_id"]
            for item in decision["edge_decisions"]
            if item["target_edge_id"] is not None
            and any(
                item["current_edge_id"].endswith(f".{token}")
                for token in (
                    "l1-to-l2",
                    "l2-to-l3-hot",
                    "l3-hot-to-l3-cool",
                    "l3-cool-to-l3-archive",
                    "l3-hot-to-l4",
                    "l4-to-l5",
                )
            )
        ),
    }
    findings = []
    for relative in (RESEARCH_PATH, DOCS_PATH):
        path = root / relative
        if not path.exists():
            findings.append(f"{relative}:missing")
            continue
        actual = _extract_manifest(path.read_text(encoding="utf-8"))
        findings.extend(f"{relative}:missing:{item}" for item in expected - actual)
        findings.extend(f"{relative}:stale:{item}" for item in actual - expected)
    if findings:
        raise BaselineDecisionError("TARGET_REFERENCE_UNRESOLVED", findings)


def load_baseline_decision(root: Path) -> tuple[str, dict[str, Any]]:
    """Load the committed canonical decision."""

    path = root / DECISION_PATH
    try:
        raw = path.read_text(encoding="utf-8")
        return raw, json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise BaselineDecisionError("DECISION_DIGEST_MISMATCH", [str(path)]) from exc


def _check_digest(raw: str, decision: dict[str, Any]) -> None:
    if raw != pretty_json(decision):
        raise BaselineDecisionError(
            "DECISION_DIGEST_MISMATCH", ["non-canonical JSON serialization"]
        )
    if decision["content_digest"] != content_digest(decision):
        raise BaselineDecisionError(
            "DECISION_DIGEST_MISMATCH", ["content_digest"]
        )


def _check_source_digest(
    inventory: dict[str, Any], decision: dict[str, Any]
) -> None:
    if decision["source_inventory_digest"] != inventory["content_digest"]:
        raise BaselineDecisionError(
            "SOURCE_INVENTORY_STALE", ["source_inventory_digest"]
        )


def check_baseline_decision(
    root: Path,
    inventory: dict[str, Any],
    schema_validator: Callable[[Path, dict[str, Any]], None],
) -> dict[str, int]:
    """Validate schema, coverage, proofs, admissibility, and target evidence."""

    raw, decision = load_baseline_decision(root)
    schema_validator(SCHEMA_PATH, decision)
    _check_digest(raw, decision)
    _check_source_digest(inventory, decision)
    if (
        decision["schema_version"] != SCHEMA_VERSION
        or decision["profile_id"] != PROFILE_ID
        or decision["profile_version"] != PROFILE_VERSION
    ):
        raise BaselineDecisionError(
            "FUNCTIONAL_PROOF_MISSING", ["profile identity"]
        )
    _check_fixed_invariants(decision)
    _check_enums(decision)
    _check_coverage(inventory, decision)
    _check_component_consistency(inventory, decision)
    _check_targets(inventory, decision)
    _check_proofs(decision)
    _check_cost_owners(inventory, decision)
    _check_provider_bundles(decision)
    _check_bindings(decision)
    _check_eventing_scope(decision)
    _check_sensitive_material(decision)
    _check_evidence_paths(root, decision)
    _check_scenarios(inventory, decision)
    _check_document_manifests(root, decision)
    return {
        "baseline_component_decisions": len(decision["component_decisions"]),
        "baseline_edge_decisions": len(decision["edge_decisions"]),
        "baseline_provider_candidates": len(decision["provider_admissibility"]),
        "baseline_scenarios": len(decision["required_scenarios"]),
    }
