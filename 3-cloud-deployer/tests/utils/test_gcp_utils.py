"""
Tests for the shared GCP Service Account parsing utility.

This tests the parse_gcp_service_account() function that handles both
file path and raw JSON content inputs.
"""
import pytest
import json
import tempfile
import os
from unittest.mock import patch, MagicMock


class TestParseGcpServiceAccount:
    """Tests for parse_gcp_service_account() function."""

    @pytest.fixture
    def valid_sa_info(self):
        """A valid service account JSON structure."""
        return {
            "type": "service_account",
            "project_id": "test-project-123",
            "private_key_id": "abc123def456ghi789",
            "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvQ...\n-----END PRIVATE KEY-----\n",
            "client_email": "test-sa@test-project-123.iam.gserviceaccount.com",
            "client_id": "123456789012345678901",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/test-sa%40test-project-123.iam.gserviceaccount.com"
        }

    @patch('google.oauth2.service_account.Credentials.from_service_account_info')
    def test_parse_json_content(self, mock_from_info, valid_sa_info):
        """Test parsing raw JSON content (starting with '{')."""
        from src.utils.gcp_utils import parse_gcp_service_account
        
        mock_credentials = MagicMock()
        mock_from_info.return_value = mock_credentials
        
        json_content = json.dumps(valid_sa_info)
        sa_info, display_info, credentials = parse_gcp_service_account(json_content)
        
        # Verify sa_info contains full data
        assert sa_info["project_id"] == "test-project-123"
        assert sa_info["client_email"] == "test-sa@test-project-123.iam.gserviceaccount.com"
        assert "private_key" in sa_info  # Full key present
        
        # Verify display_info has masked private_key_id
        assert display_info["project_id"] == "test-project-123"
        assert display_info["client_email"] == "test-sa@test-project-123.iam.gserviceaccount.com"
        assert display_info["private_key_id"] == "abc123de..."  # Masked
        
        # Verify credentials object was created
        assert credentials == mock_credentials
        mock_from_info.assert_called_once_with(valid_sa_info)

    @patch('google.oauth2.service_account.Credentials.from_service_account_info')
    def test_parse_file_path(self, mock_from_info, valid_sa_info):
        """Test parsing from a file path."""
        from src.utils.gcp_utils import parse_gcp_service_account
        
        mock_credentials = MagicMock()
        mock_from_info.return_value = mock_credentials
        
        # Create temp file with SA JSON
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(valid_sa_info, f)
            temp_path = f.name
        
        try:
            sa_info, display_info, credentials = parse_gcp_service_account(temp_path)
            
            assert sa_info["project_id"] == "test-project-123"
            assert display_info["private_key_id"] == "abc123de..."
            assert credentials == mock_credentials
        finally:
            os.unlink(temp_path)

    def test_invalid_json_content(self):
        """Test error on invalid JSON content."""
        from src.utils.gcp_utils import parse_gcp_service_account
        
        with pytest.raises(ValueError, match="Invalid JSON"):
            parse_gcp_service_account("{not valid json}")

    def test_file_not_found(self):
        """Test error when file path doesn't exist."""
        from src.utils.gcp_utils import parse_gcp_service_account
        
        with pytest.raises(ValueError, match="not found"):
            parse_gcp_service_account("/nonexistent/path/to/sa.json")

    def test_missing_required_fields(self):
        """Test error when required fields are missing."""
        from src.utils.gcp_utils import parse_gcp_service_account
        
        incomplete_sa = json.dumps({
            "type": "service_account",
            "project_id": "test-project"
            # Missing client_email
        })
        
        with pytest.raises(ValueError, match="missing required fields"):
            parse_gcp_service_account(incomplete_sa)

    def test_wrong_type(self):
        """Test error when type is not 'service_account'."""
        from src.utils.gcp_utils import parse_gcp_service_account
        
        wrong_type_sa = json.dumps({
            "type": "authorized_user",  # Wrong type
            "project_id": "test-project",
            "client_email": "user@example.com"
        })
        
        with pytest.raises(ValueError, match="Invalid credential type"):
            parse_gcp_service_account(wrong_type_sa)

    def test_empty_input(self):
        """Test error on empty input."""
        from src.utils.gcp_utils import parse_gcp_service_account
        
        with pytest.raises(ValueError, match="No GCP credentials provided"):
            parse_gcp_service_account("")
        
        with pytest.raises(ValueError, match="No GCP credentials provided"):
            parse_gcp_service_account("   ")

    @patch('google.oauth2.service_account.Credentials.from_service_account_info')
    def test_json_with_whitespace(self, mock_from_info, valid_sa_info):
        """Test parsing JSON content with leading/trailing whitespace."""
        from src.utils.gcp_utils import parse_gcp_service_account
        
        mock_from_info.return_value = MagicMock()
        
        json_content = "  \n  " + json.dumps(valid_sa_info) + "  \n  "
        sa_info, display_info, credentials = parse_gcp_service_account(json_content)
        
        assert sa_info["project_id"] == "test-project-123"

    @patch('google.oauth2.service_account.Credentials.from_service_account_info')
    def test_short_private_key_id(self, mock_from_info):
        """Test display_info handles short private_key_id gracefully."""
        from src.utils.gcp_utils import parse_gcp_service_account
        
        mock_from_info.return_value = MagicMock()
        
        sa_with_short_key = json.dumps({
            "type": "service_account",
            "project_id": "test-project",
            "client_email": "sa@test.iam.gserviceaccount.com",
            "private_key_id": "abc"  # Very short
        })
        
        sa_info, display_info, credentials = parse_gcp_service_account(sa_with_short_key)
        
        # Should not crash, returns short key as-is
        assert display_info["private_key_id"] == "abc"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
