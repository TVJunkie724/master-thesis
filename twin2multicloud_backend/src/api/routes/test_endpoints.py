# src/api/routes/test_endpoints.py
"""
Test endpoints for UI testing and development.

These endpoints simulate deployment/destroy operations without actually 
creating cloud resources. They are gated by ENABLE_TEST_ENDPOINTS=true.

Consolidated from twins.py to keep production code clean and test code separate.
"""

import os
import json
import asyncio
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from src.models.database import get_db
from src.models.twin import DigitalTwin, TwinState
from src.models.user import User
from src.api.dependencies import get_current_user
from src.api.routes.error_models import ERROR_RESPONSES
from src.repositories.twin_repository import TwinRepository
from src.services.deployment_operation_service import DeploymentOperationService
from src.services.service_errors import ConflictError, EntityNotFoundError, ValidationError
from src.services.test_deployment_service import TestDeploymentService

router = APIRouter(prefix="/twins", tags=["twins-test"])

# Gate all test endpoints behind env var
TEST_ENDPOINTS_ENABLED = os.getenv("ENABLE_TEST_ENDPOINTS", "false").lower() == "true"


def _require_test_endpoints():
    """Raise 404 if test endpoints are disabled."""
    if not TEST_ENDPOINTS_ENABLED:
        raise HTTPException(status_code=404, detail="Not found")


def _deployment_operation_service(db: Session) -> DeploymentOperationService:
    """Build the shared deployment operation service for test endpoints."""
    return DeploymentOperationService(db=db, twin_repository=TwinRepository(db))


def _test_deployment_service(db: Session) -> TestDeploymentService:
    """Build the test-only deployment service for gated UI-development flows."""
    return TestDeploymentService(db=db, twin_repository=TwinRepository(db))


def _raise_service_http_error(exc: Exception) -> None:
    """Map typed service errors to the existing test-endpoint HTTP contract."""
    if isinstance(exc, EntityNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, ValidationError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if isinstance(exc, ConflictError):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    raise exc


# =============================================================================
# Test Deploy Endpoint
# =============================================================================

@router.post(
    "/{twin_id}/test-deploy",
    operation_id="testDeployDigitalTwin",
    summary="[TEST] Simulate deployment for UI testing",
    description=(
        "**Purpose:** Simulate a realistic deployment without creating cloud resources.\n\n"
        "**When to call:** During UI development with `kUseTestDeploy = true`.\n\n"
        "**Gate:** Requires `ENABLE_TEST_ENDPOINTS=true` environment variable.\n\n"
        "**Query params:**\n"
        "- `duration`: Simulated duration in seconds (5-120, default 30)\n"
        "- `should_fail`: Simulate failure at end (boolean)\n\n"
        "**Response:** Same as real /deploy - session_id and sse_url."
    ),
    responses={
        404: ERROR_RESPONSES[404],
        409: ERROR_RESPONSES[409],
    }
)
async def test_deploy_twin(
    twin_id: str,
    duration: int = Query(30, ge=5, le=120, description="Simulated duration in seconds"),
    should_fail: bool = Query(False, description="Simulate failure at end"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Test deployment for UI testing - simulates realistic deployment with SSE logs.
    
    Requires ENABLE_TEST_ENDPOINTS=true environment variable.
    No real cloud resources are created.
    """
    _require_test_endpoints()

    async def runner(**kwargs):
        kwargs["duration"] = duration
        kwargs["should_fail"] = should_fail
        await _run_test_deploy_stream(**kwargs)

    try:
        return await _deployment_operation_service(db).deploy_twin(
            twin_id=twin_id,
            user_id=current_user.id,
            test_mode=True,
            test_stream_runner=runner,
            skip_state_validation=True,
        )
    except (ConflictError, EntityNotFoundError, ValidationError) as exc:
        _raise_service_http_error(exc)


# =============================================================================
# Test Destroy Endpoint
# =============================================================================

@router.post(
    "/{twin_id}/test-destroy",
    operation_id="testDestroyDigitalTwin",
    summary="[TEST] Simulate infrastructure destruction for UI testing",
    description=(
        "**Purpose:** Simulate a realistic destroy operation without cloud API calls.\n\n"
        "**When to call:** During UI development with `kUseTestDeploy = true`.\n\n"
        "**Gate:** Requires `ENABLE_TEST_ENDPOINTS=true` environment variable.\n\n"
        "**Query params:**\n"
        "- `duration`: Simulated duration in seconds (5-60, default 20)\n"
        "- `should_fail`: Simulate failure at end (boolean)\n\n"
        "**Response:** Same as real /destroy - session_id and sse_url."
    ),
    responses={
        404: ERROR_RESPONSES[404],
        409: ERROR_RESPONSES[409],
    }
)
async def test_destroy_twin(
    twin_id: str,
    duration: int = Query(20, ge=5, le=60, description="Simulated duration in seconds"),
    should_fail: bool = Query(False, description="Simulate failure at end"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Test destroy for UI testing - simulates realistic destruction with SSE logs.
    
    Requires ENABLE_TEST_ENDPOINTS=true environment variable.
    """
    _require_test_endpoints()

    async def runner(**kwargs):
        kwargs["duration"] = duration
        kwargs["should_fail"] = should_fail
        await _run_test_destroy_stream(**kwargs)

    try:
        return await _deployment_operation_service(db).destroy_twin(
            twin_id=twin_id,
            user_id=current_user.id,
            test_mode=True,
            test_stream_runner=runner,
            skip_state_validation=True,
        )
    except (ConflictError, EntityNotFoundError, ValidationError) as exc:
        _raise_service_http_error(exc)


# =============================================================================
# Test Log Trace Endpoint  
# =============================================================================

@router.post(
    "/{twin_id}/test-log-trace/start",
    operation_id="testStartLogTrace",
    summary="[TEST] Simulate log trace for UI testing",
    description=(
        "**Purpose:** Simulate multi-cloud log streaming without real cloud queries.\n\n"
        "**When to call:** During UI development with `kUseTestDeploy = true`.\n\n"
        "**Gate:** Requires `ENABLE_TEST_ENDPOINTS=true` environment variable.\n\n"
        "**Query params:**\n"
        "- `duration`: Simulated duration in seconds (5-90, default 30)\n"
        "- `should_fail`: Simulate trace failure (boolean)\n\n"
        "**Response:** Same as real /log-trace/start - trace_id, providers, sse_url."
    ),
    responses={
        404: ERROR_RESPONSES[404],
    }
)
async def test_log_trace_start(
    twin_id: str,
    duration: int = Query(30, ge=5, le=90, description="Simulated duration in seconds"),
    should_fail: bool = Query(False, description="Simulate trace failure"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Test log trace for UI testing - simulates realistic multi-cloud log streaming.
    
    Requires ENABLE_TEST_ENDPOINTS=true environment variable.
    No real cloud resources are queried.
    """
    _require_test_endpoints()

    try:
        return await _test_deployment_service(db).start_log_trace(
            twin_id=twin_id,
            user_id=current_user.id,
            duration=duration,
            should_fail=should_fail,
            test_log_trace_runner=_run_test_log_trace_stream,
        )
    except EntityNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# =============================================================================
# Test Download Simulator Endpoint
# =============================================================================

@router.get(
    "/{twin_id}/simulator/test-download",
    operation_id="testDownloadIoTSimulator",
    summary="[TEST] Download mock IoT simulator package",
    description=(
        "**Purpose:** Return a mock simulator zip for UI development testing.\n\n"
        "**When to call:** During UI development with `kUseTestDeploy = true`.\n\n"
        "**Note:** Does NOT require real deployment or Deployer connectivity.\n\n"
        "**Response:** ZIP file with mock simulator structure:\n"
        "- config.json, payloads.json, README.md\n"
        "- requirements.txt, src/main.py (mock code)"
    ),
    responses={
        200: {"description": "Mock simulator zip package for UI testing"},
        404: ERROR_RESPONSES[404],
    }
)
async def test_download_simulator(
    twin_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Mock endpoint for UI testing - returns a sample simulator zip.
    
    Does NOT require real deployment or Deployer connectivity.
    Use when kUseTestDeploy = true in Flutter.
    """
    _require_test_endpoints()

    try:
        archive = _test_deployment_service(db).build_mock_simulator_archive(
            twin_id=twin_id,
            user_id=current_user.id,
        )
    except EntityNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return StreamingResponse(
        archive.content,
        media_type=archive.media_type,
        headers={"Content-Disposition": f"attachment; filename={archive.filename}"}
    )


# =============================================================================
# Background Task: Test Deploy Stream
# =============================================================================

async def _run_test_deploy_stream(
    session_id: str,
    twin_id: str,
    twin_name: str,
    duration: int,
    should_fail: bool
):
    """
    Background task that simulates Terraform deployment and streams logs via SSE.
    Creates its own DB session to avoid session scoping issues.
    """
    from src.api.routes.sse import get_session
    from src.models.database import SessionLocal
    from src.models.deployment import Deployment
    
    session = await get_session(session_id)
    if not session:
        return
    
    db = SessionLocal()
    deployment = Deployment(
        twin_id=twin_id,
        session_id=session_id,
        operation_type="deploy",
        status="running"
    )
    db.add(deployment)
    db.commit()
    db.close()
    
    def _get_mock_terraform_outputs(name: str) -> dict:
        """Generate comprehensive mock terraform outputs matching outputs.tf"""
        return {
            "digital_twin_name": name,
            "aws_resource_group_name": f"rg-{name}",
            "aws_account_id": "123456789012",
            "aws_region": "us-east-1",
            "aws_l0_ingestion_function_name": f"{name}-l0-ingestion",
            "aws_l0_ingestion_url": f"https://{name}-l0-ingestion.lambda-url.us-east-1.on.aws/",
            "aws_l0_hot_writer_url": f"https://{name}-l0-hot-writer.lambda-url.us-east-1.on.aws/",
            "aws_l0_hot_reader_url": f"https://{name}-l0-hot-reader.lambda-url.us-east-1.on.aws/",
            "aws_l0_cold_writer_function_name": f"{name}-l0-cold-writer",
            "aws_l0_cold_writer_url": f"https://{name}-l0-cold-writer.lambda-url.us-east-1.on.aws/",
            "aws_l0_archive_writer_function_name": f"{name}-l0-archive-writer",
            "aws_l0_archive_writer_url": f"https://{name}-l0-archive-writer.lambda-url.us-east-1.on.aws/",
            "aws_l1_dispatcher_function_name": f"{name}-l1-dispatcher",
            "aws_iot_topic_rule_name": f"{name}_telemetry_rule",
            "aws_iot_role_arn": f"arn:aws:iam::123456789012:role/{name}-iot-rule",
            "aws_l1_connector_function_name": f"{name}-l1-connector",
            "aws_iot_endpoint": f"a1b2c3d4e5f6g7.iot.us-east-1.amazonaws.com",
            "aws_l2_persister_function_name": f"{name}-l2-persister",
            "aws_l2_event_checker_function_name": f"{name}-l2-event-checker",
            "aws_l2_step_function_arn": f"arn:aws:states:us-east-1:123456789012:stateMachine:{name}-workflow",
            "aws_dynamodb_table_name": f"{name}-hot-storage",
            "aws_dynamodb_table_arn": f"arn:aws:dynamodb:us-east-1:123456789012:table/{name}-hot-storage",
            "aws_l3_hot_reader_function_name": f"{name}-l3-hot-reader",
            "aws_l3_hot_reader_url": f"https://{name}-l3-hot-reader.lambda-url.us-east-1.on.aws/",
            "aws_s3_cold_bucket": f"{name}-cold-storage-abc123",
            "aws_s3_archive_bucket": f"{name}-archive-storage-def456",
            "aws_twinmaker_workspace_id": f"{name}-workspace",
            "aws_twinmaker_workspace_arn": f"arn:aws:iottwinmaker:us-east-1:123456789012:workspace/{name}-workspace",
            "aws_twinmaker_scene_id": f"{name}-scene",
            "aws_grafana_workspace_id": "g-abc123def456",
            "aws_grafana_endpoint": "https://g-abc123def456.grafana-workspace.us-east-1.amazonaws.com",
            "aws_platform_user_email": "user@example.com",
            "aws_sso_available": True,
            "aws_platform_user_created": True,
            "azure_resource_group_name": f"rg-{name}-eastus",
            "azure_resource_group_id": f"/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-{name}-eastus",
            "azure_managed_identity_id": f"/subscriptions/.../userAssignedIdentities/{name}-identity",
            "azure_managed_identity_client_id": "11111111-1111-1111-1111-111111111111",
            "azure_storage_account_name": f"{name.replace('-', '')}storage",
            "azure_l0_function_app_name": f"{name}-l0-glue",
            "azure_l0_function_app_url": f"https://{name}-l0-glue.azurewebsites.net",
            "azure_iothub_name": f"{name}-iothub",
            "azure_iothub_hostname": f"{name}-iothub.azure-devices.net",
            "azure_l1_function_app_name": f"{name}-l1",
            "azure_l2_function_app_name": f"{name}-l2",
            "azure_user_functions_app_name": f"{name}-user",
            "azure_dispatcher_url": f"https://{name}-l2.azurewebsites.net/api/dispatcher",
            "azure_cosmos_account_name": f"{name}-cosmos",
            "azure_cosmos_endpoint": f"https://{name}-cosmos.documents.azure.com:443/",
            "azure_l3_function_app_name": f"{name}-l3",
            "azure_l3_hot_reader_url": f"https://{name}-l3.azurewebsites.net/api/hot-reader",
            "azure_archive_storage_account": f"{name.replace('-', '')}storage",
            "azure_adt_instance_name": f"{name}-adt",
            "azure_adt_endpoint": f"https://{name}-adt.api.eus.digitaltwins.azure.net",
            "azure_3d_scenes_container_url": f"https://{name.replace('-', '')}storage.blob.core.windows.net/scenes",
            "azure_platform_user_created": False,
            "azure_grafana_name": f"{name}-grafana",
            "azure_grafana_endpoint": f"https://{name}-grafana.eus.grafana.azure.com",
            "gcp_project_id": f"{name}-project-abc123",
            "gcp_service_account_email": f"functions@{name}-project.iam.gserviceaccount.com",
            "gcp_function_source_bucket": f"{name}-function-source",
            "gcp_pubsub_telemetry_topic": f"projects/{name}-project/topics/telemetry",
            "gcp_pubsub_events_topic": f"projects/{name}-project/topics/events",
            "gcp_dispatcher_url": f"https://dispatcher-abc123-uc.a.run.app",
            "gcp_connector_url": f"https://connector-def456-uc.a.run.app",
            "gcp_processor_url": f"https://processor-ghi789-uc.a.run.app",
            "gcp_persister_url": f"https://persister-jkl012-uc.a.run.app",
            "gcp_event_checker_url": f"https://event-checker-mno345-uc.a.run.app",
            "gcp_user_functions_url": f"https://user-functions-pqr678-uc.a.run.app",
            "gcp_event_workflow_id": f"projects/{name}-project/locations/us-central1/workflows/event-workflow",
            "gcp_firestore_database": "(default)",
            "gcp_cold_bucket": f"{name}-cold-storage",
            "gcp_archive_bucket": f"{name}-archive-storage",
            "gcp_hot_reader_url": f"https://hot-reader-stu901-uc.a.run.app",
            "gcp_ingestion_url": f"https://ingestion-vwx234-uc.a.run.app",
            "gcp_hot_writer_url": f"https://hot-writer-yza567-uc.a.run.app",
            "gcp_cold_writer_url": f"https://cold-writer-bcd890-uc.a.run.app",
            "gcp_archive_writer_url": f"https://archive-writer-efg123-uc.a.run.app",
            "inter_cloud_token": "mock-inter-cloud-token-xyz789",
        }
    
    try:
        steps = [
            (0.02, "=" * 60),
            (0.02, "  TERRAFORM DEPLOYMENT - STARTING (TEST MODE)"),
            (0.02, "=" * 60),
            (0.03, ""),
            (0.04, f"[STEP 0/9] Validating cloud credentials for '{twin_name}'..."),
            (0.02, "  Configured clouds: aws, azure"),
            (0.02, "  ✓ AWS credentials validated"),
            (0.02, "  ✓ Azure credentials validated"),
            (0.03, ""),
            (0.02, "[STEP 0.5/9] Initializing cloud providers for SDK operations..."),
            (0.02, "  ✓ Providers initialized"),
            (0.03, ""),
            (0.02, "[STEP 1/9] Validating project structure..."),
            (0.02, "✓ Project validation passed"),
            (0.03, ""),
            (0.02, "[STEP 2/9] Building function packages..."),
            (0.03, "  Building dispatcher package..."),
            (0.03, "  Building persister package..."),
            (0.02, "✓ All packages built"),
            (0.03, ""),
            (0.02, "[STEP 3/9] Generating tfvars.json..."),
            (0.02, f"✓ Generated: /app/upload/{twin_name}/terraform/generated.tfvars.json"),
            (0.03, ""),
            (0.02, "[STEP 4/9] Terraform init..."),
            (0.03, "Initializing provider plugins..."),
            (0.03, "- Finding hashicorp/aws versions matching ~> 5.0..."),
            (0.03, "- Installing hashicorp/aws v5.31.0..."),
            (0.02, "✓ Terraform initialized"),
            (0.03, ""),
            (0.02, "[STEP 5/9] Terraform apply..."),
            (0.04, f"aws_iot_thing.{twin_name}_thing: Creating..."),
            (0.05, f"aws_dynamodb_table.{twin_name}_hot_storage: Creating..."),
            (0.03, f"aws_iot_thing.{twin_name}_thing: Creation complete after 2s"),
            (0.05, f"aws_dynamodb_table.{twin_name}_hot_storage: Creation complete after 8s"),
            (0.04, f"aws_lambda_function.{twin_name}_dispatcher: Creating..."),
            (0.05, f"aws_lambda_function.{twin_name}_dispatcher: Creation complete after 12s"),
            (0.02, ""),
            (0.02, "Apply complete! Resources: 15 added, 0 changed, 0 destroyed."),
            (0.02, "✓ Terraform outputs: ['aws_iot_endpoint', 'aws_dynamodb_table_name', 'aws_l1_dispatcher_function_name', ...]"),
            (0.03, ""),
            (0.02, "[STEP 6/9] Deploying Azure function code..."),
            (0.02, "  No Azure layers configured, skipping Kudu deployment"),
            (0.03, ""),
            (0.02, "[STEP 7/9] Running post-deployment operations..."),
            (0.03, "  Registering IoT devices..."),
            (0.02, "  ✓ 3 devices registered"),
            (0.03, ""),
        ]
        
        total_fraction = sum(s[0] for s in steps)
        for fraction, msg in steps:
            if msg:
                print(msg, flush=True)
                await session.push_log(msg)
            await asyncio.sleep(duration * fraction / total_fraction)
        
        if should_fail:
            error_msg = "Simulated deployment failure: Terraform apply failed with exit code 1"
            print(f"✗ {error_msg}", flush=True)
            await session.push_log(f"✗ {error_msg}", level="error")
            
            db = SessionLocal()
            try:
                twin = db.query(DigitalTwin).get(twin_id)
                if twin:
                    twin.state = TwinState.ERROR
                    twin.last_error = error_msg
                    db.commit()
                
                deployment = db.query(Deployment).filter(Deployment.session_id == session_id).first()
                if deployment:
                    deployment.status = "failed"
                    deployment.error_message = error_msg
                    deployment.completed_at = datetime.utcnow()
                    db.commit()
            finally:
                db.close()
            
            session.on_complete(success=False, message=error_msg)
            return
        
        # Success path
        for msg in ["=" * 60, "  TERRAFORM DEPLOYMENT - COMPLETE", "=" * 60]:
            print(msg, flush=True)
            await session.push_log(msg)
        
        db = SessionLocal()
        try:
            twin = db.query(DigitalTwin).get(twin_id)
            if twin:
                twin.state = TwinState.DEPLOYED
                twin.deployed_at = datetime.utcnow()
                db.commit()
            
            deployment = db.query(Deployment).filter(Deployment.session_id == session_id).first()
            if deployment:
                deployment.status = "success"
                deployment.terraform_outputs = _get_mock_terraform_outputs(twin_name)
                deployment.completed_at = datetime.utcnow()
                db.commit()
        finally:
            db.close()
        
        session.on_complete(
            success=True,
            message="Deployment complete (test mode)",
            outputs=_get_mock_terraform_outputs(twin_name)
        )
        
    except Exception as e:
        try:
            db = SessionLocal()
            twin = db.query(DigitalTwin).get(twin_id)
            if twin:
                twin.state = TwinState.ERROR
                twin.last_error = str(e)
                db.commit()
            
            deployment = db.query(Deployment).filter(Deployment.session_id == session_id).first()
            if deployment:
                deployment.status = "failed"
                deployment.error_message = str(e)
                deployment.completed_at = datetime.utcnow()
                db.commit()
            db.close()
        except Exception:
            pass
        session.on_complete(success=False, message=str(e))


# =============================================================================
# Background Task: Test Destroy Stream
# =============================================================================

async def _run_test_destroy_stream(
    session_id: str,
    twin_id: str,
    twin_name: str,
    duration: int,
    should_fail: bool
):
    """
    Background task that simulates Terraform destruction and streams logs via SSE.
    """
    from src.api.routes.sse import get_session
    from src.models.database import SessionLocal
    from src.models.deployment import Deployment
    
    session = await get_session(session_id)
    if not session:
        return
    
    db = SessionLocal()
    deployment = Deployment(
        twin_id=twin_id,
        session_id=session_id,
        operation_type="destroy",
        status="running"
    )
    db.add(deployment)
    db.commit()
    db.close()
    
    try:
        steps = [
            (0.05, "=" * 60),
            (0.05, "  TERRAFORM DESTROY - STARTING (TEST MODE)"),
            (0.05, "=" * 60),
            (0.08, ""),
            (0.08, "[STEP 1/2] Terraform destroy..."),
            (0.12, f"aws_lambda_function.{twin_name}_dispatcher: Destroying..."),
            (0.12, f"aws_lambda_function.{twin_name}_dispatcher: Destruction complete after 5s"),
            (0.08, f"aws_dynamodb_table.{twin_name}_hot_storage: Destroying..."),
            (0.12, f"aws_dynamodb_table.{twin_name}_hot_storage: Destruction complete after 10s"),
            (0.05, ""),
            (0.05, "Destroy complete! Resources: 15 destroyed."),
        ]
        
        total_fraction = sum(s[0] for s in steps)
        for fraction, msg in steps:
            if msg:
                print(msg, flush=True)
                await session.push_log(msg)
            await asyncio.sleep(duration * fraction / total_fraction)
        
        if should_fail:
            error_msg = "Simulated destroy failure: Resource still in use"
            print(f"✗ {error_msg}", flush=True)
            await session.push_log(f"✗ {error_msg}", level="error")
            
            db = SessionLocal()
            try:
                twin = db.query(DigitalTwin).get(twin_id)
                if twin:
                    twin.state = TwinState.ERROR
                    twin.last_error = error_msg
                    db.commit()
                
                deployment = db.query(Deployment).filter(Deployment.session_id == session_id).first()
                if deployment:
                    deployment.status = "failed"
                    deployment.error_message = error_msg
                    deployment.completed_at = datetime.utcnow()
                    db.commit()
            finally:
                db.close()
            
            session.on_complete(success=False, message=error_msg)
            return
        
        # Success path
        for msg in ["=" * 60, "  TERRAFORM DESTROY - COMPLETE", "=" * 60]:
            print(msg, flush=True)
            await session.push_log(msg)
        
        db = SessionLocal()
        try:
            twin = db.query(DigitalTwin).get(twin_id)
            if twin:
                twin.state = TwinState.DESTROYED
                twin.destroyed_at = datetime.utcnow()
                db.commit()
            
            deployment = db.query(Deployment).filter(Deployment.session_id == session_id).first()
            if deployment:
                deployment.status = "success"
                deployment.completed_at = datetime.utcnow()
                db.commit()
        finally:
            db.close()
        
        session.on_complete(success=True, message="Destruction complete (test mode)")
        
    except Exception as e:
        try:
            db = SessionLocal()
            twin = db.query(DigitalTwin).get(twin_id)
            if twin:
                twin.state = TwinState.ERROR
                twin.last_error = str(e)
                db.commit()
            
            deployment = db.query(Deployment).filter(Deployment.session_id == session_id).first()
            if deployment:
                deployment.status = "failed"
                deployment.error_message = str(e)
                deployment.completed_at = datetime.utcnow()
                db.commit()
            db.close()
        except Exception:
            pass
        session.on_complete(success=False, message=str(e))


# =============================================================================
# Background Task: Test Log Trace Stream
# =============================================================================

async def _run_test_log_trace_stream(
    session_id: str,
    twin_id: str,
    trace_id: str,
    providers: list,
    duration: int,
    should_fail: bool
):
    """
    Background task that simulates multi-cloud log streaming via SSE.
    Generates realistic log events based on configured providers.
    """
    from src.api.routes.sse import get_session
    
    session = await get_session(session_id)
    if not session:
        return
    
    try:
        steps = []
        storage_names = {"aws": "DynamoDB", "azure": "CosmosDB", "gcp": "Firestore"}
        
        primary = providers[0] if providers else "aws"
        storage_name = storage_names.get(primary, "Database")
        
        steps.extend([
            (0.02, "log", {"layer": "L1", "provider": primary, "function": "dispatcher",
             "message": f'{{"device_id":"test-sensor","trace_id":"{trace_id}"}}'}),
            (0.02, "log", {"layer": "L1", "provider": primary, "function": "dispatcher",
             "message": "Routing to L2 persister"}),
            (0.05, "log", {"layer": "L2", "provider": primary, "function": "persister",
             "message": "Processing payload for device: test-sensor"}),
            (0.05, "log", {"layer": "L2", "provider": primary, "function": "persister",
             "message": f"PutItem: pk=test-sensor, sk={datetime.now(timezone.utc).isoformat()}"}),
            (0.05, "log", {"layer": "L3", "provider": primary, "function": storage_name,
             "message": "Write succeeded, RCU: 1"}),
        ])
        
        for idx, prov in enumerate(providers[1:], start=1):
            sec_storage = storage_names.get(prov, "Database")
            steps.extend([
                (0.08, "log", {"layer": "L0", "provider": prov, "function": "l0-ingestion",
                 "message": f"HTTP 200: Ingested from {primary.upper()}, trace_id={trace_id}"}),
                (0.05, "log", {"layer": "L2", "provider": prov, "function": "dispatcher",
                 "message": "Processing cross-cloud payload"}),
                (0.05, "log", {"layer": "L3", "provider": prov, "function": sec_storage,
                 "message": "Write succeeded"}),
            ])
        
        steps.append((0.30, "heartbeat", {"elapsed_seconds": duration // 2}))
        
        total_fraction = sum(s[0] for s in steps)
        log_count = 0
        
        for fraction, event_type, data in steps:
            await asyncio.sleep(duration * fraction / total_fraction)
            
            data["timestamp"] = datetime.now(timezone.utc).isoformat()
            
            if event_type == "log":
                log_count += 1
                await session.push_log(json.dumps(data))
            else:
                await session.push_event(event_type, data)
        
        if should_fail:
            error_data = {
                "message": "Simulated trace failure: CloudWatch query timeout",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            await session.push_event("error", error_data)
            session.on_complete(success=False, message="Trace failed")
            return
        
        done_data = {
            "message": "Trace complete",
            "log_count": log_count,
            "duration_seconds": duration
        }
        await session.push_event("done", done_data)
        session.on_complete(success=True, message="Trace complete")
        
    except Exception as e:
        session.on_complete(success=False, message=str(e))


# =============================================================================
# Legacy Simulation Functions (kept for backward compatibility)
# =============================================================================

async def _simulate_deployment(name: str, duration: int, should_fail: bool, logger) -> list:
    """Print realistic terraform-style deployment logs. Returns collected logs."""
    collected_logs = []
    
    steps = [
        (0.02, "=" * 60),
        (0.02, "  TERRAFORM DEPLOYMENT - STARTING (TEST MODE)"),
        (0.02, "=" * 60),
        (0.05, ""),
        (0.05, f"[STEP 0/9] Validating cloud credentials for '{name}'..."),
        (0.03, "  Configured clouds: aws, azure"),
        (0.02, "✓ Deploy complete!"),
    ]
    
    total_fraction = sum(s[0] for s in steps)
    for fraction, msg in steps:
        if msg:
            logger.info(msg)
            collected_logs.append(msg)
        await asyncio.sleep(duration * fraction / total_fraction)
    
    if should_fail:
        error_msg = "Simulated deployment failure: Terraform apply failed with exit code 1"
        collected_logs.append(f"✗ {error_msg}")
        raise Exception(error_msg)
    
    return collected_logs


async def _simulate_destroy(name: str, duration: int, should_fail: bool, logger) -> list:
    """Print realistic terraform-style destruction logs. Returns collected logs."""
    collected_logs = []
    
    steps = [
        (0.05, "=" * 60),
        (0.05, "  TERRAFORM DESTROY - STARTING (TEST MODE)"),
        (0.05, "=" * 60),
        (0.10, ""),
        (0.10, "[STEP 1/2] Terraform destroy..."),
        (0.15, f"aws_lambda_function.{name}_dispatcher: Destroying..."),
        (0.15, f"aws_lambda_function.{name}_dispatcher: Destruction complete after 5s"),
        (0.10, f"aws_dynamodb_table.{name}_hot_storage: Destroying..."),
        (0.15, f"aws_dynamodb_table.{name}_hot_storage: Destruction complete after 10s"),
        (0.05, ""),
        (0.05, "Destroy complete! Resources: 15 destroyed."),
        (0.05, "=" * 60),
        (0.05, "  TERRAFORM DESTROY - COMPLETE"),
        (0.05, "=" * 60),
    ]
    
    total_fraction = sum(s[0] for s in steps)
    for fraction, msg in steps:
        if msg:
            logger.info(msg)
            print(msg, flush=True)
            collected_logs.append(msg)
        await asyncio.sleep(duration * fraction / total_fraction)
    
    if should_fail:
        error_msg = "Simulated destroy failure: Resource still in use"
        logger.error(f"✗ {error_msg}")
        print(f"✗ {error_msg}", flush=True)
        collected_logs.append(f"✗ {error_msg}")
        raise Exception(error_msg)
    
    return collected_logs
