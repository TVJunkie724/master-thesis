import shutil

import pytest
import yaml

from backend.calculation_v2.components.types import LayerType, Provider
from backend.calculation_v2.transfer_pricing import (
    TransferNetworkTier,
    TransferPricingContractError,
    TransferRouteClass,
)
from backend.pricing_registry import (
    REGISTRY_ROOT,
    load_pricing_registry,
    validate_pricing_registry,
)


def _copy_registry(tmp_path):
    target = tmp_path / "pricing_registry"
    shutil.copytree(REGISTRY_ROOT, target)
    return target


def _mutate_transfer_registry(root, mutator):
    path = root / "transfer_routes.yaml"
    document = yaml.safe_load(path.read_text())
    mutator(document)
    path.write_text(yaml.safe_dump(document, sort_keys=False))


def test_default_transfer_registry_loads_price_free_closed_world_contract():
    transfer = load_pricing_registry().transfer_routes

    assert transfer.registry_version == "2026.07.17"
    assert set(transfer.region_geographies) == set(Provider)
    assert (
        transfer.provider_policies[Provider.GCP].public_route_tier
        == TransferNetworkTier.PREMIUM
    )
    assert set(transfer.supported_routes) == {
        TransferRouteClass.SAME_PROVIDER_SAME_REGION,
        TransferRouteClass.CROSS_PROVIDER_PUBLIC_INTERNET,
    }
    assert transfer.unsupported_route_classes == {
        TransferRouteClass.SAME_PROVIDER_INTER_REGION
    }

    raw = (REGISTRY_ROOT / "transfer_routes.yaml").read_text().lower()
    assert "unit_price" not in raw
    assert "egressprice" not in raw
    assert "retail_price" not in raw


def test_registry_resolves_same_region_and_cross_provider_routes():
    transfer = load_pricing_registry().transfer_routes
    aws_l1 = transfer.endpoint(
        layer=LayerType.L1_INGESTION,
        provider=Provider.AWS,
        region="eu-central-1",
    )
    aws_l2 = transfer.endpoint(
        layer=LayerType.L2_PROCESSING,
        provider=Provider.AWS,
        region="eu-central-1",
    )
    gcp_l2 = transfer.endpoint(
        layer=LayerType.L2_PROCESSING,
        provider=Provider.GCP,
        region="europe-west1",
    )

    same = transfer.resolve_route(
        segment_id="L1_to_L2",
        source=aws_l1,
        destination=aws_l2,
        volume_bytes=1024,
    )
    cross = transfer.resolve_route(
        segment_id="L1_to_L2",
        source=aws_l1,
        destination=gcp_l2,
        volume_bytes=1024,
    )

    assert same.route_class == TransferRouteClass.SAME_PROVIDER_SAME_REGION
    assert same.network_tier == TransferNetworkTier.NOT_APPLICABLE
    assert (
        cross.route_class
        == TransferRouteClass.CROSS_PROVIDER_PUBLIC_INTERNET
    )
    assert cross.network_tier == TransferNetworkTier.PROVIDER_DEFAULT


def test_loaded_registry_collections_are_immutable():
    transfer = load_pricing_registry().transfer_routes

    with pytest.raises(TypeError):
        transfer.region_geographies[Provider.AWS]["eu-west-1"] = (
            transfer.region_geographies[Provider.AWS]["eu-central-1"]
        )
    with pytest.raises(TypeError):
        transfer.provider_policies[Provider.AWS] = transfer.provider_policies[
            Provider.GCP
        ]


def test_registry_fails_closed_for_unmapped_region_and_inter_region_route():
    transfer = load_pricing_registry().transfer_routes
    with pytest.raises(
        TransferPricingContractError,
        match="TRANSFER_REGION_UNMAPPED",
    ):
        transfer.endpoint(
            layer=LayerType.L1_INGESTION,
            provider=Provider.AWS,
            region="eu-west-1",
        )

    source = transfer.endpoint(
        layer=LayerType.L1_INGESTION,
        provider=Provider.AWS,
        region="eu-central-1",
    )
    destination = type(source)(
        layer=LayerType.L2_PROCESSING,
        provider=Provider.AWS,
        region="eu-west-1",
        geography=source.geography,
    )
    with pytest.raises(
        TransferPricingContractError,
        match="TRANSFER_ROUTE_UNSUPPORTED",
    ):
        transfer.resolve_route(
            segment_id="L1_to_L2",
            source=source,
            destination=destination,
            volume_bytes=1024,
        )


@pytest.mark.parametrize(
    "mutator, expected_message",
    [
        (
            lambda doc: doc.update({"unexpected": True}),
            "unknown fields: unexpected",
        ),
        (
            lambda doc: doc["region_geographies"]["aws"].update(
                {"eu-west-1": "moon"}
            ),
            "unsupported value 'moon'",
        ),
        (
            lambda doc: doc["provider_policies"]["gcp"].update(
                {"public_route_tier": "standard"}
            ),
            "gcp baseline requires 'premium'",
        ),
        (
            lambda doc: doc["provider_policies"]["aws"].update(
                {"catalog_tier_path": ["azure", "transfer", "pricing_tiers"]}
            ),
            "must start with provider and transfer",
        ),
        (
            lambda doc: doc["supported_routes"][
                "cross_provider_public_internet"
            ].update({"unit_price": 0.1}),
            "must not define pricing values",
        ),
        (
            lambda doc: doc.update({"registry_version": None}),
            "registry_version must be a non-empty string",
        ),
    ],
)
def test_registry_rejects_unknown_or_unsafe_route_configuration(
    tmp_path,
    mutator,
    expected_message,
):
    root = _copy_registry(tmp_path)
    _mutate_transfer_registry(root, mutator)

    errors = validate_pricing_registry(root)

    assert any(expected_message in error for error in errors)


def test_registry_version_must_include_transfer_contract(tmp_path):
    root = _copy_registry(tmp_path)
    _mutate_transfer_registry(
        root,
        lambda doc: doc.update({"registry_version": "2099.01.01"}),
    )

    errors = validate_pricing_registry(root)

    assert any("must share one registry_version" in error for error in errors)
