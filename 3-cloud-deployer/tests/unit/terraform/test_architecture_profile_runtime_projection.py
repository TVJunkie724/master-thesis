"""Regression tests for graph-selected runtime profile propagation."""

from pathlib import Path


TERRAFORM_ROOT = Path(__file__).resolve().parents[3] / "src" / "terraform"
PROVIDERS_ROOT = TERRAFORM_ROOT.parent / "providers"
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
    azure = (TERRAFORM_ROOT / "azure_five_layer_v2.tf").read_text(encoding="utf-8")
    gcp = (TERRAFORM_ROOT / "gcp_five_layer_v2.tf").read_text(encoding="utf-8")

    assert f"ArchitectureProfile = {PROFILE_EXPRESSION}" in azure
    assert (
        "architecture-profile = local.six_layer_eventing_enabled ? "
        '"six-layer-eventing-v1" : "five-layer-v2"'
    ) in gcp


def test_profile_local_six_layer_runtimes_do_not_claim_five_layer_identity() -> None:
    roots = (
        PROVIDERS_ROOT / "aws" / "lambda_functions" / "six-layer-domain",
        PROVIDERS_ROOT / "azure" / "azure_functions" / "six-layer-domain",
        PROVIDERS_ROOT / "gcp" / "containers" / "six-layer-domain",
    )

    for root in roots:
        for path in root.rglob("*"):
            if path.is_file() and path.suffix in {".py", ".template"}:
                source = path.read_text(encoding="utf-8")
                assert "five-layer-baseline@2" not in source, path
                assert "Five-layer v2" not in source, path


def test_phase8_profiles_disable_predecessor_shared_token_and_fix_regions() -> None:
    cross_cloud = (TERRAFORM_ROOT / "cross_cloud.tf").read_text(encoding="utf-8")
    main = (TERRAFORM_ROOT / "main.tf").read_text(encoding="utf-8")

    assert '!local.five_layer_v2_enabled && var.inter_cloud_token == ""' in cross_cloud
    assert 'resource "terraform_data" "phase_8_fixed_region_guard"' in main
    for region in ("eu-central-1", "westeurope", "europe-west1"):
        assert region in main
