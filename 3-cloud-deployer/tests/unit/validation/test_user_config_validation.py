"""
Tests for platform user config validation in check_user_config_for_l4_l5().
"""

import pytest
from unittest.mock import MagicMock
from src.validation.core import check_user_config_for_l4_l5, ValidationContext


class MockAccessor:
    """Minimal mock accessor for testing."""
    
    def __init__(self):
        self.files = {}
    
    def file_exists(self, path: str) -> bool:
        return path in self.files
    
    def read_text(self, path: str) -> str:
        return self.files.get(path, "")
    
    def list_files(self):
        return list(self.files.keys())
    
    def get_project_root(self):
        return ""


class TestUserConfigValidation:
    """Tests for Azure platform user email validation."""
    
    def _make_context(self, l5_provider: str, admin_email: str = None) -> ValidationContext:
        """Helper to create a ValidationContext with user config."""
        ctx = ValidationContext()
        ctx.prov_config = {"layer_5_provider": l5_provider}
        if admin_email is not None:
            ctx.user_config = {
                "admin_email": admin_email,
                "admin_first_name": "Test",
                "admin_last_name": "User"
            }
        return ctx
    
    def test_azure_valid_onmicrosoft_domain(self):
        """Valid .onmicrosoft.com domain should pass."""
        ctx = self._make_context("azure", "admin@mytenant.onmicrosoft.com")
        accessor = MockAccessor()
        
        # Should not raise
        check_user_config_for_l4_l5(accessor, ctx)
    
    def test_azure_invalid_unverified_domain(self):
        """Non-.onmicrosoft.com domain should raise ValueError."""
        ctx = self._make_context("azure", "user@gmail.com")
        accessor = MockAccessor()
        
        with pytest.raises(ValueError) as exc_info:
            check_user_config_for_l4_l5(accessor, ctx)
        
        assert "verified domain" in str(exc_info.value)
        assert "gmail.com" in str(exc_info.value)
        assert ".onmicrosoft.com" in str(exc_info.value)
    
    def test_azure_invalid_live_domain(self):
        """live.at domain (not verified) should raise ValueError."""
        ctx = self._make_context("azure", "user@live.at")
        accessor = MockAccessor()
        
        with pytest.raises(ValueError) as exc_info:
            check_user_config_for_l4_l5(accessor, ctx)
        
        assert "live.at" in str(exc_info.value)
    
    def test_azure_empty_email_allowed(self):
        """Empty email should be allowed (skips user provisioning)."""
        ctx = self._make_context("azure", "")
        accessor = MockAccessor()
        
        # Should not raise - empty email skips user provisioning
        check_user_config_for_l4_l5(accessor, ctx)
    
    def test_azure_missing_user_config_raises(self):
        """Missing config_user.json should raise ValueError."""
        ctx = ValidationContext()
        ctx.prov_config = {"layer_5_provider": "azure"}
        ctx.user_config = {}  # Empty = missing
        accessor = MockAccessor()
        
        with pytest.raises(ValueError) as exc_info:
            check_user_config_for_l4_l5(accessor, ctx)
        
        assert "Missing config_user.json" in str(exc_info.value)
    
    def test_azure_invalid_email_format(self):
        """Invalid email format should raise ValueError."""
        ctx = self._make_context("azure", "not-an-email")
        accessor = MockAccessor()
        
        with pytest.raises(ValueError) as exc_info:
            check_user_config_for_l4_l5(accessor, ctx)
        
        assert "Invalid email format" in str(exc_info.value)
    
    def test_aws_any_email_allowed(self):
        """AWS should accept any valid email format (no domain restriction)."""
        ctx = self._make_context("aws", "user@gmail.com")
        accessor = MockAccessor()
        
        # Should not raise - AWS has no domain restriction
        check_user_config_for_l4_l5(accessor, ctx)
    
    def test_gcp_skipped(self):
        """GCP L5 should not require grafana config."""
        ctx = ValidationContext()
        ctx.prov_config = {"layer_5_provider": "google"}
        ctx.user_config = {}  # Empty - OK for GCP
        accessor = MockAccessor()
        
        # Should not raise - GCP doesn't use Grafana
        check_user_config_for_l4_l5(accessor, ctx)
    
    def test_no_l5_provider_skipped(self):
        """No L5 provider should skip validation entirely."""
        ctx = ValidationContext()
        ctx.prov_config = {"layer_5_provider": ""}
        ctx.user_config = {}
        accessor = MockAccessor()
        
        # Should not raise
        check_user_config_for_l4_l5(accessor, ctx)
