"""Contract tests for bounded and single-owner destruction orchestration."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.providers.cleanup_registry import CleanupRequest, resource_name_owned_by_prefix
from src.providers.terraform.cleanup_execution import run_cleanup_attempt
from src.providers.terraform.deployer_strategy import TerraformDeployerStrategy


def _strategy(tmp_path):
    terraform_dir = tmp_path / "terraform-source"
    terraform_dir.mkdir()
    project_path = tmp_path / "project"
    project_path.mkdir()
    return TerraformDeployerStrategy(str(terraform_dir), str(project_path))


@pytest.mark.parametrize("policy", ["", "sometimes", "ALWAYS"])
def test_destroy_rejects_unknown_fallback_policy(tmp_path, policy):
    strategy = _strategy(tmp_path)
    with pytest.raises(ValueError, match="sdk_fallback"):
        strategy.destroy_all(sdk_fallback=policy)


def test_cleanup_requests_use_resource_prefix_and_normalize_google(tmp_path):
    strategy = _strategy(tmp_path)
    strategy._get_terraform_outputs_safe = MagicMock(return_value={})
    context = SimpleNamespace(
        project_name="database-record-id",
        credentials={"gcp": {"project_id": "example"}},
        config=SimpleNamespace(
            digital_twin_name="factory-twin",
            providers={"layer_1_provider": "google"},
            user={},
        ),
    )

    requests = strategy._cleanup_requests(context, dry_run=False)

    assert requests == [
        CleanupRequest(
            provider="gcp",
            credentials=context.credentials,
            prefix="factory-twin",
            dry_run=False,
        )
    ]


def test_cleanup_requests_resolve_gcp_project_and_workspace_credential_path(tmp_path):
    strategy = _strategy(tmp_path)
    strategy._terraform_outputs = {"gcp_project_id": "generated-project"}
    context = SimpleNamespace(
        project_name="database-record-id",
        credentials={
            "gcp": {
                "gcp_credentials_file": "credentials/service-account.json",
            }
        },
        config=SimpleNamespace(
            digital_twin_name="factory-twin",
            providers={"layer_1_provider": "google"},
            user={},
        ),
    )

    request = strategy._cleanup_requests(context, dry_run=False)[0]

    assert request.credentials["gcp"]["gcp_project_id"] == "generated-project"
    assert request.credentials["gcp"]["gcp_credentials_file"] == str(
        strategy.project_path / "credentials" / "service-account.json"
    )
    assert "gcp_project_id" not in context.credentials["gcp"]


def test_cleanup_requests_fail_closed_when_provider_credentials_are_missing(tmp_path):
    strategy = _strategy(tmp_path)
    strategy._terraform_outputs = {}
    context = SimpleNamespace(
        credentials={},
        config=SimpleNamespace(
            digital_twin_name="factory-twin",
            providers={"layer_1_provider": "aws"},
            user={},
        ),
    )

    with pytest.raises(ValueError, match="AWS cleanup credentials"):
        strategy._cleanup_requests(context, dry_run=False)


def test_cleanup_retry_is_bounded_and_redacts_errors(tmp_path, caplog):
    strategy = _strategy(tmp_path)
    request = CleanupRequest(
        provider="aws",
        credentials={"aws": {"aws_secret_access_key": "super-secret"}},
        prefix="factory",
    )

    with (
        caplog.at_level("WARNING"),
        patch(
            "src.providers.terraform.destruction_lifecycle.run_cleanup_attempt",
            side_effect=RuntimeError(
                "aws_secret_access_key=super-secret"
            ),
        ) as attempt,
        patch("src.providers.terraform.destruction_lifecycle.time.sleep"),
    ):
        assert strategy._run_with_retry_and_timeout(request, 2, 30) is False

    assert attempt.call_count == 3
    assert "super-secret" not in caplog.text
    assert "Sensitive deployment detail redacted" in caplog.text


def test_pre_destroy_resource_match_does_not_use_unsafe_substrings():
    assert resource_name_owned_by_prefix("factory", "factory")
    assert resource_name_owned_by_prefix("factory-ab12", "factory")
    assert resource_name_owned_by_prefix("factory_logs", "factory")
    assert not resource_name_owned_by_prefix("other-factory-ab12", "factory")
    assert not resource_name_owned_by_prefix("factory2-ab12", "factory")


def test_cleanup_process_boundary_propagates_provider_errors():
    request = CleanupRequest(
        provider="unsupported",
        credentials={},
        prefix="factory",
        dry_run=True,
    )

    with pytest.raises(RuntimeError, match="Unsupported cleanup provider"):
        run_cleanup_attempt(request, timeout_seconds=10)
