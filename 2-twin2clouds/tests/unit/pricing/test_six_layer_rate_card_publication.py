"""Immutable Six-layer rate-card publication coverage."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import scripts.publish_six_layer_rate_cards as publisher
from backend.pricing_catalog_models import canonical_json_bytes
from scripts.publish_six_layer_rate_cards import (
    RATE_CARD_KEY,
    ROUTE_CLASSES,
    SOURCE_PATH,
    _digest,
    _expected_publication,
)


ROOT = Path(__file__).resolve().parents[3]
BASELINE_ROOT = ROOT / "json" / "pricing_catalog_baselines"
CAPACITY_REGISTRY = (
    ROOT
    / "backend"
    / "contracts"
    / "generated"
    / "resolved-deployment-specification"
    / "v2"
    / "component-capacity-registry.json"
)


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_publication_is_deterministic_and_covers_every_registered_dimension():
    expected_manifest, snapshots = _expected_publication()
    actual_manifest = _read(BASELINE_ROOT / "baseline.json")
    source = _read(SOURCE_PATH)
    registry = _read(CAPACITY_REGISTRY)

    assert actual_manifest == expected_manifest.to_storage_dict()
    assert set(snapshots) == {"aws", "azure", "gcp"}

    conversions = set()
    for provider, snapshot in snapshots.items():
        reference = snapshot.reference
        path = (
            BASELINE_ROOT
            / provider
            / reference.pricing_region
            / "snapshots"
            / f"{reference.snapshot_id}.json"
        )
        assert path.read_bytes() == canonical_json_bytes(snapshot.to_storage_dict())

        card = snapshot.pricing[RATE_CARD_KEY]
        evidence = snapshot.pricing["__evidence__"][RATE_CARD_KEY]
        conversions.add(tuple(sorted(card["currencyConversions"].items())))
        assert evidence["source_manifest_digest"] == _digest(source)
        assert evidence["rate_card_digest"] == _digest(card)
        assert set(card["routeRates"]) == set(ROUTE_CLASSES)

        registered = {
            component["component_id"]: set(component["capacity_dimensions"])
            for component in registry["components"]
            if component["provider"] == provider
        }
        assert set(card["componentRates"]) == set(registered)
        for component_id, rate in card["componentRates"].items():
            for variant in rate["variants"]:
                billed = {meter["dimension"] for meter in variant["meters"]}
                non_billable = set(variant["nonBillableDimensions"])
                selectors = set(variant["selectors"])
                assert not billed & non_billable
                assert billed | non_billable == registered[component_id]
                assert selectors <= registered[component_id]

    assert len(conversions) == 1


def test_active_rates_keep_reviewed_command_and_cloud_run_model():
    source = _read(SOURCE_PATH)

    aws_rates = source["providers"]["aws"]["rates"]
    aws_source_ids = {
        item["sourceId"] for item in source["providers"]["aws"]["sources"]
    }
    assert "aws-public-price-list-iot-device-management" in aws_source_ids
    assert Decimal(aws_rates["iotCommandExecution"]) == Decimal("0.0000065")
    assert Decimal(aws_rates["iotCommandFreeExecutions"]) == 0

    gcp_rates = source["providers"]["gcp"]["rates"]
    gcp_source_ids = {
        item["sourceId"] for item in source["providers"]["gcp"]["sources"]
    }
    assert "gcp-cloud-run-request-based-pricing" in gcp_source_ids
    assert Decimal(gcp_rates["cloudRunRequest"]) == Decimal("0.0000004")
    assert Decimal(gcp_rates["cloudRunVcpuSecond"]) == Decimal("0.000024")
    assert Decimal(gcp_rates["cloudRunMemoryGibSecond"]) == Decimal("0.0000025")

    _, snapshots = _expected_publication()
    cloud_run = snapshots["gcp"].pricing[RATE_CARD_KEY]["componentRates"][
        "gcp.cloud-run-service"
    ]["variants"][0]
    assert all(meter["freeQuantity"] == "0" for meter in cloud_run["meters"])


def test_azure_iot_hub_uses_exact_frozen_scenario_capacity_prices():
    _, snapshots = _expected_publication()
    variants = snapshots["azure"].pricing[RATE_CARD_KEY]["componentRates"][
        "azure.iot-hub"
    ]["variants"]

    assert {
        variant["selectors"]["messages"]: variant["meters"][0]["minimumCharge"]
        for variant in variants
    } == {
        2_160_000: "25",
        345_600_000: "500",
        12_960_000_000: "5000",
    }


def test_rate_cards_keep_provider_meter_ownership_and_large_capacity_exact():
    _, snapshots = _expected_publication()
    aws = snapshots["aws"].pricing[RATE_CARD_KEY]["componentRates"]
    azure = snapshots["azure"].pricing[RATE_CARD_KEY]["componentRates"]
    gcp = snapshots["gcp"].pricing[RATE_CARD_KEY]["componentRates"]

    sns_variants = aws["aws.sns-fifo"]["variants"]
    assert len(sns_variants) == 3
    assert all(
        Decimal(variant["meters"][0]["tiers"][0]["pricePerUnit"])
        > Decimal("0.00000036")
        for variant in sns_variants
    )

    cosmos_variants = azure["azure.cosmos-db-nosql-raw-and-rollup"]["variants"]
    serverless = next(
        item
        for item in cosmos_variants
        if item["selectors"] == {"capacity_mode": "serverless"}
    )
    autoscale = next(
        item
        for item in cosmos_variants
        if item["selectors"] == {"capacity_mode": "autoscale"}
    )
    assert serverless["meters"][0]["tiers"][0]["pricePerUnit"] == "0.000000305"
    assert autoscale["meters"][0]["tiers"][0]["pricePerUnit"] == "0.0876"

    remote_event_hub = azure[
        "azure.event-hubs-only-for-reviewed-remote-telemetry-edge"
    ]["variants"][0]
    assert {item["dimension"] for item in remote_event_hub["meters"]} == {
        "throughput_unit_hours",
        "capacity_unit_hours",
    }

    adapter = gcp["gcp.ordered-mqtt-pubsub-adapter"]["variants"][0]
    broker = gcp["gcp.pubsub-separated-embedded-topics"]["variants"][0]
    assert {item["dimension"] for item in adapter["meters"]} == {"node_hours"}
    assert {item["dimension"] for item in broker["meters"]} == {
        "publish_bytes",
        "delivery_bytes",
    }


def test_every_tracked_predecessor_resolves_to_retained_snapshots():
    for history_path in sorted((BASELINE_ROOT / "history").glob("baseline-*.json")):
        manifest = _read(history_path)
        for provider, reference in manifest["catalogs"].items():
            assert (
                BASELINE_ROOT
                / provider
                / reference["pricing_region"]
                / "snapshots"
                / f"{reference['snapshot_id']}.json"
            ).is_file()


def test_predecessor_archiving_is_canonical_and_idempotent(tmp_path, monkeypatch):
    predecessor_path = (
        BASELINE_ROOT / "history" / "baseline-2026.07.18-57f6deebe5a3.json"
    )
    predecessor = _read(predecessor_path)
    baseline_path = tmp_path / "baseline.json"
    history_root = tmp_path / "history"
    canonical = canonical_json_bytes(predecessor)
    baseline_path.write_bytes(canonical)
    monkeypatch.setattr(publisher, "BASELINE_PATH", baseline_path)
    monkeypatch.setattr(publisher, "HISTORY_ROOT", history_root)

    publisher._archive_current_manifest(canonical)
    publisher._archive_current_manifest(canonical)

    archived = list(history_root.glob("baseline-*.json"))
    assert len(archived) == 1
    assert archived[0].read_bytes() == canonical
