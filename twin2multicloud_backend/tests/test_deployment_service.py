"""
Unit tests for deployment_service.py build_project_zip function and helpers.

Tests:
- Build ZIP with complete config
- Build ZIP with minimal config (no optional fields)
- Credential decryption error handling
- Provider normalization
- Resource name extraction
"""

import io
import json
import zipfile
import pytest
from unittest.mock import Mock, patch, MagicMock

from src.services.deployment_service import (
    build_project_zip,
    get_resource_name,
    _build_main_config,
    _build_providers_config,
    _build_credentials_config,
)


class TestGetResourceName:
    """Tests for get_resource_name helper."""
    
    def test_uses_deployer_config_name_when_present(self):
        """Should prefer deployer_config.deployer_digital_twin_name."""
        twin = Mock()
        twin.deployer_config = Mock()
        twin.deployer_config.deployer_digital_twin_name = "my-custom-name"
        twin.name = "Ignored Name"
        
        result = get_resource_name(twin)
        
        assert result == "my-custom-name"
    
    def test_falls_back_to_twin_name(self):
        """Should use normalized twin.name when no deployer config."""
        twin = Mock()
        twin.deployer_config = None
        twin.name = "My Test Twin"
        
        result = get_resource_name(twin)
        
        assert result == "my-test-twin"
    
    def test_handles_special_characters(self):
        """Should handle spaces in twin name."""
        twin = Mock()
        twin.deployer_config = Mock()
        twin.deployer_config.deployer_digital_twin_name = None
        twin.name = "Twin With   Multiple   Spaces"
        
        result = get_resource_name(twin)
        
        assert result == "twin-with---multiple---spaces"


class TestBuildMainConfig:
    """Tests for _build_main_config helper."""
    
    def test_includes_digital_twin_name(self):
        """Should include digital_twin_name from get_resource_name."""
        twin = Mock()
        twin.deployer_config = Mock()
        twin.deployer_config.deployer_digital_twin_name = "test-twin"
        
        result = _build_main_config(twin)
        
        assert result["digital_twin_name"] == "test-twin"
        assert result["mode"] == "production"


class TestBuildProvidersConfig:
    """Tests for _build_providers_config helper."""
    
    def test_normalizes_provider_names_to_lowercase(self):
        """Should convert uppercase provider names to lowercase."""
        twin = Mock()
        twin.optimizer_config = Mock()
        twin.optimizer_config.cheapest_l1 = "AWS"
        twin.optimizer_config.cheapest_l2 = "AZURE"
        twin.optimizer_config.cheapest_l3_hot = "GCP"
        twin.optimizer_config.cheapest_l3_cool = None
        twin.optimizer_config.cheapest_l3_archive = None
        twin.optimizer_config.cheapest_l4 = "AZURE"
        twin.optimizer_config.cheapest_l5 = None
        
        result = _build_providers_config(twin)
        
        assert result["layer_1_provider"] == "aws"
        assert result["layer_2_provider"] == "azure"
        assert result["layer_3_hot_provider"] == "gcp"
        assert result["layer_4_provider"] == "azure"
    
    def test_returns_empty_when_no_optimizer_config(self):
        """Should return empty dict when no optimizer_config."""
        twin = Mock()
        twin.optimizer_config = None
        
        result = _build_providers_config(twin)
        
        assert result == {}
    
    def test_handles_none_values_gracefully(self):
        """Should handle None provider values."""
        twin = Mock()
        twin.optimizer_config = Mock()
        twin.optimizer_config.cheapest_l1 = "AWS"
        twin.optimizer_config.cheapest_l2 = None
        twin.optimizer_config.cheapest_l3_hot = None
        twin.optimizer_config.cheapest_l3_cool = None
        twin.optimizer_config.cheapest_l3_archive = None
        twin.optimizer_config.cheapest_l4 = None
        twin.optimizer_config.cheapest_l5 = None
        
        result = _build_providers_config(twin)
        
        assert result["layer_1_provider"] == "aws"
        assert result["layer_2_provider"] is None


class TestBuildCredentialsConfig:
    """Tests for _build_credentials_config helper."""
    
    @patch("src.services.deployment_service.decrypt")
    def test_decrypts_aws_credentials(self, mock_decrypt):
        """Should decrypt AWS credentials."""
        mock_decrypt.side_effect = lambda val, uid, tid: f"decrypted_{val}"
        
        twin = Mock()
        twin.id = "twin-123"
        twin.configuration = Mock()
        twin.configuration.aws_access_key_id = "enc_key_id"
        twin.configuration.aws_secret_access_key = "enc_secret"
        twin.configuration.aws_session_token = None
        twin.configuration.aws_region = "eu-central-1"
        twin.configuration.azure_subscription_id = None
        twin.configuration.gcp_project_id = None
        
        result, gcp_creds = _build_credentials_config(twin, "user-123")
        
        assert result["aws"]["aws_access_key_id"] == "decrypted_enc_key_id"
        assert result["aws"]["aws_secret_access_key"] == "decrypted_enc_secret"
        assert result["aws"]["aws_region"] == "eu-central-1"
    
    @patch("src.services.deployment_service.decrypt")
    def test_handles_decryption_failure_gracefully(self, mock_decrypt):
        """Should log warning and continue on decryption failure."""
        mock_decrypt.side_effect = ValueError("Decryption failed")
        
        twin = Mock()
        twin.id = "twin-123"
        twin.configuration = Mock()
        twin.configuration.aws_access_key_id = "enc_key_id"
        twin.configuration.aws_secret_access_key = "enc_secret"
        twin.configuration.aws_session_token = None
        twin.configuration.azure_subscription_id = None
        twin.configuration.gcp_project_id = None
        
        result, gcp_creds = _build_credentials_config(twin, "user-123")
        
        # AWS should be missing due to decryption failure
        assert "aws" not in result
    
    def test_returns_empty_when_no_configuration(self):
        """Should return empty tuple when no configuration."""
        twin = Mock()
        twin.configuration = None
        
        result, gcp_creds = _build_credentials_config(twin, "user-123")
        
        assert result == {}
        assert gcp_creds is None


class TestBuildProjectZip:
    """Tests for build_project_zip function."""
    
    @patch("src.services.deployment_service.decrypt")
    def test_creates_valid_zip_file(self, mock_decrypt):
        """Should create a valid ZIP file."""
        mock_decrypt.return_value = "decrypted"
        
        twin = self._create_mock_twin()
        
        result = build_project_zip(twin, "user-123")
        
        assert isinstance(result, io.BytesIO)
        # Verify it's a valid ZIP
        with zipfile.ZipFile(result, 'r') as zf:
            assert zf.testzip() is None  # Returns None if all CRCs OK
    
    @patch("src.services.deployment_service.decrypt")
    def test_contains_required_config_files(self, mock_decrypt):
        """Should contain config.json and config_providers.json."""
        mock_decrypt.return_value = "decrypted"
        
        twin = self._create_mock_twin()
        
        result = build_project_zip(twin, "user-123")
        
        with zipfile.ZipFile(result, 'r') as zf:
            names = zf.namelist()
            assert "config.json" in names
            assert "config_providers.json" in names
            assert "config_credentials.json" in names
    
    @patch("src.services.deployment_service.decrypt")
    def test_includes_state_machine_for_azure_l2(self, mock_decrypt):
        """Should write state machine to azure location for Azure L2."""
        mock_decrypt.return_value = "decrypted"
        
        twin = self._create_mock_twin()
        twin.optimizer_config.cheapest_l2 = "azure"
        twin.deployer_config.state_machine_content = '{"definition": {}}'
        
        result = build_project_zip(twin, "user-123")
        
        with zipfile.ZipFile(result, 'r') as zf:
            names = zf.namelist()
            assert "state_machines/azure_logic_app.json" in names
    
    @patch("src.services.deployment_service.decrypt")
    def test_includes_payloads_json(self, mock_decrypt):
        """Should include payloads.json for simulator."""
        mock_decrypt.return_value = "decrypted"
        
        twin = self._create_mock_twin()
        twin.deployer_config.payloads_json = '{"device_1": {"temp": 25}}'
        
        result = build_project_zip(twin, "user-123")
        
        with zipfile.ZipFile(result, 'r') as zf:
            names = zf.namelist()
            assert "iot_device_simulator/payloads.json" in names
    
    def _create_mock_twin(self):
        """Create a mock twin with minimal required config."""
        twin = Mock()
        twin.id = "twin-123"
        twin.name = "test-twin"
        
        # Deployer config
        twin.deployer_config = Mock()
        twin.deployer_config.deployer_digital_twin_name = "test-twin"
        twin.deployer_config.config_iot_devices_json = None
        twin.deployer_config.config_events_json = None
        twin.deployer_config.user_config_content = None
        twin.deployer_config.hierarchy_content = None
        twin.deployer_config.state_machine_content = None
        twin.deployer_config.processor_contents = None
        twin.deployer_config.processor_requirements = None
        twin.deployer_config.event_action_contents = None
        twin.deployer_config.event_action_requirements = None
        twin.deployer_config.event_feedback_content = None
        twin.deployer_config.event_feedback_requirements = None
        twin.deployer_config.scene_config_content = None
        twin.deployer_config.payloads_json = None
        
        # Optimizer config
        twin.optimizer_config = Mock()
        twin.optimizer_config.cheapest_l1 = "aws"
        twin.optimizer_config.cheapest_l2 = None
        twin.optimizer_config.cheapest_l3_hot = None
        twin.optimizer_config.cheapest_l3_cool = None
        twin.optimizer_config.cheapest_l3_archive = None
        twin.optimizer_config.cheapest_l4 = None
        twin.optimizer_config.cheapest_l5 = None
        twin.optimizer_config.result_json = None
        
        # Configuration (credentials)
        twin.configuration = Mock()
        twin.configuration.aws_access_key_id = "enc_key"
        twin.configuration.aws_secret_access_key = "enc_secret"
        twin.configuration.aws_session_token = None
        twin.configuration.aws_region = "eu-central-1"
        twin.configuration.azure_subscription_id = None
        twin.configuration.gcp_project_id = None
        
        return twin
