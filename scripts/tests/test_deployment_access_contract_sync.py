from __future__ import annotations

from copy import deepcopy

import pytest

from scripts import sync_deployment_access_contracts as contract_sync


def test_source_contract_covers_exact_nine_placements() -> None:
    snapshots = contract_sync._placement_snapshots()

    assert len(snapshots) == 9
    assert {
        (snapshot["surfaces"][0]["provider"], snapshot["surfaces"][1]["provider"])
        for snapshot in snapshots
    } == {
        (l4, l5)
        for l4 in ("aws", "azure", "gcp")
        for l5 in ("aws", "azure", "gcp")
    }
    assert contract_sync.validate_source().startswith("sha256:")


def test_surface_validation_rejects_provider_auth_mismatch() -> None:
    surface = deepcopy(contract_sync._placement_snapshots()[0]["surfaces"][0])
    surface["auth"]["mode"] = "azure_entra"

    with pytest.raises(ValueError, match="provider/service/auth mismatch"):
        contract_sync.validate_surface(surface)


def test_surface_validation_rejects_url_user_info() -> None:
    surface = deepcopy(contract_sync._placement_snapshots()[0]["surfaces"][0])
    surface["url"] = "https://user:password@example.invalid/path"

    with pytest.raises(ValueError, match="safe absolute HTTPS"):
        contract_sync.validate_surface(surface)
