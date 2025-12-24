"""
Tests for duplicate Azure function name validation in azure_bundler.

Ensures that the bundler detects and rejects ZIP bundles where multiple
functions declare the same Azure function name.
"""
import pytest
from pathlib import Path

from src.providers.azure.azure_bundler import (
    _extract_function_names,
    _validate_no_duplicate_function_names,
    BundleError,
)


class TestExtractFunctionNames:
    """Tests for _extract_function_names helper."""

    def test_extracts_bp_function_name(self):
        """Extracts function names from Blueprint decorator."""
        content = '@bp.function_name(name="my-function")'
        assert _extract_function_names(content) == ["my-function"]

    def test_extracts_app_function_name(self):
        """Extracts function names from FunctionApp decorator."""
        content = '@app.function_name(name="my-function")'
        assert _extract_function_names(content) == ["my-function"]

    def test_extracts_multiple_function_names(self):
        """Extracts multiple function names from same file."""
        content = '''
@bp.function_name(name="func-a")
def handler_a(): pass

@bp.function_name(name="func-b")
def handler_b(): pass
'''
        names = _extract_function_names(content)
        assert names == ["func-a", "func-b"]

    def test_handles_single_quotes(self):
        """Extracts function names with single quotes."""
        content = "@bp.function_name(name='my-function')"
        assert _extract_function_names(content) == ["my-function"]

    def test_handles_extra_whitespace(self):
        """Handles whitespace in decorator."""
        content = '@bp.function_name( name = "my-function" )'
        assert _extract_function_names(content) == ["my-function"]

    def test_returns_empty_for_no_functions(self):
        """Returns empty list when no function names found."""
        content = "import azure.functions as func\nprint('hello')"
        assert _extract_function_names(content) == []


class TestValidateNoDuplicateFunctionNames:
    """Tests for _validate_no_duplicate_function_names."""

    def test_passes_with_unique_names(self):
        """No error when all function names are unique."""
        processed = {
            "module_a": '@bp.function_name(name="func-a")',
            "module_b": '@bp.function_name(name="func-b")',
            "module_c": '@bp.function_name(name="func-c")',
        }
        # Should not raise
        _validate_no_duplicate_function_names([], processed)

    def test_raises_on_duplicate_names(self):
        """Raises BundleError when duplicate function names detected."""
        processed = {
            "module_a": '@bp.function_name(name="same-name")',
            "module_b": '@bp.function_name(name="same-name")',
        }
        with pytest.raises(BundleError) as exc_info:
            _validate_no_duplicate_function_names([], processed)
        
        error_msg = str(exc_info.value)
        assert "Duplicate Azure function names detected" in error_msg
        assert "same-name" in error_msg
        assert "module_a" in error_msg
        assert "module_b" in error_msg

    def test_identifies_all_duplicates(self):
        """Reports all duplicate pairs, not just the first."""
        processed = {
            "module_a": '@bp.function_name(name="dup1")',
            "module_b": '@bp.function_name(name="dup1")',
            "module_c": '@bp.function_name(name="dup2")',
            "module_d": '@bp.function_name(name="dup2")',
        }
        with pytest.raises(BundleError) as exc_info:
            _validate_no_duplicate_function_names([], processed)
        
        error_msg = str(exc_info.value)
        assert "dup1" in error_msg
        assert "dup2" in error_msg

    def test_passes_with_empty_contents(self):
        """No error when no functions to validate."""
        _validate_no_duplicate_function_names([], {})

    def test_realistic_event_feedback_duplicate(self):
        """Catches the real-world bug: event-feedback with callback-2 name."""
        # This was the actual bug found in the template
        processed = {
            "event_feedback": '@bp.function_name(name="high-temperature-callback-2")',
            "high_temperature_callback_2": '@bp.function_name(name="high-temperature-callback-2")',
        }
        with pytest.raises(BundleError) as exc_info:
            _validate_no_duplicate_function_names([], processed)
        
        error_msg = str(exc_info.value)
        assert "high-temperature-callback-2" in error_msg
        assert "event_feedback" in error_msg
        assert "high_temperature_callback_2" in error_msg
