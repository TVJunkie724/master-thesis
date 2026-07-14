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
from unittest.mock import Mock

from src.services.deployment_stream_service import LogSession
from src.models.cloud_connection import CloudConnection
from src.models.deployer_config import DeployerConfiguration
from src.models.deployment import Deployment
from src.models.optimizer_config import OptimizerConfiguration
from src.models.twin import DigitalTwin, TwinState
from src.models.twin_config import TwinConfiguration
from src.models.user import User
from src.services.deployment_service import (
    DEPLOYMENT_MANIFEST_FILE,
    REQUIRED_DEPLOYER_CONFIG_FILES,
    build_deployment_package,
    build_project_zip,
    get_resource_name,
    _parse_deployer_sse_data,
    run_real_deploy_stream,
    run_real_destroy_stream,
    _build_main_config,
    _build_providers_config,
    _build_credentials_config,
    _build_deployment_manifest,
    _build_optimization_config,
)
from src.services.credential_resolution_service import DeploymentCredentials
from src.services.errors import CredentialResolutionFailed, DeploymentPackageBuildFailed
from src.utils.crypto import encrypt_scoped
from tests.conftest import TestingSessionLocal


class _FakeDeployerClient:
    def __init__(self, lines: list[str]):
        self.lines = lines

    async def deploy_stream(self, provider: str, project_name: str):
        for line in self.lines:
            yield line

    async def destroy_stream(self, provider: str, project_name: str):
        for line in self.lines:
            yield line


def _create_stream_twin(db, state=TwinState.DEPLOYING):
    user = User(email="stream-user@example.test")
    db.add(user)
    db.commit()
    db.refresh(user)
    twin = DigitalTwin(name="Stream Twin", user_id=user.id, state=state)
    db.add(twin)
    db.commit()
    db.refresh(twin)
    return twin


def _patch_stream_dependencies(monkeypatch, lines: list[str], session: LogSession):
    async def fake_get_session(session_id: str):
        return session

    monkeypatch.setattr("src.services.deployment_stream_service.get_session", fake_get_session)
    monkeypatch.setattr("src.models.database.SessionLocal", TestingSessionLocal)
    return _FakeDeployerClient(lines)


class TestDeployerSseParsing:
    """Tests for the typed Deployer SSE terminal contract."""

    def test_parses_log_event_message(self):
        log_message, result = _parse_deployer_sse_data(
            json.dumps({
                "event": "log",
                "operation": "deploy",
                "message": "terraform apply",
                "operation_id": "op-123",
            }),
            event_type=None,
            operation_type="deploy",
        )

        assert log_message == "terraform apply"
        assert result is None

    def test_parses_success_terminal_event(self):
        log_message, result = _parse_deployer_sse_data(
            json.dumps({
                "event": "complete",
                "operation": "deploy",
                "success": True,
                "outputs": {"endpoint": {"value": "ok"}},
                "operation_id": "op-123",
            }),
            event_type="complete",
            operation_type="deploy",
        )

        assert log_message is None
        assert result.success is True
        assert result.operation_id == "op-123"
        assert result.error_code is None
        assert result.outputs == {"endpoint": {"value": "ok"}}

    def test_parses_error_terminal_event_with_redaction(self):
        log_message, result = _parse_deployer_sse_data(
            json.dumps({
                "event": "error",
                "operation": "destroy",
                "success": False,
                "error": "client_secret=super-secret in /app/upload/template",
                "error_code": "DESTRUCTION_ERROR",
                "operation_id": "op-456",
            }),
            event_type="error",
            operation_type="destroy",
        )

        assert log_message is None
        assert result.success is False
        assert result.operation_id == "op-456"
        assert result.error_code == "DESTRUCTION_ERROR"
        assert result.message == "client_secret=[REDACTED] in <project-path>"
        assert "super-secret" not in result.message

    def test_malformed_terminal_payload_fails_safe(self):
        log_message, result = _parse_deployer_sse_data(
            "aws_secret_access_key=super-secret",
            event_type="error",
            operation_type="deploy",
        )

        assert log_message is None
        assert result.success is False
        assert result.error_code == "DEPLOYER_STREAM_ERROR"
        assert result.message == "aws_secret_access_key=[REDACTED]"


class TestRealDeploymentStreamPersistence:
    """Tests for real Deployer stream persistence with a fake SSE source."""

    @pytest.mark.asyncio
    async def test_deploy_stream_persists_operation_metadata_on_success(self, db, monkeypatch):
        twin = _create_stream_twin(db)
        session = LogSession(twin.id, "session-deploy", operation_type="deploy")
        lines = [
            'data: {"event":"log","operation":"deploy","message":"terraform init","operation_id":"op-deploy"}',
            "event: complete",
            'data: {"event":"complete","operation":"deploy","success":true,'
            '"outputs":{"endpoint":{"value":"ok"}},"operation_id":"op-deploy"}',
        ]
        deployer_client = _patch_stream_dependencies(monkeypatch, lines, session)

        await run_real_deploy_stream(
            session_id="session-deploy",
            twin_id=twin.id,
            resource_name="stream-twin",
            provider="aws",
            deployer_client=deployer_client,
        )

        db.expire_all()
        stored_twin = db.get(DigitalTwin, twin.id)
        deployment = db.query(Deployment).filter_by(session_id="session-deploy").one()
        complete_event = session.logs[-1]

        assert stored_twin.state == TwinState.DEPLOYED
        assert deployment.status == "success"
        assert deployment.operation_id == "op-deploy"
        assert deployment.error_code is None
        assert deployment.terraform_outputs == {"endpoint": {"value": "ok"}}
        assert session.buffer[0]["data"] == "terraform init"
        assert complete_event["operation_id"] == "op-deploy"

    @pytest.mark.asyncio
    async def test_destroy_stream_persists_error_code_and_safe_message(self, db, monkeypatch):
        twin = _create_stream_twin(db, state=TwinState.DESTROYING)
        session = LogSession(twin.id, "session-destroy", operation_type="destroy")
        lines = [
            "event: error",
            'data: {"event":"error","operation":"destroy","success":false,'
            '"error":"client_secret=super-secret in /app/upload/template",'
            '"error_code":"DESTRUCTION_ERROR","operation_id":"op-destroy"}',
        ]
        deployer_client = _patch_stream_dependencies(monkeypatch, lines, session)

        await run_real_destroy_stream(
            session_id="session-destroy",
            twin_id=twin.id,
            resource_name="stream-twin",
            provider="aws",
            deployer_client=deployer_client,
        )

        db.expire_all()
        stored_twin = db.get(DigitalTwin, twin.id)
        deployment = db.query(Deployment).filter_by(session_id="session-destroy").one()
        final_event = session.logs[-1]

        assert stored_twin.state == TwinState.ERROR
        assert stored_twin.last_error == "client_secret=[REDACTED] in <project-path>"
        assert deployment.status == "failed"
        assert deployment.operation_id == "op-destroy"
        assert deployment.error_code == "DESTRUCTION_ERROR"
        assert deployment.error_message == "client_secret=[REDACTED] in <project-path>"
        assert "super-secret" not in final_event["message"]


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
        """Should convert Optimizer provider names to Deployer project ids."""
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

    def test_normalizes_google_alias_to_deployer_project_id(self):
        """Should preserve Deployer's google project-file dialect for GCP aliases."""
        twin = Mock()
        twin.optimizer_config = Mock()
        twin.optimizer_config.cheapest_l1 = "Google"
        twin.optimizer_config.cheapest_l2 = " gcp "
        twin.optimizer_config.cheapest_l3_hot = None
        twin.optimizer_config.cheapest_l3_cool = None
        twin.optimizer_config.cheapest_l3_archive = None
        twin.optimizer_config.cheapest_l4 = None
        twin.optimizer_config.cheapest_l5 = None

        result = _build_providers_config(twin)

        assert result["layer_1_provider"] == "google"
        assert result["layer_2_provider"] == "google"
    
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
    
    def test_legacy_aws_columns_are_not_used_as_deployment_credentials(self):
        """Legacy per-twin credential columns must not be a runtime fallback."""
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
        
        with pytest.raises(CredentialResolutionFailed) as exc_info:
            _build_credentials_config(twin, "user-123")

        assert exc_info.value.errors[0]["code"] == "NO_DEPLOYMENT_PROVIDERS"
        assert "enc_secret" not in str(exc_info.value.errors)
    
    def test_raises_structured_error_when_no_configuration(self):
        """Should fail closed when no credential source is configured."""
        twin = Mock()
        twin.optimizer_config = None
        twin.configuration = None
        
        with pytest.raises(CredentialResolutionFailed) as exc_info:
            _build_credentials_config(twin, "user-123")

        assert exc_info.value.errors[0]["code"] == "NO_DEPLOYMENT_PROVIDERS"

    def test_uses_bound_aws_cloud_connection_even_if_legacy_columns_exist(self):
        """CloudConnection bindings are the only runtime credential source."""
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
    
    def test_creates_valid_zip_file(self):
        """Should create a valid ZIP file."""
        twin = self._create_mock_twin()
        
        result = build_project_zip(twin, "user-123")
        
        assert isinstance(result, io.BytesIO)
        # Verify it's a valid ZIP
        with zipfile.ZipFile(result, 'r') as zf:
            assert zf.testzip() is None  # Returns None if all CRCs OK
    
    def test_contains_required_config_files(self):
        """Should contain config.json and config_providers.json."""
        twin = self._create_mock_twin()
        
        result = build_project_zip(twin, "user-123")
        
        with zipfile.ZipFile(result, 'r') as zf:
            names = zf.namelist()
            assert "config.json" in names
            assert "config_providers.json" in names
            assert "config_credentials.json" in names
            assert "config_iot_devices.json" in names
            assert "config_events.json" in names
            assert DEPLOYMENT_MANIFEST_FILE in names

    def test_includes_secrets_free_deployment_manifest(self):
        """Should include a deployment manifest without credential payloads."""
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
            "sources": {"aws": "cloud_connection"},
            "contains_secret_payloads": False,
        }
        assert manifest["package"]["required_files"] == REQUIRED_DEPLOYER_CONFIG_FILES
        assert manifest["package"]["secret_bearing_files"] == ["config_credentials.json"]
        assert "config_credentials.json" in manifest["package"]["files"]
        assert "config_iot_devices.json" in manifest["package"]["files"]
        assert "config_events.json" in manifest["package"]["files"]
        assert DEPLOYMENT_MANIFEST_FILE not in manifest["package"]["files"]
        assert "cloud-connection-secret" not in manifest_text
        assert "AKIAIOSFODNN7EXAMPLE" not in manifest_text
        assert "aws_secret_access_key" not in manifest_text

    def test_required_config_files_default_to_empty_lists(self):
        """Should write required Deployer config files even when optional wizard data is absent."""
        twin = self._create_mock_twin()
        twin.deployer_config.config_iot_devices_json = None
        twin.deployer_config.config_events_json = None

        result = build_project_zip(twin, "user-123")

        with zipfile.ZipFile(result, 'r') as zf:
            assert json.loads(zf.read("config_iot_devices.json")) == []
            assert json.loads(zf.read("config_events.json")) == []
    
    def test_includes_state_machine_for_azure_l2(self):
        """Should write state machine to azure location for Azure L2."""
        twin = self._create_mock_twin()
        twin.optimizer_config.cheapest_l2 = "azure"
        twin.deployer_config.state_machine_content = '{"definition": {}}'
        azure_payload = {
            "azure_subscription_id": "subscription-id",
            "azure_tenant_id": "tenant-id",
            "azure_client_id": "client-id",
            "azure_client_secret": "client-secret",
            "azure_region": "westeurope",
            "azure_region_iothub": "westeurope",
            "azure_region_digital_twin": "westeurope",
        }
        twin.configuration.azure_cloud_connection_id = "connection-azure"
        twin.configuration.azure_cloud_connection = SimpleNamespace(
            id="connection-azure",
            encrypted_payload=encrypt_scoped(json.dumps(azure_payload), "user-123", "connection-azure"),
        )

        result = build_project_zip(twin, "user-123")
        
        with zipfile.ZipFile(result, 'r') as zf:
            names = zf.namelist()
            assert "state_machines/azure_logic_app.json" in names

    def test_includes_state_machine_for_google_l2_alias(self):
        """Should write GCP workflow state machine for every accepted GCP spelling."""
        twin = self._create_mock_twin()
        twin.optimizer_config.cheapest_l2 = "GCP"
        twin.deployer_config.state_machine_content = "main:\n  steps: []\n"
        service_account = {"project_id": "demo-project", "client_email": "sa@example.test"}
        gcp_payload = {
            "gcp_project_id": "demo-project",
            "gcp_region": "europe-west1",
            "gcp_credentials_file": json.dumps(service_account),
        }
        twin.configuration.gcp_cloud_connection_id = "connection-gcp"
        twin.configuration.gcp_cloud_connection = SimpleNamespace(
            id="connection-gcp",
            encrypted_payload=encrypt_scoped(json.dumps(gcp_payload), "user-123", "connection-gcp"),
        )

        result = build_project_zip(twin, "user-123")

        with zipfile.ZipFile(result, 'r') as zf:
            names = zf.namelist()
            providers = json.loads(zf.read("config_providers.json"))
            assert "state_machines/google_cloud_workflow.yaml" in names
            assert providers["layer_2_provider"] == "google"
    
    def test_includes_payloads_json(self):
        """Should include payloads.json for simulator."""
        twin = self._create_mock_twin()
        twin.deployer_config.payloads_json = '{"device_1": {"temp": 25}}'
        
        result = build_project_zip(twin, "user-123")
        
        with zipfile.ZipFile(result, 'r') as zf:
            names = zf.namelist()
            assert "iot_device_simulator/payloads.json" in names

    def test_package_is_reconstructed_from_persisted_state_and_cloud_connections(self, db):
        """Package materialization should read canonical DB state, not Flutter payload shape."""
        user = User(email="package-user@example.test")
        db.add(user)
        db.commit()
        db.refresh(user)

        aws_payload = {
            "aws_access_key_id": "AKIAIOSFODNN7EXAMPLE",
            "aws_secret_access_key": "cloud-connection-secret",
            "aws_region": "eu-central-1",
        }
        service_account = {
            "type": "service_account",
            "project_id": "factory-project",
            "client_email": "deployer@factory-project.iam.gserviceaccount.com",
            "private_key": "-----BEGIN PRIVATE KEY-----\nsecret\n-----END PRIVATE KEY-----\n",
        }
        gcp_payload = {
            "gcp_project_id": "factory-project",
            "gcp_region": "europe-west1",
            "gcp_credentials_file": json.dumps(service_account),
        }
        aws_connection = CloudConnection(
            id="connection-aws-package",
            user_id=user.id,
            provider="aws",
            display_name="AWS Deployment Account",
            cloud_scope="{}",
            auth_type="access_key",
            encrypted_payload=encrypt_scoped(
                json.dumps(aws_payload),
                user.id,
                "connection-aws-package",
            ),
            payload_fingerprint="aws-fingerprint",
        )
        gcp_connection = CloudConnection(
            id="connection-gcp-package",
            user_id=user.id,
            provider="gcp",
            display_name="GCP Deployment Account",
            cloud_scope="{}",
            auth_type="service_account_key",
            encrypted_payload=encrypt_scoped(
                json.dumps(gcp_payload),
                user.id,
                "connection-gcp-package",
            ),
            payload_fingerprint="gcp-fingerprint",
        )
        twin = DigitalTwin(name="Factory Twin", user_id=user.id)
        db.add_all([aws_connection, gcp_connection, twin])
        db.commit()
        db.refresh(twin)

        db.add_all([
            TwinConfiguration(
                twin_id=twin.id,
                debug_mode=True,
                aws_cloud_connection_id=aws_connection.id,
                gcp_cloud_connection_id=gcp_connection.id,
            ),
            OptimizerConfiguration(
                twin_id=twin.id,
                cheapest_l1="AWS",
                cheapest_l2="GCP",
                cheapest_l4="AWS",
                params=json.dumps({
                    "hotStorageDurationInMonths": 2,
                    "coolStorageDurationInMonths": 4,
                    "useEventChecking": True,
                    "needs3DModel": True,
                }),
            ),
            DeployerConfiguration(
                twin_id=twin.id,
                deployer_digital_twin_name="factory-twin",
                config_iot_devices_json='[{"id":"device-1"}]',
                config_events_json="[]",
                payloads_json='{"device-1":{"temperature":21}}',
                processor_contents=json.dumps({"device-1": "def handler(event, context): pass"}),
                processor_requirements=json.dumps({"device-1": "requests==2.32.3"}),
                scene_config_content="{}",
            ),
        ])
        db.commit()
        db.expire_all()

        persisted_twin = db.get(DigitalTwin, twin.id)
        result = build_project_zip(persisted_twin, user.id)

        with zipfile.ZipFile(result, "r") as zf:
            names = set(zf.namelist())
            credentials = json.loads(zf.read("config_credentials.json"))
            gcp_credentials = json.loads(zf.read("gcp_credentials.json"))
            manifest = json.loads(zf.read(DEPLOYMENT_MANIFEST_FILE))
            manifest_text = json.dumps(manifest)

        assert "cloud_functions/processors/device-1/main.py" in names
        assert "cloud_functions/processors/device-1/requirements.txt" in names
        assert "scene_assets/aws/scene.json" in names
        assert "iot_device_simulator/payloads.json" in names
        assert credentials["aws"] == aws_payload
        assert credentials["gcp"]["gcp_credentials_file"] == "gcp_credentials.json"
        assert gcp_credentials == service_account
        assert manifest["twin"]["resource_name"] == "factory-twin"
        assert manifest["credentials"]["sources"] == {
            "aws": "cloud_connection",
            "gcp": "cloud_connection",
        }
        assert manifest["package"]["secret_bearing_files"] == [
            "config_credentials.json",
            "gcp_credentials.json",
        ]
        assert manifest["credentials"]["contains_secret_payloads"] is False
        assert "cloud-connection-secret" not in manifest_text
        assert "private_key" not in manifest_text

    def test_package_materialization_fails_closed_on_invalid_function_json(self):
        """Invalid persisted JSON artifacts must not be silently omitted."""
        twin = self._create_mock_twin()
        twin.optimizer_config.cheapest_l2 = "aws"
        twin.deployer_config.processor_contents = "{not-json"

        with pytest.raises(DeploymentPackageBuildFailed) as exc_info:
            build_deployment_package(twin, "user-123")

        assert exc_info.value.errors == [
            {
                "code": "INVALID_JSON",
                "field": "deployer_config.processor_contents",
                "message": "Deployment artifact contains invalid JSON",
            }
        ]

    def test_package_materialization_fails_closed_on_invalid_optimizer_params(self):
        """Invalid optimizer params should fail package creation instead of using defaults."""
        twin = self._create_mock_twin()
        twin.optimizer_config.params = "{not-json"

        with pytest.raises(DeploymentPackageBuildFailed) as exc_info:
            build_deployment_package(twin, "user-123")

        assert exc_info.value.errors[0]["field"] == "optimizer_config.params"
        assert exc_info.value.errors[0]["code"] == "INVALID_JSON"

    def test_package_materialization_fails_when_uploaded_scene_binary_is_missing(
        self,
        tmp_path,
        monkeypatch,
    ):
        """Persisted artifact metadata must not point to missing managed files."""
        monkeypatch.setattr("src.services.deployment_service.settings.UPLOAD_DIR", str(tmp_path))
        twin = self._create_mock_twin()
        twin.optimizer_config.cheapest_l4 = "aws"
        twin.deployer_config.scene_config_content = "{}"
        twin.deployer_config.scene_glb_uploaded = True

        with pytest.raises(DeploymentPackageBuildFailed) as exc_info:
            build_deployment_package(twin, "user-123")

        assert exc_info.value.errors == [
            {
                "code": "MISSING_BINARY_ARTIFACT",
                "field": "deployer_config.scene_glb_uploaded",
                "message": "Scene GLB is marked as uploaded but the managed file is missing",
            }
        ]
    
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
        twin.deployer_config.scene_glb_uploaded = False
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
        aws_payload = {
            "aws_access_key_id": "AKIAIOSFODNN7EXAMPLE",
            "aws_secret_access_key": "cloud-connection-secret",
            "aws_region": "eu-central-1",
        }
        twin.configuration = Mock()
        twin.configuration.debug_mode = False
        twin.configuration.aws_cloud_connection_id = "connection-aws"
        twin.configuration.aws_cloud_connection = SimpleNamespace(
            id="connection-aws",
            encrypted_payload=encrypt_scoped(json.dumps(aws_payload), "user-123", "connection-aws"),
        )
        twin.configuration.aws_access_key_id = None
        twin.configuration.aws_secret_access_key = None
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
            sources={"aws": "cloud_connection", "azure": "cloud_connection"},
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
            "azure": "cloud_connection",
        }
        assert "must-not-leak" not in manifest_text
        assert "azure_client_secret" not in manifest_text
