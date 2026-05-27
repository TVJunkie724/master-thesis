"""
Shared test configuration and fixtures for API tests.

This file provides automatic cleanup of test artifacts created during testing.
"""
import pytest
import os
import shutil

from src.core.paths import get_upload_root


# Test project prefixes that will be cleaned up automatically
TEST_PREFIXES = ["test_", "test-", "test_api_", "test_rest_"]


@pytest.fixture(autouse=True)
def cleanup_test_projects():
    """
    Automatically clean up test projects before and after each test.
    
    This fixture runs for EVERY test in tests/api/ directory.
    It removes any folders in the upload directory that start with test prefixes.
    """
    # Get upload path
    upload_path = os.fspath(get_upload_root())
    
    def cleanup():
        """Remove all test-prefixed project folders."""
        if not os.path.exists(upload_path):
            return
        for item in os.listdir(upload_path):
            item_path = os.path.join(upload_path, item)
            if os.path.isdir(item_path):
                for prefix in TEST_PREFIXES:
                    if item.startswith(prefix):
                        shutil.rmtree(item_path, ignore_errors=True)
                        break
    
    # Cleanup before test
    cleanup()
    
    yield
    
    cleanup()
