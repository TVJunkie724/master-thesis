"""Tests for deployer credential preflight behavior."""

import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from src.providers.terraform.deployer_strategy import TerraformDeployerStrategy


def _write_project(project_path, providers, credentials):
    project_path.mkdir(parents=True)
    (project_path / "config_providers.json").write_text(json.dumps(providers))
    (project_path / "config_credentials.json").write_text(json.dumps(credentials))


def _strategy(tmp_path, providers, credentials):
    terraform_dir = tmp_path / "src" / "terraform"
    terraform_dir.mkdir(parents=True)
    project_path = tmp_path / "upload" / "factory-twin"
    _write_project(project_path, providers, credentials)
    strategy = TerraformDeployerStrategy(
        terraform_dir=str(terraform_dir),
        project_path=str(project_path),
    )
    selected = {
        "gcp" if provider == "google" else provider for provider in providers.values()
    }
    strategy._resolved_deployment_graph = SimpleNamespace(
        nodes=tuple(
            SimpleNamespace(node_id=f"node.{provider}", provider=provider)
            for provider in sorted(selected)
        )
    )
    return strategy


def test_preflight_allows_valid_aws_credentials(tmp_path):
    strategy = _strategy(
        tmp_path,
        providers={"layer_1_provider": "aws"},
        credentials={
            "aws": {"aws_access_key_id": "key", "aws_secret_access_key": "secret"}
        },
    )

    with patch(
        "src.api.credentials_checker.check_aws_credentials",
        return_value={"status": "valid", "message": "ok"},
    ) as mock_check:
        strategy._validate_credentials()

    mock_check.assert_called_once()


def test_preflight_blocks_partial_aws_permissions(tmp_path):
    strategy = _strategy(
        tmp_path,
        providers={"layer_1_provider": "aws"},
        credentials={
            "aws": {"aws_access_key_id": "key", "aws_secret_access_key": "secret"}
        },
    )

    with patch(
        "src.api.credentials_checker.check_aws_credentials",
        return_value={"status": "partial", "message": "Missing iam:CreateRole"},
    ):
        with pytest.raises(
            ValueError, match="AWS credential preflight failed \\(partial\\)"
        ):
            strategy._validate_credentials()


def test_preflight_sanitizes_checker_messages(tmp_path):
    strategy = _strategy(
        tmp_path,
        providers={"layer_1_provider": "aws"},
        credentials={
            "aws": {"aws_access_key_id": "key", "aws_secret_access_key": "secret"}
        },
    )

    with patch(
        "src.api.credentials_checker.check_aws_credentials",
        return_value={
            "status": "error",
            "message": "Downstream echoed aws_secret_access_key=super-secret-value",
        },
    ):
        with pytest.raises(ValueError) as exc_info:
            strategy._validate_credentials()

    assert "super-secret-value" not in str(exc_info.value)
    assert "Sensitive deployment detail redacted" in str(exc_info.value)


def test_preflight_validates_gcp_when_provider_uses_google_alias(tmp_path):
    strategy = _strategy(
        tmp_path,
        providers={"layer_1_provider": "google"},
        credentials={
            "gcp": {"gcp_project_id": "demo", "gcp_credentials_file": "key.json"}
        },
    )

    with patch(
        "src.api.gcp_credentials_checker.check_gcp_credentials",
        return_value={"status": "valid", "message": "ok"},
    ) as mock_check:
        strategy._validate_credentials()

    mock_check.assert_called_once()


def test_preflight_blocks_gcp_sdk_missing(tmp_path):
    strategy = _strategy(
        tmp_path,
        providers={"layer_1_provider": "gcp"},
        credentials={
            "gcp": {"gcp_project_id": "demo", "gcp_credentials_file": "key.json"}
        },
    )

    with patch(
        "src.api.gcp_credentials_checker.check_gcp_credentials",
        return_value={"status": "sdk_missing", "message": "google SDK missing"},
    ):
        with pytest.raises(
            ValueError, match="GCP credential preflight failed \\(sdk_missing\\)"
        ):
            strategy._validate_credentials()


def test_preflight_uses_eventing_provider_from_graph_not_legacy_layer_fields(tmp_path):
    strategy = _strategy(
        tmp_path,
        providers={"layer_1_provider": "aws"},
        credentials={
            "aws": {"aws_access_key_id": "key", "aws_secret_access_key": "secret"},
            "azure": {
                "azure_subscription_id": "subscription",
                "azure_tenant_id": "tenant",
                "azure_client_id": "client",
                "azure_client_secret": "secret",
            },
        },
    )
    strategy._resolved_deployment_graph = SimpleNamespace(
        nodes=(SimpleNamespace(node_id="node.eventing", provider="azure"),)
    )

    with (
        patch(
            "src.api.azure_credentials_checker.check_azure_credentials",
            return_value={"status": "valid", "message": "ok"},
        ) as azure_check,
        patch("src.api.credentials_checker.check_aws_credentials") as aws_check,
    ):
        strategy._validate_credentials()

    azure_check.assert_called_once()
    aws_check.assert_not_called()
