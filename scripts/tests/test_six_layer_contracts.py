from __future__ import annotations

from scripts import sync_six_layer_contracts as contracts


def test_standalone_six_layer_contract_bundle_is_valid() -> None:
    contracts.validate_source()


def test_six_layer_is_the_only_shared_profile() -> None:
    profile_root = contracts.DEFINITIONS / "profiles"
    assert sorted(path.name for path in profile_root.iterdir()) == [
        "six-layer-eventing"
    ]


def test_six_layer_manifest_has_no_inheritance() -> None:
    manifest = contracts._read(contracts.DEFINITION_MANIFEST_PATH)
    assert not any(key.startswith("inherited_") for key in manifest)
