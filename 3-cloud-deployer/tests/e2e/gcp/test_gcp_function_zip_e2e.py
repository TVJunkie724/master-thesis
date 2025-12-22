"""
GCP Cloud Function ZIP Deploy E2E Test (SDK-Only).

This test deploys a single Cloud Function using Python SDK (not Terraform) to verify
that the function ZIP is correctly bundled and deployed.

Uses Python SDK only (no Terraform) for:
1. Create Cloud Storage bucket
2. Upload function ZIP
3. Deploy Cloud Function 2nd gen
4. Invoke function to verify
5. Cleanup all resources

IMPORTANT: This test deploys REAL GCP resources and incurs costs (~$0.01).
Run with: pytest -m live -s

Estimated duration: 5-10 minutes
"""
import pytest
import os
import sys
import json
import time
import uuid
import zipfile
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))


# ==============================================================================
# Fixtures
# ==============================================================================

@pytest.fixture(scope="module")
def gcp_credentials():
    """Load GCP credentials from template."""
    creds_path = Path(__file__).parent.parent.parent.parent / "upload" / "template" / "config_credentials.json"
    
    if not creds_path.exists():
        pytest.skip("GCP credentials not found")
    
    with open(creds_path) as f:
        creds = json.load(f)
    
    gcp_creds = creds.get("gcp", {})
    
    if not gcp_creds.get("gcp_project_id"):
        pytest.skip("GCP project ID not configured")
    
    # Set credentials file if available
    creds_file = gcp_creds.get("gcp_credentials_file")
    if creds_file:
        # Handle relative path - resolve against template directory
        if not os.path.isabs(creds_file):
            template_dir = creds_path.parent
            creds_file = str(template_dir / creds_file)
        
        if os.path.exists(creds_file):
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = creds_file
        else:
            pytest.skip(f"GCP credentials file not found: {creds_file}")
    
    return gcp_creds


@pytest.fixture(scope="module")
def template_project_path():
    """Return path to template project."""
    return str(Path(__file__).parent.parent.parent.parent / "upload" / "template")


# ==============================================================================
# Test Class  
# ==============================================================================

@pytest.mark.live
class TestGCPFunctionZipE2E:
    """
    SDK-only E2E test for GCP Cloud Function ZIP deployment.
    
    Pattern matches test_azure_functions_only.py:
    - Create resources via SDK
    - Deploy ZIP
    - Verify function works
    - Cleanup
    """
    
    @pytest.fixture(scope="class")
    def gcp_infra(self, gcp_credentials, template_project_path):
        """
        Create GCP infrastructure for function deployment using SDK.
        
        Creates:
        - Cloud Storage bucket for function source
        - Cloud Function 2nd gen
        """
        try:
            from google.cloud import storage
            from google.cloud import functions_v2
            from google.cloud.functions_v2 import types
        except ImportError:
            pytest.skip("GCP SDK not installed (google-cloud-functions, google-cloud-storage)")
        
        project_id = gcp_credentials["gcp_project_id"]
        region = gcp_credentials.get("gcp_region", "europe-west1")
        
        # Generate unique names (keep short for GCP limits)
        unique_id = str(uuid.uuid4())[:8]
        bucket_name = f"{project_id}-ziptest-{unique_id}"[:63]  # Max 63 chars
        function_name = f"ziptest-{unique_id}"
        
        print(f"\n{'='*60}")
        print(f"  GCP CLOUD FUNCTION ZIP E2E TEST")
        print(f"{'='*60}")
        print(f"  Project: {project_id}")
        print(f"  Region: {region}")
        print(f"  Bucket: {bucket_name}")
        print(f"  Function: {function_name}")
        print(f"{'='*60}\n")
        
        storage_client = storage.Client(project=project_id)
        functions_client = functions_v2.FunctionServiceClient()
        
        function_url = None
        bucket = None
        
        try:
            # 1. Create Storage Bucket
            print("1️⃣ Creating storage bucket...")
            bucket = storage_client.create_bucket(bucket_name, location=region)
            print(f"   ✓ Bucket created: {bucket_name}")
            
            # 2. Create test function ZIP
            print("2️⃣ Creating test function ZIP...")
            handler_code = '''
import functions_framework
import json

@functions_framework.http
def handle_request(request):
    """Simple test handler that confirms execution."""
    return json.dumps({
        "message": "Hello from GCP ZIP test!",
        "test": "success"
    }), 200, {"Content-Type": "application/json"}
'''
            requirements = "functions-framework==3.*\n"
            
            with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
                with zipfile.ZipFile(tmp.name, 'w', zipfile.ZIP_DEFLATED) as zf:
                    zf.writestr("main.py", handler_code)
                    zf.writestr("requirements.txt", requirements)
                zip_path = tmp.name
            print(f"   ✓ ZIP created")
            
            # 3. Upload ZIP to bucket
            print("3️⃣ Uploading ZIP to bucket...")
            blob = bucket.blob("function-source.zip")
            blob.upload_from_filename(zip_path)
            source_uri = f"gs://{bucket_name}/function-source.zip"
            print(f"   ✓ ZIP uploaded: {source_uri}")
            
            # Cleanup temp file
            os.unlink(zip_path)
            
            # 4. Deploy Cloud Function
            print("4️⃣ Deploying Cloud Function (this may take 2-3 minutes)...")
            parent = f"projects/{project_id}/locations/{region}"
            function_path = f"{parent}/functions/{function_name}"
            
            function = types.Function(
                name=function_path,
                build_config=types.BuildConfig(
                    runtime="python311",
                    entry_point="handle_request",
                    source=types.Source(
                        storage_source=types.StorageSource(
                            bucket=bucket_name,
                            object_="function-source.zip"
                        )
                    )
                ),
                service_config=types.ServiceConfig(
                    max_instance_count=1,
                    available_memory="256M",
                    timeout_seconds=60,
                    ingress_settings=types.ServiceConfig.IngressSettings.ALLOW_ALL,
                )
            )
            
            operation = functions_client.create_function(
                parent=parent,
                function=function,
                function_id=function_name
            )
            
            print("   ⏳ Waiting for deployment...")
            result = operation.result(timeout=300)
            function_url = result.service_config.uri
            print(f"   ✓ Function deployed: {function_url}")
            
            # 5. Wait for function to be ready
            print("5️⃣ Waiting for function to be ready (15s)...")
            time.sleep(15)
            
            print(f"\n{'='*60}")
            print(f"  INFRASTRUCTURE READY - RUNNING TESTS")
            print(f"{'='*60}\n")
            
            yield {
                "project_id": project_id,
                "region": region,
                "bucket_name": bucket_name,
                "function_name": function_name,
                "function_url": function_url,
                "storage_client": storage_client,
                "functions_client": functions_client,
            }
            
        finally:
            # Cleanup
            print(f"\n{'='*60}")
            print(f"  CLEANUP: Deleting GCP resources")
            print(f"{'='*60}")
            
            # Delete function
            try:
                function_path = f"projects/{project_id}/locations/{region}/functions/{function_name}"
                operation = functions_client.delete_function(name=function_path)
                operation.result(timeout=120)
                print("   ✓ Function deleted")
            except Exception as e:
                print(f"   ⚠ Function cleanup: {e}")
            
            # Delete bucket (with contents)
            try:
                if bucket:
                    bucket.delete(force=True)
                    print("   ✓ Bucket deleted")
            except Exception as e:
                print(f"   ⚠ Bucket cleanup: {e}")
    
    # ==========================================================================
    # TESTS
    # ==========================================================================
    
    def test_01_function_deployed(self, gcp_infra):
        """Verify Cloud Function was deployed."""
        assert gcp_infra["function_url"], "Function URL should exist"
        print(f"\n  ✓ Function deployed: {gcp_infra['function_name']}")
        print(f"  ✓ URL: {gcp_infra['function_url']}")
    
    def test_02_function_invocation(self, gcp_infra):
        """Invoke function with authenticated request using ID token."""
        import google.auth
        from google.auth.transport.requests import Request
        from google.oauth2 import id_token
        import requests
        
        function_url = gcp_infra["function_url"]
        print(f"\n  Invoking (authenticated): {function_url}")
        
        # For Cloud Functions 2nd gen (backed by Cloud Run), we need an ID token
        # with the function URL as the audience
        credentials, project = google.auth.default()
        
        # Get ID token for the function URL
        auth_req = Request()
        token = id_token.fetch_id_token(auth_req, function_url)
        
        # Make authenticated request with ID token
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(function_url, headers=headers, timeout=30)
        print(f"  Status: {response.status_code}")
        print(f"  Response: {response.text[:200]}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("test") == "success", f"Response should indicate success: {data}"
        
        print(f"\n  ✅ GCP FUNCTION INVOCATION VERIFIED")


# Allow running this file directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "-m", "live"])
