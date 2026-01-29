# src/services/deployment_service.py
"""
Deployment services extracted from twins.py route handlers.

This module provides:
- Real deployment streaming functions (subscribe to Deployer SSE)
- Build deployment config helper
- Shared constants and error handling

These functions were previously embedded in twins.py but are now
centralized for reusability and maintainability.
"""

import json
import httpx
from datetime import datetime

from src.config import settings

# Deployer API URL from settings
DEPLOYER_API_URL = getattr(settings, 'DEPLOYER_URL', 'http://3cloud-deployer:8000')


def build_deploy_config(twin) -> dict:
    """
    Build the config.json payload from saved configurations.
    
    Combines:
    - OptimizerConfiguration (layer providers, parameters)
    - DeployerConfiguration (config files, user functions)
    
    Args:
        twin: DigitalTwin model instance with related configs
        
    Returns:
        dict: Configuration payload ready for Deployer API
    """
    config = {
        "resource_name": twin.name.lower().replace(" ", "-"),
        "twin_id": twin.id,
    }
    
    # Add from deployer config
    if twin.deployer_config:
        dc = twin.deployer_config
        config["resource_name"] = dc.deployer_digital_twin_name or config["resource_name"]
        
        # Parse JSON fields
        if dc.config_events_json:
            config["config_events"] = json.loads(dc.config_events_json)
        if dc.config_iot_devices_json:
            config["config_iot_devices"] = json.loads(dc.config_iot_devices_json)
        if dc.payloads_json:
            config["payloads"] = json.loads(dc.payloads_json)
        if dc.state_machine_content:
            config["state_machine"] = dc.state_machine_content
        if dc.hierarchy_content:
            config["hierarchy"] = dc.hierarchy_content
        if dc.scene_config_content:
            config["scene_config"] = dc.scene_config_content
        if dc.user_config_content:
            config["user_config"] = dc.user_config_content
        
        # User functions
        if dc.processor_contents:
            config["processors"] = json.loads(dc.processor_contents)
        if dc.event_feedback_content:
            config["event_feedback"] = dc.event_feedback_content
        if dc.event_action_contents:
            config["event_actions"] = json.loads(dc.event_action_contents)
    
    # Add from optimizer config
    if twin.optimizer_config:
        oc = twin.optimizer_config
        config["layers"] = {
            "l1": oc.cheapest_l1,
            "l2": oc.cheapest_l2,
            "l3_hot": oc.cheapest_l3_hot,
            "l3_cool": oc.cheapest_l3_cool,
            "l3_archive": oc.cheapest_l3_archive,
            "l4": oc.cheapest_l4,
            "l5": oc.cheapest_l5,
        }
        if oc.result_json:
            config["optimizer_result"] = json.loads(oc.result_json)
    
    return config


async def run_real_deploy_stream(
    session_id: str,
    twin_id: str,
    resource_name: str,
    provider: str
):
    """
    Background task that subscribes to Deployer SSE and forwards logs.
    Updates Deployment record on completion.
    
    Args:
        session_id: SSE session ID for pushing logs to client
        twin_id: ID of the twin being deployed
        resource_name: Deployer project/resource name
        provider: Cloud provider (aws, azure, gcp)
    """
    # Late imports to avoid circular dependencies
    from src.api.routes.sse import get_session
    from src.models.database import SessionLocal
    from src.models.twin import DigitalTwin, TwinState
    from src.models.deployment import Deployment
    
    session = await get_session(session_id)
    if not session:
        return
    
    # Create Deployment record at start
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
    
    terraform_outputs = {}
    
    try:
        # Subscribe to Deployer SSE with long timeouts
        timeout = httpx.Timeout(connect=30.0, read=None, write=30.0, pool=30.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST",
                f"{DEPLOYER_API_URL}/infrastructure/deploy/stream",
                params={"provider": provider, "project_name": resource_name}
            ) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        msg = line[6:]  # Remove "data: " prefix
                        print(msg, flush=True)  # Container logs
                        await session.push_log(msg)
                    elif line.startswith("event: complete"):
                        # Next line contains JSON
                        pass
                    elif line.startswith('{"success":'):
                        # Parse completion event
                        try:
                            result = json.loads(line)
                            if result.get("success"):
                                terraform_outputs = result.get("outputs", {})
                        except json.JSONDecodeError:
                            pass
        
        # Success path
        db = SessionLocal()
        try:
            twin = db.query(DigitalTwin).get(twin_id)
            if twin:
                twin.state = TwinState.DEPLOYED
                twin.deployed_at = datetime.utcnow()
                db.commit()
            
            # Update Deployment record
            deployment = db.query(Deployment).filter(Deployment.session_id == session_id).first()
            if deployment:
                deployment.status = "success"
                deployment.terraform_outputs = terraform_outputs
                deployment.completed_at = datetime.utcnow()
                db.commit()
        finally:
            db.close()
        
        session.on_complete(success=True, message="Deployment complete", outputs=terraform_outputs)
        
    except Exception as e:
        # Error path
        db = SessionLocal()
        try:
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
        finally:
            db.close()
        
        await session.push_log(f"✗ Deployment error: {e}", level="error")
        session.on_complete(success=False, message=str(e))


async def run_real_destroy_stream(
    session_id: str,
    twin_id: str,
    resource_name: str,
    provider: str
):
    """
    Background task that subscribes to Deployer destroy SSE and forwards logs.
    
    Args:
        session_id: SSE session ID for pushing logs to client
        twin_id: ID of the twin being destroyed
        resource_name: Deployer project/resource name
        provider: Cloud provider (aws, azure, gcp)
    """
    # Late imports to avoid circular dependencies
    from src.api.routes.sse import get_session
    from src.models.database import SessionLocal
    from src.models.twin import DigitalTwin, TwinState
    from src.models.deployment import Deployment
    
    session = await get_session(session_id)
    if not session:
        return
    
    # Create Deployment record at start
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
        # Subscribe to Deployer destroy SSE
        timeout = httpx.Timeout(connect=30.0, read=None, write=30.0, pool=30.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST",
                f"{DEPLOYER_API_URL}/infrastructure/destroy/stream",
                params={"provider": provider, "project_name": resource_name}
            ) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        msg = line[6:]
                        print(msg, flush=True)
                        await session.push_log(msg)
        
        # Success path
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
        
        session.on_complete(success=True, message="Destruction complete")
        
    except Exception as e:
        db = SessionLocal()
        try:
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
        finally:
            db.close()
        
        await session.push_log(f"✗ Destroy error: {e}", level="error")
        session.on_complete(success=False, message=str(e))
