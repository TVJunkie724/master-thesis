"""Tests for configuration response helper provider normalization."""

from types import SimpleNamespace

from src.api.helpers.config_builder import check_provider_configured


def test_check_provider_configured_accepts_google_alias():
    config = SimpleNamespace(gcp_cloud_connection_id="connection-gcp")

    assert check_provider_configured(config, "Google") is True
