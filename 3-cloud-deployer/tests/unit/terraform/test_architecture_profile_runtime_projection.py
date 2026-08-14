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
