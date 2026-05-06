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
from types import SimpleNamespace
from unittest.mock import Mock, patch, MagicMock

from src.services.deployment_service import (
    DEPLOYMENT_MANIFEST_FILE,
    build_project_zip,
    get_resource_name,
    _build_main_config,
    _build_providers_config,
    _build_credentials_config,
    _build_deployment_manifest,
    _build_optimization_config,
)
from src.services.credential_resolution_service import DeploymentCredentials
from src.services.errors import CredentialResolutionFailed
from src.utils.crypto import encrypt_scoped


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
        twin.optimizer_config = Mock()
        twin.optimizer_config.params = json.dumps({
            "hotStorageDurationInMonths": 2,
            "coolStorageDurationInMonths": 6,
        })
        twin.configuration = Mock()
        twin.configuration.debug_mode = False
        
        result = _build_main_config(twin)
        
        assert result["digital_twin_name"] == "test-twin"
        assert result["mode"] == "production"
        assert result["hot_storage_size_in_days"] == 60
        assert result["cold_storage_size_in_days"] == 180
    
    def test_storage_days_from_optimizer_params(self):
        """Should convert months to days from optimizer params."""
        twin = Mock()
        twin.deployer_config = Mock()
        twin.deployer_config.deployer_digital_twin_name = "test"
        twin.optimizer_config = Mock()
        twin.optimizer_config.params = json.dumps({
            "hotStorageDurationInMonths": 1,
            "coolStorageDurationInMonths": 3,
        })
        twin.configuration = None
        
        result = _build_main_config(twin)
        
        assert result["hot_storage_size_in_days"] == 30
        assert result["cold_storage_size_in_days"] == 90
    
    def test_storage_days_defaults_when_no_params(self):
        """Should use defaults (30/90) when no optimizer params."""
        twin = Mock()
        twin.deployer_config = Mock()
        twin.deployer_config.deployer_digital_twin_name = "test"
        twin.optimizer_config = None
        twin.configuration = None
        
        result = _build_main_config(twin)
        
        assert result["hot_storage_size_in_days"] == 30
        assert result["cold_storage_size_in_days"] == 90
    
    def test_mode_from_debug_mode(self):
        """Should set mode based on debug_mode flag."""
        twin = Mock()
        twin.deployer_config = Mock()
        twin.deployer_config.deployer_digital_twin_name = "test"
        twin.optimizer_config = None
        twin.configuration = Mock()
        twin.configuration.debug_mode = True
        
        result = _build_main_config(twin)
        
        assert result["mode"] == "debug"


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
        assert result["layer_3_hot_provider"] == "google"
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
    
    @patch("src.services.credential_resolution_service.decrypt")
    def test_decrypts_aws_credentials(self, mock_decrypt):
        """Should decrypt AWS credentials."""
        mock_decrypt.side_effect = lambda val, uid, tid: f"decrypted_{val}"
        
        twin = Mock()
        twin.id = "twin-123"
        twin.optimizer_config = None
        twin.configuration = Mock()
        twin.configuration.aws_access_key_id = "enc_key_id"
        twin.configuration.aws_secret_access_key = "enc_secret"
        twin.configuration.aws_session_token = None
        twin.configuration.aws_region = "eu-central-1"
        twin.configuration.aws_sso_region = None
        twin.configuration.aws_cloud_connection_id = None
        twin.configuration.azure_subscription_id = None
        twin.configuration.azure_cloud_connection_id = None
        twin.configuration.gcp_project_id = None
        twin.configuration.gcp_cloud_connection_id = None
        twin.configuration.gcp_billing_account = None
        twin.configuration.gcp_service_account_json = None
        
        result, gcp_creds = _build_credentials_config(twin, "user-123")
        
        assert result["aws"]["aws_access_key_id"] == "decrypted_enc_key_id"
        assert result["aws"]["aws_secret_access_key"] == "decrypted_enc_secret"
        assert result["aws"]["aws_region"] == "eu-central-1"
    
    @patch("src.services.credential_resolution_service.decrypt")
    def test_raises_structured_error_on_decryption_failure(self, mock_decrypt):
        """Should fail closed with a structured, secret-safe credential error."""
        mock_decrypt.side_effect = ValueError("Decryption failed")
        
        twin = Mock()
        twin.id = "twin-123"
        twin.optimizer_config = None
        twin.configuration = Mock()
        twin.configuration.aws_access_key_id = "enc_key_id"
        twin.configuration.aws_secret_access_key = "enc_secret"
        twin.configuration.aws_session_token = None
        twin.configuration.aws_sso_region = None
        twin.configuration.aws_cloud_connection_id = None
        twin.configuration.azure_subscription_id = None
        twin.configuration.azure_cloud_connection_id = None
        twin.configuration.gcp_project_id = None
        twin.configuration.gcp_cloud_connection_id = None
        twin.configuration.gcp_billing_account = None
        twin.configuration.gcp_service_account_json = None
        
        with pytest.raises(CredentialResolutionFailed) as exc_info:
            _build_credentials_config(twin, "user-123")

        assert exc_info.value.errors == [
            {
                "provider": "aws",
                "code": "LEGACY_CREDENTIAL_DECRYPTION_FAILED",
                "field": "credentials",
                "message": "Legacy credentials cannot be decrypted",
            }
        ]
        assert "enc_secret" not in str(exc_info.value.errors)
    
    def test_raises_structured_error_when_no_configuration(self):
        """Should fail closed when no credential source is configured."""
        twin = Mock()
        twin.optimizer_config = None
        twin.configuration = None
        
        with pytest.raises(CredentialResolutionFailed) as exc_info:
            _build_credentials_config(twin, "user-123")

        assert exc_info.value.errors[0]["code"] == "NO_DEPLOYMENT_PROVIDERS"

    def test_prefers_bound_aws_cloud_connection(self):
        """CloudConnection bindings should override legacy encrypted fields."""
        payload = {
            "aws_access_key_id": "AKIAIOSFODNN7EXAMPLE",
            "aws_secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            "aws_region": "eu-central-1",
        }
        connection = SimpleNamespace(
            id="connection-aws",
            encrypted_payload=encrypt_scoped(json.dumps(payload), "user-123", "connection-aws"),
        )
        twin = SimpleNamespace(
            id="twin-123",
            configuration=SimpleNamespace(
                aws_cloud_connection_id="connection-aws",
                aws_cloud_connection=connection,
                aws_access_key_id="legacy_enc_key",
                azure_cloud_connection_id=None,
                azure_subscription_id=None,
                gcp_cloud_connection_id=None,
                gcp_project_id=None,
            ),
        )

        result, gcp_creds = _build_credentials_config(twin, "user-123")

        assert result["aws"] == payload
        assert gcp_creds is None

    def test_bound_gcp_cloud_connection_writes_separate_credentials_file(self):
        """GCP CloudConnections keep service account JSON in the separate deployer file."""
        service_account = {
            "type": "service_account",
            "client_email": "deployer@example.iam.gserviceaccount.com",
        }
        payload = {
            "gcp_project_id": "demo-project",
            "gcp_billing_account": "012345-6789AB-CDEF01",
            "gcp_region": "europe-west1",
            "gcp_credentials_file": json.dumps(service_account),
        }
        connection = SimpleNamespace(
            id="connection-gcp",
            encrypted_payload=encrypt_scoped(json.dumps(payload), "user-123", "connection-gcp"),
        )
        twin = SimpleNamespace(
            id="twin-123",
            configuration=SimpleNamespace(
                aws_cloud_connection_id=None,
                aws_access_key_id=None,
                azure_cloud_connection_id=None,
                azure_subscription_id=None,
                gcp_cloud_connection_id="connection-gcp",
                gcp_cloud_connection=connection,
                gcp_project_id=None,
            ),
        )

        result, gcp_creds = _build_credentials_config(twin, "user-123")

        assert result["gcp"]["gcp_project_id"] == "demo-project"
        assert result["gcp"]["gcp_credentials_file"] == "gcp_credentials.json"
        assert gcp_creds == service_account


class TestBuildProjectZip:
    """Tests for build_project_zip function."""
    
    @patch("src.services.credential_resolution_service.decrypt")
    def test_creates_valid_zip_file(self, mock_decrypt):
        """Should create a valid ZIP file."""
        mock_decrypt.return_value = "decrypted"
        
        twin = self._create_mock_twin()
        
        result = build_project_zip(twin, "user-123")
        
        assert isinstance(result, io.BytesIO)
        # Verify it's a valid ZIP
        with zipfile.ZipFile(result, 'r') as zf:
            assert zf.testzip() is None  # Returns None if all CRCs OK
    
    @patch("src.services.credential_resolution_service.decrypt")
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
            assert DEPLOYMENT_MANIFEST_FILE in names

    @patch("src.services.credential_resolution_service.decrypt")
    def test_includes_secrets_free_deployment_manifest(self, mock_decrypt):
        """Should include a deployment manifest without credential payloads."""
        mock_decrypt.side_effect = lambda value, *_args: f"plain-{value}"

        twin = self._create_mock_twin()

        result = build_project_zip(twin, "user-123")

        with zipfile.ZipFile(result, 'r') as zf:
            manifest = json.loads(zf.read(DEPLOYMENT_MANIFEST_FILE))
            manifest_text = json.dumps(manifest)

        assert manifest["manifest_version"] == "1.0"
        assert manifest["generated_at"].endswith("Z")
        assert manifest["producer"] == "twin2multicloud_backend"
        assert manifest["twin"]["id"] == "twin-123"
        assert manifest["twin"]["resource_name"] == "test-twin"
        assert manifest["providers"] == {"layer_1_provider": "aws"}
        assert manifest["credentials"] == {
            "providers": ["aws"],
            "sources": {"aws": "legacy"},
            "contains_secret_payloads": False,
        }
        assert "config_credentials.json" in manifest["package"]["files"]
        assert DEPLOYMENT_MANIFEST_FILE not in manifest["package"]["files"]
        assert "plain-enc_secret" not in manifest_text
        assert "plain-enc_key" not in manifest_text
        assert "aws_secret_access_key" not in manifest_text
    
    @patch("src.services.credential_resolution_service.decrypt")
    def test_includes_state_machine_for_azure_l2(self, mock_decrypt):
        """Should write state machine to azure location for Azure L2."""
        mock_decrypt.return_value = "decrypted"
        
        twin = self._create_mock_twin()
        twin.optimizer_config.cheapest_l2 = "azure"
        twin.deployer_config.state_machine_content = '{"definition": {}}'
        twin.configuration.azure_subscription_id = "enc_subscription"
        twin.configuration.azure_tenant_id = "enc_tenant"
        twin.configuration.azure_client_id = "enc_client"
        twin.configuration.azure_client_secret = "enc_client_secret"

        result = build_project_zip(twin, "user-123")
        
        with zipfile.ZipFile(result, 'r') as zf:
            names = zf.namelist()
            assert "state_machines/azure_logic_app.json" in names
    
    @patch("src.services.credential_resolution_service.decrypt")
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
        twin.optimizer_config.params = json.dumps({
            "hotStorageDurationInMonths": 1,
            "coolStorageDurationInMonths": 3,
            "useEventChecking": True,
            "triggerNotificationWorkflow": False,
            "returnFeedbackToDevice": False,
            "integrateErrorHandling": False,
            "needs3DModel": False,
        })
        
        # Configuration (credentials)
        twin.configuration = Mock()
        twin.configuration.debug_mode = False
        twin.configuration.aws_cloud_connection_id = None
        twin.configuration.aws_cloud_connection = None
        twin.configuration.aws_access_key_id = "enc_key"
        twin.configuration.aws_secret_access_key = "enc_secret"
        twin.configuration.aws_session_token = None
        twin.configuration.aws_region = "eu-central-1"
        twin.configuration.aws_sso_region = None
        twin.configuration.azure_cloud_connection_id = None
        twin.configuration.azure_cloud_connection = None
        twin.configuration.azure_subscription_id = None
        twin.configuration.azure_tenant_id = None
        twin.configuration.azure_client_id = None
        twin.configuration.azure_client_secret = None
        twin.configuration.azure_region = "westeurope"
        twin.configuration.azure_region_iothub = None
        twin.configuration.azure_region_digital_twin = None
        twin.configuration.gcp_cloud_connection_id = None
        twin.configuration.gcp_cloud_connection = None
        twin.configuration.gcp_project_id = None
        twin.configuration.gcp_billing_account = None
        twin.configuration.gcp_service_account_json = None
        twin.configuration.gcp_region = "europe-west1"
        
        return twin


class TestBuildOptimizationConfig:
    """Tests for _build_optimization_config helper."""
    
    def test_wraps_params_in_result_envelope(self):
        """Should produce {result: {inputParamsUsed: {...}}} structure."""
        oc = Mock()
        oc.params = json.dumps({
            "useEventChecking": True,
            "triggerNotificationWorkflow": False,
            "returnFeedbackToDevice": True,
            "integrateErrorHandling": False,
            "needs3DModel": True,
        })
        
        result = _build_optimization_config(oc)
        
        assert "result" in result
        assert "inputParamsUsed" in result["result"]
        flags = result["result"]["inputParamsUsed"]
        assert flags["useEventChecking"] is True
        assert flags["triggerNotificationWorkflow"] is False
        assert flags["needs3DModel"] is True
    
    def test_defaults_when_no_params(self):
        """Should return all-false flags when params is None."""
        oc = Mock()
        oc.params = None
        
        result = _build_optimization_config(oc)
        
        assert result == {"result": {"inputParamsUsed": {}}}


class TestBuildDeploymentManifest:
    """Tests for secrets-free deployment manifest construction."""

    def test_omits_empty_providers_and_preserves_credential_sources(self):
        twin = Mock()
        twin.id = "twin-123"
        twin.name = "Factory Twin"
        twin.deployer_config = Mock()
        twin.deployer_config.deployer_digital_twin_name = "factory-twin"

        credentials = DeploymentCredentials(
            providers=("aws", "azure"),
            config_credentials={
                "aws": {"aws_secret_access_key": "must-not-leak"},
                "azure": {"azure_client_secret": "must-not-leak"},
            },
            sources={"aws": "cloud_connection", "azure": "legacy"},
        )

        result = _build_deployment_manifest(
            twin,
            {
                "layer_1_provider": "aws",
                "layer_2_provider": None,
                "layer_3_hot_provider": "",
                "layer_4_provider": "azure",
            },
            credentials,
            ["config.json", "config_credentials.json"],
        )
        manifest_text = json.dumps(result)

        assert result["providers"] == {
            "layer_1_provider": "aws",
            "layer_4_provider": "azure",
        }
        assert result["credentials"]["sources"] == {
            "aws": "cloud_connection",
            "azure": "legacy",
        }
        assert "must-not-leak" not in manifest_text
        assert "azure_client_secret" not in manifest_text
