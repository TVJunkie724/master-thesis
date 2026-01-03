"""
Cleanup script for all old TwinMaker E2E test resources.
Deletes entities, component types, then workspace via SDK.
"""
import json
import os
import sys
import time

# Workspaces to clean up
WORKSPACES_TO_DELETE = [
    "tm-e2e-full-ryaqzx",
    "tm-e2e-full-v06ngl",
]

CREDS_FILE = "/app/tests/e2e/aws/e2e_state/tf-e2e-tm/config_credentials.json"
BACKUP_CREDS = "/app/config_credentials.json"

def cleanup_workspace(twinmaker, workspace_id):
    """Delete all resources in a workspace then delete the workspace."""
    print(f"\n{'='*60}")
    print(f"Cleaning up workspace: {workspace_id}")
    print(f"{'='*60}")
    
    # Check if workspace exists
    try:
        twinmaker.get_workspace(workspaceId=workspace_id)
    except Exception as e:
        print(f"  Workspace not found or error: {e}")
        return False
    
    # Delete all entities
    try:
        response = twinmaker.list_entities(workspaceId=workspace_id)
        entities = response.get("entitySummaries", [])
        
        if entities:
            print(f"  Deleting {len(entities)} entities...")
            for entity in entities:
                entity_id = entity.get("entityId")
                if entity_id and entity_id != "$ROOT":
                    try:
                        twinmaker.delete_entity(
                            workspaceId=workspace_id, 
                            entityId=entity_id, 
                            isRecursive=True
                        )
                        print(f"    ✓ Deleted entity: {entity_id}")
                    except Exception as e:
                        print(f"    ⚠ Could not delete entity {entity_id}: {e}")
        else:
            print("  No entities to delete")
    except Exception as e:
        print(f"  Could not list entities: {e}")
    
    # Delete all scenes
    try:
        response = twinmaker.list_scenes(workspaceId=workspace_id)
        scenes = response.get("sceneSummaries", [])
        
        if scenes:
            print(f"  Deleting {len(scenes)} scenes...")
            for scene in scenes:
                scene_id = scene.get("sceneId")
                try:
                    twinmaker.delete_scene(workspaceId=workspace_id, sceneId=scene_id)
                    print(f"    ✓ Deleted scene: {scene_id}")
                except Exception as e:
                    print(f"    ⚠ Could not delete scene {scene_id}: {e}")
        else:
            print("  No scenes to delete")
    except Exception as e:
        print(f"  Could not list scenes: {e}")
    
    # Delete all component types
    try:
        response = twinmaker.list_component_types(workspaceId=workspace_id)
        component_types = response.get("componentTypeSummaries", [])
        
        custom_types = [ct for ct in component_types 
                       if not ct.get("componentTypeId", "").startswith("com.amazon")]
        
        if custom_types:
            print(f"  Deleting {len(custom_types)} custom component types...")
            for ct in custom_types:
                ct_id = ct.get("componentTypeId")
                try:
                    twinmaker.delete_component_type(
                        workspaceId=workspace_id, 
                        componentTypeId=ct_id
                    )
                    print(f"    ✓ Deleted component type: {ct_id}")
                except Exception as e:
                    print(f"    ⚠ Could not delete component type {ct_id}: {e}")
        else:
            print("  No custom component types to delete")
    except Exception as e:
        print(f"  Could not list component types: {e}")
    
    # Wait for deletions to propagate
    print("  ⏳ Waiting 10s for deletions to propagate...")
    time.sleep(10)
    
    # Delete workspace
    try:
        print(f"  Deleting workspace {workspace_id}...")
        twinmaker.delete_workspace(workspaceId=workspace_id)
        print(f"  ✓ Workspace {workspace_id} deleted!")
        return True
    except Exception as e:
        print(f"  ✗ Could not delete workspace: {e}")
        return False


def main():
    # Find credentials
    creds_path = None
    for path in [CREDS_FILE, BACKUP_CREDS]:
        if os.path.exists(path):
            creds_path = path
            break
    
    if not creds_path:
        print("ERROR: No credentials file found")
        sys.exit(1)
    
    print(f"Loading credentials from: {creds_path}")
    with open(creds_path) as f:
        creds = json.load(f)
    
    aws_creds = creds.get("aws", {})
    region = aws_creds.get("aws_region", "eu-central-1")
    
    import boto3
    twinmaker = boto3.client(
        'iottwinmaker',
        region_name=region,
        aws_access_key_id=aws_creds.get("aws_access_key_id"),
        aws_secret_access_key=aws_creds.get("aws_secret_access_key")
    )
    
    print(f"Region: {region}")
    print(f"Workspaces to clean: {WORKSPACES_TO_DELETE}")
    
    success_count = 0
    for ws_id in WORKSPACES_TO_DELETE:
        if cleanup_workspace(twinmaker, ws_id):
            success_count += 1
    
    print(f"\n{'='*60}")
    print(f"Cleanup complete: {success_count}/{len(WORKSPACES_TO_DELETE)} workspaces deleted")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
