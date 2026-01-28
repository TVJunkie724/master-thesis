"""
Integration tests for /validate/zip/extract endpoint.

Tests the full extraction flow including:
- Mode A (Wizard Step 3) with context injection
- Mode B (Full Import) with credentials
- Error handling for invalid ZIPs
- GLB base64 encoding
"""
import pytest
import io
import zipfile
import json
from fastapi.testclient import TestClient

# Import the FastAPI app from rest_api
import rest_api

client = TestClient(rest_api.app)


def create_test_zip(files: dict[str, str | bytes]) -> bytes:
    """Create a test ZIP file in memory."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for filename, content in files.items():
            if isinstance(content, bytes):
                zf.writestr(filename, content)
            else:
                zf.writestr(filename, content.encode('utf-8'))
    return buffer.getvalue()


# ==========================================
# Happy Path Tests
# ==========================================

class TestExtractionHappyPaths:
    """Test successful extraction scenarios."""
    
    def test_mode_a_valid_zip_extracts_files(self):
        """Mode A: Valid zip with context returns extracted files."""
        zip_bytes = create_test_zip({
            "config.json": '{"digital_twin_name": "test", "hot_storage_size_in_days": 7, "cold_storage_size_in_days": 30}',
            "config_events.json": '[{"id": "event1"}]',
            "config_iot_devices.json": '[{"id": "device-1"}]',
            "config_providers.json": '{"layer_2_provider": "aws"}',
            "config_optimization.json": '{"result": {"inputParamsUsed": {}}}',
            "config_credentials.json": '{"aws": {"key": "secret"}}',  # Should NOT be returned
            "lambda_functions/processors/device-1/lambda_function.py": 'def lambda_handler(event, context): pass',
        })
        
        context = json.dumps({
            "l2_provider": "aws",
            "skip_credentials": True
        })
        
        response = client.post(
            "/validate/zip/extract",
            files={"file": ("test.zip", zip_bytes, "application/zip")},
            params={"validation_context": context}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify structure
        assert "files" in data
        assert "functions" in data
        assert "validation_errors" in data
        
        # Verify config files extracted
        assert data["files"]["config.json"]["exists"] == True
        assert "digital_twin_name" in data["files"]["config.json"]["content"]
        
        # Verify credentials NOT returned (skip_credentials=True)
        assert "config_credentials.json" not in data["files"]
        
        # Verify processor extracted
        assert "device-1" in data["functions"]["processors"]
        assert data["functions"]["processors"]["device-1"]["exists"] == True
    
    def test_mode_b_includes_credentials(self):
        """Mode B: With include_credentials=true, credentials are returned."""
        zip_bytes = create_test_zip({
            "config.json": '{"digital_twin_name": "test", "hot_storage_size_in_days": 7, "cold_storage_size_in_days": 30}',
            "config_providers.json": '{"layer_2_provider": "aws"}',
            "config_optimization.json": '{"result": {"inputParamsUsed": {}}}',
            "config_iot_devices.json": '[]',
            "config_events.json": '[]',
            "config_credentials.json": '{"aws": {"key": "secret"}}',
        })
        
        response = client.post(
            "/validate/zip/extract",
            files={"file": ("test.zip", zip_bytes, "application/zip")},
            params={"include_credentials": True}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify credentials ARE returned
        assert "config_credentials.json" in data["files"]
        assert data["files"]["config_credentials.json"]["exists"] == True


# ==========================================
# Error Tests
# ==========================================

class TestExtractionErrors:
    """Test error handling scenarios."""
    
    def test_corrupted_zip_returns_400(self):
        """Corrupted ZIP file returns 400 error."""
        response = client.post(
            "/validate/zip/extract",
            files={"file": ("test.zip", b"not a zip file", "application/zip")}
        )
        
        assert response.status_code == 400
        assert "Invalid or corrupted ZIP" in response.json()["detail"]
    
    def test_invalid_context_json_returns_422(self):
        """Invalid JSON in validation_context returns 422."""
        zip_bytes = create_test_zip({
            "config.json": '{"digital_twin_name": "test"}'
        })
        
        response = client.post(
            "/validate/zip/extract",
            files={"file": ("test.zip", zip_bytes, "application/zip")},
            params={"validation_context": "not valid json"}
        )
        
        assert response.status_code == 422
        assert "Invalid JSON" in response.json()["detail"]


# ==========================================
# Edge Case Tests
# ==========================================

class TestExtractionEdgeCases:
    """Test edge cases and security scenarios."""
    
    def test_zip_slip_rejected(self):
        """ZIP with path traversal (Zip Slip) is rejected."""
        # Create a malicious ZIP with path traversal
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as zf:
            zf.writestr("../../../etc/passwd", "malicious content")
        
        response = client.post(
            "/validate/zip/extract",
            files={"file": ("evil.zip", buffer.getvalue(), "application/zip")}
        )
        
        assert response.status_code == 400
        assert "Unsafe path" in response.json()["detail"]
    
    def test_glb_extracted_as_base64(self):
        """GLB binary file is extracted as base64."""
        # Fake GLB content
        glb_content = b'\x67\x6c\x54\x46\x02\x00\x00\x00'  # glTF magic bytes
        
        zip_bytes = create_test_zip({
            "config.json": '{"digital_twin_name": "test", "hot_storage_size_in_days": 7, "cold_storage_size_in_days": 30}',
            "config_providers.json": '{"layer_2_provider": "aws"}',
            "config_optimization.json": '{"result": {"inputParamsUsed": {}}}',
            "config_iot_devices.json": '[]',
            "config_events.json": '[]',
            "config_credentials.json": '{}',
            "scene_assets/scene.glb": glb_content,
        })
        
        response = client.post(
            "/validate/zip/extract",
            files={"file": ("test.zip", zip_bytes, "application/zip")}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify GLB extracted
        assert data["assets"]["scene_glb"] is not None
        assert data["assets"]["scene_glb"]["exists"] == True
        assert data["assets"]["scene_glb"]["is_binary"] == True
        
        # Verify base64 encoded
        import base64
        decoded = base64.b64decode(data["assets"]["scene_glb"]["content"])
        assert decoded == glb_content
    
    def test_empty_zip_returns_errors(self):
        """Empty ZIP returns validation errors."""
        zip_bytes = create_test_zip({})
        
        response = client.post(
            "/validate/zip/extract",
            files={"file": ("empty.zip", zip_bytes, "application/zip")}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have validation errors for missing files
        assert data["success"] == False
        assert len(data["validation_errors"]) > 0
    
    def test_azure_functions_extracted(self):
        """Azure function_app.py files are correctly extracted."""
        zip_bytes = create_test_zip({
            "config.json": '{"digital_twin_name": "test", "hot_storage_size_in_days": 7, "cold_storage_size_in_days": 30}',
            "config_providers.json": '{"layer_2_provider": "azure"}',
            "config_optimization.json": '{"result": {"inputParamsUsed": {}}}',
            "config_iot_devices.json": '[{"id": "sensor-1"}]',
            "config_events.json": '[]',
            "config_credentials.json": '{}',
            "azure_functions/processors/sensor-1/function_app.py": 'def main(req): return "OK"',
        })
        
        context = json.dumps({"l2_provider": "azure"})
        
        response = client.post(
            "/validate/zip/extract",
            files={"file": ("test.zip", zip_bytes, "application/zip")},
            params={"validation_context": context}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify Azure processor extracted
        assert "sensor-1" in data["functions"]["processors"]
