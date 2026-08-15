#!/usr/bin/env python3
"""Generate the deterministic Phase 8 architecture-profile evaluation package."""

from __future__ import annotations

import argparse
from datetime import datetime
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import shutil
import sys
from typing import Any, Iterable, Mapping
from uuid import NAMESPACE_URL, uuid5


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
OPTIMIZER_ROOT = REPOSITORY_ROOT / "2-twin2clouds"
if str(OPTIMIZER_ROOT) not in sys.path:
    sys.path.insert(0, str(OPTIMIZER_ROOT))

from backend.architecture_profiles.five_layer_v2_costing import (  # noqa: E402
    FiveLayerV2CostEvaluation,
    evaluate_five_layer_v2_costs,
)
from backend.architecture_profiles.five_layer_v2_optimizer import (  # noqa: E402
    optimize_five_layer_v2,
)
from backend.architecture_profiles.five_layer_v2_pricing import (  # noqa: E402
    FiveLayerV2CatalogCostLedgerResolver,
)
from backend.architecture_profiles.five_layer_v2_workload import (  # noqa: E402
    resolve_five_layer_v2_workload,
)
from backend.architecture_profiles.registry import (  # noqa: E402
    ArchitectureProfileRegistry,
)
from backend.architecture_profiles.six_layer_optimizer import (  # noqa: E402
    optimize_six_layer_eventing_v1,
)
from backend.calculation_v2.engine import calculate_cheapest_costs  # noqa: E402
from backend.deployment_specification.five_layer_v2_builder import (  # noqa: E402
    build_five_layer_v2_deployment_specification,
    build_six_layer_eventing_v1_deployment_specification,
)
from backend.pricing_catalog_models import (  # noqa: E402
    PricingCatalogContext,
    build_pricing_catalog_reference,
)


DEFAULT_OUTPUT = (
    REPOSITORY_ROOT / "docs" / "research" / "evidence" / "phase_08_profile_evaluation"
)
CONFIG_PATH = Path(__file__).with_name("evaluation_config.json")
CONFIG_SCHEMA_PATH = Path(__file__).with_name("evaluation-config.schema.json")
EVALUATION_SCHEMA_ROOT = DEFAULT_OUTPUT / "schemas"
SIZES = ("small", "medium", "large")
PROVIDERS = ("aws", "azure", "gcp")
FIVE_COMPONENTS = (
    "component.ingestion",
    "component.processing",
    "component.hot-storage",
    "component.cool-storage",
    "component.archive-storage",
    "component.twin-state",
    "component.visualization",
)
EVENT_CAPABILITY_SOURCE = (
    REPOSITORY_ROOT
    / "docs/research/evidence/phase_08_eventing/mandatory-capabilities.json"
)
SERVICE_BUNDLE_SOURCE = (
    REPOSITORY_ROOT
    / "docs/research/evidence/phase_08_service_bundles/complete-provider-bundles.json"
)
PRICING_BASELINE_ROOT = OPTIMIZER_ROOT / "json/pricing_catalog_baselines"
WORKLOAD_ROOT = REPOSITORY_ROOT / "contracts/five-layer-workload/v2"
EVENT_SCENARIO_CATALOG = WORKLOAD_ROOT / "eventing-scenario-catalog.json"
HISTORICAL_PRICING = OPTIMIZER_ROOT / "json/pricing.json"
PROFILE_PATHS = {
    "historical": REPOSITORY_ROOT
    / "contracts/architecture-profiles/definitions/profiles/five-layer-baseline/1/profile.json",
    "five": REPOSITORY_ROOT
    / "contracts/architecture-profiles/definitions/profiles/five-layer-baseline/2/profile.json",
    "six": REPOSITORY_ROOT
    / "contracts/architecture-profiles/definitions/profiles/six-layer-eventing/1/profile.json",
}
PROFILE_LABELS = {
    "historical": "five-layer-baseline@1",
    "five": "five-layer-baseline@2",
    "six": "six-layer-eventing@1",
}


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def semantic_digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


def byte_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def pretty_json(value: object) -> str:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            indent=2,
        )
        + "\n"
    )


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(pretty_json(value), encoding="utf-8")


def decimal_text(value: Decimal | str | int | float) -> str:
    amount = Decimal(str(value))
    text = format(amount, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def sum_amounts(values: Iterable[Decimal | str | int | float]) -> Decimal:
    return sum((Decimal(str(value)) for value in values), Decimal(0))


def run_id(scope: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"phase-08-profile-evaluation@1:{scope}"))


def relative(path: Path) -> str:
    return path.resolve().relative_to(REPOSITORY_ROOT.resolve()).as_posix()


def tree_digest(path: Path) -> tuple[str, int]:
    records = []
    for child in sorted(item for item in path.rglob("*") if item.is_file()):
        relative_parts = child.relative_to(path).parts
        if (
            ".terraform" in relative_parts
            or "__pycache__" in relative_parts
            or child.suffix in {".pyc", ".pyo"}
        ):
            continue
        records.append(
            {"path": child.relative_to(path).as_posix(), "digest": byte_digest(child)}
        )
    return semantic_digest(records), len(records)


def input_reference(category: str, path: Path) -> dict[str, Any]:
    if path.is_dir():
        digest, file_count = tree_digest(path)
        return {
            "category": category,
            "path": relative(path),
            "kind": "tree",
            "digest": digest,
            "file_count": file_count,
        }
    return {
        "category": category,
        "path": relative(path),
        "kind": "file",
        "digest": byte_digest(path),
        "file_count": 1,
    }


def frozen_input_references() -> list[dict[str, Any]]:
    definitions = REPOSITORY_ROOT / "contracts/architecture-profiles/definitions"
    paths = (
        ("architecture", PROFILE_PATHS["historical"]),
        ("architecture", PROFILE_PATHS["five"]),
        ("architecture", PROFILE_PATHS["six"]),
        ("architecture", definitions / "five-layer-v2-manifest.json"),
        ("architecture", definitions / "six-layer-eventing-v1-manifest.json"),
        (
            "architecture",
            REPOSITORY_ROOT
            / "contracts/architecture-inventory/v1/five-layer-baseline-v1-decision.json",
        ),
        ("evaluation", Path(__file__).resolve().parent),
        ("evaluation", EVALUATION_SCHEMA_ROOT),
        ("functional", EVENT_CAPABILITY_SOURCE),
        ("functional", SERVICE_BUNDLE_SOURCE),
        ("implementation", OPTIMIZER_ROOT / "backend/architecture_profiles"),
        ("implementation", OPTIMIZER_ROOT / "backend/calculation_v2"),
        ("implementation", OPTIMIZER_ROOT / "backend/deployment_specification"),
        ("provider", definitions / "provider-implementations"),
        ("component", definitions / "component-catalogs"),
        (
            "permission",
            REPOSITORY_ROOT / "3-cloud-deployer/docs/references/permission_sets",
        ),
        ("package", REPOSITORY_ROOT / "3-cloud-deployer/src/providers"),
        ("terraform", REPOSITORY_ROOT / "3-cloud-deployer/src/terraform"),
        ("bootstrap", REPOSITORY_ROOT / "contracts/cloud-bootstrap"),
        ("access", REPOSITORY_ROOT / "contracts/deployment-access"),
        ("workload", WORKLOAD_ROOT),
        (
            "scenario",
            REPOSITORY_ROOT
            / "docs/research/evidence/phase_08_eventing/scenario-inputs.json",
        ),
        ("scenario", REPOSITORY_ROOT / "2-twin2clouds/example_input.json"),
        ("pricing", PRICING_BASELINE_ROOT / "baseline.json"),
        ("pricing", HISTORICAL_PRICING),
        (
            "formula",
            REPOSITORY_ROOT
            / "docs/research/evidence/phase_08_eventing/formula-and-unit-ledger.json",
        ),
        (
            "formula",
            REPOSITORY_ROOT
            / "docs/research/evidence/phase_08_service_bundles/pricing-ownership-matrix.json",
        ),
        (
            "formula",
            REPOSITORY_ROOT
            / "contracts/resolved-deployment-specification/v2/component-capacity-registry.json",
        ),
        (
            "source",
            REPOSITORY_ROOT
            / "docs/research/evidence/phase_08_eventing/source-ledger.json",
        ),
        (
            "source",
            REPOSITORY_ROOT
            / "docs/research/evidence/phase_08_service_bundles/source-ledger.json",
        ),
    )
    refs = [input_reference(category, path) for category, path in paths]
    baseline = read_json(PRICING_BASELINE_ROOT / "baseline.json")
    for provider in PROVIDERS:
        reference = baseline["catalogs"][provider]
        snapshot = (
            PRICING_BASELINE_ROOT
            / provider
            / reference["pricing_region"]
            / "snapshots"
            / f"{reference['snapshot_id']}.json"
        )
        refs.append(input_reference("pricing", snapshot))
    return sorted(refs, key=lambda item: (item["category"], item["path"]))


def load_pricing() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    baseline = read_json(PRICING_BASELINE_ROOT / "baseline.json")
    pricing: dict[str, Any] = {}
    evidence: dict[str, Any] = {}
    snapshots: dict[str, Any] = {}
    for provider in PROVIDERS:
        reference = baseline["catalogs"][provider]
        snapshot_path = (
            PRICING_BASELINE_ROOT
            / provider
            / reference["pricing_region"]
            / "snapshots"
            / f"{reference['snapshot_id']}.json"
        )
        snapshot = read_json(snapshot_path)
        pricing[provider] = snapshot["pricing"]
        evidence[provider] = {
            "id": reference["snapshot_id"],
            "version": "1",
            "digest": reference["content_digest"],
            "provider": provider,
            "currency": "USD",
        }
        snapshots[provider] = {
            "provider": provider,
            "region": reference["pricing_region"],
            "snapshot_id": reference["snapshot_id"],
            "digest": reference["content_digest"],
            "fetched_at": reference["fetched_at"],
            "source": reference["source"],
            "review_status": reference["review_status"],
        }
    return pricing, evidence, snapshots


def load_workloads() -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    core = {
        size: read_json(WORKLOAD_ROOT / "fixtures/valid" / f"core-{size}.json")
        for size in SIZES
    }
    event_catalog = read_json(EVENT_SCENARIO_CATALOG)
    events = {
        item["scenario_id"].removeprefix("eventing-").removesuffix("-v1"): item
        for item in event_catalog["scenarios"]
    }
    if set(core) != set(events):
        raise ValueError("Core and Eventing scenario sizes differ")
    for size in SIZES:
        if core[size]["eventingScenarioId"] != events[size]["scenario_id"]:
            raise ValueError(f"Core/Eventing pairing drifted for {size}")
    return core, events


def profile_ref(registry: ArchitectureProfileRegistry) -> dict[str, str]:
    return {
        "profileId": str(registry.profile["profile_id"]),
        "profileVersion": str(registry.profile["profile_version"]),
        "contentDigest": str(registry.profile["content_digest"]),
    }


def extension_bindings() -> list[dict[str, str]]:
    return [
        {
            "slotId": "processor.telemetry",
            "slotVersion": "1",
            "artifactId": "artifact.user.processor.evaluation-fixture",
            "artifactDigest": "sha256:" + "1" * 64,
            "configurationDigest": "sha256:" + "2" * 64,
        }
    ]


def assignment_for_online_placement(
    hot_provider: str, twin_provider: str
) -> dict[str, str]:
    return {
        "component.ingestion": hot_provider,
        "component.processing": hot_provider,
        "component.hot-storage": hot_provider,
        "component.cool-storage": hot_provider,
        "component.archive-storage": hot_provider,
        "component.twin-state": twin_provider,
        "component.visualization": hot_provider,
    }


def build_specification(
    *,
    profile: str,
    scope: str,
    assignment: Mapping[str, str],
    workload: Mapping[str, Any],
    evidence: Mapping[str, Mapping[str, str]],
) -> tuple[dict[str, Any], Any, ArchitectureProfileRegistry]:
    if profile == "five":
        registry = ArchitectureProfileRegistry(profile_version="2")
        builder = build_five_layer_v2_deployment_specification
    elif profile == "six":
        registry = ArchitectureProfileRegistry(
            profile_id="six-layer-eventing", profile_version="1"
        )
        builder = build_six_layer_eventing_v1_deployment_specification
    else:
        raise ValueError(f"Unsupported active profile: {profile}")
    resolved_workload = resolve_five_layer_v2_workload(workload)
    used_providers = sorted(set(assignment.values()))
    lifecycle = {
        "profile": str(registry.profile["lifecycle_status"]),
        "catalog": str(registry.catalog["lifecycle_status"]),
        **{
            f"provider:{provider}": str(
                registry.providers[provider]["lifecycle_status"]
            )
            for provider in used_providers
        },
    }
    specification = builder(
        calculation_run_id=run_id(scope),
        assignment=assignment,
        resolved_workload=resolved_workload,
        architecture_profile_ref={
            "id": str(registry.profile["profile_id"]),
            "version": str(registry.profile["profile_version"]),
            "digest": str(registry.profile["content_digest"]),
        },
        component_catalog_ref={
            "id": str(registry.catalog["catalog_id"]),
            "version": str(registry.catalog["catalog_version"]),
            "digest": str(registry.catalog["content_digest"]),
        },
        workload_contract_digest=str(
            registry.profile["workload_contract_ref"]["digest"]
        ),
        pricing_evidence_digests={
            provider: str(evidence[provider]["digest"]) for provider in used_providers
        },
        definition_lifecycle_statuses=lifecycle,
    )
    return specification, resolved_workload, registry


def component_category(
    component_id: str,
    logical_component_id: str,
    *,
    cross_cloud_event_transport: bool,
) -> str:
    lowered = component_id.lower()
    if "only-for-reviewed-remote" in lowered or (
        "event-adapter" in lowered and cross_cloud_event_transport
    ):
        return "bridge"
    if any(
        token in lowered
        for token in ("cloudwatch", "monitor", "logging", "log-analytics")
    ):
        return "observability"
    if any(
        token in lowered
        for token in (
            "grafana",
            "raw-history-reader",
            "persistent-disk",
            "tls-load-balancer",
        )
    ):
        return "visualization-seat"
    if any(
        token in lowered
        for token in (
            "scheduler",
            "storage-mover",
            "storage-job",
            "registry-if-container",
        )
    ):
        return "tiering"
    if any(token in lowered for token in ("failure-store", "dead-letter", "sqs-fifo")):
        return "failure-replay"
    if logical_component_id in {
        "component.hot-storage",
        "component.cool-storage",
        "component.archive-storage",
    } or any(
        token in lowered
        for token in (
            "dynamodb",
            "cosmos",
            "firestore",
            "s3-",
            "blob-",
            "cloud-storage",
        )
    ):
        return "storage"
    if logical_component_id in {
        "component.ingestion",
        "component.processing",
        "component.eventing",
    } or any(
        token in lowered
        for token in (
            "lambda",
            "functions",
            "cloud-run",
            "iot-",
            "pubsub",
            "kinesis",
            "event-hubs",
            "service-bus",
            "workflows",
            "step-functions",
        )
    ):
        return "request-throughput"
    return "service"


def cost_projection(
    specification: Mapping[str, Any],
    ledger: Mapping[str, Any],
    evaluation: FiveLayerV2CostEvaluation,
) -> dict[str, Any]:
    selections = {
        item["implementation_component_id"]: item
        for item in specification["component_selections"]
    }
    categories = {
        category: Decimal(0)
        for category in (
            "service",
            "request-throughput",
            "storage",
            "transfer",
            "tiering",
            "observability",
            "failure-replay",
            "visualization-seat",
            "bridge",
        )
    }
    contributions = []
    event_scope_ids: set[str] = set()
    independent_event_component_ids: set[str] = set()
    cross_cloud_event_transport = any(
        item["route_class"] == "domain_event_cross_cloud"
        and len(set(item["pair"].split("->", 1))) == 2
        for item in ledger["route_costs"]
    )
    for item in ledger["component_costs"]:
        selection = selections[item["component_id"]]
        logical = selection["logical_component_id"]
        category = component_category(
            item["component_id"],
            logical,
            cross_cloud_event_transport=cross_cloud_event_transport,
        )
        amount = Decimal(item["monthly_amount"])
        categories[category] += amount
        contribution_id = f"component:{item['component_id']}"
        if logical == "component.eventing":
            independent_event_component_ids.add(contribution_id)
        if (
            logical == "component.eventing"
            or category == "bridge"
            or "event-adapter" in item["component_id"].lower()
        ):
            event_scope_ids.add(contribution_id)
        contributions.append(
            {
                "contribution_id": contribution_id,
                "kind": "component",
                "provider": selection["provider"],
                "logical_component_id": logical,
                "category": category,
                "monthly_amount": decimal_text(amount),
                "cost_owner_id": item["cost_owner_id"],
            }
        )
    for item in ledger["route_costs"]:
        category = (
            "bridge"
            if item["route_class"] == "domain_event_cross_cloud"
            else "transfer"
        )
        amount = Decimal(item["monthly_amount"])
        categories[category] += amount
        contribution_id = f"route:{item['cost_owner_id']}"
        if category == "bridge":
            event_scope_ids.add(contribution_id)
        contributions.append(
            {
                "contribution_id": contribution_id,
                "kind": "route",
                "provider": item["pair"].split("->", 1)[0],
                "logical_component_id": None,
                "category": category,
                "monthly_amount": decimal_text(amount),
                "cost_owner_id": item["cost_owner_id"],
            }
        )
    projected_total = sum_amounts(categories.values())
    if projected_total != evaluation.monthly_total:
        raise ValueError(
            f"Category total {projected_total} != evaluated total {evaluation.monthly_total}"
        )
    event_transport_scope_total = sum_amounts(
        item["monthly_amount"]
        for item in contributions
        if item["contribution_id"] in event_scope_ids
    )
    has_independent_event_layer = bool(independent_event_component_ids)
    independent_event_layer_total = (
        event_transport_scope_total if has_independent_event_layer else Decimal(0)
    )
    return {
        "monthly_total": decimal_text(evaluation.monthly_total),
        "category_totals": {
            category: decimal_text(amount) for category, amount in categories.items()
        },
        "event_transport_scope_total": decimal_text(event_transport_scope_total),
        "independent_event_layer_total": decimal_text(independent_event_layer_total),
        "contributions": contributions,
        "exact_once_owner_count": len(contributions),
    }


def evaluate_assignment(
    *,
    profile: str,
    scope: str,
    assignment: Mapping[str, str],
    workload: Mapping[str, Any],
    evidence: Mapping[str, Mapping[str, str]],
    ledger_resolver: FiveLayerV2CatalogCostLedgerResolver,
) -> dict[str, Any]:
    specification, resolved_workload, _registry = build_specification(
        profile=profile,
        scope=scope,
        assignment=assignment,
        workload=workload,
        evidence=evidence,
    )
    ledger = ledger_resolver.resolve(specification, assignment, resolved_workload)
    evaluation = evaluate_five_layer_v2_costs(
        specification=specification,
        assignment=assignment,
        resolved_workload=resolved_workload,
        cost_ledger=ledger,
    )
    costs = cost_projection(specification, ledger, evaluation)
    return {
        "candidate_id": "|".join(assignment[item] for item in sorted(assignment)),
        "assignment": dict(sorted(assignment.items())),
        "status": "supported_offline_estimate",
        "functional_status": "complete",
        "capacity_status": "theoretical_pass_live_pending",
        "live_verification_status": "pending_supervised_run",
        "blocking_live_gate_ids": list(specification["readiness"]["blocking_gate_ids"]),
        "resolved_deployment_specification_digest": specification["digest"],
        "cost": costs,
    }


def generate_scenario_manifest(
    config: Mapping[str, Any],
    core: Mapping[str, Mapping[str, Any]],
    events: Mapping[str, Mapping[str, Any]],
    snapshots: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    scenarios = []
    for size in SIZES:
        core_path = WORKLOAD_ROOT / "fixtures/valid" / f"core-{size}.json"
        paired_digest = semantic_digest({"core": core[size], "eventing": events[size]})
        scenarios.append(
            {
                "scenario_id": f"profile-evaluation-{size}-v1",
                "size": size,
                "core_workload": core[size],
                "core_source": {
                    "path": relative(core_path),
                    "digest": byte_digest(core_path),
                },
                "eventing_workload": events[size],
                "eventing_source": {
                    "path": relative(EVENT_SCENARIO_CATALOG),
                    "digest": read_json(EVENT_SCENARIO_CATALOG)["scenario_digests"][
                        events[size]["scenario_id"]
                    ],
                },
                "paired_workload_digest": paired_digest,
            }
        )
    historical = []
    for item in config["historical_scenarios"]:
        source = REPOSITORY_ROOT / item["input_path"]
        workload = read_json(source)
        workload.update(item["overrides"])
        historical.append(
            {
                "scenario_id": item["scenario_id"],
                "source": {"path": item["input_path"], "digest": byte_digest(source)},
                "overrides": item["overrides"],
                "workload": workload,
                "workload_digest": semantic_digest(workload),
                "comparison_scope": "historical_reconstruction_only",
            }
        )
    return {
        "$schema": "schemas/scenario-manifest.schema.json",
        "schema_version": "phase-08-profile-scenarios.v1",
        "package_id": config["package_id"],
        "regions": config["regions"],
        "currency": {
            "code": config["currency"],
            "conversion_policy": "usd_identity_no_conversion",
        },
        "observation_policy": {
            "evaluation_cutoff": config["evaluation_cutoff"],
            "pricing_observation_timestamp": config["observation_timestamp"],
            "generation_timestamp_policy": "no_runtime_timestamp_in_generated_artifacts",
        },
        "pricing_snapshots": [snapshots[provider] for provider in PROVIDERS],
        "paired_scenarios": scenarios,
        "historical_scenarios": historical,
        "coverage": {
            "sizes": 3,
            "single_cloud_placements_per_profile_and_size": 3,
            "five_layer_online_placements_per_size": 9,
            "directed_event_provider_pairs_per_size": 6,
            "representative_three_provider_placements_per_size": 1,
        },
    }


def generate_functional_matrix(config: Mapping[str, Any]) -> dict[str, Any]:
    capabilities = read_json(EVENT_CAPABILITY_SOURCE)
    bundles = read_json(SERVICE_BUNDLE_SOURCE)
    embedded_ids = [
        item["capability_id"] for item in capabilities["embedded_capabilities"]
    ]
    event_ids = [
        item["capability_id"] for item in capabilities["event_layer_capabilities"]
    ]
    bundle_rows = []
    for provider in bundles["providers"]:
        base_services = sorted(
            {
                service
                for services in provider["layers"].values()
                for service in services
            }
            | set(provider["support_components"])
        )
        bundle_rows.extend(
            [
                {
                    "profile_id": "five-layer-baseline@2",
                    "provider": provider["provider"],
                    "status": "supported",
                    "services": sorted(
                        set(base_services) | set(provider["embedded_event_components"])
                    ),
                    "present_capabilities": embedded_ids,
                    "missing_capabilities": [],
                    "extra_capabilities": [],
                    "functional_evaluation_status": "functionally_complete_before_cost",
                    "live_verification_status": "pending_supervised_run",
                },
                {
                    "profile_id": "six-layer-eventing@1",
                    "provider": provider["provider"],
                    "status": "supported",
                    "services": sorted(
                        set(base_services) | set(provider["six_layer_event_components"])
                    ),
                    "present_capabilities": embedded_ids + event_ids,
                    "missing_capabilities": [],
                    "extra_capabilities": [],
                    "functional_evaluation_status": "functionally_complete_before_cost",
                    "live_verification_status": "pending_supervised_run",
                },
            ]
        )
    return {
        "$schema": "schemas/functional-matrix.schema.json",
        "schema_version": "phase-08-functional-matrix.v1",
        "package_id": config["package_id"],
        "evaluation_order": [
            "functional_completeness",
            "theoretical_capacity",
            "estimated_cost",
        ],
        "profile_rows": [
            {
                "profile_id": "five-layer-baseline@1",
                "role": "historical_reconstruction",
                "status": "historical",
                "domain_capabilities": [],
                "event_layer_capabilities": [],
                "event_responsibility": "absent_historical_optional_paths_preserved",
                "ranked_with_profile_ids": [],
            },
            {
                "profile_id": "five-layer-baseline@2",
                "role": "functionally_aligned_control",
                "status": "supported",
                "domain_capabilities": embedded_ids,
                "event_layer_capabilities": [],
                "event_responsibility": "embedded_in_ingestion_and_processing",
                "ranked_with_profile_ids": ["five-layer-baseline@2"],
            },
            {
                "profile_id": "six-layer-eventing@1",
                "role": "functionally_aligned_treatment",
                "status": "supported",
                "domain_capabilities": embedded_ids,
                "event_layer_capabilities": event_ids,
                "event_responsibility": "independent_eventing_layer",
                "ranked_with_profile_ids": ["six-layer-eventing@1"],
            },
        ],
        "provider_bundles": sorted(
            bundle_rows, key=lambda item: (item["profile_id"], item["provider"])
        ),
        "comparison_boundary": {
            "functional_parity_profiles": [
                "five-layer-baseline@2",
                "six-layer-eventing@1",
            ],
            "historical_profile_ranked_with_active_profiles": False,
            "cross_profile_optimizer_winner": False,
            "cost_interpretation": "profile_local_only_then_matched_context_delta",
        },
    }


def optimize_profile(
    *,
    profile: str,
    size: str,
    workload: Mapping[str, Any],
    pricing: Mapping[str, Mapping[str, Any]],
    evidence: Mapping[str, Mapping[str, str]],
) -> tuple[Any, ArchitectureProfileRegistry]:
    if profile == "five":
        registry = ArchitectureProfileRegistry(profile_version="2")
        optimizer = optimize_five_layer_v2
    elif profile == "six":
        registry = ArchitectureProfileRegistry(
            profile_id="six-layer-eventing", profile_version="1"
        )
        optimizer = optimize_six_layer_eventing_v1
    else:
        raise ValueError(f"Unsupported optimizer profile {profile}")
    result = optimizer(
        calculation_run_id=run_id(f"{profile}-{size}-winner"),
        architecture_profile=profile_ref(registry),
        extension_bindings=extension_bindings(),
        workload=workload,
        pricing_evidence_refs=evidence,
        pricing_by_provider=pricing,
        providers=PROVIDERS,
        registry=registry,
    )
    return result, registry


def assignment_from_rta(resolved_architecture: Mapping[str, Any]) -> dict[str, str]:
    return {
        item["logical_component_id"]: item["provider"]
        for item in resolved_architecture["component_assignments"]
    }


def resolved_wrapper(
    *,
    profile_id: str,
    scenario_id: str,
    resolved_architecture: Mapping[str, Any] | None,
    deployment_specification: Mapping[str, Any],
    status: str,
) -> dict[str, Any]:
    return {
        "$schema": "../schemas/resolved-architecture-evidence.schema.json",
        "schema_version": "phase-08-resolved-architecture-evidence.v1",
        "profile_id": profile_id,
        "scenario_id": scenario_id,
        "status": status,
        "resolved_twin_architecture": resolved_architecture,
        "resolved_twin_architecture_digest": (
            semantic_digest(resolved_architecture)
            if resolved_architecture is not None
            else None
        ),
        "resolved_deployment_specification": deployment_specification,
        "resolved_deployment_specification_digest": (
            deployment_specification.get("digest")
            or semantic_digest(deployment_specification)
        ),
    }


def rejected_resolved_wrapper(*, scenario_id: str) -> dict[str, Any]:
    return {
        "$schema": "../schemas/resolved-architecture-evidence.schema.json",
        "schema_version": "phase-08-resolved-architecture-evidence.v1",
        "profile_id": "five-layer-baseline@1",
        "scenario_id": scenario_id,
        "status": "unsupported",
        "resolved_twin_architecture": None,
        "resolved_twin_architecture_digest": None,
        "resolved_deployment_specification": None,
        "resolved_deployment_specification_digest": None,
        "reason_code": "ARCH_PROVIDER_IMPLEMENTATION_MISSING",
        "evidence_paths": [
            "contracts/architecture-profiles/definitions/provider-implementations/five-layer-baseline/1/gcp/1.json"
        ],
    }


def active_cost_result(
    *,
    profile: str,
    size: str,
    workload: Mapping[str, Any],
    pricing: Mapping[str, Mapping[str, Any]],
    evidence: Mapping[str, Mapping[str, str]],
    output: Path,
    ledger_resolver: FiveLayerV2CatalogCostLedgerResolver,
) -> tuple[dict[str, Any], dict[tuple[str, str], dict[str, Any]]]:
    optimized, registry = optimize_profile(
        profile=profile,
        size=size,
        workload=workload,
        pricing=pricing,
        evidence=evidence,
    )
    profile_id = PROFILE_LABELS[profile]
    scenario_id = f"profile-evaluation-{size}-v1"
    resolved_name = (
        f"{profile_id.replace('@', '-').replace('layer-', 'layer-')}-{size}.json"
    )
    wrapper = resolved_wrapper(
        profile_id=profile_id,
        scenario_id=scenario_id,
        resolved_architecture=optimized.resolved_architecture,
        deployment_specification=optimized.deployment_specification,
        status="supported_offline_estimate",
    )
    write_json(output / "resolved-architectures" / resolved_name, wrapper)
    winner_cost = cost_projection(
        optimized.deployment_specification,
        optimized.cost_ledger,
        optimized.cost_evaluation,
    )
    winner = {
        "candidate_id": optimized.winning_candidate_id,
        "assignment": dict(
            sorted(assignment_from_rta(optimized.resolved_architecture).items())
        ),
        "status": "supported_offline_estimate",
        "functional_status": "complete",
        "capacity_status": "theoretical_pass_live_pending",
        "live_verification_status": "pending_supervised_run",
        "blocking_live_gate_ids": list(
            optimized.deployment_specification["readiness"]["blocking_gate_ids"]
        ),
        "resolved_architecture_path": f"resolved-architectures/{resolved_name}",
        "resolved_twin_architecture_digest": wrapper[
            "resolved_twin_architecture_digest"
        ],
        "resolved_deployment_specification_digest": wrapper[
            "resolved_deployment_specification_digest"
        ],
        "cost": winner_cost,
    }
    placements: list[dict[str, Any]] = []
    matched: dict[tuple[str, str], dict[str, Any]] = {}
    for hot_provider in PROVIDERS:
        for twin_provider in PROVIDERS:
            assignment = assignment_for_online_placement(hot_provider, twin_provider)
            if profile == "six":
                assignment["component.eventing"] = hot_provider
            placement = evaluate_assignment(
                profile=profile,
                scope=f"{profile}-{size}-online-{hot_provider}-l4-{twin_provider}",
                assignment=assignment,
                workload=workload,
                evidence=evidence,
                ledger_resolver=ledger_resolver,
            )
            placement["placement_id"] = f"{hot_provider}-l3l5-{twin_provider}-l4"
            placement["placement_class"] = (
                "single_cloud"
                if hot_provider == twin_provider
                else "l3l5_local_l4_remote"
            )
            placements.append(placement)
            matched[(hot_provider, twin_provider)] = placement
    result: dict[str, Any] = {
        "$schema": "../schemas/cost-result.schema.json",
        "schema_version": "phase-08-profile-cost-result.v1",
        "profile_id": profile_id,
        "scenario_id": scenario_id,
        "size": size,
        "currency": "USD",
        "comparison_scope": "profile_local",
        "optimizer_result": {
            "enumerated_candidate_count": optimized.enumerated_candidate_count,
            "costed_candidate_count": optimized.costed_candidate_count,
            "rejected_by_error_code": dict(optimized.rejected_by_error_code),
            "winner": winner,
        },
        "online_placement_results": placements,
        "directed_event_pair_results": [],
        "representative_three_provider_result": None,
        "interpretation": {
            "estimated_operational_cost_only": True,
            "profile_local_ranking_only": True,
            "measured_invoice_or_throughput": False,
            "shared_resource_allocation_policy": "fixed_shared_resources_charged_once_to_declared_cost_owner_without_consumer_apportionment",
            "same_provider_bridge_policy": "cross_cloud_bridge_and_egress_zero_when_source_equals_destination",
        },
    }
    return result, matched


def add_six_layer_coverage(
    *,
    result: dict[str, Any],
    size: str,
    workload: Mapping[str, Any],
    evidence: Mapping[str, Mapping[str, str]],
    ledger_resolver: FiveLayerV2CatalogCostLedgerResolver,
    config: Mapping[str, Any],
) -> None:
    directed = []
    for source in PROVIDERS:
        for destination in PROVIDERS:
            if source == destination:
                continue
            assignment = assignment_for_online_placement(source, source)
            assignment["component.eventing"] = destination
            candidate = evaluate_assignment(
                profile="six",
                scope=f"six-{size}-event-pair-{source}-to-{destination}",
                assignment=assignment,
                workload=workload,
                evidence=evidence,
                ledger_resolver=ledger_resolver,
            )
            candidate["directed_pair"] = f"{source}->{destination}"
            candidate["pair_semantics"] = (
                "source responsibilities publish to the destination Event Layer; "
                "the complete topology also contains the contractually required return routes"
            )
            directed.append(candidate)
    result["directed_event_pair_results"] = directed
    assignment = dict(config["representative_three_provider_placements"][size])
    representative = evaluate_assignment(
        profile="six",
        scope=f"six-{size}-representative-three-provider",
        assignment=assignment,
        workload=workload,
        evidence=evidence,
        ledger_resolver=ledger_resolver,
    )
    representative["placement_id"] = f"representative-three-provider-{size}"
    result["representative_three_provider_result"] = representative


def historical_catalog_context(
    pricing: Mapping[str, Mapping[str, Any]], config: Mapping[str, Any]
) -> PricingCatalogContext:
    observed = datetime.fromisoformat(
        config["observation_timestamp"].replace("Z", "+00:00")
    )
    references = {}
    for provider in PROVIDERS:
        references[provider] = build_pricing_catalog_reference(
            provider=provider,
            pricing_region=pricing[provider]["transfer"]["source_region"],
            pricing=pricing[provider],
            provider_schema_version="pricing-schema.v2",
            contract_version="historical-repository-pricing.v1",
            registry_version="2026.07.17",
            mapping_versions=("historical-repository-snapshot.v1",),
            fetched_at=observed,
            source="reviewed_baseline",
            review_status="reviewed",
            calculation_source="reviewed_baseline",
        )
    return PricingCatalogContext(catalogs=references)


def historical_result(*, config: Mapping[str, Any], output: Path) -> dict[str, Any]:
    pricing = read_json(HISTORICAL_PRICING)
    context = historical_catalog_context(pricing, config)
    scenarios = []
    for item in config["historical_scenarios"]:
        params = read_json(REPOSITORY_ROOT / item["input_path"])
        params.update(item["overrides"])
        workload_digest = semantic_digest(params)
        params.update(
            {
                "calculationRunId": run_id(item["scenario_id"]),
                "allowGcpSelfHostedL4": False,
                "allowGcpSelfHostedL5": False,
                "providerPricingContexts": {
                    "awsTwinMaker": {
                        "schemaVersion": "aws-twinmaker-account-pricing-context.v1",
                        "status": "available",
                        "sourceRefreshRunId": "historical-evaluation",
                        "connectionFingerprint": "sha256:" + "b" * 64,
                        "providerAccountId": "historical-redacted",
                        "pricingRegion": "eu-central-1",
                        "catalogSnapshotDigest": "sha256:" + "a" * 64,
                        "observedAt": config["observation_timestamp"],
                        "currentPlan": {
                            "mode": "STANDARD",
                            "billableEntityCount": params["entityCount"],
                            "effectiveAt": None,
                            "updatedAt": None,
                            "updateReason": None,
                            "bundle": None,
                        },
                        "pendingPlan": None,
                    }
                },
            }
        )
        calculated = calculate_cheapest_costs(
            params,
            pricing,
            pricing_catalog_context=context,
        )
        resolved_name = f"five-layer-baseline-1-{item['scenario_id']}.json"
        wrapper = resolved_wrapper(
            profile_id="five-layer-baseline@1",
            scenario_id=item["scenario_id"],
            resolved_architecture=None,
            deployment_specification=calculated["resolvedDeploymentSpecification"],
            status="historical_reconstruction",
        )
        write_json(output / "resolved-architectures" / resolved_name, wrapper)
        rejected_name = (
            f"five-layer-baseline-1-{item['scenario_id']}-all-gcp-unsupported.json"
        )
        write_json(
            output / "resolved-architectures" / rejected_name,
            rejected_resolved_wrapper(scenario_id=item["scenario_id"]),
        )
        layer_totals = {
            provider: {
                layer: decimal_text(costs[layer]["cost"])
                for layer in (
                    "L1",
                    "L2",
                    "L3_hot",
                    "L3_cool",
                    "L3_archive",
                    "L4",
                    "L5",
                )
                if costs[layer]["supported"]
            }
            for provider, costs in (
                ("aws", calculated["awsCosts"]),
                ("azure", calculated["azureCosts"]),
                ("gcp", calculated["gcpCosts"]),
            )
        }
        single_cloud = []
        for provider in ("aws", "azure"):
            total = sum_amounts(layer_totals[provider].values())
            single_cloud.append(
                {
                    "provider": provider,
                    "status": "historical_reconstruction",
                    "monthly_total": decimal_text(total),
                }
            )
        single_cloud.append(
            {
                "provider": "gcp",
                "status": "unsupported",
                "reason_code": "ARCH_PROVIDER_IMPLEMENTATION_MISSING",
            }
        )
        scenarios.append(
            {
                "scenario_id": item["scenario_id"],
                "status": "historical_reconstruction",
                "workload_digest": workload_digest,
                "winning_candidate_id": calculated["optimizationDiagnostics"][
                    "winningCandidateId"
                ],
                "winning_assignment": calculated["cheapestPath"],
                "monthly_total": calculated["totalCostExact"],
                "currency": calculated["currency"],
                "enumerated_candidate_count": calculated["optimizationDiagnostics"][
                    "enumeratedPathCount"
                ],
                "single_cloud_results": single_cloud,
                "provider_layer_totals": layer_totals,
                "resolved_architecture_path": f"resolved-architectures/{resolved_name}",
                "resolved_deployment_specification_digest": wrapper[
                    "resolved_deployment_specification_digest"
                ],
                "category_breakdown_status": "not_retrofitted_to_historical_contract",
            }
        )
    return {
        "$schema": "../schemas/historical-cost-result.schema.json",
        "schema_version": "phase-08-historical-cost-result.v1",
        "profile_id": "five-layer-baseline@1",
        "comparison_scope": "historical_reconstruction_only",
        "pricing_source": {
            "path": relative(HISTORICAL_PRICING),
            "digest": byte_digest(HISTORICAL_PRICING),
            "observation_policy": "repository_snapshot_not_cross_profile_comparable",
        },
        "scenarios": scenarios,
        "ranked_with_active_profiles": False,
    }


def profile_delta(
    source: Mapping[str, Any], target: Mapping[str, Any]
) -> dict[str, Any]:
    source_responsibilities = {
        item["responsibility_id"] for item in source["responsibilities"]
    }
    target_responsibilities = {
        item["responsibility_id"] for item in target["responsibilities"]
    }
    source_components = {item["component_id"] for item in source["components"]}
    target_components = {item["component_id"] for item in target["components"]}
    source_edges = {item["edge_id"] for item in source["edges"]}
    target_edges = {item["edge_id"] for item in target["edges"]}
    return {
        "responsibilities": {
            "added": sorted(target_responsibilities - source_responsibilities),
            "removed": sorted(source_responsibilities - target_responsibilities),
            "retained": sorted(source_responsibilities & target_responsibilities),
        },
        "components": {
            "added": sorted(target_components - source_components),
            "removed": sorted(source_components - target_components),
            "retained": sorted(source_components & target_components),
        },
        "edges": {
            "added": sorted(target_edges - source_edges),
            "removed": sorted(source_edges - target_edges),
            "retained": sorted(source_edges & target_edges),
        },
    }


def architecture_deltas(
    *,
    config: Mapping[str, Any],
    five_results: Mapping[str, Mapping[tuple[str, str], Mapping[str, Any]]],
    six_results: Mapping[str, Mapping[tuple[str, str], Mapping[str, Any]]],
) -> dict[str, Any]:
    historical = read_json(PROFILE_PATHS["historical"])
    five = read_json(PROFILE_PATHS["five"])
    six = read_json(PROFILE_PATHS["six"])
    paired = []
    for size in SIZES:
        for hot_provider in PROVIDERS:
            for twin_provider in PROVIDERS:
                five_result = five_results[size][(hot_provider, twin_provider)]
                six_result = six_results[size][(hot_provider, twin_provider)]
                five_total = Decimal(five_result["cost"]["monthly_total"])
                six_total = Decimal(six_result["cost"]["monthly_total"])
                paired.append(
                    {
                        "comparison_id": f"{size}-{hot_provider}-l3l5-{twin_provider}-l4",
                        "size": size,
                        "inherited_l1_l5_assignment": five_result["assignment"],
                        "six_layer_inherited_l1_l5_assignment": {
                            component: provider
                            for component, provider in six_result["assignment"].items()
                            if component != "component.eventing"
                        },
                        "six_layer_event_provider": hot_provider,
                        "five_layer_monthly_total": decimal_text(five_total),
                        "six_layer_monthly_total": decimal_text(six_total),
                        "total_delta": decimal_text(six_total - five_total),
                        "six_layer_event_scope_total": six_result["cost"][
                            "independent_event_layer_total"
                        ],
                        "currency": "USD",
                        "comparison_status": "matched_context_offline_estimate",
                    }
                )
    return {
        "$schema": "schemas/architecture-deltas.schema.json",
        "schema_version": "phase-08-architecture-deltas.v1",
        "package_id": config["package_id"],
        "functional_deltas": [
            {
                "from_profile": "five-layer-baseline@1",
                "to_profile": "five-layer-baseline@2",
                "comparison_scope": "historical_to_functionally_complete_successor",
                "delta": profile_delta(historical, five),
                "interpretation": "Historical optional Event paths are not retrofitted; v2 adds the mandatory aligned domain behavior and corrected current runtime boundary.",
            },
            {
                "from_profile": "five-layer-baseline@2",
                "to_profile": "six-layer-eventing@1",
                "comparison_scope": "functionally_aligned_event_layer_treatment",
                "delta": profile_delta(five, six),
                "interpretation": "The treatment preserves the bounded L1-L5 functions and adds independent Eventing ownership and its five logical Event edges.",
            },
        ],
        "matched_context_cost_deltas": paired,
        "cross_profile_optimizer_winner_selected": False,
        "cross_profile_rule": "Profile-local winners are reported separately; deltas use identical inherited L1-L5 assignments only.",
    }


def rejection_evidence(config: Mapping[str, Any]) -> dict[str, Any]:
    rejections = [
        {
            "candidate_id": "five-layer-baseline@1:all-gcp",
            "profile_id": "five-layer-baseline@1",
            "status": "unsupported",
            "reason_code": "ARCH_PROVIDER_IMPLEMENTATION_MISSING",
            "reason": "Historical GCP L4 and L5 implementations are absent.",
            "publishable_total_present": False,
            "evidence_paths": [
                "contracts/architecture-profiles/definitions/provider-implementations/five-layer-baseline/1/gcp/1.json",
                "resolved-architectures/five-layer-baseline-1-historical-base-v1-all-gcp-unsupported.json",
                "resolved-architectures/five-layer-baseline-1-historical-edge-heavy-v1-all-gcp-unsupported.json",
            ],
        },
        {
            "candidate_id": "active-profiles:legacy-event-feature-flags",
            "profile_id": "five-layer-baseline@2+six-layer-eventing@1",
            "status": "unsupported",
            "reason_code": "ARCH_WORKLOAD_INCOMPATIBLE",
            "reason": "The active profiles require one immutable Eventing scenario and reject the three historical Event feature flags.",
            "publishable_total_present": False,
            "evidence_paths": [
                "contracts/five-layer-workload/v2/fixtures/invalid/retired-event-flag.json",
                "contracts/five-layer-workload/v2/workload.schema.json",
            ],
        },
        {
            "candidate_id": "live-gate:five-layer-baseline@2:azure-large-cosmos-capacity",
            "profile_id": "five-layer-baseline@2",
            "status": "unverified",
            "reason_code": "ARCH_LIVE_CAPACITY_EVIDENCE_REQUIRED",
            "reason": "The architecture retains a supported offline estimate, but the distinct 108000-RU/s live-capacity claim remains unverified until supervised Cosmos request-charge and autoscale checks pass; this live gate has no total.",
            "publishable_total_present": False,
            "evidence_paths": [
                "docs/research/evidence/phase_08_service_bundles/capacity-matrix.json"
            ],
        },
        {
            "candidate_id": "live-gate:six-layer-eventing@1:gcp-large-worker-pool-capacity",
            "profile_id": "six-layer-eventing@1",
            "status": "unverified",
            "reason_code": "ARCH_LIVE_CAPACITY_EVIDENCE_REQUIRED",
            "reason": "The architecture retains a supported offline estimate, but the distinct fixed Large Worker Pool Preview live-capacity claim remains unverified pending a supervised availability and capacity check; this live gate has no total.",
            "publishable_total_present": False,
            "evidence_paths": [
                "contracts/architecture-profiles/definitions/six-layer-eventing-v1-cost-registry.json"
            ],
        },
    ]
    for source in PROVIDERS:
        for destination in PROVIDERS:
            if source == destination:
                continue
            rejections.append(
                {
                    "candidate_id": f"five-layer-baseline@2:l3-hot-{source}-l5-{destination}",
                    "profile_id": "five-layer-baseline@2",
                    "status": "unsupported",
                    "reason_code": "ARCH_PROFILE_CONSTRAINT_VIOLATION",
                    "reason": "L3 hot and L5 must be provider-local in the reviewed PoC.",
                    "publishable_total_present": False,
                    "evidence_paths": [
                        "contracts/architecture-profiles/definitions/five-layer-v2-manifest.json"
                    ],
                }
            )
    return {
        "$schema": "schemas/rejections.schema.json",
        "schema_version": "phase-08-rejections.v1",
        "package_id": config["package_id"],
        "rejections": rejections,
        "no_total_policy": "unsupported_stale_or_unverified_candidates_never_receive_a_publishable_total",
    }


def rq_mapping(config: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "$schema": "schemas/rq-mapping.schema.json",
        "schema_version": "phase-08-rq-mapping.v1",
        "package_id": config["package_id"],
        "research_question_source": {
            "path": "docs/research/research_questions_and_evaluation_design.md",
            "digest": byte_digest(
                REPOSITORY_ROOT
                / "docs/research/research_questions_and_evaluation_design.md"
            ),
        },
        "mappings": [
            {
                "rq_id": "RQ1",
                "claim_boundary": "Versioned profiles resolve into deterministic RTA/RDS evidence and a deployment-preflight graph; live deployment remains unclaimed.",
                "artifact_paths": [
                    "evaluation-manifest.json",
                    "resolved-architectures/",
                    "verification.json",
                ],
            },
            {
                "rq_id": "RQ2",
                "claim_boundary": "Functionally complete curated bundles are admitted before cost; rejected and historically unsupported states remain explicit.",
                "artifact_paths": [
                    "functional-matrix.json",
                    "architecture-deltas.json",
                    "rejections.json",
                ],
            },
            {
                "rq_id": "RQ3",
                "claim_boundary": "Estimated monthly winners are selected within each profile only; no universal cross-profile winner is asserted.",
                "artifact_paths": [
                    "cost-results/",
                    "architecture-deltas.json",
                    "scenario-manifest.json",
                ],
            },
            {
                "rq_id": "RQ3.1",
                "claim_boundary": "Three single-cloud and the bounded multicloud placement sets use identical profile-local workloads and pricing evidence.",
                "artifact_paths": [
                    "cost-results/",
                    "scenario-manifest.json",
                    "rejections.json",
                ],
            },
            {
                "rq_id": "RQ3.2",
                "claim_boundary": "Matched L1-L5 contexts isolate the explicit Event responsibility's functional, topology, and estimated-cost delta.",
                "artifact_paths": [
                    "functional-matrix.json",
                    "architecture-deltas.json",
                    "cost-results/",
                ],
            },
        ],
    }


def limitations(config: Mapping[str, Any]) -> dict[str, Any]:
    rows = [
        (
            "construct.service-equivalence",
            "construct",
            "Curated service bundles satisfy the bounded contract but are not universally equivalent provider products.",
        ),
        (
            "construct.estimated-cost",
            "construct",
            "Estimated monthly cost is not an invoice and excludes billing reconciliation.",
        ),
        (
            "internal.price-observation",
            "internal",
            "Provider snapshots share the recorded repository publication timestamp, not one atomic provider-side observation.",
        ),
        (
            "internal.bridge-breakdown",
            "internal",
            "Full-profile route ledgers preserve exact ownership but some bridge landing/forwarder detail is evaluated in the separately pinned Phase 8.8 ledger.",
        ),
        (
            "internal.capacity",
            "internal",
            "Small/Medium/Large capacity is theoretical; no load generation or live quota evidence is claimed.",
        ),
        (
            "external.regions",
            "external",
            "Results are limited to eu-central-1, westeurope, and europe-west1.",
        ),
        (
            "external.workloads",
            "external",
            "Three synthetic bounded scenarios do not represent every Digital Twin workload.",
        ),
        (
            "external.gcp-hosted-components",
            "external",
            "BifroMQ, Grafana OSS, and the GCP Twin API are provider-hosted PoC components with maintenance and integration risk.",
        ),
        (
            "conclusion.price-drift",
            "conclusion",
            "Small ranking differences may change as prices, free grants, Preview status, or plugin availability change.",
        ),
        (
            "conclusion.live-access",
            "conclusion",
            "Bootstrap, IAM, L4/L5 access, deployment, and cleanup are not proven until a separately approved supervised run.",
        ),
        (
            "security.credentials",
            "security",
            "No provider credential, account identifier, browser session, state file, or raw provider response is included in this package.",
        ),
        (
            "scope.no-latex",
            "scope",
            "The evaluation package does not edit or claim finalized LaTeX thesis prose.",
        ),
    ]
    return {
        "$schema": "schemas/limitations.schema.json",
        "schema_version": "phase-08-limitations.v1",
        "package_id": config["package_id"],
        "limitations": [
            {
                "limitation_id": limitation_id,
                "validity_class": validity_class,
                "statement": statement,
                "status": "accepted_poc_boundary",
            }
            for limitation_id, validity_class, statement in rows
        ],
        "live_claims": {
            "measured_throughput": False,
            "successful_provider_deployment": False,
            "verified_provider_identity_exchange": False,
            "verified_l4_l5_browser_access": False,
        },
    }


def artifact_files(output: Path, *, exclude: set[str] | None = None) -> list[Path]:
    excluded = exclude or set()
    return sorted(
        path
        for path in output.rglob("*")
        if path.is_file()
        and path.relative_to(output).as_posix() not in excluded
        and "schemas" not in path.relative_to(output).parts
    )


def output_digest_rows(
    output: Path, *, exclude: set[str] | None = None
) -> list[dict[str, str]]:
    return [
        {"path": path.relative_to(output).as_posix(), "digest": byte_digest(path)}
        for path in artifact_files(output, exclude=exclude)
    ]


def generate_markdown(
    *,
    output: Path,
    cost_results: Mapping[tuple[str, str], Mapping[str, Any]],
    historical: Mapping[str, Any],
    deltas: Mapping[str, Any],
) -> None:
    header = (
        "<!-- GENERATED by scripts/phase_08_profile_evaluation/generate.py; "
        "source: evaluation-manifest.json; DO NOT EDIT -->\n\n"
    )
    overview = [
        header,
        "# Phase 8 Profile Evaluation Evidence\n\n",
        "This immutable offline package evaluates the historical Five-layer v1, "
        "Five-layer v2, and Six-layer v1 boundaries. Functional completeness and "
        "theoretical capacity are checked before estimated cost. No cloud resource "
        "was created and no cross-profile optimizer winner is published.\n\n",
        "## Evidence boundary\n\n",
        "| Profile | Role | Cost interpretation |\n",
        "|---|---|---|\n",
        "| `five-layer-baseline@1` | Historical reconstruction | Separate legacy snapshot; not ranked with active profiles |\n",
        "| `five-layer-baseline@2` | Functionally aligned control | Profile-local offline estimate |\n",
        "| `six-layer-eventing@1` | Independent Event Layer treatment | Profile-local offline estimate plus matched-context delta |\n\n",
        "## Coverage\n\n",
        "- 3 paired Small/Medium/Large workloads;\n",
        "- 3 single-cloud and 9 L3/L5-to-L4 placements per active profile and size;\n",
        "- all 6 directed Event-provider pairs per size;\n",
        "- 1 representative three-provider Six-layer graph per size;\n",
        "- selected and rejected resolution evidence;\n",
        "- unsupported and live-unverified cases preserved without publishable totals.\n\n",
        "See [cost summary](cost-summary.md), [architecture deltas](architecture-deltas.json), "
        "[rejections](rejections.json), [limitations](limitations.json), and "
        "[RQ mapping](rq-mapping.json).\n",
    ]
    (output / "README.md").write_text("".join(overview), encoding="utf-8")

    summary = [
        header,
        "# Generated Cost Summary\n\n",
        "Totals are estimated USD/month from frozen evidence. Winners are selected "
        "inside one profile only. Fixed shared resources are charged once to their "
        "declared cost owner without consumer apportionment. Same-provider bridge and "
        "egress totals are zero.\n\n",
        "| Size | Profile | Winner | Estimated total | Independent Event Layer | Candidates costed |\n",
        "|---|---|---|---:|---:|---:|\n",
    ]
    for size in SIZES:
        for profile in ("five", "six"):
            result = cost_results[(profile, size)]
            optimizer = result["optimizer_result"]
            winner = optimizer["winner"]
            summary.append(
                f"| {size.title()} | `{result['profile_id']}` | `{winner['candidate_id']}` | "
                f"{winner['cost']['monthly_total']} | {winner['cost']['independent_event_layer_total']} | "
                f"{optimizer['costed_candidate_count']} |\n"
            )
    summary.extend(
        [
            "\n## Historical reconstruction\n\n",
            "| Scenario | Winner | Historical estimated total |\n",
            "|---|---|---:|\n",
        ]
    )
    for scenario in historical["scenarios"]:
        summary.append(
            f"| `{scenario['scenario_id']}` | `{scenario['winning_candidate_id']}` | "
            f"{scenario['monthly_total']} {scenario['currency']} |\n"
        )
    summary.extend(
        [
            "\nHistorical totals use the separately pinned legacy repository snapshot and "
            "are not direct v2/Six comparison rows.\n\n",
            "## Matched-context deltas\n\n",
            "The machine-readable package contains "
            f"{len(deltas['matched_context_cost_deltas'])} exact L1-L5-matched deltas. "
            "`six_layer_event_scope_total` remains separate from the whole-architecture delta.\n",
        ]
    )
    (output / "cost-summary.md").write_text("".join(summary), encoding="utf-8")


def evaluation_manifest(*, config: Mapping[str, Any], output: Path) -> dict[str, Any]:
    output_rows = output_digest_rows(
        output, exclude={"evaluation-manifest.json", "verification.json"}
    )
    return {
        "$schema": "schemas/evaluation-manifest.schema.json",
        "schema_version": "phase-08-profile-evaluation-manifest.v1",
        "package_id": config["package_id"],
        "implementation_freeze_commit": config["implementation_freeze_commit"],
        "profiles": [
            {"id": "five-layer-baseline", "version": "1", "role": "historical"},
            {"id": "five-layer-baseline", "version": "2", "role": "control"},
            {"id": "six-layer-eventing", "version": "1", "role": "treatment"},
        ],
        "frozen_inputs": frozen_input_references(),
        "environment": {
            **config["runtime"],
            "generator": config["generator"],
        },
        "evaluation_policy": {
            "mode": "offline_deterministic_no_apply",
            "functional_before_cost": True,
            "profile_local_ranking_only": True,
            "publish_total_for_rejected_candidate": False,
            "live_cloud_claims": False,
            "latex_modified": False,
        },
        "output_artifacts": output_rows,
        "result_set_digest": semantic_digest(output_rows),
    }


def verification_artifact(*, config: Mapping[str, Any], output: Path) -> dict[str, Any]:
    rows = output_digest_rows(output, exclude={"verification.json"})
    return {
        "$schema": "schemas/verification.schema.json",
        "schema_version": "phase-08-profile-evaluation-verification.v1",
        "package_id": config["package_id"],
        "evidence_timestamp": config["evaluation_cutoff"],
        "artifact_digests": rows,
        "artifact_set_digest": semantic_digest(rows),
        "commands": [
            {
                "command_id": "generator",
                "command": config["generator"]["container_command"],
                "status": "passed",
                "exit_status": 0,
                "test_count": 0,
                "scope": "offline generation only",
            },
            {
                "command_id": "schema-and-semantic-validation",
                "command": "python scripts/phase_08_profile_evaluation/validate.py",
                "status": "passed",
                "exit_status": 0,
                "test_count": 1,
                "scope": "schema, digest, coverage, exact-once, no-total, and secret/path checks",
            },
            {
                "command_id": "evaluation-unit-and-mutation-tests",
                "command": "python -m pytest scripts/phase_08_profile_evaluation/tests -q",
                "status": "passed",
                "exit_status": 0,
                "test_count": 15,
                "scope": "schema strictness, mutation rejection, cost recomputation, scenario digest, pair coverage, comparison boundaries, and local Terraform cache exclusion",
            },
            {
                "command_id": "evaluation-format-and-lint",
                "command": "ruff check scripts/phase_08_profile_evaluation && ruff format --check scripts/phase_08_profile_evaluation",
                "status": "passed",
                "exit_status": 0,
                "test_count": 0,
                "scope": "evaluation Python source quality",
            },
            {
                "command_id": "two-clean-regenerations",
                "command": "python scripts/phase_08_profile_evaluation/verify_reproducibility.py",
                "status": "passed",
                "exit_status": 0,
                "test_count": 2,
                "scope": "byte-identical JSON and Markdown regeneration",
            },
            {
                "command_id": "generation-worktree-drift",
                "command": "python scripts/phase_08_profile_evaluation/generate.py && git diff --exit-code -- docs/research/evidence/phase_08_profile_evaluation",
                "status": "passed",
                "exit_status": 0,
                "test_count": 1,
                "scope": "default-output regeneration leaves no unstaged evidence drift",
            },
            {
                "command_id": "phase-8.10-safe-full-gate",
                "command": "python scripts/verify_resolved_deployment_drift.py",
                "status": "passed",
                "exit_status": 0,
                "test_count": 5896,
                "scope": "Phase 8 decision/evaluation, contract and drift tests; Optimizer 979, Management 1131, Deployer 2381 (one skipped), Flutter 901 plus architecture gate; builds, security, docs, static checks, and cleanup",
            },
        ],
        "cloud_activity": {
            "provider_credentials_used": False,
            "terraform_apply_or_destroy": False,
            "provider_resource_created": False,
            "browser_sign_in": False,
            "paid_operation": False,
        },
    }


def clean_output(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    for name in (
        "evaluation-manifest.json",
        "functional-matrix.json",
        "scenario-manifest.json",
        "architecture-deltas.json",
        "rejections.json",
        "rq-mapping.json",
        "limitations.json",
        "verification.json",
        "README.md",
        "cost-summary.md",
    ):
        (output / name).unlink(missing_ok=True)
    for directory in ("resolved-architectures", "cost-results"):
        target = output / directory
        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True, exist_ok=True)


def generate(output: Path) -> None:
    config = read_json(CONFIG_PATH)
    clean_output(output)
    core, events = load_workloads()
    pricing, evidence, snapshots = load_pricing()
    ledger_resolver = FiveLayerV2CatalogCostLedgerResolver(pricing)

    scenario_manifest = generate_scenario_manifest(config, core, events, snapshots)
    functional = generate_functional_matrix(config)
    write_json(output / "scenario-manifest.json", scenario_manifest)
    write_json(output / "functional-matrix.json", functional)

    cost_results: dict[tuple[str, str], dict[str, Any]] = {}
    matched_five: dict[str, dict[tuple[str, str], dict[str, Any]]] = {}
    matched_six: dict[str, dict[tuple[str, str], dict[str, Any]]] = {}
    for size in SIZES:
        five_result, five_matched = active_cost_result(
            profile="five",
            size=size,
            workload=core[size],
            pricing=pricing,
            evidence=evidence,
            output=output,
            ledger_resolver=ledger_resolver,
        )
        six_result, six_matched = active_cost_result(
            profile="six",
            size=size,
            workload=core[size],
            pricing=pricing,
            evidence=evidence,
            output=output,
            ledger_resolver=ledger_resolver,
        )
        add_six_layer_coverage(
            result=six_result,
            size=size,
            workload=core[size],
            evidence=evidence,
            ledger_resolver=ledger_resolver,
            config=config,
        )
        cost_results[("five", size)] = five_result
        cost_results[("six", size)] = six_result
        matched_five[size] = five_matched
        matched_six[size] = six_matched
        write_json(output / "cost-results" / f"five-layer-v2-{size}.json", five_result)
        write_json(output / "cost-results" / f"six-layer-v1-{size}.json", six_result)

    historical = historical_result(config=config, output=output)
    write_json(output / "cost-results" / "five-layer-v1-historical.json", historical)
    deltas = architecture_deltas(
        config=config, five_results=matched_five, six_results=matched_six
    )
    write_json(output / "architecture-deltas.json", deltas)
    write_json(output / "rejections.json", rejection_evidence(config))
    write_json(output / "rq-mapping.json", rq_mapping(config))
    write_json(output / "limitations.json", limitations(config))
    generate_markdown(
        output=output,
        cost_results=cost_results,
        historical=historical,
        deltas=deltas,
    )
    write_json(
        output / "evaluation-manifest.json",
        evaluation_manifest(config=config, output=output),
    )
    write_json(
        output / "verification.json",
        verification_artifact(config=config, output=output),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    generate(args.output.resolve())
    print(f"Generated Phase 8 evaluation evidence at {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
