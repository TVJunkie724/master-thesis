"""Debug script to trace the exact import/execution order that causes the os error."""
import sys
import os  # Make sure os is available first
sys.path.insert(0, '/app/src')
sys.path.insert(0, '/app')

print(f"os module loaded: {os}")
print(f"os.path.exists available: {os.path.exists}")

# Now trace imports exactly as the test does
print("\n=== Tracing imports ===")

try:
    print("1. Importing src.core.config_loader...")
    from src.core.config_loader import load_project_config, load_credentials
    print("   OK")
except Exception as e:
    print(f"   FAILED: {e}")

try:
    print("2. Importing src.core.context...")
    from src.core.context import DeploymentContext
    print("   OK")
except Exception as e:
    print(f"   FAILED: {e}")

try:
    print("3. Importing src.providers.terraform.deployer_strategy...")
    from src.providers.terraform.deployer_strategy import TerraformDeployerStrategy
    print("   OK")
except Exception as e:
    print(f"   FAILED: {e}")

try:
    print("4. Importing validator...")
    import validator
    print("   OK")
except Exception as e:
    print(f"   FAILED: {e}")

try:
    print("5. Importing constants...")
    import constants as CONSTANTS
    print("   OK")
except Exception as e:
    print(f"   FAILED: {e}")

# Now check if os is still available
print(f"\nos module still available: {os}")

# Check the conftest imports
print("\n=== Tracing conftest imports ===")

try:
    print("1. Importing json...")
    import json
    print("   OK")
except Exception as e:
    print(f"   FAILED: {e}")

try:
    print("2. Importing shutil...")
    import shutil
    print("   OK")
except Exception as e:
    print(f"   FAILED: {e}")

try:
    print("3. Importing pathlib.Path...")
    from pathlib import Path
    print("   OK")
except Exception as e:
    print(f"   FAILED: {e}")

# Now simulate gcp_credentials fixture call
print("\n=== Simulating gcp_credentials fixture ===")

template_path = Path('/app/upload/template')
creds_path = template_path / "config_credentials.json"

print(f"creds_path.exists(): {creds_path.exists()}")

if creds_path.exists():
    with open(creds_path, "r") as f:
        all_creds = json.load(f)
    
    gcp_creds = all_creds.get("gcp", {})
    
    has_creds_file = gcp_creds.get("gcp_credentials_file")
    has_project = gcp_creds.get("gcp_project_id") or gcp_creds.get("gcp_billing_account")
    
    print(f"has_creds_file: {has_creds_file}")
    print(f"has_project: {has_project}")
    
    if has_creds_file and has_project:
        # This is where the error might occur
        print(f"Testing os.path.exists({has_creds_file})...")
        result = os.path.exists(has_creds_file)
        print(f"   Result: {result}")
        
        print("Testing os.environ assignment...")
        os.environ["TEST_VAR"] = "test"
        print(f"   Result: {os.environ.get('TEST_VAR')}")

print("\n=== All imports and fixtures OK ===")
