"""
Simple script to destroy AWS TwinMaker E2E test resources.
Reads credentials from config_credentials.json, cleans up SDK resources, then runs terraform destroy.
"""
import json
import subprocess
import os
import sys

# Paths
PROJECT_ROOT = "/app"
TERRAFORM_DIR = os.path.join(PROJECT_ROOT, "tests/e2e/aws_twinmaker_test")
CREDS_FILE = os.path.join(PROJECT_ROOT, "tests/e2e/aws/e2e_state/tf-e2e-tm/config_credentials.json")

def cleanup_sdk_resources(twinmaker, workspace_id):
    """Delete all entities and component types from workspace."""
    print(f"Cleaning up SDK resources from workspace: {workspace_id}")
    
    # List and delete all entities
    try:
        response = twinmaker.list_entities(workspaceId=workspace_id)
        entities = response.get("entitySummaries", [])
        
        if entities:
            print(f"  Deleting {len(entities)} entities...")
            for entity in entities:
                entity_id = entity.get("entityId")
                if entity_id and entity_id != "$ROOT":
                    try:
                        twinmaker.delete_entity(workspaceId=workspace_id, entityId=entity_id, isRecursive=True)
                        print(f"    ✓ Deleted entity: {entity_id}")
                    except Exception as e:
                        print(f"    ⚠ Could not delete entity {entity_id}: {e}")
        else:
            print("  No entities to delete")
    except Exception as e:
        print(f"  Could not list entities: {e}")
    
    # List and delete all component types
    try:
        response = twinmaker.list_component_types(workspaceId=workspace_id)
        component_types = response.get("componentTypeSummaries", [])
        
        # Filter out built-in types (start with com.amazon)
        custom_types = [ct for ct in component_types if not ct.get("componentTypeId", "").startswith("com.amazon")]
        
        if custom_types:
            print(f"  Deleting {len(custom_types)} custom component types...")
            for ct in custom_types:
                ct_id = ct.get("componentTypeId")
                try:
                    twinmaker.delete_component_type(workspaceId=workspace_id, componentTypeId=ct_id)
                    print(f"    ✓ Deleted component type: {ct_id}")
                except Exception as e:
                    print(f"    ⚠ Could not delete component type {ct_id}: {e}")
        else:
            print("  No custom component types to delete")
    except Exception as e:
        print(f"  Could not list component types: {e}")

def main():
    # Load credentials
    if not os.path.exists(CREDS_FILE):
        print(f"ERROR: Credentials file not found: {CREDS_FILE}")
        sys.exit(1)
    
    with open(CREDS_FILE) as f:
        creds = json.load(f)
    
    aws_creds = creds.get("aws", {})
    region = aws_creds.get("aws_region", "eu-central-1")
    
    # Get workspace ID from terraform state
    tfstate_path = os.path.join(TERRAFORM_DIR, "terraform.tfstate")
    workspace_id = None
    if os.path.exists(tfstate_path):
        with open(tfstate_path) as f:
            tfstate = json.load(f)
        outputs = tfstate.get("outputs", {})
        workspace_id = outputs.get("workspace_id", {}).get("value")
    
    # Clean up SDK resources first
    if workspace_id:
        import boto3
        twinmaker = boto3.client(
            'iottwinmaker',
            region_name=region,
            aws_access_key_id=aws_creds.get("aws_access_key_id"),
            aws_secret_access_key=aws_creds.get("aws_secret_access_key")
        )
        cleanup_sdk_resources(twinmaker, workspace_id)
        print("Waiting 5s for deletions to propagate...")
        import time
        time.sleep(5)
    else:
        print("No workspace ID found in state, skipping SDK cleanup")
    
    # Build tfvars
    tfvars = {
        "aws_access_key_id": aws_creds.get("aws_access_key_id"),
        "aws_secret_access_key": aws_creds.get("aws_secret_access_key"),
        "aws_region": region,
        "scene_assets_path": "/app/upload/template/scene_assets"
    }
    
    # Write tfvars
    tfvars_path = os.path.join(TERRAFORM_DIR, "destroy.tfvars.json")
    with open(tfvars_path, "w") as f:
        json.dump(tfvars, f, indent=2)
    
    print(f"Running terraform destroy...")
    
    # Run destroy
    result = subprocess.run(
        ["terraform", "destroy", "-auto-approve", f"-var-file={tfvars_path}"],
        cwd=TERRAFORM_DIR,
        capture_output=True,
        text=True,
        timeout=300
    )
    
    print(result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout)
    if result.returncode != 0:
        print(f"STDERR: {result.stderr[-500:]}")
        sys.exit(1)
    
    print("Destroy complete!")
    
    # Clean up tfvars
    os.remove(tfvars_path)

if __name__ == "__main__":
    main()
