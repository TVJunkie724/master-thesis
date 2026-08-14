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
from datetime import datetime, timezone
from pathlib import Path
import pytest
from types import SimpleNamespace
from unittest.mock import Mock

from src.services.deployment_stream_service import LogSession
from src.models.cloud_connection import CloudConnection
from src.models.cost_calculation import CostCalculationRun
from src.models.deployer_config import DeployerConfiguration
from src.models.deployment import Deployment
from src.models.optimizer_config import OptimizerConfiguration
from src.models.twin import DigitalTwin, TwinState
from src.models.twin_config import TwinConfiguration
from src.models.user import User
from src.services.deployment_service import (
    PHASE_8_FORBIDDEN_OPTIMIZER_FIELDS,
    DEPLOYMENT_MANIFEST_FILE,
    REQUIRED_DEPLOYER_CONFIG_FILES,
    build_deployment_package,
    build_project_zip,
    get_resource_name,
    _parse_deployer_sse_data,
    run_real_deploy_stream,
    run_real_destroy_stream,
    upload_project_to_deployer,
    _build_main_config,
    _build_providers_config,
    _build_credentials_config,
    _build_deployment_manifest,
    _build_optimization_config,
    _build_optimization_config_from_params,
    _component_catalog_ref,
    _architecture_provider_ids,
    _validate_phase8_deployer_artifacts,
    _validate_phase8_deployment_regions,
    _validate_architecture_specification_path,
)
from src.services.credential_resolution_service import DeploymentCredentials
from src.services.errors import (
    CredentialResolutionFailed,
    DeploymentPackageBuildFailed,
    ExternalServiceError,
    ExternalServiceUnavailable,
)
from src.services.service_errors import DownstreamServiceError
from src.utils.crypto import encrypt_scoped
from tests.conftest import TestingSessionLocal
from tests.pricing_catalog_test_data import catalog_context
from tests.resolved_deployment_specification_test_data import (
    build_resolved_deployment_specification,
)
from tests.architecture_test_data import calculation_result_and_contracts
from src.services.architecture_contract_service import (
    calculate_digest as calculate_architecture_digest,
)
from src.services.provider_contract import normalize_provider_id


TEST_CALCULATION_RUN_ID = "018f0f5e-7b5e-7b2d-9f0b-7f66c2a88a01"


def _deployment_run_contract(twin) -> dict:
    oc = twin.optimizer_config
    calculation_result = {
        "L1": oc.cheapest_l1,
        "L2": oc.cheapest_l2,
        "L3": {
            "Hot": oc.cheapest_l3_hot,
            "Cool": oc.cheapest_l3_cool,
            "Archive": oc.cheapest_l3_archive,
        },
        "L4": oc.cheapest_l4,
        "L5": oc.cheapest_l5,
    }
    result = {
        "optimization_profile_id": "cost_minimization_v1",
        "calculation_strategy_id": "cost_calculation_v2",
        "optimizationProfile": {
            "profile_version": "2026.06.08",
            "pricing_registry_version": "2026.07.17",
        },
        "calculationStrategy": {
            "formula_set_id": "cost_formula_set_v1",
            "workload_contract_id": "digital_twin_workload_v1",
        },
        "calculationResult": calculation_result,
        "pricingCatalogs": catalog_context().to_http_dict(),
    }
    specification = build_resolved_deployment_specification(
        result,
        calculation_run_id=TEST_CALCULATION_RUN_ID,
        pricing_catalogs=result["pricingCatalogs"],
    )
    result["resolvedDeploymentSpecification"] = specification
    cheapest_path = {
        "l1": calculation_result["L1"],
        "l2": calculation_result["L2"],
        "l3_hot": calculation_result["L3"]["Hot"],
        "l3_cool": calculation_result["L3"]["Cool"],
        "l3_archive": calculation_result["L3"]["Archive"],
        "l4": calculation_result["L4"],
        "l5": calculation_result["L5"],
    }
    return {
        "result": result,
        "specification": specification,
        "cheapest_path": cheapest_path,
    }


def _attach_selected_run(twin) -> None:
    contract = _deployment_run_contract(twin)
    _, _, architecture = calculation_result_and_contracts("aws")
    provider_by_logical = {
        "component.ingestion": normalize_provider_id(twin.optimizer_config.cheapest_l1),
        "component.processing": normalize_provider_id(
            twin.optimizer_config.cheapest_l2
        ),
        "component.hot-storage": normalize_provider_id(
            twin.optimizer_config.cheapest_l3_hot
        ),
        "component.cool-storage": normalize_provider_id(
            twin.optimizer_config.cheapest_l3_cool
        ),
        "component.archive-storage": normalize_provider_id(
            twin.optimizer_config.cheapest_l3_archive
        ),
        "component.twin-state": normalize_provider_id(
            twin.optimizer_config.cheapest_l4
        ),
        "component.visualization": normalize_provider_id(
            twin.optimizer_config.cheapest_l5
        ),
    }
    catalog_root = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "contracts"
        / "generated"
        / "architecture-profiles"
        / "definitions"
    )
    catalog = json.loads(
        (
            catalog_root / "component-catalogs" / "baseline" / "1" / "catalog.json"
        ).read_text("utf-8")
    )
    components = {
        (item["provider"], item["logical_component_ids"][0]): item
        for item in catalog["components"]
        if len(item["logical_component_ids"]) == 1
    }
    profile_cache = {}
    specification_ids = {
        item["component_id"] for item in contract["specification"]["components"]
    }
    for assignment in architecture["component_assignments"]:
        provider = provider_by_logical[assignment["logical_component_id"]]
        component = components[(provider, assignment["logical_component_id"])]
        if provider not in profile_cache:
            profile_cache[provider] = json.loads(
                (
                    catalog_root
                    / "provider-implementations"
                    / "five-layer-baseline"
                    / "1"
                    / provider
                    / "1.json"
                ).read_text("utf-8")
            )
        provider_profile = profile_cache[provider]
        assignment.update(
            {
                "provider": provider,
                "provider_implementation_profile_ref": {
                    "id": provider_profile["implementation_profile_id"],
                    "version": provider_profile["implementation_profile_version"],
                    "digest": provider_profile["content_digest"],
                },
                "deployment_component_id": component["deployment_component_id"],
                "deployment_component_version": component["component_version"],
                "service_id": component["service_id"],
                "deployment_specification_component_ids": [
                    item["component_id"]
                    for item in component["deployment_specification_bindings"]
                    if item["component_id"] in specification_ids
                ],
            }
        )
    architecture["deployment_specification_ref"] = {
        "schema_version": contract["specification"]["schema_version"],
        "calculation_run_id": TEST_CALCULATION_RUN_ID,
        "digest": contract["specification"]["digest"],
    }
    architecture["content_digest"] = calculate_architecture_digest(architecture)
    record = SimpleNamespace(
        canonical_json=json.dumps(architecture),
        content_digest=architecture["content_digest"],
        functional_completeness_status="complete",
    )
    twin.cost_calculation_runs = [
        SimpleNamespace(
            id=TEST_CALCULATION_RUN_ID,
            status="succeeded",
            params_json=twin.optimizer_config.params,
            result_summary_json=json.dumps(contract["result"]),
            cheapest_path_json=json.dumps(contract["cheapest_path"]),
            pricing_catalog_context_json=catalog_context().canonical_json(),
            deployment_specification_json=json.dumps(
                contract["specification"],
                sort_keys=True,
                separators=(",", ":"),
            ),
            deployment_specification_digest=contract["specification"]["digest"],
            deployment_specification_version=(
                contract["specification"]["schema_version"]
            ),
            deployment_compatibility_status="ready",
            architecture_compatibility_status="ready",
            resolved_architecture_digest=architecture["content_digest"],
            resolved_architecture=record,
            selected_for_deployment_at=datetime.now(timezone.utc),
        )
    ]


def _all_aws_specification() -> dict:
    optimizer_config = SimpleNamespace(
        cheapest_l1="aws",
        cheapest_l2="aws",
        cheapest_l3_hot="aws",
        cheapest_l3_cool="aws",
        cheapest_l3_archive="aws",
        cheapest_l4="aws",
        cheapest_l5="aws",
    )
    return _deployment_run_contract(SimpleNamespace(optimizer_config=optimizer_config))[
        "specification"
    ]


class _FakeDeployerClient:
    def __init__(self, lines: list[str]):
        self.lines = lines

    async def deploy_stream(
        self, provider: str, project_name: str, operation_token: str
    ):
        for line in self.lines:
            yield line

    async def destroy_stream(
        self, provider: str, project_name: str, operation_token: str
    ):
        for line in self.lines:
            yield line


class _FakeOperationPackageClient:
    def __init__(self, *, result=None, exc=None):
        self.result = result or {"operation_token": "opaque-token"}
        self.exc = exc
        self.calls = []

    async def stage_operation_package(self, project_name: str, content: bytes):
        self.calls.append((project_name, content))
        if self.exc:
            raise self.exc
        return self.result


@pytest.mark.asyncio
async def test_upload_project_stages_only_the_canonical_operation_package():
    client = _FakeOperationPackageClient()

    result = await upload_project_to_deployer(
        "factory",
        io.BytesIO(b"deployment-package"),
        deployer_client=client,
    )

    assert result == {"operation_token": "opaque-token"}
    assert client.calls == [("factory", b"deployment-package")]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("failure", "status_code", "detail"),
    [
        (
            ExternalServiceUnavailable("Deployer unavailable"),
            503,
            "Deployer API unavailable during project setup",
        ),
        (
            ExternalServiceError(
                "client_secret=internal-secret",
                upstream_status_code=500,
                public_detail="client_secret=internal-secret",
            ),
            502,
            "Deployer project setup failed: client_secret=[REDACTED]",
        ),
        (
            ExternalServiceError(
                "archive too large",
                upstream_status_code=413,
                public_detail="archive too large",
            ),
            413,
            "Deployer project setup failed: archive too large",
        ),
    ],
)
async def test_upload_project_maps_downstream_failures_to_safe_service_errors(
    failure,
    status_code,
    detail,
):
    client = _FakeOperationPackageClient(exc=failure)

    with pytest.raises(DownstreamServiceError) as exc_info:
        await upload_project_to_deployer(
            "factory",
            io.BytesIO(b"deployment-package"),
            deployer_client=client,
        )

    assert exc_info.value.status_code == status_code
    assert exc_info.value.public_detail == detail


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

    monkeypatch.setattr(
        "src.services.deployment_stream_service.get_session", fake_get_session
    )
    monkeypatch.setattr("src.models.database.SessionLocal", TestingSessionLocal)
    return _FakeDeployerClient(lines)


class TestDeployerSseParsing:
    """Tests for the typed Deployer SSE terminal contract."""

    def test_parses_log_event_message(self):
        log_message, result = _parse_deployer_sse_data(
            json.dumps(
                {
                    "event": "log",
                    "operation": "deploy",
                    "message": "terraform apply",
                    "operation_id": "op-123",
                }
            ),
            event_type=None,
            operation_type="deploy",
        )

        assert log_message == "terraform apply"
        assert result is None

    def test_parses_success_terminal_event(self):
        log_message, result = _parse_deployer_sse_data(
            json.dumps(
                {
                    "event": "complete",
                    "operation": "deploy",
                    "success": True,
                    "outputs": {"endpoint": {"value": "ok"}},
                    "deployment_access_evidence": {
                        "schema_version": "deployment-access-evidence.v1"
                    },
                    "operation_id": "op-123",
                }
            ),
            event_type="complete",
            operation_type="deploy",
        )

        assert log_message is None
        assert result.success is True
        assert result.operation_id == "op-123"
        assert result.error_code is None
        assert result.outputs == {"endpoint": {"value": "ok"}}
        assert result.deployment_access_evidence == {
            "schema_version": "deployment-access-evidence.v1"
        }

    def test_parses_error_terminal_event_with_redaction(self):
        log_message, result = _parse_deployer_sse_data(
            json.dumps(
                {
                    "event": "error",
                    "operation": "destroy",
                    "success": False,
                    "error": "client_secret=super-secret in /app/upload/template",
                    "error_code": "DESTRUCTION_ERROR",
                    "operation_id": "op-456",
                }
            ),
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
    async def test_deploy_stream_persists_operation_metadata_on_success(
        self, db, monkeypatch
    ):
        twin = _create_stream_twin(db)
        session = LogSession(twin.id, "session-deploy", operation_type="deploy")
        lines = [
            'data: {"event":"log","operation":"deploy",'
            '"message":"T2MC_STAGE_COMPLETED:package",'
            '"operation_id":"op-deploy"}',
            'data: {"event":"log","operation":"deploy",'
            '"message":"T2MC_STAGE_COMPLETED:preplan",'
            '"operation_id":"op-deploy"}',
            'data: {"event":"log","operation":"deploy","message":"terraform init","operation_id":"op-deploy"}',
            "event: complete",
            'data: {"event":"complete","operation":"deploy","success":true,'
            '"outputs":{"endpoint":{"value":"ok"}},'
            '"deployment_access_evidence":{"schema_version":"deployment-access-evidence.v1"},'
            '"operation_id":"op-deploy"}',
        ]
        deployer_client = _patch_stream_dependencies(monkeypatch, lines, session)

        await run_real_deploy_stream(
            session_id="session-deploy",
            twin_id=twin.id,
            resource_name="stream-twin",
            provider="aws",
            operation_token="deploy-token",
            deployer_client=deployer_client,
            graph_evidence={"graph_digest": "sha256:" + ("1" * 64)},
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
        assert deployment.deployment_access_evidence == {
            "schema_version": "deployment-access-evidence.v1"
        }
        assert deployment.completed_stage == "postapply"
        assert session.buffer[0]["data"] == "terraform init"
        assert complete_event["operation_id"] == "op-deploy"

    @pytest.mark.asyncio
    async def test_destroy_stream_persists_error_code_and_safe_message(
        self, db, monkeypatch
    ):
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
            operation_token="destroy-token",
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
        twin.optimizer_config.params = json.dumps(
            {
                "hotStorageDurationInMonths": 2,
                "coolStorageDurationInMonths": 6,
                "archiveStorageDurationInMonths": 18,
            }
        )
        twin.configuration = Mock()
        twin.configuration.debug_mode = False

        result = _build_main_config(twin)

        assert result["digital_twin_name"] == "test-twin"
        assert result["mode"] == "production"
        assert result["hot_storage_size_in_days"] == 60
        assert result["cold_storage_size_in_days"] == 180
        assert result["archive_storage_size_in_days"] == 540

    def test_storage_days_from_optimizer_params(self):
        """Should convert months to days from optimizer params."""
        twin = Mock()
        twin.deployer_config = Mock()
        twin.deployer_config.deployer_digital_twin_name = "test"
        twin.optimizer_config = Mock()
        twin.optimizer_config.params = json.dumps(
            {
                "hotStorageDurationInMonths": 1,
                "coolStorageDurationInMonths": 3,
                "archiveStorageDurationInMonths": 12,
            }
        )
        twin.configuration = None

        result = _build_main_config(twin)

        assert result["hot_storage_size_in_days"] == 30
        assert result["cold_storage_size_in_days"] == 90
        assert result["archive_storage_size_in_days"] == 360

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
        assert result["archive_storage_size_in_days"] == 360

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
        architecture = {
            "component_assignments": [
                {"logical_component_id": logical, "provider": provider}
                for logical, provider in (
                    ("component.ingestion", "AWS"),
                    ("component.processing", "AZURE"),
                    ("component.hot-storage", "GCP"),
                    ("component.cool-storage", "AWS"),
                    ("component.archive-storage", "AWS"),
                    ("component.twin-state", "AZURE"),
                    ("component.visualization", "AZURE"),
                )
            ]
        }

        result = _build_providers_config(architecture)

        assert result["layer_1_provider"] == "aws"
        assert result["layer_2_provider"] == "azure"
        assert result["layer_3_hot_provider"] == "google"
        assert result["layer_4_provider"] == "azure"

    def test_normalizes_google_alias_to_deployer_project_id(self):
        """Should preserve Deployer's google project-file dialect for GCP aliases."""
        architecture = {
            "component_assignments": [
                {"logical_component_id": logical, "provider": "gcp"}
                for logical in (
                    "component.ingestion",
                    "component.processing",
                    "component.hot-storage",
                    "component.cool-storage",
                    "component.archive-storage",
                    "component.twin-state",
                    "component.visualization",
                )
            ]
        }

        result = _build_providers_config(architecture)

        assert result["layer_1_provider"] == "google"
        assert result["layer_2_provider"] == "google"

    def test_rejects_incomplete_architecture(self):
        with pytest.raises(DeploymentPackageBuildFailed):
            _build_providers_config(
                {
                    "component_assignments": [
                        {
                            "logical_component_id": "component.ingestion",
                            "provider": "aws",
                        }
                    ]
                }
            )

    def test_six_layer_adds_independent_event_provider_to_project_config(self):
        fixture = json.loads(
            (
                Path(__file__).resolve().parents[1]
                / "src/contracts/generated/deployment-manifest/v4/fixtures/valid"
                / "six-layer-aws-azure-eventing-small.json"
            ).read_text(encoding="utf-8")
        )

        providers = _build_providers_config(
            fixture["resolved_twin_architecture"]
        )

        assert providers["event_layer_provider"] == "azure"

    def test_v2_specification_matches_all_project_provider_owners(self):
        fixture = json.loads(
            (
                Path(__file__).resolve().parents[1]
                / "src/contracts/generated/deployment-manifest/v4/fixtures/valid"
                / "six-layer-aws-azure-eventing-small.json"
            ).read_text(encoding="utf-8")
        )
        architecture = fixture["resolved_twin_architecture"]
        specification = fixture["resolved_deployment_specification"]
        providers = _build_providers_config(architecture)

        _validate_architecture_specification_path(
            providers,
            architecture,
            specification,
        )

        providers["event_layer_provider"] = "google"
        with pytest.raises(DeploymentPackageBuildFailed) as exc_info:
            _validate_architecture_specification_path(
                providers,
                architecture,
                specification,
            )

        assert exc_info.value.errors[0]["message"] == (
            "DEPLOYMENT_ARCHITECTURE_SPEC_MISMATCH"
        )


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
            encrypted_payload=encrypt_scoped(
                json.dumps(payload), "user-123", "connection-aws"
            ),
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
            encrypted_payload=encrypt_scoped(
                json.dumps(payload), "user-123", "connection-gcp"
            ),
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

    def test_rejects_package_without_selected_optimizer_run(self):
        twin = self._create_mock_twin()
        twin.cost_calculation_runs = []

        with pytest.raises(DeploymentPackageBuildFailed) as exc_info:
            build_deployment_package(twin, "user-123")

        assert exc_info.value.errors[0]["field"] == "cost_calculation_run"

    def test_rejects_unsupported_topology_before_credential_resolution(
        self,
        monkeypatch,
    ):
        twin = self._create_mock_twin()
        params = json.loads(twin.cost_calculation_runs[0].params_json)
        params["integrateErrorHandling"] = True
        twin.cost_calculation_runs[0].params_json = json.dumps(params)
        credential_resolution_called = False

        def fail_if_called(*_args, **_kwargs):
            nonlocal credential_resolution_called
            credential_resolution_called = True
            raise AssertionError("credential resolution must not run")

        monkeypatch.setattr(
            "src.services.deployment_service._build_deployment_credentials",
            fail_if_called,
        )

        with pytest.raises(DeploymentPackageBuildFailed) as exc_info:
            build_deployment_package(twin, "user-123")

        assert exc_info.value.errors[0]["code"] == (
            "UNSUPPORTED_ERROR_HANDLING_TOPOLOGY"
        )
        assert credential_resolution_called is False

    def test_rejects_ambiguous_selected_optimizer_runs(self):
        twin = self._create_mock_twin()
        twin.cost_calculation_runs.append(twin.cost_calculation_runs[0])

        with pytest.raises(DeploymentPackageBuildFailed) as exc_info:
            build_deployment_package(twin, "user-123")

        assert exc_info.value.errors[0]["field"] == "cost_calculation_run"

    def test_fixed_provider_projection_cannot_change_executable_package(self):
        twin = self._create_mock_twin()
        twin.optimizer_config.cheapest_l2 = "azure"

        package = build_deployment_package(twin, "user-123")

        assert package.manifest["providers"]["layer_2_provider"] == "aws"

    def test_rejects_selected_run_with_inconsistent_specification_metadata(self):
        twin = self._create_mock_twin()
        selected_run = twin.cost_calculation_runs[0]
        selected_run.deployment_specification_digest = "sha256:" + ("f" * 64)

        with pytest.raises(DeploymentPackageBuildFailed) as exc_info:
            build_deployment_package(twin, "user-123")

        assert exc_info.value.errors == [
            {
                "field": "cost_calculation_run",
                "message": "DEPLOYMENT_SPECIFICATION_METADATA_MISMATCH",
            }
        ]

    def test_creates_valid_zip_file(self):
        """Should create a valid ZIP file."""
        twin = self._create_mock_twin()

        result = build_project_zip(twin, "user-123")

        assert isinstance(result, io.BytesIO)
        # Verify it's a valid ZIP
        with zipfile.ZipFile(result, "r") as zf:
            assert zf.testzip() is None  # Returns None if all CRCs OK

    def test_contains_required_config_files(self):
        """Should contain config.json and config_providers.json."""
        twin = self._create_mock_twin()

        result = build_project_zip(twin, "user-123")

        with zipfile.ZipFile(result, "r") as zf:
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

        with zipfile.ZipFile(result, "r") as zf:
            manifest = json.loads(zf.read(DEPLOYMENT_MANIFEST_FILE))
            manifest_text = json.dumps(manifest)

        assert manifest["manifest_version"] == "3.0"
        assert (
            manifest["resolved_twin_architecture_digest"]
            == (manifest["resolved_twin_architecture"]["content_digest"])
        )
        assert manifest["generated_at"].endswith("Z")
        assert manifest["producer"] == "twin2multicloud_backend"
        assert manifest["twin"]["id"] == "twin-123"
        assert manifest["twin"]["resource_name"] == "test-twin"
        assert manifest["providers"] == {
            "layer_1_provider": "aws",
            "layer_2_provider": "aws",
            "layer_3_hot_provider": "aws",
            "layer_3_cold_provider": "aws",
            "layer_3_archive_provider": "aws",
            "layer_4_provider": "aws",
            "layer_5_provider": "aws",
        }
        assert manifest["calculation_run_id"] == TEST_CALCULATION_RUN_ID
        assert (
            manifest["resolved_deployment_specification_digest"]
            == manifest["resolved_deployment_specification"]["digest"]
        )
        assert (
            manifest["resolved_deployment_specification"]["calculation_run_id"]
            == TEST_CALCULATION_RUN_ID
        )
        assert manifest["credentials"] == {
            "providers": ["aws"],
            "sources": {"aws": "cloud_connection"},
            "contains_secret_payloads": False,
        }
        assert manifest["package"]["required_files"] == REQUIRED_DEPLOYER_CONFIG_FILES
        assert manifest["package"]["secret_bearing_files"] == [
            "config_credentials.json"
        ]
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

        with zipfile.ZipFile(result, "r") as zf:
            assert json.loads(zf.read("config_iot_devices.json")) == []
            assert json.loads(zf.read("config_events.json")) == []

    def test_includes_state_machine_for_azure_l2(self):
        """Should write state machine to azure location for Azure L2."""
        twin = self._create_mock_twin()
        twin.optimizer_config.cheapest_l2 = "azure"
        _attach_selected_run(twin)
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
            encrypted_payload=encrypt_scoped(
                json.dumps(azure_payload), "user-123", "connection-azure"
            ),
        )

        result = build_project_zip(twin, "user-123")

        with zipfile.ZipFile(result, "r") as zf:
            names = zf.namelist()
            assert "state_machines/azure_logic_app.json" in names

    def test_includes_state_machine_for_google_l2_alias(self):
        """Should write GCP workflow state machine for every accepted GCP spelling."""
        twin = self._create_mock_twin()
        twin.optimizer_config.cheapest_l2 = "GCP"
        _attach_selected_run(twin)
        twin.deployer_config.state_machine_content = "main:\n  steps: []\n"
        service_account = {
            "project_id": "demo-project",
            "client_email": "sa@example.test",
        }
        gcp_payload = {
            "gcp_project_id": "demo-project",
            "gcp_region": "europe-west1",
            "gcp_credentials_file": json.dumps(service_account),
        }
        twin.configuration.gcp_cloud_connection_id = "connection-gcp"
        twin.configuration.gcp_cloud_connection = SimpleNamespace(
            id="connection-gcp",
            encrypted_payload=encrypt_scoped(
                json.dumps(gcp_payload), "user-123", "connection-gcp"
            ),
        )

        result = build_project_zip(twin, "user-123")

        with zipfile.ZipFile(result, "r") as zf:
            names = zf.namelist()
            providers = json.loads(zf.read("config_providers.json"))
            assert "state_machines/google_cloud_workflow.yaml" in names
            assert providers["layer_2_provider"] == "google"

    def test_includes_payloads_json(self):
        """Should include payloads.json for simulator."""
        twin = self._create_mock_twin()
        twin.deployer_config.payloads_json = '{"device_1": {"temp": 25}}'

        result = build_project_zip(twin, "user-123")

        with zipfile.ZipFile(result, "r") as zf:
            names = zf.namelist()
            assert "iot_device_simulator/payloads.json" in names

    def test_legacy_selected_run_without_architecture_is_rejected(self, db):
        """A selected historical run cannot bypass the immutable architecture gate."""
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

        db.add_all(
            [
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
                    cheapest_l3_hot="AWS",
                    cheapest_l3_cool="AWS",
                    cheapest_l3_archive="AWS",
                    cheapest_l4="AWS",
                    cheapest_l5="AWS",
                    params=json.dumps(
                        {
                            "hotStorageDurationInMonths": 2,
                            "coolStorageDurationInMonths": 4,
                            "useEventChecking": True,
                            "needs3DModel": True,
                        }
                    ),
                ),
                DeployerConfiguration(
                    twin_id=twin.id,
                    deployer_digital_twin_name="factory-twin",
                    config_iot_devices_json='[{"id":"device-1"}]',
                    config_events_json="[]",
                    payloads_json='{"device-1":{"temperature":21}}',
                    scene_config_content="{}",
                ),
            ]
        )
        db.commit()
        db.expire_all()

        persisted_twin = db.get(DigitalTwin, twin.id)
        contract = _deployment_run_contract(persisted_twin)
        db.add(
            CostCalculationRun(
                id=TEST_CALCULATION_RUN_ID,
                twin_id=persisted_twin.id,
                user_id=user.id,
                status="succeeded",
                params_json="{}",
                result_summary_json=json.dumps(contract["result"]),
                cheapest_path_json=json.dumps(contract["cheapest_path"]),
                currency="USD",
                optimization_profile_id="cost_minimization_v1",
                optimization_profile_version="2026.06.08",
                scoring_strategy_id="min_total_cost_v1",
                calculation_model_version="cost_model_v1",
                pricing_registry_version="2026.07.17",
                pricing_catalog_context_json=catalog_context().canonical_json(),
                deployment_specification_json=json.dumps(
                    contract["specification"],
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                deployment_specification_digest=(contract["specification"]["digest"]),
                deployment_specification_version=(
                    contract["specification"]["schema_version"]
                ),
                deployment_compatibility_status="ready",
                created_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
                selected_for_deployment_at=datetime.now(timezone.utc),
            )
        )
        db.commit()
        db.expire_all()
        persisted_twin = db.get(DigitalTwin, twin.id)
        with pytest.raises(DeploymentPackageBuildFailed) as exc_info:
            build_project_zip(persisted_twin, user.id)

        assert exc_info.value.errors[0]["code"] == ("DEPLOYMENT_ARCHITECTURE_MISSING")

    def test_package_materialization_blocks_unvalidated_legacy_function_json(self):
        """Unvalidated legacy user logic must fail before artifact parsing."""
        twin = self._create_mock_twin()
        twin.optimizer_config.cheapest_l2 = "aws"
        twin.deployer_config.processor_contents = "{not-json"

        with pytest.raises(DeploymentPackageBuildFailed) as exc_info:
            build_deployment_package(twin, "user-123")

        assert exc_info.value.errors == [
            {
                "code": "EXTENSION_BINDING_UNRESOLVED",
                "field": "extension_bindings",
                "message": (
                    "Legacy unvalidated user logic cannot be selected for a "
                    "new deployment."
                ),
            }
        ]

    def test_package_materialization_fails_closed_on_invalid_optimizer_params(self):
        """Invalid immutable run params fail instead of reading mutable config."""
        twin = self._create_mock_twin()
        twin.cost_calculation_runs[0].params_json = "{not-json"

        with pytest.raises(DeploymentPackageBuildFailed) as exc_info:
            build_deployment_package(twin, "user-123")

        assert exc_info.value.errors[0]["field"] == "cost_calculation_run.params_json"
        assert exc_info.value.errors[0]["code"] == "INVALID_JSON"

    def test_package_uses_frozen_run_params_after_optimizer_config_changes(self):
        """Retry/destroy inputs stay bound to the selected calculation run."""
        twin = self._create_mock_twin()
        twin.optimizer_config.params = json.dumps(
            {
                "hotStorageDurationInMonths": 9,
                "coolStorageDurationInMonths": 12,
                "useEventChecking": False,
                "needs3DModel": True,
            }
        )

        package = build_deployment_package(twin, "user-123")
        files = {item.path: item.content for item in package.files}
        main_config = json.loads(files["config.json"])
        flags = json.loads(files["config_optimization.json"])["result"][
            "inputParamsUsed"
        ]

        assert main_config["hot_storage_size_in_days"] == 30
        assert main_config["cold_storage_size_in_days"] == 90
        assert main_config["archive_storage_size_in_days"] == 360
        assert flags["useEventChecking"] is True
        assert flags["needs3DModel"] is False

    def test_package_materialization_fails_when_uploaded_scene_binary_is_missing(
        self,
        tmp_path,
        monkeypatch,
    ):
        """Persisted artifact metadata must not point to missing managed files."""
        monkeypatch.setattr(
            "src.services.deployment_service.settings.UPLOAD_DIR", str(tmp_path)
        )
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
        twin.user_id = "user-123"
        twin.extension_bindings = []

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
        twin.optimizer_config.cheapest_l2 = "aws"
        twin.optimizer_config.cheapest_l3_hot = "aws"
        twin.optimizer_config.cheapest_l3_cool = "aws"
        twin.optimizer_config.cheapest_l3_archive = "aws"
        twin.optimizer_config.cheapest_l4 = "aws"
        twin.optimizer_config.cheapest_l5 = "aws"
        twin.optimizer_config.result_json = None
        twin.optimizer_config.params = json.dumps(
            {
                "hotStorageDurationInMonths": 1,
                "coolStorageDurationInMonths": 3,
                "useEventChecking": True,
                "triggerNotificationWorkflow": False,
                "returnFeedbackToDevice": False,
                "integrateErrorHandling": False,
                "needs3DModel": False,
            }
        )

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
            encrypted_payload=encrypt_scoped(
                json.dumps(aws_payload), "user-123", "connection-aws"
            ),
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

        _attach_selected_run(twin)
        return twin


class TestBuildOptimizationConfig:
    """Tests for _build_optimization_config helper."""

    def test_wraps_params_in_result_envelope(self):
        """Should produce {result: {inputParamsUsed: {...}}} structure."""
        oc = Mock()
        oc.params = json.dumps(
            {
                "useEventChecking": True,
                "triggerNotificationWorkflow": False,
                "returnFeedbackToDevice": True,
                "integrateErrorHandling": False,
                "needs3DModel": True,
            }
        )

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

    @pytest.mark.parametrize(
        "profile_ref",
        [
            {"id": "five-layer-baseline", "version": "2"},
            {"id": "six-layer-eventing", "version": "1"},
        ],
    )
    def test_phase8_profiles_emit_no_legacy_feature_flags(self, profile_ref):
        result = _build_optimization_config_from_params(
            {
                "numberOfDevices": 100,
                "workloadSize": "small",
            },
            architecture_profile_ref=profile_ref,
        )

        assert result == {"result": {"inputParamsUsed": {}}}

    def test_phase8_profile_rejects_even_false_legacy_feature_flag(self):
        with pytest.raises(DeploymentPackageBuildFailed) as exc_info:
            _build_optimization_config_from_params(
                {"useEventChecking": False},
                architecture_profile_ref={
                    "id": "six-layer-eventing",
                    "version": "1",
                },
            )

        assert exc_info.value.errors[0]["code"] == "FORBIDDEN_PROFILE_FIELD"

    def test_phase8_forbidden_fields_match_frozen_profile_contract(self):
        assert PHASE_8_FORBIDDEN_OPTIMIZER_FIELDS == {
            "allowGcpSelfHostedL4",
            "allowGcpSelfHostedL5",
            "amountOfActiveEditors",
            "amountOfActiveViewers",
            "apiCallsPerDashboardRefresh",
            "average3DModelSizeInMB",
            "dashboardRefreshesPerHour",
            "entityCount",
            "eventTriggerRate",
            "eventsPerMessage",
            "integrateErrorHandling",
            "needs3DModel",
            "numberOfEventActions",
            "orchestrationActionsPerMessage",
            "returnFeedbackToDevice",
            "triggerNotificationWorkflow",
            "useEventChecking",
        }

    def test_rejects_legacy_unsupported_error_handling_topology(self):
        oc = Mock()
        oc.params = json.dumps({"integrateErrorHandling": True})

        with pytest.raises(DeploymentPackageBuildFailed) as exc_info:
            _build_optimization_config(oc)

        assert exc_info.value.errors == [
            {
                "code": "UNSUPPORTED_ERROR_HANDLING_TOPOLOGY",
                "field": "optimizer_config.params.integrateErrorHandling",
                "message": (
                    "The executable five-layer baseline does not deploy the "
                    "requested error-handling topology"
                ),
            }
        ]


@pytest.mark.parametrize(
    ("provider", "field", "invalid"),
    [
        ("aws", "aws_region", "us-east-1"),
        ("azure", "azure_region", "northeurope"),
        ("gcp", "gcp_region", "us-central1"),
    ],
)
def test_phase8_deployment_rejects_regions_outside_priced_contract(
    provider,
    field,
    invalid,
):
    architecture = {
        "architecture_profile_ref": {
            "id": "six-layer-eventing",
            "version": "1",
        }
    }
    providers = {
        "layer_1_provider": "aws",
        "layer_2_provider": "azure",
        "layer_3_hot_provider": "google",
    }
    credentials = {
        "aws": {"aws_region": "eu-central-1"},
        "azure": {
            "azure_region": "westeurope",
            "azure_region_iothub": "westeurope",
        },
        "gcp": {"gcp_region": "europe-west1"},
    }
    credentials[provider][field] = invalid

    with pytest.raises(DeploymentPackageBuildFailed) as exc_info:
        _validate_phase8_deployment_regions(
            architecture,
            providers,
            credentials,
        )

    assert exc_info.value.errors[0]["code"] == "DEPLOYMENT_REGION_UNSUPPORTED"


def test_six_layer_credential_projection_includes_event_only_provider():
    architecture = {
        "component_assignments": [
            {
                "logical_component_id": "component.ingestion",
                "provider": "aws",
            },
            {
                "logical_component_id": "component.eventing",
                "provider": "azure",
            },
        ]
    }

    assert _architecture_provider_ids(architecture) == {"aws", "azure"}


def test_phase8_region_guard_includes_event_only_provider():
    architecture = {
        "architecture_profile_ref": {
            "id": "six-layer-eventing",
            "version": "1",
        },
        "component_assignments": [
            {
                "logical_component_id": "component.ingestion",
                "provider": "aws",
            },
            {
                "logical_component_id": "component.eventing",
                "provider": "azure",
            },
        ],
    }

    with pytest.raises(DeploymentPackageBuildFailed) as exc_info:
        _validate_phase8_deployment_regions(
            architecture,
            {"layer_1_provider": "aws"},
            {
                "aws": {"aws_region": "eu-central-1"},
                "azure": {"azure_region": "northeurope"},
            },
        )

    assert exc_info.value.errors[0]["field"] == (
        "config_credentials.azure.azure_region"
    )


@pytest.mark.parametrize(
    "field",
    [
        "processor_contents",
        "event_action_contents",
        "event_feedback_content",
        "hierarchy_content",
        "state_machine_content",
        "scene_config_content",
        "scene_glb_uploaded",
    ],
)
def test_phase8_deployment_rejects_historical_user_logic_and_scenes(field):
    deployer_config = SimpleNamespace(
        **{
            name: False if name == "scene_glb_uploaded" else None
            for name in (
                "event_action_contents",
                "event_action_requirements",
                "event_feedback_content",
                "event_feedback_requirements",
                "hierarchy_content",
                "processor_contents",
                "processor_requirements",
                "scene_config_content",
                "scene_glb_uploaded",
                "state_machine_content",
            )
        }
    )
    setattr(deployer_config, field, True if field == "scene_glb_uploaded" else "old")

    with pytest.raises(DeploymentPackageBuildFailed) as exc_info:
        _validate_phase8_deployer_artifacts(
            deployer_config,
            {"id": "five-layer-baseline", "version": "2"},
        )

    assert exc_info.value.errors[0]["code"] == "FORBIDDEN_PROFILE_FIELD"


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
            resolved_architecture=calculation_result_and_contracts("aws")[2],
            deployment_specification=_all_aws_specification(),
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

    def test_v2_contract_pair_produces_manifest_v4_and_complete_catalog(self):
        root = (
            Path(__file__).resolve().parents[1]
            / "src"
            / "contracts"
            / "generated"
            / "deployment-manifest"
            / "v4"
            / "fixtures"
            / "valid"
        )
        fixture = json.loads(
            (root / "single-cloud-aws-small.json").read_text(encoding="utf-8")
        )
        twin = Mock()
        twin.id = "twin-v2"
        twin.name = "Five Layer V2"
        twin.deployer_config = Mock()
        twin.deployer_config.deployer_digital_twin_name = "five-layer-v2"

        result = _build_deployment_manifest(
            twin,
            fixture["providers"],
            DeploymentCredentials(
                providers=("aws",),
                config_credentials={},
                sources={"aws": "cloud_connection"},
            ),
            ["config.json", "config_credentials.json"],
            resolved_architecture=fixture["resolved_twin_architecture"],
            deployment_specification=fixture["resolved_deployment_specification"],
        )

        assert result["manifest_version"] == "4.0"
        assert (
            result["compatibility"]["component_catalog_ref"]
            == fixture["compatibility"]["component_catalog_ref"]
        )

    def test_six_layer_profile_resolves_its_exact_component_catalog(self):
        root = (
            Path(__file__).resolve().parents[1]
            / "src"
            / "contracts"
            / "generated"
            / "architecture-profiles"
            / "definitions"
            / "component-catalogs"
            / "six-layer-eventing"
            / "1"
            / "catalog.json"
        )
        catalog = json.loads(root.read_text(encoding="utf-8"))

        assert _component_catalog_ref({"id": "six-layer-eventing", "version": "1"}) == {
            "id": catalog["catalog_id"],
            "version": catalog["catalog_version"],
            "digest": catalog["content_digest"],
        }

    def test_cross_version_contract_pair_is_rejected(self):
        _, _, architecture = calculation_result_and_contracts("aws")
        v2_specification = json.loads(
            (
                Path(__file__).resolve().parents[1]
                / "src"
                / "contracts"
                / "generated"
                / "resolved-deployment-specification"
                / "v2"
                / "fixtures"
                / "valid"
                / "single-cloud-aws-small.json"
            ).read_text(encoding="utf-8")
        )

        with pytest.raises(DeploymentPackageBuildFailed) as exc_info:
            _build_deployment_manifest(
                Mock(),
                {},
                DeploymentCredentials(
                    providers=("aws",),
                    config_credentials={},
                    sources={"aws": "cloud_connection"},
                ),
                [],
                resolved_architecture=architecture,
                deployment_specification=v2_specification,
            )

        assert exc_info.value.errors[0]["message"] == (
            "DEPLOYMENT_ARCHITECTURE_SPEC_MISMATCH"
        )
