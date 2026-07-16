from pathlib import Path

import pytest

from src.provider_capabilities import (
    LAYER_IDS,
    CapabilityAvailability,
    ProviderCapabilityError,
    get_provider_capabilities,
    selections_from_cheapest_path,
    validate_terraform_provider_capabilities,
)
from src.providers.terraform import package_builder


def test_registry_contains_complete_provider_layer_matrix():
    contract = get_provider_capabilities()

    assert contract.schema_version == "provider-service-capabilities.v1"
    assert [item.provider for item in contract.providers] == ["aws", "azure", "gcp"]
    assert all(
        tuple(layer.layer for layer in item.layers) == LAYER_IDS
        for item in contract.providers
    )


def test_gcp_l4_and_l5_are_planned_but_unavailable():
    gcp = next(
        item for item in get_provider_capabilities().providers
        if item.provider == "gcp"
    )

    for layer_id in ("l4", "l5"):
        capability = next(item for item in gcp.layers if item.layer == layer_id)
        assert capability.availability is CapabilityAvailability.UNSUPPORTED
        assert capability.roadmap.value == "planned"
        assert capability.reason_code == "DEPLOYMENT_PATH_NOT_IMPLEMENTED"


def test_nested_and_flat_cheapest_paths_use_canonical_layer_ids():
    assert selections_from_cheapest_path(
        {
            "L1": "AWS",
            "L2": "Azure",
            "L3": {"Hot": "GCP", "Cool": "AWS", "Archive": "Azure"},
            "L4": "AWS",
            "L5": "Azure",
        }
    ) == {
        "l1": "AWS",
        "l2": "Azure",
        "l3_hot": "GCP",
        "l3_cool": "AWS",
        "l3_archive": "Azure",
        "l4": "AWS",
        "l5": "Azure",
    }
    assert selections_from_cheapest_path({"L3_cold": "google"}) == {
        "l3_cool": "google"
    }


def test_package_build_rejects_unavailable_capability_before_filesystem_side_effects(
    tmp_path: Path,
):
    project = tmp_path / "project"

    with pytest.raises(ProviderCapabilityError) as exc_info:
        package_builder.build_all_packages(
            tmp_path / "terraform",
            project,
            {"layer_4_provider": "gcp"},
        )

    assert exc_info.value.violations[0].reason_code == "DEPLOYMENT_PATH_NOT_IMPLEMENTED"
    assert not project.exists()


def test_supported_terraform_configuration_passes_capability_gate():
    validate_terraform_provider_capabilities(
        {
            "layer_1_provider": "gcp",
            "layer_2_provider": "gcp",
            "layer_3_hot_provider": "google",
            "layer_3_cold_provider": "aws",
            "layer_3_archive_provider": "azure",
            "layer_4_provider": "aws",
            "layer_5_provider": "azure",
        }
    )
