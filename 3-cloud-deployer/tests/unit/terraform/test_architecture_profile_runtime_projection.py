"""Regression tests for graph-selected runtime profile propagation."""

from pathlib import Path


TERRAFORM_ROOT = Path(__file__).resolve().parents[3] / "src" / "terraform"
PROVIDERS_ROOT = TERRAFORM_ROOT.parent / "providers"
PROFILE_EXPRESSION = (
    '"${var.architecture_profile_id}@${var.architecture_profile_version}"'
)


def test_six_layer_runtimes_use_the_standalone_profile() -> None:

    for name in ("azure_six_layer.tf", "gcp_six_layer.tf"):
        source = (TERRAFORM_ROOT / name).read_text(encoding="utf-8")
        assert (
            'value = "six-layer-eventing@1"' in source or PROFILE_EXPRESSION in source
        )


def test_resource_labels_identify_the_selected_profile() -> None:
    azure = (TERRAFORM_ROOT / "azure_six_layer.tf").read_text(encoding="utf-8")
    gcp = (TERRAFORM_ROOT / "gcp_six_layer.tf").read_text(encoding="utf-8")

    assert f"ArchitectureProfile = {PROFILE_EXPRESSION}" in azure
    assert 'architecture-profile = "six-layer-eventing-v1"' in gcp


def test_profile_local_six_layer_runtimes_claim_no_five_layer_identity() -> None:
    roots = (
        PROVIDERS_ROOT / "aws" / "lambda_functions" / "six-layer-domain",
        PROVIDERS_ROOT / "azure" / "azure_functions" / "six-layer-domain",
        PROVIDERS_ROOT / "gcp" / "containers" / "six-layer-domain",
    )

    for root in roots:
        for path in root.rglob("*"):
            if path.is_file() and path.suffix in {".py", ".template"}:
                source = path.read_text(encoding="utf-8")
                assert "five-layer" not in source.lower(), path


def test_six_layer_disables_legacy_shared_token_and_fixes_regions() -> None:
    cross_cloud = (TERRAFORM_ROOT / "cross_cloud.tf").read_text(encoding="utf-8")
    main = (TERRAFORM_ROOT / "main.tf").read_text(encoding="utf-8")

    assert '!local.six_layer_enabled && var.inter_cloud_token == ""' in cross_cloud
    assert 'resource "terraform_data" "phase_8_fixed_region_guard"' in main
    for region in ("eu-central-1", "westeurope", "europe-west1"):
        assert region in main
