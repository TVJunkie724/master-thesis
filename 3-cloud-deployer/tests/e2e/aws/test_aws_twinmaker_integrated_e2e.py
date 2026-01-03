"""
AWS TwinMaker (L4) Integrated E2E Test.

This test combines Terraform deployment with SDK post-deployment operations
to verify the complete TwinMaker deployment flow:

1. Terraform deployment (aws_twinmaker_test/main.tf):
   - TwinMaker Workspace creation
   - S3 bucket for scenes and workspace data
   - GLB file upload
   - scene.json configuration upload
   - TwinMaker Scene creation
   - IAM roles and permissions

2. SDK post-deployment (layer_4_twinmaker.py patterns):
   - Component Type creation
   - Entity creation from aws_hierarchy.json

IMPORTANT: Run this test via the helper script for full output capture:
    python tests/e2e/run_e2e_test.py aws-twinmaker-full

Estimated duration: 3-5 minutes
Estimated cost: ~$0.05 USD
"""
import pytest
import subprocess
import json
import os
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, Any, Optional
import time

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src")))

# Configure logging
import logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')


# Directory containing the focused Terraform config
TERRAFORM_DIR = Path(__file__).parent.parent / "aws_twinmaker_test"

# Path to scene assets (template)
SCENE_ASSETS_PATH = Path(__file__).parent.parent.parent.parent / "upload" / "template" / "scene_assets"


def _cleanup_twinmaker_resources_sdk(credentials: dict, workspace_id: str) -> None:
    """
    SDK cleanup of AWS TwinMaker resources.
    
    This is a fallback cleanup that runs after terraform destroy to catch
    any orphaned resources that weren't tracked in Terraform state.
    
    AWS TwinMaker cleanup order (required due to dependencies):
    1. Delete all entities
    2. Delete all component types
    3. Delete workspace
    4. Empty and delete S3 bucket
    
    Args:
        credentials: Dict with AWS credentials
        workspace_id: The TwinMaker workspace ID to clean up
    """
    import boto3
    from botocore.exceptions import ClientError
    
    aws_creds = credentials.get("aws", {})
    
    # Create clients
    twinmaker = boto3.client(
        'iottwinmaker',
        region_name=aws_creds.get("aws_region", "eu-west-1"),
        aws_access_key_id=aws_creds["aws_access_key_id"],
        aws_secret_access_key=aws_creds["aws_secret_access_key"]
    )
    
    s3 = boto3.client(
        's3',
        region_name=aws_creds.get("aws_region", "eu-west-1"),
        aws_access_key_id=aws_creds["aws_access_key_id"],
        aws_secret_access_key=aws_creds["aws_secret_access_key"]
    )
    
    print(f"    [AWS SDK] Fallback cleanup for workspace: {workspace_id}")
    
    # Step 1: Check if workspace exists
    try:
        workspace = twinmaker.get_workspace(workspaceId=workspace_id)
        s3_bucket = workspace.get('s3Location', '').replace('arn:aws:s3:::', '')
        print(f"      Found workspace: {workspace_id}")
        print(f"      S3 bucket: {s3_bucket}")
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            print(f"      Workspace does not exist: {workspace_id}")
            return
        raise
    
    # Step 2: Delete all entities (recursive for hierarchical entities)
    print(f"    [1/4] Deleting entities...")
    try:
        paginator = twinmaker.get_paginator('list_entities')
        entity_count = 0
        for page in paginator.paginate(workspaceId=workspace_id):
            for entity in page.get('entitySummaries', []):
                entity_id = entity['entityId']
                try:
                    twinmaker.delete_entity(
                        workspaceId=workspace_id,
                        entityId=entity_id,
                        isRecursive=True
                    )
                    entity_count += 1
                    print(f"        Deleted entity: {entity_id}")
                except ClientError as e:
                    if e.response['Error']['Code'] != 'ResourceNotFoundException':
                        print(f"        Failed to delete entity {entity_id}: {e}")
        print(f"      ✓ Deleted {entity_count} entities")
    except ClientError as e:
        print(f"      Error listing entities: {e}")
    
    # Step 3: Delete all component types (skip AWS built-ins)
    print(f"    [2/4] Deleting component types...")
    try:
        paginator = twinmaker.get_paginator('list_component_types')
        ct_count = 0
        for page in paginator.paginate(workspaceId=workspace_id):
            for ct in page.get('componentTypeSummaries', []):
                ct_id = ct['componentTypeId']
                # Skip AWS built-in component types
                if ct_id.startswith('com.amazon.'):
                    continue
                try:
                    twinmaker.delete_component_type(
                        workspaceId=workspace_id,
                        componentTypeId=ct_id
                    )
                    ct_count += 1
                    print(f"        Deleted component type: {ct_id}")
                except ClientError as e:
                    if e.response['Error']['Code'] != 'ResourceNotFoundException':
                        print(f"        Failed to delete component type {ct_id}: {e}")
        print(f"      ✓ Deleted {ct_count} component types")
    except ClientError as e:
        print(f"      Error listing component types: {e}")
    
    # Step 4: Delete scenes
    print(f"    [3/4] Deleting scenes...")
    try:
        paginator = twinmaker.get_paginator('list_scenes')
        scene_count = 0
        for page in paginator.paginate(workspaceId=workspace_id):
            for scene in page.get('sceneSummaries', []):
                scene_id = scene['sceneId']
                try:
                    twinmaker.delete_scene(
                        workspaceId=workspace_id,
                        sceneId=scene_id
                    )
                    scene_count += 1
                    print(f"        Deleted scene: {scene_id}")
                except ClientError as e:
                    if e.response['Error']['Code'] != 'ResourceNotFoundException':
                        print(f"        Failed to delete scene {scene_id}: {e}")
        print(f"      ✓ Deleted {scene_count} scenes")
    except ClientError as e:
        print(f"      Error listing scenes: {e}")
    
    # Step 5: Delete workspace
    print(f"    [4/4] Deleting workspace...")
    try:
        twinmaker.delete_workspace(workspaceId=workspace_id)
        print(f"      ✓ Workspace deleted: {workspace_id}")
    except ClientError as e:
        print(f"      ✗ Failed to delete workspace: {e}")
    
    # Step 6: Empty and delete S3 bucket (if exists)
    if s3_bucket:
        print(f"    [Cleanup] Emptying S3 bucket: {s3_bucket}...")
        try:
            # Delete all objects
            paginator = s3.get_paginator('list_objects_v2')
            for page in paginator.paginate(Bucket=s3_bucket):
                objects = page.get('Contents', [])
                if objects:
                    delete_keys = [{'Key': obj['Key']} for obj in objects]
                    s3.delete_objects(
                        Bucket=s3_bucket,
                        Delete={'Objects': delete_keys}
                    )
                    print(f"        Deleted {len(objects)} objects")
            
            # Delete bucket
            s3.delete_bucket(Bucket=s3_bucket)
            print(f"      ✓ S3 bucket deleted: {s3_bucket}")
        except ClientError as e:
            print(f"      ✗ Failed to delete S3 bucket: {e}")
    
    print(f"    [AWS SDK] Fallback cleanup complete")


@dataclass
class MockConfig:
    """Mock config object for SDK operations."""
    digital_twin_name: str
    hierarchy: Dict[str, Any]


@pytest.mark.live
class TestAwsTwinmakerIntegratedE2E:
    """
    Integrated E2E test for AWS TwinMaker (L4) deployment.
    
    Tests the complete deployment flow:
    1. Terraform infrastructure (TwinMaker + S3 + Scenes)
    2. SDK operations (Component Types + Entities)
    3. Verification of all resources
    """
    
    @pytest.fixture(scope="class")
    def deployed_environment(self, request, aws_twinmaker_e2e_project_path, aws_credentials):
        """
        Deploy TwinMaker via Terraform + SDK operations with cleanup.
        
        Uses the focused terraform config (aws_twinmaker_test/main.tf) for infrastructure,
        then calls SDK operations to create component types and entities.
        """
        # Create a dedicated debug log file that bypasses pytest capture
        debug_log_path = TERRAFORM_DIR / "sdk_debug.log"
        debug_log = open(debug_log_path, "w")
        def debug(msg):
            """Write to debug log AND stdout."""
            print(msg)
            debug_log.write(msg + "\\n")
            debug_log.flush()
        
        debug("\\n" + "="*60)
        debug("  AWS TWINMAKER INTEGRATED E2E TEST")
        debug("="*60)
        
        project_path = Path(aws_twinmaker_e2e_project_path)
        
        # ==========================================
        # PHASE 1: Load Credentials
        # ==========================================
        print("\n[PHASE 1] Loading credentials...")
        
        creds_paths = [
            project_path / "config_credentials.json",
            Path("/app/config_credentials.json"),
            Path("/app/upload/template/config_credentials.json"),
        ]
        
        credentials = None
        for creds_path in creds_paths:
            if creds_path.exists():
                with open(creds_path) as f:
                    credentials = json.load(f)
                print(f"  ✓ Loaded credentials from: {creds_path}")
                break
        
        if not credentials or not credentials.get("aws"):
            pytest.skip("AWS credentials not found")
        
        aws_creds = credentials["aws"]
        required_fields = [
            "aws_access_key_id",
            "aws_secret_access_key"
        ]
        for field in required_fields:
            if not aws_creds.get(field):
                pytest.skip(f"Missing AWS credential: {field}")
        
        print(f"  ✓ Access Key: {aws_creds['aws_access_key_id'][:8]}...")
        
        # ==========================================
        # PHASE 2: Load Hierarchy from Template
        # ==========================================
        print("\n[PHASE 2] Loading hierarchy...")
        
        hierarchy_path = project_path / "twin_hierarchy" / "aws_hierarchy.json"
        if not hierarchy_path.exists():
            print(f"  ⚠ Hierarchy not found: {hierarchy_path} - will skip SDK operations")
            hierarchy = []
        else:
            with open(hierarchy_path) as f:
                hierarchy = json.load(f)
            
            # Count entities from hierarchy
            def count_entities(nodes):
                count = 0
                for node in nodes:
                    if node.get("type") == "entity":
                        count += 1
                        count += count_entities(node.get("children", []))
                return count
            
            entity_count = count_entities(hierarchy)
            print(f"  ✓ Loaded hierarchy: {entity_count} entities")
        
        # ==========================================
        # PHASE 3: Build Terraform tfvars
        # ==========================================
        print("\n[PHASE 3] Building Terraform tfvars...")
        
        tfvars = {
            "aws_access_key_id": aws_creds["aws_access_key_id"],
            "aws_secret_access_key": aws_creds["aws_secret_access_key"],
            "aws_region": aws_creds.get("aws_region", "eu-west-1"),
            "test_name_suffix": "e2e-full",
            "scene_assets_path": str(SCENE_ASSETS_PATH),
        }
        
        tfvars_path = TERRAFORM_DIR / "test.tfvars.json"
        with open(tfvars_path, "w") as f:
            json.dump(tfvars, f, indent=2)
        print(f"  ✓ Created tfvars: {tfvars_path}")
        
        # Track terraform outputs and state
        terraform_outputs = {}
        workspace_id = None
        
        # Cleanup function - runs SDK cleanup + terraform destroy
        def terraform_cleanup():
            """Cleanup function - runs terraform destroy + SDK fallback."""
            print("\n" + "="*60)
            print("  CLEANUP: TERRAFORM DESTROY")
            print("="*60)
            
            try:
                # First try SDK cleanup to remove entities/component types
                if workspace_id:
                    _cleanup_twinmaker_resources_sdk(credentials, workspace_id)
                
                # Then terraform destroy for infrastructure
                result = subprocess.run(
                    [
                        "terraform", "destroy",
                        "-no-color",
                        "-auto-approve",
                        f"-var-file={tfvars_path}",
                    ],
                    cwd=TERRAFORM_DIR,
                    capture_output=True,
                    text=True,
                    timeout=600,
                )
                print(result.stdout)
                if result.returncode != 0:
                    print(f"[CLEANUP] ✗ Terraform destroy failed: {result.stderr}")
                    # Fallback to SDK cleanup
                    if workspace_id:
                        print("[CLEANUP] Attempting SDK fallback cleanup...")
                        _cleanup_twinmaker_resources_sdk(credentials, workspace_id)
                else:
                    print("[CLEANUP] ✓ Terraform destroy completed")
            except Exception as e:
                print(f"[CLEANUP] ✗ Destroy failed: {e}")
                # Fallback SDK cleanup on any failure
                if workspace_id:
                    try:
                        _cleanup_twinmaker_resources_sdk(credentials, workspace_id)
                    except Exception as cleanup_error:
                        print(f"[CLEANUP] SDK fallback also failed: {cleanup_error}")
            
            # Always cleanup tfvars (contains secrets)
            if tfvars_path.exists():
                tfvars_path.unlink()
                print("  ✓ Removed tfvars file")
        
        # Register cleanup to run ALWAYS (on success or failure)
        request.addfinalizer(terraform_cleanup)
        
        # ==========================================
        # PHASE 4: Terraform Init
        # ==========================================
        print("\n[PHASE 4] Terraform init...")
        
        result = subprocess.run(
            ["terraform", "init", "-no-color"],
            cwd=TERRAFORM_DIR,
            capture_output=True,
            text=True,
            timeout=120,
        )
        
        if result.returncode != 0:
            print(result.stderr)
            pytest.fail(f"terraform init failed: {result.stderr}")
        print("  ✓ Terraform initialized")
        
        # ==========================================
        # PHASE 5: Terraform Plan
        # ==========================================
        print("\n[PHASE 5] Terraform plan...")
        
        result = subprocess.run(
            [
                "terraform", "plan",
                "-no-color",
                f"-var-file={tfvars_path}",
                "-out=plan.tfplan",
            ],
            cwd=TERRAFORM_DIR,
            capture_output=True,
            text=True,
            timeout=180,
        )
        
        if result.returncode != 0:
            print(result.stderr)
            pytest.fail(f"terraform plan failed: {result.stderr}")
        print("  ✓ Terraform plan created")
        
        # ==========================================
        # PHASE 6: Terraform Apply
        # ==========================================
        print("\n[PHASE 6] Terraform apply...")
        
        result = subprocess.run(
            [
                "terraform", "apply",
                "-no-color",
                "-auto-approve",
                "plan.tfplan",
            ],
            cwd=TERRAFORM_DIR,
            capture_output=True,
            text=True,
            timeout=600,
        )
        
        print(result.stdout)
        
        if result.returncode != 0:
            print(result.stderr)
            pytest.fail(f"terraform apply failed: {result.stderr}")
        print("  ✓ Terraform apply completed")
        
        # ==========================================
        # PHASE 6.5: Wait for IAM Propagation
        # ==========================================
        # FIX Issue #5: Terraform already has 30s time_sleep for IAM propagation
        # Only add minimal additional wait for API consistency
        print("\n[PHASE 6.5] IAM propagation...")
        print("  ✓ Terraform handled 30s IAM propagation wait")
        
        # ==========================================
        # PHASE 7: Get Terraform Outputs
        # ==========================================
        print("\n[PHASE 7] Getting Terraform outputs...")
        
        result = subprocess.run(
            ["terraform", "output", "-json"],
            cwd=TERRAFORM_DIR,
            capture_output=True,
            text=True,
            timeout=30,
        )
        
        if result.returncode != 0:
            pytest.fail(f"terraform output failed: {result.stderr}")
        
        outputs = json.loads(result.stdout)
        terraform_outputs = {k: v.get("value") for k, v in outputs.items()}
        
        workspace_id = terraform_outputs.get("workspace_id")
        s3_bucket = terraform_outputs.get("s3_bucket_name")
        
        print(f"  ✓ Workspace ID: {workspace_id}")
        print(f"  ✓ S3 Bucket: {s3_bucket}")
        
        # ==========================================
        # PHASE 8: SDK - Create Component Types + Entities
        # ==========================================
        # FIX Issue #3: Create component types BEFORE entities
        debug("\\n[PHASE 8] SDK - Creating component types and entities...")
        
        debug(f"  [DEBUG] Hierarchy type: {type(hierarchy)}, length: {len(hierarchy) if hierarchy else 0}")
        if hierarchy:
            debug(f"  [DEBUG] Hierarchy content: {json.dumps(hierarchy, indent=2)[:500]}...")
        
        if hierarchy:
            try:
                import boto3
                from botocore.exceptions import ClientError
                
                # Create TwinMaker client
                twinmaker = boto3.client(
                    'iottwinmaker',
                    region_name=aws_creds.get("aws_region", "eu-west-1"),
                    aws_access_key_id=aws_creds["aws_access_key_id"],
                    aws_secret_access_key=aws_creds["aws_secret_access_key"]
                )
                
                # Step 8.1: Extract and create component types from hierarchy
                def extract_component_types(nodes):
                    """Extract unique component types from hierarchy."""
                    types = set()
                    for node in nodes:
                        if node.get("type") == "component":
                            ct_id = node.get("componentTypeId")
                            if ct_id:
                                types.add(ct_id)
                        # Recurse into children (entities can have component children)
                        types.update(extract_component_types(node.get("children", [])))
                    return types
                
                component_types = extract_component_types(hierarchy)
                debug(f"  [DEBUG] Extracted component types: {component_types}")
                
                created_types = set()
                if component_types:
                    debug(f"  Creating {len(component_types)} component types...")
                    for ct_id in component_types:
                        try:
                            # Create a basic sensor component type with temperature property
                            debug(f"    Calling create_component_type for: {ct_id}")
                            twinmaker.create_component_type(
                                workspaceId=workspace_id,
                                componentTypeId=ct_id,
                                isSingleton=False,  # Allow multiple instances
                                description=f"Sensor component type: {ct_id}",
                                propertyDefinitions={
                                    # Static property to make component type concrete
                                    "sensorId": {
                                        "dataType": {"type": "STRING"},
                                        "isTimeSeries": False,
                                        "isStoredExternally": False,
                                        "isRequiredInEntity": False,
                                        "defaultValue": {"stringValue": "sensor-default"}
                                    },
                                    "sensorType": {
                                        "dataType": {"type": "STRING"},
                                        "isTimeSeries": False,
                                        "isStoredExternally": False,
                                        "isRequiredInEntity": False,
                                        "defaultValue": {"stringValue": "temperature"}
                                    }
                                }
                            )
                            created_types.add(ct_id)
                            debug(f"    ✓ Component Type: {ct_id}")
                        except ClientError as e:
                            error_code = e.response.get('Error', {}).get('Code', '')
                            if error_code == 'ConflictException' or 'already exists' in str(e).lower():
                                created_types.add(ct_id)
                                debug(f"    ✓ Component Type exists: {ct_id}")
                            else:
                                debug(f"    ✗ Failed to create component type {ct_id}: {error_code} - {e}")
                    
                    # Wait for all component types to become ACTIVE
                    if created_types:
                        debug(f"  ⏳ Waiting for {len(created_types)} component types to become ACTIVE...")
                        for ct_id_check in created_types:
                            for attempt in range(30):  # Max 30 seconds per component type
                                try:
                                    resp = twinmaker.get_component_type(
                                        workspaceId=workspace_id,
                                        componentTypeId=ct_id_check
                                    )
                                    state = resp.get("status", {}).get("state", "UNKNOWN")
                                    if state == "ACTIVE":
                                        debug(f"    ✓ Component type {ct_id_check} is ACTIVE")
                                        break
                                    elif state == "ERROR":
                                        debug(f"    ✗ Component type {ct_id_check} is in ERROR state")
                                        break
                                    else:
                                        time.sleep(1)
                                except ClientError as e:
                                    debug(f"    ⚠ Error checking component type {ct_id_check}: {e}")
                                    time.sleep(1)
                            else:
                                debug(f"    ⚠ Component type {ct_id_check} did not reach ACTIVE state in 30s")
                else:
                    debug("  [DEBUG] No component types found to create")
                
                # Step 8.2: Create entities first (without components)
                def create_entities(nodes, parent_entity_id=None):
                    """Create entities recursively without attaching components."""
                    created = 0
                    for node in nodes:
                        if node.get("type") == "entity":
                            entity_id = node.get("id")
                            
                            try:
                                create_args = {
                                    "workspaceId": workspace_id,
                                    "entityId": entity_id,
                                    "entityName": entity_id,
                                }
                                if parent_entity_id:
                                    create_args["parentEntityId"] = parent_entity_id
                                
                                debug(f"    Creating entity: {entity_id} (parent={parent_entity_id})")
                                twinmaker.create_entity(**create_args)
                                created += 1
                                debug(f"    ✓ Entity: {entity_id}")
                            except ClientError as e:
                                if "ConflictException" in str(e):
                                    debug(f"    ✓ Entity exists: {entity_id}")
                                    created += 1
                                else:
                                    debug(f"    ✗ Failed to create entity {entity_id}: {e}")
                                    raise  # Fail fast on unexpected errors
                            
                            # Recursively create child entities
                            entity_children = [c for c in node.get("children", []) if c.get("type") == "entity"]
                            created += create_entities(entity_children, entity_id)
                    return created
                
                # Step 8.3: Attach components via update_entity (matching production pattern)
                def attach_components(nodes, failures=None):
                    """Attach components to entities using update_entity (production pattern)."""
                    if failures is None:
                        failures = []
                    attached = 0
                    
                    for node in nodes:
                        if node.get("type") == "entity":
                            entity_id = node.get("id")
                            
                            for child in node.get("children", []):
                                if child.get("type") == "component":
                                    comp_name = child.get("name")
                                    ct_id = child.get("componentTypeId")
                                    
                                    if comp_name and ct_id:
                                        try:
                                            twinmaker.update_entity(
                                                workspaceId=workspace_id,
                                                entityId=entity_id,
                                                componentUpdates={
                                                    comp_name: {"componentTypeId": ct_id}
                                                }
                                            )
                                            attached += 1
                                            debug(f"    ✓ Attached {comp_name} → {entity_id}")
                                        except ClientError as e:
                                            if "ConflictException" in str(e):
                                                debug(f"    Component already attached: {comp_name}")
                                                attached += 1
                                            else:
                                                debug(f"    ✗ Attach failed for {comp_name} → {entity_id}: {e}")
                                                failures.append((comp_name, entity_id, str(e)))
                            
                            # Recurse into child entities
                            entity_children = [c for c in node.get("children", []) if c.get("type") == "entity"]
                            child_attached = attach_components(entity_children, failures)
                            attached += child_attached
                    
                    return attached
                
                # Run entity creation
                debug(f"  Creating entities from hierarchy with {len(hierarchy)} top-level nodes...")
                created_count = create_entities(hierarchy)
                print(f"  ✓ Created {created_count} entities")
                
                # Run component attachment
                debug(f"  Attaching components to entities...")
                failures = []
                attached_count = attach_components(hierarchy, failures)
                print(f"  ✓ Attached {attached_count} components")
                
                if failures:
                    print(f"  ⚠ {len(failures)} component attachments failed:")
                    for comp, entity, err in failures:
                        print(f"      {comp} → {entity}: {err}")
                
            except ImportError as e:
                print(f"  ⚠ boto3 not available: {e}")
            except Exception as e:
                print(f"  ⚠ SDK operations failed: {e}")
        else:
            print("  ⚠ No hierarchy found - skipping entity creation")
        
        print("\n" + "="*60)
        print("  DEPLOYMENT COMPLETE - RUNNING VERIFICATION TESTS")
        print("="*60)
        
        yield {
            "terraform_outputs": terraform_outputs,
            "workspace_id": workspace_id,
            "hierarchy": hierarchy,
            "credentials": credentials,
            "project_path": str(project_path),
        }
    
    # =========================================================================
    # VERIFICATION TESTS
    # =========================================================================
    
    def test_01_workspace_deployed(self, deployed_environment):
        """Verify TwinMaker workspace was created by Terraform."""
        outputs = deployed_environment["terraform_outputs"]
        
        workspace_id = outputs.get("workspace_id")
        assert workspace_id is not None, "Workspace ID should exist"
        
        workspace_arn = outputs.get("workspace_arn")
        assert workspace_arn is not None, "Workspace ARN should exist"
        assert ":iottwinmaker:" in workspace_arn, "Should be TwinMaker ARN"
        
        print(f"[VERIFY] ✓ Workspace ID: {workspace_id}")
        print(f"[VERIFY] ✓ Workspace ARN: {workspace_arn}")
    
    def test_02_s3_bucket_deployed(self, deployed_environment):
        """Verify S3 bucket was created for TwinMaker workspace."""
        outputs = deployed_environment["terraform_outputs"]
        
        bucket_name = outputs.get("s3_bucket_name")
        assert bucket_name is not None, "S3 bucket should exist"
        
        bucket_arn = outputs.get("s3_bucket_arn")
        assert bucket_arn is not None, "S3 bucket ARN should exist"
        
        print(f"[VERIFY] ✓ S3 Bucket: {bucket_name}")
    
    def test_03_scene_files_uploaded(self, deployed_environment):
        """Verify 3D scene files were uploaded to S3."""
        outputs = deployed_environment["terraform_outputs"]
        
        glb_url = outputs.get("scene_glb_url")
        json_url = outputs.get("scene_json_url")
        
        assert glb_url is not None and glb_url != "", "GLB file URL should exist"
        assert json_url is not None and json_url != "", "JSON file URL should exist"
        assert "scene.glb" in glb_url, "GLB should be scene.glb"
        assert "scene.json" in json_url, "JSON should be scene.json"
        
        scene_id = outputs.get("scene_id")
        assert scene_id is not None, "TwinMaker Scene ID should exist"
        
        print(f"[VERIFY] ✓ GLB File: {glb_url}")
        print(f"[VERIFY] ✓ JSON File: {json_url}")
        print(f"[VERIFY] ✓ Scene ID: {scene_id}")
    
    def test_04_entities_exist(self, deployed_environment):
        """Verify entities were created in TwinMaker via SDK."""
        workspace_id = deployed_environment["workspace_id"]
        credentials = deployed_environment["credentials"]
        hierarchy = deployed_environment["hierarchy"]
        
        if not workspace_id:
            pytest.skip("Workspace ID not available")
        
        if not hierarchy:
            pytest.skip("No hierarchy - entities not created")
        
        try:
            import boto3
            from botocore.exceptions import ClientError
            
            aws_creds = credentials["aws"]
            twinmaker = boto3.client(
                'iottwinmaker',
                region_name=aws_creds.get("aws_region", "eu-west-1"),
                aws_access_key_id=aws_creds["aws_access_key_id"],
                aws_secret_access_key=aws_creds["aws_secret_access_key"]
            )
            
            # Extract entity IDs from hierarchy
            def get_entity_ids(nodes):
                ids = []
                for node in nodes:
                    if node.get("type") == "entity":
                        ids.append(node.get("id"))
                        ids.extend(get_entity_ids(node.get("children", [])))
                return ids
            
            entity_ids = get_entity_ids(hierarchy)
            verified_count = 0
            
            for entity_id in entity_ids:
                try:
                    twinmaker.get_entity(
                        workspaceId=workspace_id,
                        entityId=entity_id
                    )
                    print(f"[VERIFY] ✓ Entity exists: {entity_id}")
                    verified_count += 1
                except ClientError as e:
                    print(f"[VERIFY] ✗ Entity not found: {entity_id} - {e}")
            
            assert verified_count == len(entity_ids), f"Expected {len(entity_ids)} entities, found {verified_count}"
            print(f"[VERIFY] ✓ All {verified_count} entities verified")
            
        except ImportError:
            pytest.skip("boto3 not installed")
    
    def test_05_deployment_summary(self, deployed_environment):
        """Print deployment summary for manual verification."""
        outputs = deployed_environment["terraform_outputs"]
        hierarchy = deployed_environment["hierarchy"]
        
        # Count entities from hierarchy
        def count_entities(nodes):
            count = 0
            for node in nodes:
                if node.get("type") == "entity":
                    count += 1
                    count += count_entities(node.get("children", []))
            return count
        
        entity_count = count_entities(hierarchy) if hierarchy else 0
        
        print("\n" + "="*60)
        print("  DEPLOYMENT SUMMARY (for manual verification)")
        print("="*60)
        print(f"\n  Workspace ID: {outputs.get('workspace_id')}")
        print(f"  S3 Bucket: {outputs.get('s3_bucket_name')}")
        print(f"\n  Entities: {entity_count}")
        print("\n  Scene Files:")
        print(f"    GLB: {outputs.get('scene_glb_url')}")
        print(f"    JSON: {outputs.get('scene_json_url')}")
        print("\n  Console Links:")
        print(f"    TwinMaker: {outputs.get('aws_twinmaker_console_url')}")
        print(f"    S3: {outputs.get('aws_s3_console_url')}")
        print("\n  To cleanup:")
        print(f"    cd {TERRAFORM_DIR}")
        print(f"    terraform destroy -var-file=test.tfvars.json")
        print("="*60)
        
        assert True  # Always pass - informational test


# Allow running this file directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
