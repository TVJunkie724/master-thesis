"""Regression tests for graph-selected runtime profile propagation."""

from pathlib import Path


TERRAFORM_ROOT = Path(__file__).resolve().parents[3] / "src" / "terraform"
PROFILE_EXPRESSION = (
    '"${var.architecture_profile_id}@${var.architecture_profile_version}"'
)


def test_inherited_azure_and_gcp_runtimes_use_the_resolved_profile() -> None:
    """Six-layer inheritance must not relabel neutral runtimes as Five-layer."""

    for name in ("azure_five_layer_v2.tf", "gcp_five_layer_v2.tf"):
        source = (TERRAFORM_ROOT / name).read_text(encoding="utf-8")
        assert 'value = "five-layer-baseline@2"' not in source
        assert 'ARCHITECTURE_PROFILE     = "five-layer-baseline@2"' not in source
        assert 'ARCHITECTURE_PROFILE        = "five-layer-baseline@2"' not in source
        assert PROFILE_EXPRESSION in source


def test_inherited_resource_labels_identify_the_selected_profile() -> None:
    azure = (TERRAFORM_ROOT / "azure_five_layer_v2.tf").read_text(
        encoding="utf-8"
    )
    gcp = (TERRAFORM_ROOT / "gcp_five_layer_v2.tf").read_text(encoding="utf-8")

    assert f"ArchitectureProfile = {PROFILE_EXPRESSION}" in azure
    assert (
        'architecture-profile = local.six_layer_eventing_enabled ? '
        '"six-layer-eventing-v1" : "five-layer-v2"'
    ) in gcp
