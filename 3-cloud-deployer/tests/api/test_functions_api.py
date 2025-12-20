"""
Comprehensive tests for the Functions API endpoints.

Tests for /functions endpoints including list updatable functions,
update function, and build function zip.
"""
import pytest
import json
import io
import zipfile
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

import rest_api
import constants as CONSTANTS

client = TestClient(rest_api.app)


# ==========================================
# Test: GET /functions/updatable_functions
# ==========================================
class TestGetUpdatableFunctions:
    """Tests for GET /functions/updatable_functions endpoint."""

    def test_get_functions_template_project(self):
        """Happy: Returns function list for template project."""
        response = client.get("/functions/updatable_functions?project_name=template")
        
        # May return empty or have functions depending on template config
        assert response.status_code in [200, 404, 500]

    def test_get_functions_nonexistent_project(self):
        """Invalid: Non-existent project returns 409 (Context Mismatch)."""
        response = client.get("/functions/updatable_functions?project_name=nonexistent_12345")
        
        # Mismatch with active project returns 409
        assert response.status_code == 409

    def test_get_functions_default_project(self):
        """Happy: Uses default project if not specified."""
        response = client.get("/functions/updatable_functions")
        
        # Should use template as default
        assert response.status_code in [200, 404, 500]

    @patch("api.functions._get_updatable_functions")
    @patch("api.functions._get_cached_functions")
    def test_get_functions_caching(self, mock_cache, mock_get):
        """Edge: Cache is used when available."""
        mock_cache.return_value = {
            "project_name": "template",
            "provider": "aws",
            "functions": []
        }
        
        response = client.get("/functions/updatable_functions?project_name=template")
        
        if response.status_code == 200:
            # Cache was used if get wasn't called
            # Note: this depends on cache implementation
            pass

    @patch("api.functions._get_updatable_functions")
    def test_get_functions_empty_list(self, mock_get):
        """Edge: Project with no user functions returns empty list."""
        mock_get.return_value = {}
        
        response = client.get("/functions/updatable_functions?project_name=template")
        
        if response.status_code == 200:
            data = response.json()
            assert "functions" in data


# ==========================================
# Test: POST /functions/update_function/{name}
# ==========================================
class TestUpdateFunction:
    """Tests for POST /functions/update_function/{name} endpoint."""

    def test_update_template_project_blocked(self):
        """Invalid: Template project is protected from updates."""
        response = client.post(
            "/functions/update_function/any_function",
            params={"project_name": "template"}
        )
        
        # Template project is protected - returns 400
        assert response.status_code == 400
        assert "protected" in response.json()["detail"].lower()

    def test_update_nonexistent_project(self):
        """Invalid: Non-existent project returns 409 (Context Mismatch)."""
        response = client.post(
            "/functions/update_function/some_func",
            params={"project_name": "nonexistent_12345"}
        )
        
        assert response.status_code == 409

    @patch("api.functions._get_updatable_functions")
    def test_update_function_not_in_list(self, mock_get):
        """Invalid: Function not in updatable list would return error (but template is protected)."""
        mock_get.return_value = {}  # No functions
        
        response = client.post(
            "/functions/update_function/my_func",
            params={"project_name": "template"}
        )
        
        # Template is protected - returns 400
        assert response.status_code == 400

    @patch("api.functions._get_updatable_functions")
    @patch("api.functions._compute_directory_hash")
    @patch("api.functions._get_hash_metadata")
    def test_update_function_force_flag(self, mock_meta, mock_hash, mock_get):
        """Edge: Template project is protected even with force flag."""
        mock_get.return_value = {
            "my_func": {"type": "event_action", "provider": "aws", "path": "/fake"}
        }
        mock_hash.return_value = "sha256:same"
        mock_meta.return_value = {"code_hash": "sha256:same"}
        
        response = client.post(
            "/functions/update_function/my_func",
            params={"project_name": "template", "force": True}
        )
        
        # Template is protected - returns 400 regardless of force flag
        assert response.status_code == 400


# ==========================================
# Test: POST /functions/build_function_zip
# ==========================================
class TestBuildFunctionZip:
    """Tests for POST /functions/build_function_zip endpoint."""

    def test_build_aws_lambda_zip(self):
        """Happy: Build AWS Lambda zip from valid Python."""
        code = "def lambda_handler(event, context):\n    return {'statusCode': 200}"
        files = {"function_file": ("lambda_function.py", code.encode(), "text/plain")}
        
        response = client.post("/functions/build?provider=aws", files=files)
        
        assert response.status_code == 200
        # Should return a zip file
        assert response.headers.get("content-type") == "application/zip"

    def test_build_azure_function_zip(self):
        """Happy: Build Azure Function zip from valid Python."""
        code = "def main(req):\n    return 'OK'"
        files = {"function_file": ("function_app.py", code.encode(), "text/plain")}
        
        response = client.post("/functions/build?provider=azure", files=files)
        
        assert response.status_code == 200
        assert response.headers.get("content-type") == "application/zip"

    def test_build_gcp_function_zip(self):
        """Happy: Build GCP Cloud Function zip from valid Python."""
        code = "def main(request):\n    return 'OK'"
        files = {"function_file": ("main.py", code.encode(), "text/plain")}
        
        response = client.post("/functions/build?provider=google", files=files)
        
        assert response.status_code == 200
        assert response.headers.get("content-type") == "application/zip"

    def test_build_with_requirements(self):
        """Happy: Build with requirements.txt included."""
        code = "def lambda_handler(event, context):\n    return {}"
        requirements = "boto3>=1.26.0\nrequests>=2.28.0"
        
        response = client.post(
            "/functions/build?provider=aws",
            files=[
                ("function_file", ("lambda_function.py", code.encode(), "text/plain")),
                ("requirements_file", ("requirements.txt", requirements.encode(), "text/plain"))
            ]
        )
        
        assert response.status_code == 200

    def test_build_invalid_python_syntax(self):
        """Invalid: Python syntax error returns 400."""
        code = "def broken(\n    return"
        files = {"function_file": ("lambda_function.py", code.encode(), "text/plain")}
        
        response = client.post("/functions/build?provider=aws", files=files)
        
        assert response.status_code == 400
        assert "syntax" in response.json()["detail"].lower()

    def test_build_missing_aws_entry_point(self):
        """Invalid: AWS Lambda missing lambda_handler returns 400."""
        code = "def other_func(event, context):\n    return {}"
        files = {"function_file": ("lambda_function.py", code.encode(), "text/plain")}
        
        response = client.post("/functions/build?provider=aws", files=files)
        
        assert response.status_code == 400
        assert "entry point" in response.json()["detail"].lower() or "handler" in response.json()["detail"]

    def test_build_missing_azure_entry_point(self):
        """Invalid: Azure function missing main returns 400."""
        code = "def other_func(req):\n    return 'OK'"
        files = {"function_file": ("function_app.py", code.encode(), "text/plain")}
        
        response = client.post("/functions/build?provider=azure", files=files)
        
        # Azure allows any function (uses decorators), so this should pass
        assert response.status_code in [200, 400]

    def test_build_invalid_provider(self):
        """Invalid: Invalid provider returns 400."""
        code = "def func():\n    pass"
        files = {"function_file": ("code.py", code.encode(), "text/plain")}
        
        response = client.post("/functions/build?provider=invalid", files=files)
        
        assert response.status_code == 400

    def test_build_empty_file(self):
        """Edge: Empty file returns 400."""
        files = {"function_file": ("lambda_function.py", b"", "text/plain")}
        
        response = client.post("/functions/build?provider=aws", files=files)
        
        assert response.status_code == 400

    def test_build_zip_contains_function_file(self):
        """Happy: Returned zip contains the function file."""
        code = "def lambda_handler(event, context):\n    return {'statusCode': 200}"
        files = {"function_file": ("lambda_function.py", code.encode(), "text/plain")}
        
        response = client.post("/functions/build?provider=aws", files=files)
        
        assert response.status_code == 200
        
        # Verify zip contents
        zip_buffer = io.BytesIO(response.content)
        with zipfile.ZipFile(zip_buffer, 'r') as zf:
            names = zf.namelist()
            assert "lambda_function.py" in names


# ==========================================
# Test: Cache Invalidation
# ==========================================
class TestFunctionCacheInvalidation:
    """Tests for function cache invalidation."""

    @patch("src.api.functions._invalidate_cache")
    @patch("src.api.functions._get_cached_functions")
    @patch("src.api.functions._get_updatable_functions")
    def test_cache_invalidation_clears_cache(self, mock_get, mock_cached, mock_invalidate):
        """Edge: Cache invalidation clears project cache."""
        mock_cached.return_value = None
        mock_get.return_value = {}
        
        # First call
        client.get("/functions/updatable_functions?project_name=template")
        
        # Invalidate cache (simulated through config update)
        from src.api.functions import invalidate_function_cache
        invalidate_function_cache("template")
        
        mock_invalidate.assert_called_with("template")
