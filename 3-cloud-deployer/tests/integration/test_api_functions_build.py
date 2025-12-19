"""
Tests for POST /functions/build endpoint.

Tests cover:
- Happy path: valid function files for each provider
- Error cases: syntax errors, missing entry points, invalid providers
- Edge cases: empty files, wrong extensions, with/without requirements.txt
"""

import io
import zipfile
import pytest
from fastapi.testclient import TestClient

from rest_api import app

client = TestClient(app)


# ==========================================
# Test Fixtures
# ==========================================

VALID_AWS_FUNCTION = b"""
def handler(event, context):
    '''AWS Lambda handler'''
    return {"statusCode": 200, "body": "Hello AWS"}
"""

VALID_AZURE_FUNCTION = b"""
import azure.functions as func

def process_request(req: func.HttpRequest) -> func.HttpResponse:
    '''Azure Function'''
    return func.HttpResponse("Hello Azure", status_code=200)
"""

VALID_GCP_FUNCTION = b"""
def main(request):
    '''GCP Cloud Function'''
    return "Hello GCP", 200
"""

INVALID_SYNTAX = b"""
def handler(event, context):
    return {"broken
"""

MISSING_ENTRY_AWS = b"""
def process_data(data):
    '''Missing handler function'''
    return data
"""

MISSING_ENTRY_GCP = b"""
def process(request):
    '''Wrong function name for GCP'''
    return "Missing main/handler"
"""

EMPTY_FILE = b""

SAMPLE_REQUIREMENTS = b"""requests>=2.28.0
boto3>=1.26.0
"""


# ==========================================
# Happy Path Tests
# ==========================================

class TestBuildFunctionZipHappyPath:
    """Test successful ZIP builds for all providers."""
    
    def test_build_aws_lambda_zip(self):
        """Build valid AWS Lambda ZIP."""
        files = {"function_file": ("handler.py", io.BytesIO(VALID_AWS_FUNCTION), "text/plain")}
        
        response = client.post("/functions/build?provider=aws", files=files)
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/zip"
        assert "lambda_function.zip" in response.headers["content-disposition"]
        
        # Verify ZIP contents
        with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
            assert "lambda_function.py" in zf.namelist()
            content = zf.read("lambda_function.py")
            assert b"def handler" in content
    
    def test_build_azure_function_zip(self):
        """Build valid Azure Function ZIP."""
        files = {"function_file": ("function.py", io.BytesIO(VALID_AZURE_FUNCTION), "text/plain")}
        
        response = client.post("/functions/build?provider=azure", files=files)
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/zip"
        assert "azure_function.zip" in response.headers["content-disposition"]
        
        # Verify ZIP contents
        with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
            namelist = zf.namelist()
            assert "function_app.py" in namelist
            assert "host.json" in namelist
            assert "requirements.txt" in namelist
            
            # Check default requirements
            req_content = zf.read("requirements.txt").decode()
            assert "azure-functions" in req_content
    
    def test_build_gcp_cloud_function_zip(self):
        """Build valid GCP Cloud Function ZIP."""
        files = {"function_file": ("main.py", io.BytesIO(VALID_GCP_FUNCTION), "text/plain")}
        
        response = client.post("/functions/build?provider=google", files=files)
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/zip"
        assert "cloud_function.zip" in response.headers["content-disposition"]
        
        # Verify ZIP contents
        with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
            namelist = zf.namelist()
            assert "main.py" in namelist
            assert "requirements.txt" in namelist
            
            # Check default requirements
            req_content = zf.read("requirements.txt").decode()
            assert "functions-framework" in req_content
    
    def test_build_with_custom_requirements(self):
        """Build ZIP with custom requirements.txt."""
        files = {
            "function_file": ("handler.py", io.BytesIO(VALID_AWS_FUNCTION), "text/plain"),
            "requirements_file": ("requirements.txt", io.BytesIO(SAMPLE_REQUIREMENTS), "text/plain")
        }
        
        response = client.post("/functions/build?provider=aws", files=files)
        
        assert response.status_code == 200
        
        # Verify custom requirements included
        with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
            req_content = zf.read("requirements.txt").decode()
            assert "requests>=2.28.0" in req_content
            assert "boto3>=1.26.0" in req_content


# ==========================================
# Error Case Tests
# ==========================================

class TestBuildFunctionZipErrors:
    """Test error handling for invalid inputs."""
    
    def test_invalid_provider(self):
        """Reject invalid provider."""
        files = {"function_file": ("handler.py", io.BytesIO(VALID_AWS_FUNCTION), "text/plain")}
        
        response = client.post("/functions/build?provider=invalid", files=files)
        
        assert response.status_code == 400
        assert "Invalid provider" in response.json()["detail"]
    
    def test_syntax_error(self):
        """Reject file with Python syntax error."""
        files = {"function_file": ("handler.py", io.BytesIO(INVALID_SYNTAX), "text/plain")}
        
        response = client.post("/functions/build?provider=aws", files=files)
        
        assert response.status_code == 400
        assert "syntax error" in response.json()["detail"].lower()
    
    def test_missing_aws_entry_point(self):
        """Reject AWS function missing handler."""
        files = {"function_file": ("handler.py", io.BytesIO(MISSING_ENTRY_AWS), "text/plain")}
        
        response = client.post("/functions/build?provider=aws", files=files)
        
        assert response.status_code == 400
        assert "handler" in response.json()["detail"].lower()
    
    def test_missing_gcp_entry_point(self):
        """Reject GCP function missing main/handler."""
        files = {"function_file": ("main.py", io.BytesIO(MISSING_ENTRY_GCP), "text/plain")}
        
        response = client.post("/functions/build?provider=google", files=files)
        
        assert response.status_code == 400
        assert "main" in response.json()["detail"].lower() or "handler" in response.json()["detail"].lower()
    
    def test_wrong_file_extension(self):
        """Reject non-Python files."""
        files = {"function_file": ("handler.js", io.BytesIO(b"console.log('hello')"), "text/plain")}
        
        response = client.post("/functions/build?provider=aws", files=files)
        
        assert response.status_code == 400
        assert ".py" in response.json()["detail"]


# ==========================================
# Edge Case Tests
# ==========================================

class TestBuildFunctionZipEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_empty_function_file(self):
        """Reject empty file."""
        files = {"function_file": ("handler.py", io.BytesIO(EMPTY_FILE), "text/plain")}
        
        response = client.post("/functions/build?provider=aws", files=files)
        
        assert response.status_code == 400
        detail = response.json()["detail"].lower()
        # Empty file could fail on "empty" check or "syntax error" (empty parse)
        assert "empty" in detail or "syntax" in detail or "handler" in detail
    
    def test_aws_with_lambda_handler_name(self):
        """Accept lambda_handler as entry point for AWS."""
        code = b"""
def lambda_handler(event, context):
    return {"statusCode": 200}
"""
        files = {"function_file": ("handler.py", io.BytesIO(code), "text/plain")}
        
        response = client.post("/functions/build?provider=aws", files=files)
        
        assert response.status_code == 200
    
    def test_gcp_with_handler_name(self):
        """Accept handler as entry point for GCP."""
        code = b"""
def handler(request):
    return "OK", 200
"""
        files = {"function_file": ("main.py", io.BytesIO(code), "text/plain")}
        
        response = client.post("/functions/build?provider=google", files=files)
        
        assert response.status_code == 200
    
    def test_provider_case_insensitive(self):
        """Provider name should be case-insensitive."""
        files = {"function_file": ("handler.py", io.BytesIO(VALID_AWS_FUNCTION), "text/plain")}
        
        response = client.post("/functions/build?provider=AWS", files=files)
        
        assert response.status_code == 200
    
    def test_azure_accepts_any_function(self):
        """Azure should accept any function since it uses decorators."""
        code = b"""
def my_custom_function(req):
    return "Custom function"
"""
        files = {"function_file": ("function.py", io.BytesIO(code), "text/plain")}
        
        response = client.post("/functions/build?provider=azure", files=files)
        
        assert response.status_code == 200
    
    def test_missing_required_provider_param(self):
        """Missing provider should return 422."""
        files = {"function_file": ("handler.py", io.BytesIO(VALID_AWS_FUNCTION), "text/plain")}
        
        response = client.post("/functions/build", files=files)
        
        assert response.status_code == 422  # FastAPI validation error
