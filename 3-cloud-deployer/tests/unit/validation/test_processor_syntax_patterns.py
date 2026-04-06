"""
Unit tests for check_processor_syntax() with updated file patterns.

Tests that validation correctly identifies:
- AWS: lambda_functions/processors/*/lambda_function.py with lambda_handler()
- Azure: azure_functions/processors/*/function_app.py with main()
- GCP: cloud_functions/processors/*/main.py with process()

Tests the fix from Phase 0 of the Zip Upload implementation plan.
"""
import pytest
from unittest.mock import MagicMock
from src.validation.core import (
    check_processor_syntax,
    _validate_entry_point_signature,
    ValidationContext,
    FileAccessor,
)


class MockAccessor:
    """Mock FileAccessor for testing."""
    
    def __init__(self, files: dict[str, str]):
        self._files = files
    
    def list_files(self) -> list[str]:
        return list(self._files.keys())
    
    def file_exists(self, path: str) -> bool:
        return path in self._files
    
    def read_text(self, path: str) -> str:
        if path not in self._files:
            raise FileNotFoundError(path)
        return self._files[path]
    
    def get_project_root(self) -> str:
        return ""


# ==========================================
# Happy Path Tests
# ==========================================

class TestProcessorSyntaxHappyPaths:
    """Test valid processor files pass validation."""
    
    def test_aws_lambda_function_passes(self):
        """AWS: lambda_functions/processors/device-1/lambda_function.py passes."""
        valid_aws_code = '''
def lambda_handler(event, context):
    return {"statusCode": 200, "body": "OK"}
'''
        accessor = MockAccessor({
            "lambda_functions/processors/device-1/lambda_function.py": valid_aws_code
        })
        ctx = ValidationContext()
        ctx.all_files = accessor.list_files()
        
        # Should not raise
        check_processor_syntax(accessor, ctx, l2_provider="aws")
    
    def test_azure_function_app_passes(self):
        """Azure: azure_functions/processors/device-1/function_app.py passes."""
        valid_azure_code = '''
import azure.functions as func

def main(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse("OK")
'''
        accessor = MockAccessor({
            "azure_functions/processors/device-1/function_app.py": valid_azure_code
        })
        ctx = ValidationContext()
        ctx.all_files = accessor.list_files()
        
        # Should not raise
        check_processor_syntax(accessor, ctx, l2_provider="azure")
    
    def test_gcp_main_py_passes(self):
        """GCP: cloud_functions/processors/device-1/main.py passes."""
        valid_gcp_code = '''
def main(request):
    return "OK"
'''
        accessor = MockAccessor({
            "cloud_functions/processors/device-1/main.py": valid_gcp_code
        })
        ctx = ValidationContext()
        ctx.all_files = accessor.list_files()
        
        # Should not raise
        check_processor_syntax(accessor, ctx, l2_provider="gcp")


# ==========================================
# Error Tests
# ==========================================

class TestProcessorSyntaxErrors:
    """Test invalid processor files are rejected."""
    
    def test_aws_missing_lambda_handler_fails(self):
        """AWS: Missing lambda_handler() function fails."""
        invalid_aws_code = '''
def some_other_function(event, context):
    return {"statusCode": 200}
'''
        accessor = MockAccessor({
            "lambda_functions/processors/device-1/lambda_function.py": invalid_aws_code
        })
        ctx = ValidationContext()
        ctx.all_files = accessor.list_files()
        
        with pytest.raises(ValueError, match="Missing required lambda_handler"):
            check_processor_syntax(accessor, ctx, l2_provider="aws")
    
    def test_aws_lambda_handler_wrong_params_fails(self):
        """AWS: lambda_handler() with only 1 param fails (needs event, context)."""
        invalid_aws_code = '''
def lambda_handler(event):
    return {"statusCode": 200}
'''
        accessor = MockAccessor({
            "lambda_functions/processors/device-1/lambda_function.py": invalid_aws_code
        })
        ctx = ValidationContext()
        ctx.all_files = accessor.list_files()
        
        with pytest.raises(ValueError, match="requires at least 2 parameter"):
            check_processor_syntax(accessor, ctx, l2_provider="aws")


# ==========================================
# Edge Case Tests
# ==========================================

class TestProcessorSyntaxEdgeCases:
    """Test edge cases in processor validation."""
    
    def test_old_process_py_pattern_ignored(self):
        """Old process.py pattern should NOT be validated (it's obsolete)."""
        # This file should be ignored - it's the old pattern
        old_pattern_code = '''
def process(data: dict) -> dict:
    return data
'''
        accessor = MockAccessor({
            "lambda_functions/processors/device-1/process.py": old_pattern_code
        })
        ctx = ValidationContext()
        ctx.all_files = accessor.list_files()
        
        # Should NOT raise - file is ignored (not matched by new patterns)
        check_processor_syntax(accessor, ctx, l2_provider="aws")
    
    def test_only_validates_configured_provider_folders(self):
        """When l2_provider=aws, only lambda_functions/ is validated."""
        # AWS code is valid
        valid_aws = '''
def lambda_handler(event, context):
    return {"statusCode": 200}
'''
        # GCP code in same project (should be ignored when l2=aws)
        invalid_gcp = '''
def wrong_function():
    pass
'''
        accessor = MockAccessor({
            "lambda_functions/processors/device-1/lambda_function.py": valid_aws,
            "cloud_functions/processors/device-1/main.py": invalid_gcp,
        })
        ctx = ValidationContext()
        ctx.all_files = accessor.list_files()
        
        # Should NOT raise - GCP folder ignored when l2_provider=aws
        check_processor_syntax(accessor, ctx, l2_provider="aws")
    
    def test_event_action_files_also_validated(self):
        """Event action files are also validated with correct patterns."""
        valid_aws_action = '''
def lambda_handler(event, context):
    return {"statusCode": 200, "body": "Action executed"}
'''
        accessor = MockAccessor({
            "lambda_functions/event_actions/alert-handler/lambda_function.py": valid_aws_action
        })
        ctx = ValidationContext()
        ctx.all_files = accessor.list_files()
        
        # Should not raise
        check_processor_syntax(accessor, ctx, l2_provider="aws")
    
    def test_event_feedback_files_also_validated(self):
        """Event feedback files are also validated with correct patterns."""
        valid_azure_feedback = '''
def main(req):
    return "Feedback processed"
'''
        accessor = MockAccessor({
            "azure_functions/event-feedback/function_app.py": valid_azure_feedback
        })
        ctx = ValidationContext()
        ctx.all_files = accessor.list_files()
        
        # Should not raise
        check_processor_syntax(accessor, ctx, l2_provider="azure")
    
    def test_syntax_error_in_file_raises(self):
        """Python syntax errors are caught and reported."""
        invalid_syntax = '''
def lambda_handler(event, context)
    return {"statusCode": 200}  # Missing colon above
'''
        accessor = MockAccessor({
            "lambda_functions/processors/device-1/lambda_function.py": invalid_syntax
        })
        ctx = ValidationContext()
        ctx.all_files = accessor.list_files()
        
        with pytest.raises(ValueError, match="Syntax error"):
            check_processor_syntax(accessor, ctx, l2_provider="aws")
