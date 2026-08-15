#!/usr/bin/env python3
"""Validate Phase 8 evaluation schemas, digests, coverage, and claim boundaries."""

from __future__ import annotations

import argparse
from decimal import Decimal
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Iterable, Mapping

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PACKAGE = REPOSITORY_ROOT / "docs/research/evidence/phase_08_profile_evaluation"
SCHEMA_DIRECTORY = DEFAULT_PACKAGE / "schemas"
CONFIG_PATH = Path(__file__).with_name("evaluation_config.json")
CONFIG_SCHEMA = Path(__file__).with_name("evaluation-config.schema.json")
PROVIDERS = ("aws", "azure", "gcp")
SIZES = ("small", "medium", "large")
DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
CORE_WORKLOAD_ROOT = REPOSITORY_ROOT / "contracts/five-layer-workload/v2"
EVENT_SCENARIO_CATALOG = CORE_WORKLOAD_ROOT / "eventing-scenario-catalog.json"


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"Expected object: {path}")
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


def repository_path(relative_path: str) -> Path:
    path = (REPOSITORY_ROOT / relative_path).resolve()
    assert path.is_relative_to(REPOSITORY_ROOT.resolve()), relative_path
    return path


def package_path(package: Path, relative_path: str) -> Path:
    package_root = package.resolve()
    path = (package_root / relative_path).resolve()
    assert path.is_relative_to(package_root), relative_path
    return path


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
            {
                "path": child.relative_to(path).as_posix(),
                "digest": byte_digest(child),
            }
        )
    return semantic_digest(records), len(records)


@lru_cache(maxsize=1)
def offline_schema_registry() -> Registry:
    """Build a closed local registry so schema validation never performs I/O."""
    contracts = REPOSITORY_ROOT / "contracts"
    schema_paths = list(contracts.rglob("*.schema.json"))
    schema_paths.extend(contracts.rglob("schema.json"))
    schema_paths.extend(SCHEMA_DIRECTORY.glob("*.json"))
    schema_paths.append(CONFIG_SCHEMA)
    resources: dict[str, Resource] = {}
    for path in sorted(set(schema_paths)):
        contents = read_json(path)
        resource = Resource.from_contents(contents)
        resources[path.resolve().as_uri()] = resource
        schema_id = contents.get("$id")
        if isinstance(schema_id, str) and "://" in schema_id:
            resources[schema_id] = resource
    return Registry().with_resources(resources.items())


def validate_schema(instance: Mapping[str, Any], schema_path: Path) -> None:
    schema = read_json(schema_path)
    validator = Draft202012Validator(
        schema,
        registry=offline_schema_registry(),
        format_checker=FormatChecker(),
    )
    errors = sorted(validator.iter_errors(instance), key=lambda item: list(item.path))
    if errors:
        rendered = "\n".join(
            f"{schema_path.name}:{'/'.join(map(str, error.path)) or '$'}: {error.message}"
            for error in errors[:20]
        )
        raise AssertionError(rendered)


def validate_all_schemas(package: Path) -> None:
    validate_schema(read_json(CONFIG_PATH), CONFIG_SCHEMA)
    mapping = {
        "evaluation-manifest.json": "evaluation-manifest.schema.json",
        "functional-matrix.json": "functional-matrix.schema.json",
        "scenario-manifest.json": "scenario-manifest.schema.json",
        "architecture-deltas.json": "architecture-deltas.schema.json",
        "rejections.json": "rejections.schema.json",
        "rq-mapping.json": "rq-mapping.schema.json",
        "limitations.json": "limitations.schema.json",
        "verification.json": "verification.schema.json",
    }
    for artifact, schema in mapping.items():
        validate_schema(read_json(package / artifact), SCHEMA_DIRECTORY / schema)
    for artifact in sorted((package / "cost-results").glob("*.json")):
        schema = (
            "historical-cost-result.schema.json"
            if artifact.name == "five-layer-v1-historical.json"
            else "cost-result.schema.json"
        )
        validate_schema(read_json(artifact), SCHEMA_DIRECTORY / schema)
    wrapper_schema = SCHEMA_DIRECTORY / "resolved-architecture-evidence.schema.json"
    rejected_wrapper_count = 0
    for artifact in sorted((package / "resolved-architectures").glob("*.json")):
        wrapper = read_json(artifact)
        validate_schema(wrapper, wrapper_schema)
        if wrapper["status"] == "unsupported":
            rejected_wrapper_count += 1
            assert wrapper["resolved_twin_architecture"] is None
            assert wrapper["resolved_twin_architecture_digest"] is None
            assert wrapper["resolved_deployment_specification"] is None
            assert wrapper["resolved_deployment_specification_digest"] is None
            assert wrapper["reason_code"] == "ARCH_PROVIDER_IMPLEMENTATION_MISSING"
            continue
        assert "reason_code" not in wrapper
        assert "evidence_paths" not in wrapper
        if wrapper["resolved_twin_architecture"] is not None:
            validate_schema(
                wrapper["resolved_twin_architecture"],
                REPOSITORY_ROOT
                / "contracts/architecture-profiles/v2/resolved-twin-architecture.schema.json",
            )
            validate_schema(
                wrapper["resolved_deployment_specification"],
                REPOSITORY_ROOT
                / "contracts/resolved-deployment-specification/v2/schema.json",
            )
        else:
            validate_schema(
                wrapper["resolved_deployment_specification"],
                REPOSITORY_ROOT
                / "contracts/resolved-deployment-specification/v1/schema.json",
            )
    assert rejected_wrapper_count == 2


def validate_manifest_digests(package: Path) -> None:
    manifest = read_json(package / "evaluation-manifest.json")
    for reference in manifest["frozen_inputs"]:
        path = repository_path(reference["path"])
        assert path.exists(), reference["path"]
        if reference["kind"] == "tree":
            digest, count = tree_digest(path)
            assert count == reference["file_count"], reference["path"]
        else:
            digest = byte_digest(path)
            assert reference["file_count"] == 1
        assert digest == reference["digest"], reference["path"]
    for row in manifest["output_artifacts"]:
        assert byte_digest(package_path(package, row["path"])) == row["digest"], row[
            "path"
        ]
    assert (
        semantic_digest(manifest["output_artifacts"]) == manifest["result_set_digest"]
    )

    verification = read_json(package / "verification.json")
    for row in verification["artifact_digests"]:
        assert byte_digest(package_path(package, row["path"])) == row["digest"], row[
            "path"
        ]
    assert (
        semantic_digest(verification["artifact_digests"])
        == verification["artifact_set_digest"]
    )


def candidates(result: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
    yield result["optimizer_result"]["winner"]
    yield from result["online_placement_results"]
    yield from result["directed_event_pair_results"]
    if result["representative_three_provider_result"] is not None:
        yield result["representative_three_provider_result"]


def validate_cost(cost: Mapping[str, Any]) -> None:
    category_total = sum(
        (Decimal(value) for value in cost["category_totals"].values()), Decimal(0)
    )
    contribution_total = sum(
        (Decimal(item["monthly_amount"]) for item in cost["contributions"]),
        Decimal(0),
    )
    total = Decimal(cost["monthly_total"])
    assert total == category_total == contribution_total
    owner_ids = [item["cost_owner_id"] for item in cost["contributions"]]
    assert len(owner_ids) == len(set(owner_ids)) == cost["exact_once_owner_count"]
    assert Decimal(cost["event_transport_scope_total"]) >= Decimal(
        cost["independent_event_layer_total"]
    )


def validate_active_results(package: Path) -> None:
    expected_pairs = {
        f"{source}->{destination}"
        for source in PROVIDERS
        for destination in PROVIDERS
        if source != destination
    }
    expected_placements = {
        f"{hot}-l3l5-{twin}-l4" for hot in PROVIDERS for twin in PROVIDERS
    }
    for size in SIZES:
        for profile, expected_count in (("five-layer-v2", 729), ("six-layer-v1", 2187)):
            result = read_json(package / "cost-results" / f"{profile}-{size}.json")
            optimizer = result["optimizer_result"]
            assert optimizer["enumerated_candidate_count"] == expected_count
            assert optimizer["costed_candidate_count"] == expected_count
            assert not optimizer["rejected_by_error_code"]
            assert {
                item["placement_id"] for item in result["online_placement_results"]
            } == expected_placements
            assert (
                sum(
                    item["placement_class"] == "single_cloud"
                    for item in result["online_placement_results"]
                )
                == 3
            )
            for placement in result["online_placement_results"]:
                if placement["placement_class"] == "single_cloud":
                    assert Decimal(placement["cost"]["category_totals"]["bridge"]) == 0
                    assert (
                        Decimal(placement["cost"]["category_totals"]["transfer"]) == 0
                    )
            for candidate in candidates(result):
                assert candidate["status"] == "supported_offline_estimate"
                assert candidate["functional_status"] == "complete"
                assert candidate["capacity_status"] == "theoretical_pass_live_pending"
                validate_cost(candidate["cost"])
            assert (
                result["interpretation"]["shared_resource_allocation_policy"]
                == "fixed_shared_resources_charged_once_to_declared_cost_owner_without_consumer_apportionment"
            )
            assert (
                result["interpretation"]["same_provider_bridge_policy"]
                == "cross_cloud_bridge_and_egress_zero_when_source_equals_destination"
            )
            independent = Decimal(
                optimizer["winner"]["cost"]["independent_event_layer_total"]
            )
            if profile == "five-layer-v2":
                assert independent == 0
                assert result["directed_event_pair_results"] == []
                assert result["representative_three_provider_result"] is None
            else:
                assert independent > 0
                assert {
                    item["directed_pair"]
                    for item in result["directed_event_pair_results"]
                } == expected_pairs
                for pair in result["directed_event_pair_results"]:
                    source, destination = pair["directed_pair"].split("->")
                    assert pair["assignment"]["component.ingestion"] == source
                    assert pair["assignment"]["component.eventing"] == destination
                representative = result["representative_three_provider_result"]
                assert set(representative["assignment"].values()) == set(PROVIDERS)


def validate_scenarios_and_deltas(package: Path) -> None:
    scenarios = read_json(package / "scenario-manifest.json")
    event_catalog = read_json(EVENT_SCENARIO_CATALOG)
    event_scenarios = {item["scenario_id"]: item for item in event_catalog["scenarios"]}
    assert {item["size"] for item in scenarios["paired_scenarios"]} == set(SIZES)
    for item in scenarios["paired_scenarios"]:
        expected_core_path = (
            CORE_WORKLOAD_ROOT / "fixtures/valid" / f"core-{item['size']}.json"
        )
        assert repository_path(item["core_source"]["path"]) == expected_core_path
        assert (
            repository_path(item["eventing_source"]["path"]) == EVENT_SCENARIO_CATALOG
        )
        assert (
            read_json(repository_path(item["core_source"]["path"]))
            == item["core_workload"]
        )
        event_scenario_id = item["eventing_workload"]["scenario_id"]
        assert event_scenarios[event_scenario_id] == item["eventing_workload"]
        assert (
            event_catalog["scenario_digests"][event_scenario_id]
            == item["eventing_source"]["digest"]
        )
        assert item["paired_workload_digest"] == semantic_digest(
            {"core": item["core_workload"], "eventing": item["eventing_workload"]}
        )
        assert (
            item["core_workload"]["eventingScenarioId"]
            == item["eventing_workload"]["scenario_id"]
        )
        assert (
            byte_digest(repository_path(item["core_source"]["path"]))
            == item["core_source"]["digest"]
        )
        assert (
            semantic_digest(item["eventing_workload"])
            == item["eventing_source"]["digest"]
        )
    config = read_json(CONFIG_PATH)
    configured_historical = {
        item["scenario_id"]: item for item in config["historical_scenarios"]
    }
    assert {item["scenario_id"] for item in scenarios["historical_scenarios"]} == set(
        configured_historical
    )
    for item in scenarios["historical_scenarios"]:
        configured = configured_historical[item["scenario_id"]]
        assert item["source"]["path"] == configured["input_path"]
        assert item["overrides"] == configured["overrides"]
        assert item["workload_digest"] == semantic_digest(item["workload"])
        assert (
            byte_digest(repository_path(item["source"]["path"]))
            == item["source"]["digest"]
        )
        expected_workload = read_json(repository_path(item["source"]["path"]))
        expected_workload.update(item["overrides"])
        assert expected_workload == item["workload"]

    deltas = read_json(package / "architecture-deltas.json")
    assert not deltas["cross_profile_optimizer_winner_selected"]
    for row in deltas["matched_context_cost_deltas"]:
        assert (
            row["inherited_l1_l5_assignment"]
            == row["six_layer_inherited_l1_l5_assignment"]
        )
        assert Decimal(row["six_layer_monthly_total"]) - Decimal(
            row["five_layer_monthly_total"]
        ) == Decimal(row["total_delta"])
        assert Decimal(row["six_layer_event_scope_total"]) > 0


def validate_rejections_and_research_mapping(package: Path) -> None:
    rejections = read_json(package / "rejections.json")
    assert len(rejections["rejections"]) >= 10
    for item in rejections["rejections"]:
        assert not item["publishable_total_present"]
        assert "monthly_total" not in item and "total" not in item
        for evidence_path in item["evidence_paths"]:
            path = (
                package_path(package, evidence_path)
                if evidence_path.startswith("resolved-architectures/")
                else repository_path(evidence_path)
            )
            assert path.is_file(), evidence_path
    mapping = read_json(package / "rq-mapping.json")
    source = mapping["research_question_source"]
    assert byte_digest(repository_path(source["path"])) == source["digest"]
    assert {item["rq_id"] for item in mapping["mappings"]} == {
        "RQ1",
        "RQ2",
        "RQ3",
        "RQ3.1",
        "RQ3.2",
    }
    functional = read_json(package / "functional-matrix.json")
    assert functional["evaluation_order"][0] == "functional_completeness"
    assert not functional["comparison_boundary"]["cross_profile_optimizer_winner"]
    expected_capabilities = {
        row["profile_id"]: set(row["domain_capabilities"])
        | set(row["event_layer_capabilities"])
        for row in functional["profile_rows"]
        if row["status"] == "supported"
    }
    assert {
        (bundle["profile_id"], bundle["provider"])
        for bundle in functional["provider_bundles"]
    } == {
        (profile, provider)
        for profile in ("five-layer-baseline@2", "six-layer-eventing@1")
        for provider in PROVIDERS
    }
    for bundle in functional["provider_bundles"]:
        assert (
            set(bundle["present_capabilities"])
            == expected_capabilities[bundle["profile_id"]]
        )
        assert bundle["missing_capabilities"] == []
        assert bundle["extra_capabilities"] == []
        assert bundle["functional_evaluation_status"] == (
            "functionally_complete_before_cost"
        )


def validate_sources() -> None:
    event_sources = read_json(
        REPOSITORY_ROOT / "docs/research/evidence/phase_08_eventing/source-ledger.json"
    )["sources"]
    for source in event_sources:
        assert source["canonical_url"].startswith("https://")
        assert source["retrieved_at"] and source["effective_at"]
        assert DIGEST_PATTERN.fullmatch(source["content_digest"])
        assert source["review_status"] == "reviewed"
    service_sources = read_json(
        REPOSITORY_ROOT
        / "docs/research/evidence/phase_08_service_bundles/source-ledger.json"
    )["sources"]
    for source in service_sources:
        if "url" in source:
            assert source["url"].startswith("https://")
            assert re.fullmatch(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}", source["checked_on"])
        else:
            local_source = repository_path(source["path"])
            assert local_source.is_file()
            assert byte_digest(local_source) == source["byte_digest"]
    artifacts = read_json(
        REPOSITORY_ROOT
        / "docs/research/evidence/phase_08_service_bundles/complete-provider-bundles.json"
    )["pinned_self_hosted_artifacts"]
    for artifact in artifacts:
        assert artifact["license"]
        assert DIGEST_PATTERN.fullmatch(artifact["digest"])


def validate_safe_content(package: Path) -> None:
    forbidden = (
        re.compile(r"/Users/"),
        re.compile(r"AKIA[0-9A-Z]{16}"),
        re.compile(r"arn:aws[^\s\"']*:[0-9]{12}:[^\s\"']*"),
        re.compile(r"/subscriptions/[0-9a-fA-F-]{36}(?:/|\b)"),
        re.compile(r"/projects/[a-z][a-z0-9-]{4,28}[a-z0-9](?:/|\b)"),
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
        re.compile(
            r"(?i)(?:client_secret|access_token|refresh_token|password)\s*[:=]\s*['\"][^'\"]+"
        ),
    )
    for path in sorted(package.rglob("*")):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for pattern in forbidden:
            assert not pattern.search(text), (
                f"unsafe content in {path}: {pattern.pattern}"
            )
        assert "terraform.tfstate" not in text
        assert "2026-08-14T" not in text


def validate_package(package: Path) -> None:
    validate_all_schemas(package)
    validate_manifest_digests(package)
    validate_active_results(package)
    validate_scenarios_and_deltas(package)
    validate_rejections_and_research_mapping(package)
    validate_sources()
    validate_safe_content(package)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path, default=DEFAULT_PACKAGE)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    validate_package(args.package.resolve())
    print("Phase 8 profile evaluation package: valid")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, KeyError, ValueError) as exc:
        print(f"Phase 8 profile evaluation validation failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
