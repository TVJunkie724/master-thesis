"""
Shared test configuration and fixtures for API tests.

This file provides automatic cleanup of test artifacts created during testing.
"""
import pytest
import os
import shutil

import src.core.state as state


# Test project prefixes that will be cleaned up automatically
TEST_PREFIXES = ["test_", "test-", "test_api_", "test_rest_"]


@pytest.fixture(autouse=True)
def cleanup_test_projects():
    """
    Automatically clean up test projects before and after each test.
    
    This fixture runs for EVERY test in tests/api/ directory.
    It removes any folders in the upload directory that start with test prefixes.
    """
    # Reset state before test
    state.reset_state()
    
    # Get upload path
    upload_path = state.get_project_upload_path()
    
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
    
    # Cleanup after test
    state.reset_state()
    cleanup()
