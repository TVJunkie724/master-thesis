"""Unit tests for DiagnosticSettingsHelper.

Tests the REST API helper that replaces the broken azure-mgmt-monitor v7.0.0 SDK.
"""
import pytest
from unittest.mock import MagicMock, patch
from azure.core.exceptions import ClientAuthenticationError

from src.providers.azure.diagnostic_settings_helper import DiagnosticSettingsHelper


@pytest.fixture
def mock_credential():
    """Create a mock Azure credential."""
    credential = MagicMock()
    token = MagicMock()
    token.token = "fake-token"
    credential.get_token.return_value = token
    return credential


@pytest.fixture
def helper(mock_credential):
    """Create a DiagnosticSettingsHelper instance."""
    return DiagnosticSettingsHelper(mock_credential, "fake-subscription-id")


class TestList:
    def test_list_returns_settings(self, helper):
        """Test that list() returns diagnostic settings correctly."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "value": [
                {"name": "logs-to-analytics", "properties": {}},
                {"name": "metrics-to-storage", "properties": {}}
            ]
        }
        
        with patch("requests.request", return_value=mock_response):
            settings = helper.list("/subscriptions/sub/resourceGroups/rg/providers/Microsoft.Devices/IotHubs/hub")
        
        assert len(settings) == 2
        assert settings[0]["name"] == "logs-to-analytics"
        assert settings[1]["name"] == "metrics-to-storage"
    
    def test_list_empty_on_404(self, helper):
        """Test that list() returns empty list on 404."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        
        with patch("requests.request", return_value=mock_response):
            settings = helper.list("/subscriptions/sub/resourceGroups/rg/providers/Microsoft.Devices/IotHubs/hub")
        
        assert settings == []
    
    def test_list_empty_response(self, helper):
        """Test that list() handles empty value array."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"value": []}
        
        with patch("requests.request", return_value=mock_response):
            settings = helper.list("/subscriptions/sub/resourceGroups/rg/providers/Microsoft.Devices/IotHubs/hub")
        
        assert settings == []


class TestDelete:
    def test_delete_success(self, helper):
        """Test that delete() returns True on success."""
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_response.raise_for_status = MagicMock()
        
        with patch("requests.request", return_value=mock_response):
            result = helper.delete(
                "/subscriptions/sub/resourceGroups/rg/providers/Microsoft.Devices/IotHubs/hub",
                "logs-to-analytics"
            )
        
        assert result is True
    
    def test_delete_not_found(self, helper):
        """Test that delete() returns False on 404."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        
        with patch("requests.request", return_value=mock_response):
            result = helper.delete(
                "/subscriptions/sub/resourceGroups/rg/providers/Microsoft.Devices/IotHubs/hub",
                "logs-to-analytics"
            )
        
        assert result is False


class TestRetryAndAuth:
    def test_retry_on_429(self, helper):
        """Test that 429 responses trigger retry with backoff."""
        mock_429 = MagicMock()
        mock_429.status_code = 429
        
        mock_200 = MagicMock()
        mock_200.status_code = 200
        mock_200.json.return_value = {"value": [{"name": "test"}]}
        
        with patch("requests.request", side_effect=[mock_429, mock_429, mock_200]) as mock_req:
            with patch("time.sleep") as mock_sleep:
                settings = helper.list("/subscriptions/sub/resourceGroups/rg/providers/Microsoft.Devices/IotHubs/hub")
        
        assert len(settings) == 1
        assert mock_req.call_count == 3
        assert mock_sleep.call_count == 2
    
    def test_auth_error_on_401(self, helper):
        """Test that 401 raises ClientAuthenticationError."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        
        with patch("requests.request", return_value=mock_response):
            with pytest.raises(ClientAuthenticationError):
                helper.list("/subscriptions/sub/resourceGroups/rg/providers/Microsoft.Devices/IotHubs/hub")

    def test_auth_error_on_403(self, helper):
        """Test that 403 raises ClientAuthenticationError."""
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.text = "Forbidden"

        with patch("requests.request", return_value=mock_response):
            with pytest.raises(ClientAuthenticationError):
                helper.list("/subscriptions/sub/resourceGroups/rg/providers/Microsoft.Devices/IotHubs/hub")


class TestCleanupOutcome:
    def test_provider_scan_failures_are_counted_and_redacted(self, helper, caplog):
        adt_client = MagicMock()
        adt_client.digital_twins.list.side_effect = RuntimeError(
            "azure_client_secret=must-not-leak"
        )
        storage_client = MagicMock()
        storage_client.storage_accounts.list.side_effect = RuntimeError(
            "azure_client_secret=must-not-leak"
        )

        with (
            patch(
                "azure.mgmt.digitaltwins.AzureDigitalTwinsManagementClient",
                return_value=adt_client,
            ),
            patch(
                "azure.mgmt.storage.StorageManagementClient",
                return_value=storage_client,
            ),
            caplog.at_level("WARNING"),
        ):
            result = helper.cleanup_orphaned_by_prefix("factory-twin")

        assert result["errors"] == 2
        assert "must-not-leak" not in caplog.text
