"""
AWS Lambda ZIP Deploy E2E Test (SDK-Only).

This test deploys a single Lambda function using Python SDK (not Terraform) to verify
that the Lambda ZIP is correctly deployed and invocable.

Uses Python SDK only (no Terraform) for:
1. Create IAM role
2. Create Lambda function from ZIP
3. Invoke Lambda to verify
4. Cleanup all resources

IMPORTANT: This test deploys REAL AWS resources and incurs costs (~$0.01).
Run with: pytest -m live -s

Estimated duration: 2-5 minutes
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
def aws_credentials():
    """Load AWS credentials from template."""
    creds_path = Path(__file__).parent.parent.parent.parent / "upload" / "template" / "config_credentials.json"
    
    if not creds_path.exists():
        pytest.skip("AWS credentials not found")
    
    with open(creds_path) as f:
        creds = json.load(f)
    
    aws_creds = creds.get("aws", {})
    
    if not aws_creds.get("aws_access_key_id"):
        pytest.skip("AWS credentials not configured")
    
    # Set environment variables for boto3
    os.environ["AWS_ACCESS_KEY_ID"] = aws_creds["aws_access_key_id"]
    os.environ["AWS_SECRET_ACCESS_KEY"] = aws_creds["aws_secret_access_key"]
    os.environ["AWS_REGION"] = aws_creds.get("aws_region", "eu-west-1")
    
    return aws_creds


@pytest.fixture(scope="module")
def template_project_path():
    """Return path to template project."""
    return str(Path(__file__).parent.parent.parent.parent / "upload" / "template")


# ==============================================================================
# Test Class
# ==============================================================================

@pytest.mark.live
class TestAWSLambdaZipE2E:
    """
    SDK-only E2E test for AWS Lambda ZIP deployment.
    
    Pattern matches test_azure_functions_only.py:
    - Create resources via SDK
    - Deploy ZIP
    - Verify function works
    - Cleanup
    """
    
    @pytest.fixture(scope="class")
    def aws_infra(self, aws_credentials, template_project_path):
        """
        Create AWS infrastructure for Lambda deployment using SDK.
        
        Creates:
        - IAM role for Lambda
        - Lambda function from ZIP
        """
        try:
            import boto3
            from botocore.exceptions import ClientError
        except ImportError:
            pytest.skip("boto3 not installed")
        
        region = aws_credentials.get("aws_region", "eu-west-1")
        
        # Generate unique names
        unique_id = str(uuid.uuid4())[:8]
        role_name = f"ziptest-role-{unique_id}"
        function_name = f"ziptest-lambda-{unique_id}"
        
        print(f"\n{'='*60}")
        print(f"  AWS LAMBDA ZIP E2E TEST")
        print(f"{'='*60}")
        print(f"  Region: {region}")
        print(f"  Role: {role_name}")
        print(f"  Function: {function_name}")
        print(f"{'='*60}\n")
        
        iam_client = boto3.client('iam', region_name=region)
        lambda_client = boto3.client('lambda', region_name=region)
        
        role_arn = None
        
        try:
            # 1. Create IAM Role
            print("1️⃣ Creating IAM role...")
            assume_role_policy = json.dumps({
                "Version": "2012-10-17",
                "Statement": [{
                    "Effect": "Allow",
                    "Principal": {"Service": "lambda.amazonaws.com"},
                    "Action": "sts:AssumeRole"
                }]
            })
            
            role_response = iam_client.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=assume_role_policy,
                Description="Test role for ZIP E2E test"
            )
            role_arn = role_response["Role"]["Arn"]
            
            # Attach basic execution policy
            iam_client.attach_role_policy(
                RoleName=role_name,
                PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
            )
            print(f"   ✓ Role created: {role_arn}")
            
            # Wait for role to propagate (IAM is eventually consistent)
            print("   ⏳ Waiting for role propagation (10s)...")
            time.sleep(10)
            
            # 2. Create test Lambda ZIP
            print("2️⃣ Creating test Lambda ZIP...")
            handler_code = '''
import json

def lambda_handler(event, context):
    """Simple test handler that confirms execution."""
    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": "Hello from AWS ZIP test!",
            "test": "success"
        })
    }
'''
            with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
                with zipfile.ZipFile(tmp.name, 'w', zipfile.ZIP_DEFLATED) as zf:
                    zf.writestr("lambda_function.py", handler_code)
                zip_path = tmp.name
            
            with open(zip_path, 'rb') as f:
                zip_bytes = f.read()
            print(f"   ✓ ZIP created: {len(zip_bytes)} bytes")
            
            # Cleanup temp file
            os.unlink(zip_path)
            
            # 3. Create Lambda Function
            print("3️⃣ Creating Lambda function...")
            lambda_client.create_function(
                FunctionName=function_name,
                Runtime="python3.11",
                Role=role_arn,
                Handler="lambda_function.lambda_handler",
                Code={"ZipFile": zip_bytes},
                Timeout=30,
                MemorySize=128
            )
            print(f"   ✓ Function created: {function_name}")
            
            # Wait for function to be active
            print("   ⏳ Waiting for function to be active...")
            waiter = lambda_client.get_waiter('function_active')
            waiter.wait(FunctionName=function_name)
            print(f"   ✓ Function active")
            
            print(f"\n{'='*60}")
            print(f"  INFRASTRUCTURE READY - RUNNING TESTS")
            print(f"{'='*60}\n")
            
            yield {
                "region": region,
                "role_name": role_name,
                "role_arn": role_arn,
                "function_name": function_name,
                "iam_client": iam_client,
                "lambda_client": lambda_client,
            }
            
        finally:
            # Cleanup
            print(f"\n{'='*60}")
            print(f"  CLEANUP: Deleting AWS resources")
            print(f"{'='*60}")
            
            # Delete function
            try:
                lambda_client.delete_function(FunctionName=function_name)
                print("   ✓ Function deleted")
            except Exception as e:
                print(f"   ⚠ Function cleanup: {e}")
            
            # Detach policy and delete role
            try:
                iam_client.detach_role_policy(
                    RoleName=role_name,
                    PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
                )
                iam_client.delete_role(RoleName=role_name)
                print("   ✓ Role deleted")
            except Exception as e:
                print(f"   ⚠ Role cleanup: {e}")
    
    # ==========================================================================
    # TESTS
    # ==========================================================================
    
    def test_01_lambda_deployed(self, aws_infra):
        """Verify Lambda was deployed."""
        assert aws_infra["function_name"], "Function name should exist"
        print(f"\n  ✓ Lambda deployed: {aws_infra['function_name']}")
    
    def test_02_lambda_invocation(self, aws_infra):
        """Invoke Lambda and verify response."""
        lambda_client = aws_infra["lambda_client"]
        function_name = aws_infra["function_name"]
        
        print(f"\n  Invoking: {function_name}")
        
        response = lambda_client.invoke(
            FunctionName=function_name,
            InvocationType='RequestResponse',
            Payload=json.dumps({"test": "data"})
        )
        
        assert response["StatusCode"] == 200, f"Expected 200, got {response['StatusCode']}"
        
        payload = json.loads(response["Payload"].read())
        print(f"  Response: {json.dumps(payload, indent=2)}")
        
        body = json.loads(payload["body"])
        assert body.get("test") == "success", f"Expected success, got: {body}"
        
        print(f"\n  ✅ AWS LAMBDA INVOCATION VERIFIED")


# Allow running this file directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "-m", "live"])
