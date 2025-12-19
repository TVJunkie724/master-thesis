"""
Infrastructure Status API - Hybrid Deployment Status Checks.

This module provides endpoints for checking deployment status using a hybrid approach:
1. Terraform State: Fast infrastructure check via `terraform state list`
2. Hash Metadata: User function deployment status from .build/metadata/
3. SDK Managed: Dynamic resources checked via cloud SDK (TwinMaker, IoT, Grafana)

Endpoints:
- GET /infrastructure/status: Unified status check with categorized output
- GET /infrastructure/status?detailed=true: Includes terraform plan -refresh-only for drift detection

Architecture:
    Infrastructure (Terraform State) + User Functions (Hash Metadata) + SDK Managed (API Calls)
"""

import json
import os
import subprocess
from typing import Dict, Any, Optional, List

from fastapi import APIRouter, HTTPException, Query

import constants as CONSTANTS
import src.core.state as state
import src.validator as validator
from api.dependencies import validate_project_context
from logger import print_stack_trace, logger


def _get_upload_dir(project_name: str) -> str:
    """Get the upload directory path for a project."""
    return os.path.join(state.get_project_base_path(), CONSTANTS.PROJECT_UPLOAD_DIR_NAME, project_name)


router = APIRouter()


# ==========================================
# Terraform State Check Functions
# ==========================================

def _run_terraform_command(args: List[str], project_name: str) -> subprocess.CompletedProcess:
    """
    Run a terraform command in the terraform directory.
    
    Args:
        args: List of terraform arguments (without 'terraform' prefix)
        project_name: Name of the project for var-file
        
    Returns:
        CompletedProcess result
        
    Raises:
        ValueError: If terraform command fails
    """
    terraform_dir = "/app/src/terraform"
    
    cmd = ["terraform", "-chdir=" + terraform_dir] + args
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60
        )
        return result
    except subprocess.TimeoutExpired:
        raise ValueError("Terraform command timed out")
    except Exception as e:
        raise ValueError(f"Terraform command failed: {e}")


def check_terraform_state(project_name: str) -> Dict[str, Any]:
    """
    Check infrastructure status via terraform state list.
    
    Fast check that reads local state file without cloud API calls.
    
    Args:
        project_name: Name of the project
        
    Returns:
        Dict with layer deployment status
    """
    try:
        result = _run_terraform_command(["state", "list"], project_name)
        
        if result.returncode != 0:
            # State might not exist yet (no deployment)
            if "No state file was found" in result.stderr or "does not exist" in result.stderr:
                return {
                    "status": "not_deployed",
                    "l1": {"deployed": False},
                    "l2": {"deployed": False},
                    "l3": {"hot": {"deployed": False}, "cold": {"deployed": False}, "archive": {"deployed": False}},
                    "l4": {"deployed": False},
                    "l5": {"deployed": False}
                }
            logger.warning(f"Terraform state list warning: {result.stderr}")
        
        resources = result.stdout.strip().split("\n") if result.stdout.strip() else []
        
        # Categorize resources by layer based on naming patterns
        return {
            "status": "deployed" if resources else "not_deployed",
            "l1": {
                "deployed": any("l1_" in r or "dispatcher" in r or "iot_hub" in r.lower() for r in resources),
                "resources": [r for r in resources if "l1_" in r or "dispatcher" in r]
            },
            "l2": {
                "deployed": any("l2_" in r or "persister" in r or "processor" in r for r in resources),
                "resources": [r for r in resources if "l2_" in r or "persister" in r]
            },
            "l3": {
                "hot": {
                    "deployed": any("l3_hot" in r or "hot_" in r or "dynamodb" in r.lower() or "cosmos" in r.lower() for r in resources),
                    "resources": [r for r in resources if "hot" in r.lower()]
                },
                "cold": {
                    "deployed": any("l3_cold" in r or "cold_" in r for r in resources),
                    "resources": [r for r in resources if "cold" in r.lower()]
                },
                "archive": {
                    "deployed": any("l3_archive" in r or "archive_" in r or "glacier" in r.lower() for r in resources),
                    "resources": [r for r in resources if "archive" in r.lower()]
                }
            },
            "l4": {
                "deployed": any("l4_" in r or "twinmaker" in r.lower() or "digital_twin" in r.lower() for r in resources),
                "resources": [r for r in resources if "l4_" in r or "twin" in r.lower()]
            },
            "l5": {
                "deployed": any("l5_" in r or "grafana" in r.lower() for r in resources),
                "resources": [r for r in resources if "l5_" in r or "grafana" in r.lower()]
            },
            "total_resources": len(resources)
        }
    except Exception as e:
        logger.warning(f"Terraform state check failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "l1": {"deployed": False},
            "l2": {"deployed": False},
            "l3": {"hot": {"deployed": False}, "cold": {"deployed": False}, "archive": {"deployed": False}},
            "l4": {"deployed": False},
            "l5": {"deployed": False}
        }


# ==========================================
# Hash Metadata Check Functions
# ==========================================

def check_code_hashes(project_name: str) -> Dict[str, Any]:
    """
    Check user function deployment status from hash metadata files.
    
    Reads .build/metadata/*.json to determine which functions have been deployed.
    
    Args:
        project_name: Name of the project
        
    Returns:
        Dict mapping function names to deployment status
    """
    upload_dir = _get_upload_dir(project_name)
    metadata_dir = os.path.join(upload_dir, ".build", "metadata")
    
    if not os.path.exists(metadata_dir):
        return {
            "status": "no_deployments",
            "functions": {}
        }
    
    functions = {}
    
    for filename in os.listdir(metadata_dir):
        if filename.endswith(".json"):
            filepath = os.path.join(metadata_dir, filename)
            try:
                with open(filepath, 'r') as f:
                    metadata = json.load(f)
                    func_name = metadata.get("function", filename.replace(".json", ""))
                    functions[func_name] = {
                        "deployed": True,
                        "provider": metadata.get("provider"),
                        "hash": metadata.get("zip_hash"),
                        "last_updated": metadata.get("last_deployed")
                    }
            except Exception as e:
                logger.warning(f"Failed to read hash metadata {filename}: {e}")
    
    return {
        "status": "deployed" if functions else "no_deployments",
        "functions": functions
    }


# ==========================================
# SDK Managed Resources Check
# ==========================================

def check_sdk_managed(project_name: str, provider: str) -> Dict[str, Any]:
    """
    Check SDK-managed dynamic resources.
    
    Uses existing info functions from deployer strategies to verify:
    - TwinMaker entities/components (AWS) or Digital Twin instances (Azure)
    - IoT devices registration status
    - Grafana workspace status
    
    Args:
        project_name: Name of the project
        provider: Cloud provider (aws/azure)
        
    Returns:
        Dict with SDK-managed resource status
    """
    from src.core.factory import create_context
    import providers.deployer as deployer
    
    result = {
        "status": "checking",
        "provider": provider,
        "twin_management": {"status": "unknown"},
        "iot_devices": {"status": "unknown"},
        "visualization": {"status": "unknown"}
    }
    
    try:
        # Create context to access provider strategies
        context = create_context(project_name, provider)
        strategy = deployer._get_strategy(context, provider)
        
        # Check L4 (TwinMaker/ADT) status
        try:
            l4_info = strategy.info_l4(context)
            if l4_info:
                result["twin_management"] = {
                    "status": "deployed",
                    "details": l4_info if isinstance(l4_info, dict) else {"checked": True}
                }
            else:
                result["twin_management"] = {"status": "not_deployed"}
        except Exception as e:
            result["twin_management"] = {"status": "error", "message": str(e)}
        
        # Check L1 (IoT) status
        try:
            l1_info = strategy.info_l1(context)
            if l1_info:
                result["iot_devices"] = {
                    "status": "deployed",
                    "details": l1_info if isinstance(l1_info, dict) else {"checked": True}
                }
            else:
                result["iot_devices"] = {"status": "not_deployed"}
        except Exception as e:
            result["iot_devices"] = {"status": "error", "message": str(e)}
        
        # Check L5 (Grafana) status
        try:
            l5_info = strategy.info_l5(context)
            if l5_info:
                result["visualization"] = {
                    "status": "deployed",
                    "details": l5_info if isinstance(l5_info, dict) else {"checked": True}
                }
            else:
                result["visualization"] = {"status": "not_deployed"}
        except Exception as e:
            result["visualization"] = {"status": "error", "message": str(e)}
        
        # Compute overall status
        statuses = [
            result["twin_management"].get("status"),
            result["iot_devices"].get("status"),
            result["visualization"].get("status")
        ]
        
        if all(s == "deployed" for s in statuses):
            result["status"] = "all_deployed"
        elif any(s == "deployed" for s in statuses):
            result["status"] = "partial"
        elif any(s == "error" for s in statuses):
            result["status"] = "error"
        else:
            result["status"] = "not_deployed"
            
    except ValueError as e:
        # Project or provider not found
        result["status"] = "error"
        result["message"] = str(e)
    except Exception as e:
        result["status"] = "error"
        result["message"] = f"Failed to check SDK resources: {e}"
    
    return result


# ==========================================
# Detailed Drift Detection
# ==========================================

def check_terraform_drift(project_name: str) -> Dict[str, Any]:
    """
    Detect configuration drift using terraform plan -refresh-only.
    
    This makes actual cloud API calls to compare state with real resources.
    More expensive but detects manually deleted/modified resources.
    
    Args:
        project_name: Name of the project
        
    Returns:
        Dict with drift detection results
    """
    try:
        upload_dir = _get_upload_dir(project_name)
        var_file = os.path.join(upload_dir, "terraform", "generated.tfvars.json")
        
        if not os.path.exists(var_file):
            return {
                "status": "no_var_file",
                "error": "No generated.tfvars.json found - run deployment first"
            }
        
        # Run terraform plan -refresh-only
        result = _run_terraform_command([
            "plan",
            "-refresh-only",
            "-detailed-exitcode",
            f"-var-file={var_file}"
        ], project_name)
        
        # Exit codes: 0 = no changes, 1 = error, 2 = changes detected
        if result.returncode == 0:
            return {
                "status": "no_drift",
                "message": "Infrastructure matches Terraform state"
            }
        elif result.returncode == 2:
            return {
                "status": "drift_detected",
                "message": "Infrastructure has drifted from Terraform state",
                "details": result.stdout
            }
        else:
            return {
                "status": "error",
                "error": result.stderr or result.stdout
            }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


# ==========================================
# API Endpoints
# ==========================================

@router.get(
    "/infrastructure/status", 
    tags=["Infrastructure"],
    summary="Check deployment status",
    responses={
        200: {"description": "Status check successful"},
        400: {"description": "Invalid project or provider"}
    }
)
def check_endpoint(
    provider: str = Query("aws", description="Cloud provider: aws, azure, or google"),
    project_name: str = Query("template", description="Name of the project context"),
    detailed: bool = Query(False, description="Include drift detection (slower, makes cloud API calls)")
):
    """
    Unified infrastructure and deployment status check.
    
    **Returns three categories of status:**
    1. **infrastructure**: Terraform-managed resources (fast, local state check)
    2. **user_functions**: User function deployment status (from hash metadata)
    3. **sdk_managed**: Dynamic resources (TwinMaker entities, IoT devices)
    
    **Performance:**
    - Default: ~instant (reads local terraform state file)
    - With `detailed=true`: 5-30 seconds (makes cloud API calls for drift detection)
    
    **Use case:** Dashboard status display, pre-deploy checks.
    """
    validate_project_context(project_name)
    
    try:
        provider = provider.lower()
        if provider not in ("aws", "azure", "google"):
            raise ValueError(f"Invalid provider: {provider}. Must be aws, azure, or google.")
        
        # 1. Check Terraform state (fast, local)
        infrastructure = check_terraform_state(project_name)
        
        # 2. Check user function hashes (fast, local)
        user_functions = check_code_hashes(project_name)
        
        # 3. Check SDK-managed resources (placeholder)
        sdk_managed = check_sdk_managed(project_name, provider)
        
        result = {
            "project": project_name,
            "provider": provider,
            "infrastructure": infrastructure,
            "user_functions": user_functions,
            "sdk_managed": sdk_managed
        }
        
        # 4. Optional drift detection (slow, cloud API calls)
        if detailed:
            result["drift_detection"] = check_terraform_drift(project_name)
        
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print_stack_trace()
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))

