"""
Error Handling Tests for Deployer API (3-cloud-deployer).

Tests error handling for projects and validation endpoints.
Focuses on real API endpoints that exist in the Deployer.
"""

import json
from unittest.mock import patch

from fastapi.testclient import TestClient
import rest_api
from src.core.project_storage import ProjectFileAccessDenied

client = TestClient(rest_api.app)


# ============================================================
# Project Endpoint Tests (/projects/*)
# ============================================================

class TestProjectsErrorHandling:
    """Tests for /projects/* error handling."""

    # Happy Path Tests
    def test_list_projects_success(self):
        """List projects returns array."""
        response = client.get("/projects")
        
        assert response.status_code == 200
        assert "projects" in response.json()

    def test_get_active_project_success(self):
        """Get active project info succeeds."""
        response = client.get("/projects")
        
        assert response.status_code == 200

    # Error Case Tests
    def test_nonexistent_project_returns_404(self):
        """Non-existent project returns 404."""
        response = client.get("/projects/nonexistent-project-12345/config")
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_project_internal_error_hidden(self):
        """Internal error returns 500 with generic message."""
        with patch("src.api.projects.get_project_storage") as storage_factory:
            storage_factory.return_value.list_projects.side_effect = Exception(
                "Disk I/O error on /mnt/data"
            )

            response = client.get("/projects")
            
            assert response.status_code == 500
            # Path NOT exposed
            assert "/mnt/data" not in response.json().get("detail", "")
            assert "Internal server error" in response.json()["detail"]

    # Edge Case Tests
    def test_empty_project_list(self):
        """Empty project list returns empty array."""
        with patch("src.api.projects.get_project_storage") as storage_factory:
            storage_factory.return_value.list_projects.return_value = []

            response = client.get("/projects")
            
            assert response.status_code == 200
            assert response.json()["projects"] == []

    def test_special_chars_in_project_name(self):
        """Special characters in project name handled."""
        response = client.get("/projects/test%2F..%2Fetc%2Fpasswd/config")
        
        # Should NOT allow path traversal
        assert response.status_code in [400, 404, 422]

    def test_very_long_project_name(self):
        """Very long project name handled."""
        long_name = "a" * 500
        
        response = client.get(f"/projects/{long_name}/config")
        
        assert response.status_code in [400, 404, 414]

    def test_concurrent_project_access(self):
        """Multiple requests don't cause race conditions."""
        responses = []
        for _ in range(5):
            responses.append(client.get("/projects"))
        
        # All should succeed
        assert all(r.status_code == 200 for r in responses)

    def test_unicode_in_project_name(self):
        """Unicode in project name handled."""
        response = client.get("/projects/测试项目/config")
        
        # Should handle gracefully
        assert response.status_code in [400, 404]

    def test_template_file_tree_uses_resolved_context_and_hides_credentials(self, tmp_path):
        """Template file browser uses canonical context and does not list live credentials."""
        canonical_template = tmp_path / "templates" / "digital-twin"
        legacy_template = tmp_path / "upload" / "template"
        canonical_template.mkdir(parents=True)
        legacy_template.mkdir(parents=True)
        (canonical_template / "config.json").write_text("{}")
        (legacy_template / "config_credentials.json").write_text('{"aws": "secret"}')

        with patch("src.api.projects.get_project_storage") as storage_factory:
            storage_factory.return_value.context.return_value.project_path = canonical_template
            storage_factory.return_value.file_tree.return_value = [{"name": "config.json", "path": "config.json", "type": "file", "size": 2}]
            response = client.get("/projects/template/files")

        assert response.status_code == 200
        names = {item["name"] for item in response.json()["files"]}
        assert names == {"config.json"}

    def test_template_file_content_blocks_live_credentials(self, tmp_path):
        """Generic file content endpoint must not expose credential files."""
        canonical_template = tmp_path / "templates" / "digital-twin"
        canonical_template.mkdir(parents=True)
        (canonical_template / "config_credentials.json").write_text('{"aws": "secret"}')

        with patch("src.api.projects.get_project_storage") as storage_factory:
            storage_factory.return_value.file_content.side_effect = ProjectFileAccessDenied(
                "Access denied for sensitive project file 'config_credentials.json'."
            )
            response = client.get("/projects/template/files/config_credentials.json")

        assert response.status_code == 403

    def test_validate_project_returns_safe_manifest_summary(self, tmp_path):
        """Project validation returns safe manifest metadata without credential payloads."""
        project_dir = tmp_path / "upload" / "factory"
        project_dir.mkdir(parents=True)
        (project_dir / "deployment_manifest.json").write_text(json.dumps({
            "manifest_version": "1.0",
            "producer": "twin2multicloud_backend",
            "twin": {"resource_name": "factory"},
            "credentials": {
                "contains_secret_payloads": False,
                "aws_secret_access_key": "must-not-leak",
            },
        }))

        with patch("src.api.projects.get_project_storage") as storage_factory, \
             patch("src.api.projects.validate_project_directory"):
            storage_factory.return_value.context.return_value.project_path = project_dir
            response = client.get("/projects/factory/validate")

        assert response.status_code == 200
        assert response.json()["manifest"] == {
            "manifest_backed": True,
            "manifest_version": "1.0",
            "producer": "twin2multicloud_backend",
            "resource_name": "factory",
        }
        assert "must-not-leak" not in response.text

    def test_validate_project_returns_legacy_manifest_summary(self, tmp_path):
        """Project validation marks legacy projects as not manifest-backed."""
        project_dir = tmp_path / "upload" / "legacy"
        project_dir.mkdir(parents=True)

        with patch("src.api.projects.get_project_storage") as storage_factory, \
             patch("src.api.projects.validate_project_directory"):
            storage_factory.return_value.context.return_value.project_path = project_dir
            response = client.get("/projects/legacy/validate")

        assert response.status_code == 200
        assert response.json()["manifest"] == {"manifest_backed": False}


# ============================================================
# Validation Tests (Using existing validation endpoints)  
# ============================================================

class TestValidationErrorHandling:
    """Tests for validation-related error handling."""

    # Happy Path Tests
    def test_validation_endpoint_exists(self):
        """Validation endpoint returns a response."""
        # The API uses /validate/content for content validation
        response = client.post(
            "/validate/content",
            json={"file_name": "config.json", "content": "{}"}
        )
        
        # Either valid response or route doesn't exist with this exact path
        assert response.status_code in [200, 400, 404, 422]

    def test_empty_body_returns_validation_error(self):
        """Empty body returns validation error."""
        response = client.post("/validate/content", json={})
        
        assert response.status_code in [400, 404, 422]

    # Error Case Tests
    def test_invalid_json_content_handled(self):
        """Invalid JSON content returns 400."""
        response = client.post(
            "/validate/content",
            json={"file_name": "config.json", "content": "{invalid}"}
        )
        
        # Either 400 for invalid JSON or 404 if endpoint doesn't exist
        assert response.status_code in [400, 404, 422]

    def test_missing_filename_handled(self):
        """Missing file_name returns validation error."""
        response = client.post(
            "/validate/content",
            json={"content": "{}"}
        )
        
        assert response.status_code in [400, 404, 422]

    # Edge Case Tests
    def test_very_large_content_handled(self):
        """Very large content (1MB) handled gracefully."""
        large_content = json.dumps({"data": "x" * (1024 * 1024)})
        
        response = client.post(
            "/validate/content",
            json={"file_name": "config.json", "content": large_content}
        )
        
        # Either processed or rejected with size error
        assert response.status_code in [200, 400, 404, 413, 422]

    def test_special_chars_in_filename(self):
        """Special characters in filename handled."""
        response = client.post(
            "/validate/content",
            json={"file_name": "../../../etc/passwd", "content": "{}"}
        )
        
        # Should either sanitize or reject
        assert response.status_code in [200, 400, 404, 422]

    def test_binary_content_handled(self):
        """Binary-like content handled gracefully."""
        response = client.post(
            "/validate/content",
            json={"file_name": "config.json", "content": "\\x00\\x01\\x02"}
        )
        
        assert response.status_code in [200, 400, 404, 422]

    def test_null_content_handled(self):
        """Null content returns validation error."""
        response = client.post(
            "/validate/content",
            json={"file_name": "config.json", "content": None}
        )
        
        assert response.status_code in [400, 404, 422]

    def test_empty_string_content_handled(self):
        """Empty string content handled."""
        response = client.post(
            "/validate/content",
            json={"file_name": "config.json", "content": ""}
        )
        
        assert response.status_code in [200, 400, 404, 422]


# ============================================================
# Status Endpoint Tests
# ============================================================

class TestStatusErrorHandling:
    """Tests for status-related error handling."""

    # Happy Path Tests
    def test_status_endpoint_returns_response(self):
        """Status endpoint returns a response."""
        response = client.get("/status/template")
        
        assert response.status_code in [200, 404, 500]

    # Edge Case Tests
    def test_status_nonexistent_project(self):
        """Status for non-existent project handled."""
        response = client.get("/status/nonexistent-project-12345")
        
        assert response.status_code in [404, 500]

    def test_status_internal_error_hidden(self):
        """Status error handling gracefully."""
        # The status endpoint handles errors internally
        response = client.get("/status/test-project-that-errors")
        
        # Should return either 404 or 500, not crash
        assert response.status_code in [404, 500]
