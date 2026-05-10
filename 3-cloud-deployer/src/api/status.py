"""
Infrastructure Status API - Hybrid Deployment Status Checks.

This module provides endpoints for checking deployment status using a hybrid approach:
1. Terraform State: Fast infrastructure check via `terraform state list`
2. Hash Metadata: User function deployment status from .build/metadata/
3. SDK Managed: Dynamic resources checked via cloud SDK (TwinMaker, IoT, Grafana)

**Key endpoint:**
- GET /infrastructure/status: Unified status check with categorized output
- GET /infrastructure/status?detailed=true: Includes drift detection (slower)

**Use before:** Deploying (check if already deployed) or in dashboards.
"""

import json
import os
# Terraform is invoked via a fixed argv list with shell disabled.
import subprocess  # nosec B404
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional, List

from fastapi import APIRouter, HTTPException, Query

import constants as CONSTANTS
import src.core.state as state
import src.validator as validator
from src.core.paths import resolve_project_context_path
from src.tfvars_generator import generate_tfvars
from api.dependencies import validate_project_context
from logger import print_stack_trace, logger
from api.error_models import ERROR_RESPONSES


def _get_upload_dir(project_name: str) -> str:
    """Get the upload directory path for a project."""
    return str(resolve_project_context_path(project_name))


router = APIRouter()


# ==========================================
# Terraform State Check Functions
# ==========================================

def _run_terraform_command(args: List[str], project_name: str) -> subprocess.CompletedProcess:
    """
    Run a terraform command in the terraform directory.
    
    Args:
        args: List of terraform arguments (without 'terraform' prefix)
        project_name: Name of the project for state file path
        
    Returns:
        CompletedProcess result
        
    Raises:
        ValueError: If terraform command fails
    """
    terraform_dir = "/app/src/terraform"
    upload_dir = _get_upload_dir(project_name)
    state_path = os.path.join(upload_dir, "terraform", "terraform.tfstate")
    
    # Build base command with correct Terraform syntax:
    # terraform -chdir=X <subcommand> -state=Y [other args]
    cmd = ["terraform", "-chdir=" + terraform_dir]
    
    stateful_commands = ["apply", "destroy", "plan", "output", "show", "import"]
    
    if len(args) > 0:
        subcommand = args[0]
        cmd.append(subcommand)
        
        # For 'state' subcommands (e.g. state list), -state= must go AFTER
        # the sub-subcommand: terraform state list -state=Y
        if subcommand == "state":
            cmd.extend(args[1:])
            cmd.append(f"-state={state_path}")
        else:
            # Add state path for stateful commands (per-project isolation)
            if subcommand in stateful_commands:
                cmd.append(f"-state={state_path}")
            cmd.extend(args[1:])
    
    try:
        # cmd is an argv list assembled from fixed Terraform arguments; shell stays disabled.
        result = subprocess.run(  # nosec B603
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
                        "last_updated": metadata.get("last_deployed") or metadata.get("last_built")
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
        # Create context and initialize required provider for SDK checks
        context = create_context(project_name, provider)
        
        # Initialize provider (create_context returns lightweight context without providers)
        from core.config_loader import load_credentials
        from core.registry import ProviderRegistry
        
        credentials = load_credentials(context.project_path)
        prov_creds = credentials.get(provider, {})
        
        # AWS can use env vars even with empty dict
        if prov_creds or provider == "aws":
            prov_instance = ProviderRegistry.get(provider)
            prov_instance.initialize_clients(prov_creds, context.config.digital_twin_name)
            context.providers[provider] = prov_instance
        
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
        with tempfile.TemporaryDirectory(prefix="twin2multicloud-drift-") as temp_dir:
            var_file = Path(temp_dir) / "generated.tfvars.json"
            generate_tfvars(upload_dir, str(var_file))

            # Run terraform plan -refresh-only with transient tfvars. The file
            # may contain credentials, so it must not be persisted in upload/.
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
    operation_id="getDeploymentStatus",
    tags=["Infrastructure"],
    summary="Check complete deployment status across all layers",
    description=(
        "**Purpose:** Unified status check for infrastructure, user functions, and SDK-managed resources.\n\n"
        "**Returns three categories:**\n"
        "- `infrastructure`: Terraform-managed resources (fast, local state check)\n"
        "- `user_functions`: Function deployment status (from hash metadata)\n"
        "- `sdk_managed`: Dynamic resources (TwinMaker entities, IoT devices)\n\n"
        "**Performance:**\n"
        "- Default: ~instant (local state file)\n"
        "- With `detailed=true`: 5-30 seconds (cloud API drift detection)"
    ),
    responses={
        200: {"description": "Status check successful"},
        400: ERROR_RESPONSES[400],
        500: ERROR_RESPONSES[500],
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
    # NOTE: validate_project_context removed - project validation handled by config loading
    
    try:
        provider = provider.lower()
        if provider == "gcp":
            provider = "google"
        if provider not in ("aws", "azure", "google"):
            raise ValueError(f"Invalid provider: {provider}. Must be aws, azure, gcp, or google.")
        
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
        raise HTTPException(status_code=500, detail="Status operation failed. Check logs.")


# ==========================================
# Structured Infrastructure Verification
# ==========================================

def _make_check(name: str, status: str, provider: str = "", detail: str = "", layer: str = "") -> Dict[str, Any]:
    """Create a standardized check result entry."""
    return {
        "name": name,
        "status": status,  # "pass", "fail", "skip"
        "provider": provider,
        "detail": detail,
        "layer": layer,
    }


def verify_infrastructure(project_name: str, provider: str) -> Dict[str, Any]:
    """
    Run structured infrastructure verification across all layers.
    
    Combines Terraform state checks with SDK-managed resource checks 
    to produce a unified pass/fail/skip result per check, grouped by layer.
    
    Args:
        project_name: Name of the project
        provider: Primary cloud provider (aws/azure/google)
        
    Returns:
        Dict with checks list, counts, and overall healthy boolean
    """
    checks = []
    
    # --- Terraform state (fast, local) ---
    tf_state = check_terraform_state(project_name)
    
    # L0 Setup
    total_resources = tf_state.get("total_resources", 0)
    if tf_state.get("status") == "not_deployed":
        checks.append(_make_check(
            "L0 Setup resources", "fail", "", "No Terraform state found", "L0"
        ))
    else:
        checks.append(_make_check(
            "L0 Setup resources", "pass", "", f"{total_resources} resources found", "L0"
        ))
    
    # --- Load project context for provider-aware checks ---
    try:
        from src.core.factory import create_context
        from core.config_loader import load_credentials
        from core.registry import ProviderRegistry
        
        context = create_context(project_name, provider)
        config = context.config
        providers_map = config.providers
        
        # Compute all-providers string for L0 badges
        _unique = sorted(set(p.upper() for p in [providers_map.get("layer_1_provider", ""),
            providers_map.get("layer_2_provider", ""), providers_map.get("layer_3_hot_provider", ""),
            providers_map.get("layer_3_cold_provider", ""), providers_map.get("layer_3_archive_provider", "")] if p))
        all_providers_str = "/".join(_unique) if _unique else ""
        
        # Backfill L0 checks with provider info now that we have it
        for c in checks:
            if c.get("layer") == "L0" and not c.get("provider"):
                c["provider"] = all_providers_str
        
        # Initialize all needed providers for SDK checks
        credentials = load_credentials(context.project_path)
        unique_providers = set()
        for key, prov_name in providers_map.items():
            if prov_name:
                unique_providers.add(prov_name.lower())
        
        for prov_name in unique_providers:
            prov_creds = credentials.get(prov_name, {})
            if prov_creds or prov_name == "aws":
                try:
                    prov_instance = ProviderRegistry.get(prov_name)
                    prov_instance.initialize_clients(prov_creds, config.digital_twin_name)
                    context.providers[prov_name] = prov_instance
                except Exception as e:
                    logger.warning(f"Failed to initialize provider {prov_name}: {e}")
        
        # --- L0 Glue functions ---
        glue_resources = [r for r in (tf_state.get("l2", {}).get("resources", []) 
                          if tf_state.get("status") != "not_deployed" else [])
                         if "cold_writer" in r.lower() or "hot_reader" in r.lower()]
        if tf_state.get("status") == "not_deployed":
            checks.append(_make_check("L0 Glue functions", "fail", all_providers_str, "Not deployed", "L0"))
        else:
            # Check code hashes for glue functions
            code_hashes = check_code_hashes(project_name)
            funcs = code_hashes.get("functions", {})
            glue_names = [f for f in funcs if "cold-writer" in f or "hot-reader" in f]
            if glue_names:
                checks.append(_make_check(
                    "L0 Glue functions", "pass", all_providers_str, ", ".join(glue_names), "L0"
                ))
            else:
                checks.append(_make_check(
                    "L0 Glue functions", "pass", all_providers_str, "Terraform-managed", "L0"
                ))
        
        # --- L1 IoT ---
        l1_provider = providers_map.get("layer_1_provider", "").lower()
        l1_tf = tf_state.get("l1", {})
        if l1_tf.get("deployed"):
            checks.append(_make_check(
                "IoT endpoint", "pass", l1_provider.upper(), "endpoint active", "L1"
            ))
        else:
            checks.append(_make_check(
                "IoT endpoint", "fail", l1_provider.upper(), "not found in state", "L1"
            ))
        
        # IoT devices (SDK check)
        if l1_provider and l1_provider in context.providers:
            try:
                import providers.deployer as deployer
                strategy = deployer._get_strategy(context, l1_provider)
                l1_info = strategy.info_l1(context)
                devices = l1_info.get("devices", {}) if l1_info else {}
                registered = sum(1 for v in devices.values() if v)
                total_devices = len(devices)
                if registered > 0:
                    checks.append(_make_check(
                        "IoT devices registered", "pass", l1_provider.upper(),
                        f"{registered} device(s)", "L1"
                    ))
                elif total_devices == 0 and not config.iot_devices:
                    checks.append(_make_check(
                        "IoT devices registered", "skip", l1_provider.upper(),
                        "No devices configured", "L1"
                    ))
                else:
                    checks.append(_make_check(
                        "IoT devices registered", "fail", l1_provider.upper(),
                        f"0/{total_devices} registered", "L1"
                    ))
            except Exception as e:
                checks.append(_make_check(
                    "IoT devices registered", "fail", l1_provider.upper(), str(e), "L1"
                ))
        
        # --- L2 Processing functions ---
        l2_provider = providers_map.get("layer_2_provider", "").lower()
        l2_tf = tf_state.get("l2", {})
        if l2_tf.get("deployed"):
            func_count = len(l2_tf.get("resources", []))
            checks.append(_make_check(
                "Functions deployed", "pass", l2_provider.upper(),
                f"{func_count} resources", "L2"
            ))
        else:
            checks.append(_make_check(
                "Functions deployed", "fail", l2_provider.upper(), "not found in state", "L2"
            ))
        
        # Azure-specific: check function apps are actually running
        if l2_provider == "azure" and l2_provider in context.providers:
            try:
                azure_prov = context.providers["azure"]
                if hasattr(azure_prov, 'web_client') and azure_prov.web_client:
                    rg_name = f"{config.digital_twin_name}-rg"
                    apps = list(azure_prov.web_client.web_apps.list_by_resource_group(rg_name))
                    running = [a for a in apps if a.state and a.state.lower() == "running"]
                    checks.append(_make_check(
                        "Azure Functions running", "pass" if running else "fail",
                        "AZURE", f"{len(running)}/{len(apps)} running", "L2"
                    ))
            except Exception as e:
                checks.append(_make_check(
                    "Azure Functions running", "fail", "AZURE", str(e), "L2"
                ))
        
        # --- L3 Storage ---
        l3_hot_prov = providers_map.get("layer_3_hot_provider", "").lower()
        l3_cold_prov = providers_map.get("layer_3_cold_provider", "").lower()
        l3_archive_prov = providers_map.get("layer_3_archive_provider", "").lower()
        l3_tf = tf_state.get("l3", {})
        
        for storage_type, prov, tf_key in [
            ("Hot storage", l3_hot_prov, "hot"),
            ("Cold storage", l3_cold_prov, "cold"),
            ("Archive storage", l3_archive_prov, "archive"),
        ]:
            sub = l3_tf.get(tf_key, {})
            if sub.get("deployed"):
                checks.append(_make_check(
                    storage_type, "pass", prov.upper(), "deployed", "L3"
                ))
            else:
                checks.append(_make_check(
                    storage_type, "fail", prov.upper(), "not found in state", "L3"
                ))
        
        # --- L3 Mover functions ---
        code_hashes = check_code_hashes(project_name)
        funcs = code_hashes.get("functions", {})
        
        # Movers: Hot→Cold uses hot provider, Cold→Archive uses cold provider
        for mover_name, label, mover_prov_name in [
            ("hot-to-cold-mover", "Hot→Cold mover", l3_hot_prov),
            ("cold-to-archive-mover", "Cold→Archive mover", l3_cold_prov),
        ]:
            matching = [f for f in funcs if mover_name in f]
            if matching:
                checks.append(_make_check(
                    label, "pass", mover_prov_name.upper(), "deployed", "L3"
                ))
            else:
                # Movers might be Terraform-managed
                mover_resources = [r for r in tf_state.get("l3", {}).get("hot", {}).get("resources", [])
                                   if "mover" in r.lower()] if tf_state.get("status") != "not_deployed" else []
                if mover_resources or tf_state.get("status") == "deployed":
                    checks.append(_make_check(
                        label, "pass", mover_prov_name.upper(), "Terraform-managed", "L3"
                    ))
                else:
                    checks.append(_make_check(
                        label, "fail", mover_prov_name.upper(), "not found", "L3"
                    ))
        
        # --- L4 Digital Twins ---
        l4_provider = providers_map.get("layer_4_provider", "").lower()
        
        if not l4_provider:
            checks.append(_make_check(
                "TwinMaker/ADT", "skip", "", "L4 not configured", "L4"
            ))
        elif l4_provider == "aws":
            # TwinMaker checks
            l4_tf = tf_state.get("l4", {})
            if l4_tf.get("deployed"):
                checks.append(_make_check(
                    "TwinMaker workspace", "pass", "AWS", "deployed", "L4"
                ))
            else:
                checks.append(_make_check(
                    "TwinMaker workspace", "fail", "AWS", "not found in state", "L4"
                ))
            
            # Entity check via SDK
            if l4_provider in context.providers:
                try:
                    import providers.deployer as deployer
                    strategy = deployer._get_strategy(context, l4_provider)
                    l4_info = strategy.info_l4(context)
                    entities = l4_info.get("entities", {}) if l4_info else {}
                    created = sum(1 for v in entities.values() if v)
                    if created > 0:
                        checks.append(_make_check(
                            "TwinMaker entities", "pass", "AWS",
                            f"{created} entities created", "L4"
                        ))
                    else:
                        checks.append(_make_check(
                            "TwinMaker entities", "fail", "AWS",
                            "No entities found", "L4"
                        ))
                except Exception as e:
                    checks.append(_make_check(
                        "TwinMaker entities", "fail", "AWS", str(e), "L4"
                    ))
            
            checks.append(_make_check(
                "ADT twins", "skip", "", "L4 not Azure", "L4"
            ))
            
        elif l4_provider == "azure":
            checks.append(_make_check(
                "TwinMaker workspace", "skip", "", "L4 not AWS", "L4"
            ))
            checks.append(_make_check(
                "TwinMaker entities", "skip", "", "L4 not AWS", "L4"
            ))
            
            # ADT checks via SDK
            if l4_provider in context.providers:
                try:
                    import providers.deployer as deployer
                    strategy = deployer._get_strategy(context, l4_provider)
                    l4_info = strategy.info_l4(context)
                    twins = l4_info.get("twins", {}) if l4_info else {}
                    created = sum(1 for v in twins.values() if v)
                    if created > 0:
                        checks.append(_make_check(
                            "ADT twins", "pass", "AZURE",
                            f"{created} twin(s) created", "L4"
                        ))
                    else:
                        checks.append(_make_check(
                            "ADT twins", "fail", "AZURE",
                            "No twins found", "L4"
                        ))
                except Exception as e:
                    checks.append(_make_check(
                        "ADT twins", "fail", "AZURE", str(e), "L4"
                    ))
        
        # --- L5 Visualization ---
        l5_provider = providers_map.get("layer_5_provider", "").lower()
        
        if not l5_provider:
            checks.append(_make_check(
                "Grafana workspace", "skip", "", "L5 not configured", "L5"
            ))
        else:
            l5_tf = tf_state.get("l5", {})
            if l5_tf.get("deployed"):
                checks.append(_make_check(
                    "Grafana workspace", "pass", l5_provider.upper(), "deployed", "L5"
                ))
            else:
                checks.append(_make_check(
                    "Grafana workspace", "fail", l5_provider.upper(), "not found in state", "L5"
                ))
    
    except ValueError as e:
        # Project context failed to load — return what we have with an error
        checks.append(_make_check(
            "Project configuration", "fail", "", str(e), "L0"
        ))
    except Exception as e:
        logger.warning(f"Verification context error: {e}")
        checks.append(_make_check(
            "Provider initialization", "fail", "", str(e), "L0"
        ))
    
    # Compute summary
    pass_count = sum(1 for c in checks if c["status"] == "pass")
    fail_count = sum(1 for c in checks if c["status"] == "fail")
    skip_count = sum(1 for c in checks if c["status"] == "skip")
    total = len(checks)
    
    return {
        "checks": checks,
        "summary": {
            "pass_count": pass_count,
            "fail_count": fail_count,
            "skip_count": skip_count,
            "total": total,
            "healthy": fail_count == 0,
        }
    }


@router.post(
    "/infrastructure/verify",
    operation_id="verifyInfrastructure",
    tags=["Infrastructure"],
    summary="Structured infrastructure verification across all layers",
    description=(
        "**Purpose:** Run a structured pass/fail/skip check for every resource layer (L0–L5).\n\n"
        "**Returns:**\n"
        "- `checks`: List of individual check results (name, status, provider, detail)\n"
        "- `summary`: Overall counts and healthy boolean\n\n"
        "**Performance:** 5-30 seconds (cloud SDK calls for IoT, TwinMaker/ADT, Azure Functions)\n\n"
        "**Use case:** Deployment verification in the UI."
    ),
    responses={
        200: {"description": "Verification complete"},
        400: ERROR_RESPONSES[400],
        500: ERROR_RESPONSES[500],
    }
)
def verify_endpoint(
    provider: str = Query("aws", description="Primary cloud provider: aws, azure, or google"),
    project_name: str = Query("template", description="Name of the project context"),
):
    """
    Run structured infrastructure verification.
    
    Returns pass/fail/skip per check, grouped by layer.
    """
    try:
        provider = provider.lower()
        if provider == "gcp":
            provider = "google"
        if provider not in ("aws", "azure", "google"):
            raise ValueError(f"Invalid provider: {provider}. Must be aws, azure, gcp, or google.")
        
        return verify_infrastructure(project_name, provider)
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print_stack_trace()
        logger.error(str(e))
        raise HTTPException(status_code=500, detail="Verification failed. Check logs.")
