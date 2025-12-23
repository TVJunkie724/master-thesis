"""
Unit tests for processor function name rewriting in package_builder.

Tests the _rewrite_azure_function_names function.
Note: GCP and AWS renaming functions were removed as Terraform handles naming.
"""

import pytest
from pathlib import Path

from src.providers.terraform.package_builder import (
    _rewrite_azure_function_names,
)


class TestAzureFunctionNameRewriting:
    """Test suite for Azure function name rewriting."""
    
    def test_rewrite_route_decorator(self):
        """Test rewriting @bp.route() decorator."""
        content = '''
@bp.route(route="old-processor-name", auth_level=func.AuthLevel.FUNCTION)
@bp.function_name("old-processor-name")
def main(req: func.HttpRequest) -> func.HttpResponse:
    pass
'''
        result = _rewrite_azure_function_names(content, "my-twin", "temp-sensor-1")
        
        assert '@bp.route(route="my-twin-temp-sensor-1-processor"' in result
        assert '@bp.function_name("my-twin-temp-sensor-1-processor")' in result
        assert 'old-processor-name' not in result
    
    def test_rewrite_function_name_decorator(self):
        """Test rewriting @bp.function_name() decorator."""
        content = '''
@bp.function_name("default-processor")
def processor(req: func.HttpRequest) -> func.HttpResponse:
    pass
'''
        result = _rewrite_azure_function_names(content, "factory-twin", "pressure-sensor-1")
        
        assert '@bp.function_name("factory-twin-pressure-sensor-1-processor")' in result
        assert 'default-processor' not in result
    
    def test_preserves_other_content(self):
        """Test that other content is preserved."""
        content = '''
import azure.functions as func
from azure.functions import Blueprint

bp = Blueprint()

@bp.route(route="processor", auth_level=func.AuthLevel.FUNCTION)
@bp.function_name("processor")
def main(req: func.HttpRequest) -> func.HttpResponse:
    # Process data
    return func.HttpResponse("OK", status_code=200)
'''
        result = _rewrite_azure_function_names(content, "twin", "device-1")
        
        # Check imports are preserved
        assert 'import azure.functions as func' in result
        assert 'from azure.functions import Blueprint' in result
        
        # Check function body is preserved
        assert '# Process data' in result
        assert 'return func.HttpResponse("OK", status_code=200)' in result
    
    def test_multiple_functions(self):
        """Test rewriting when there are multiple functions (should rewrite all)."""
        content = '''
@bp.route(route="processor1", auth_level=func.AuthLevel.FUNCTION)
@bp.function_name("processor1")
def func1(req):
    pass

@bp.route(route="processor2", auth_level=func.AuthLevel.FUNCTION)
@bp.function_name("processor2")
def func2(req):
    pass
'''
        result = _rewrite_azure_function_names(content, "twin", "device")
        
        # Both should be rewritten to the same name (device ID determines the name)
        assert result.count('twin-device-processor') >= 2


# NOTE: TestGCPFunctionNameRewriting and TestAWSLambdaNameRewriting removed
# because those renaming functions were removed - Terraform handles naming.


class TestEdgeCases:
    """Test edge cases for Azure rewriting function."""
    
    def test_azure_empty_content(self):
        """Test Azure rewriting with empty content."""
        result = _rewrite_azure_function_names("", "twin", "device")
        assert result == ""
    
    def test_azure_no_matches(self):
        """Test Azure rewriting when there are no matches."""
        content = "# Just a comment"
        result = _rewrite_azure_function_names(content, "twin", "device")
        assert result == content
    
    def test_special_characters_in_names(self):
        """Test rewriting with special characters in twin/device names."""
        azure_content = '@bp.route(route="old", auth_level=func.AuthLevel.FUNCTION)'
        azure_result = _rewrite_azure_function_names(azure_content, "my-twin-123", "device_1")
        assert 'my-twin-123-device_1-processor' in azure_result

