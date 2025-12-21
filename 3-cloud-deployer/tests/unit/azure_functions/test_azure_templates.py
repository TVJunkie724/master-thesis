"""
Tests for Azure Template Functions.

Tests the user-uploadable template functions in upload/template/azure_functions/.
These tests are skipped if the azure_functions directory does not exist.
"""
import pytest
import json
import sys
import os
from unittest.mock import patch, MagicMock

# Path to Azure template functions
AZURE_TEMPLATES_PATH = os.path.join(
    os.path.dirname(__file__), 
    '..', '..', '..', 'upload', 'template', 'azure_functions'
)

# Skip all tests in this module if the template directory doesn't exist
pytestmark = pytest.mark.skipif(
    not os.path.exists(AZURE_TEMPLATES_PATH),
    reason=f"Azure template directory not found: {AZURE_TEMPLATES_PATH}"
)


@pytest.fixture(autouse=True)
def setup_azure_paths():
    """Add Azure template paths to sys.path for imports."""
    original_path = sys.path.copy()
    
    # Add template directories
    event_feedback_path = os.path.join(AZURE_TEMPLATES_PATH, 'event-feedback')
    callback_path = os.path.join(AZURE_TEMPLATES_PATH, 'event_actions', 'high-temperature-callback')
    callback2_path = os.path.join(AZURE_TEMPLATES_PATH, 'event_actions', 'high-temperature-callback-2')
    processor_path = os.path.join(AZURE_TEMPLATES_PATH, 'processors', 'default_processor')
    temp_sensor_path = os.path.join(AZURE_TEMPLATES_PATH, 'processors', 'temperature-sensor-2')
    
    for path in [event_feedback_path, callback_path, callback2_path, processor_path, temp_sensor_path]:
        if path not in sys.path:
            sys.path.insert(0, path)
    
    yield
    
    # Restore original path
    sys.path[:] = original_path


class TestAzureTemplateProcessLogic:
    """Tests for default_processor/process.py logic."""
    
    def test_process_passthrough(self):
        """Test that default process() returns event unchanged."""
        # Using fresh import mechanics for each test could be safer, 
        # but sys.path hack usually works for simple cases.
        # We need to ensure we import the right 'process' module if multiple exist in path.
        # Given the fixture order, default_processor is in path.
        try:
            from process import process
        except ImportError:
            # Fallback if not directly importable or masked
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "default_process", 
                os.path.join(AZURE_TEMPLATES_PATH, 'processors', 'default_processor', 'process.py')
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            process = module.process
        
        event = {"iotDeviceId": "sensor-1", "temperature": 25}
        result = process(event)
        
        assert result == event
    
    def test_process_with_complex_event(self):
        """Test process with complex event data."""
        try:
            from process import process
        except ImportError:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "default_process", 
                os.path.join(AZURE_TEMPLATES_PATH, 'processors', 'default_processor', 'process.py')
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            process = module.process
        
        event = {
            "iotDeviceId": "temperature-sensor-1",
            "time": "2024-01-01T00:00:00Z",
            "temperature": 28,
            "humidity": 65,
            "nested": {"value": 123}
        }
        result = process(event)
        
        assert result == event
        assert result["iotDeviceId"] == "temperature-sensor-1"
        assert result["nested"]["value"] == 123


class TestAzureTemplateSyntax:
    """Tests for Azure template function syntax validity."""
    
    def test_event_feedback_syntax(self):
        """Test event-feedback process.py has valid syntax."""
        # UPDATED: Now checks process.py
        path = os.path.join(AZURE_TEMPLATES_PATH, 'event-feedback', 'process.py')
        assert os.path.exists(path), f"File not found: {path}"
        
        with open(path, 'r') as f:
            code = f.read()
        
        # Should parse without error
        import ast
        tree = ast.parse(code)
        
        # Should have process function (not main)
        func_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
        assert 'process' in func_names
    
    def test_high_temperature_callback_syntax(self):
        """Test high-temperature-callback has valid syntax (LEGACY: function_app.py)."""
        # This one wasn't standardized yet, implies function_app.py
        path = os.path.join(AZURE_TEMPLATES_PATH, 'event_actions', 'high-temperature-callback', 'function_app.py')
        # Only test if it exists, otherwise skip (in case it was removed/changed)
        if not os.path.exists(path):
            return 

        with open(path, 'r') as f:
            code = f.read()
        
        import ast
        tree = ast.parse(code)
        
        func_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
        assert 'main' in func_names
    
    def test_high_temperature_callback_2_syntax(self):
        """Test high-temperature-callback-2 has valid syntax (LEGACY: function_app.py)."""
        path = os.path.join(AZURE_TEMPLATES_PATH, 'event_actions', 'high-temperature-callback-2', 'function_app.py')
        if not os.path.exists(path):
            return 

        with open(path, 'r') as f:
            code = f.read()
        
        import ast
        tree = ast.parse(code)
        
        func_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
        assert 'main' in func_names
    
    def test_temperature_sensor_2_syntax(self):
        """Test temperature-sensor-2 processor has valid syntax."""
        # UPDATED: Now checks process.py
        path = os.path.join(AZURE_TEMPLATES_PATH, 'processors', 'temperature-sensor-2', 'process.py')
        assert os.path.exists(path), f"File not found: {path}"
        
        with open(path, 'r') as f:
            code = f.read()
        
        import ast
        tree = ast.parse(code)
        
        func_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
        assert 'process' in func_names
    
    def test_default_processor_syntax(self):
        """Test default_processor/process.py has valid syntax."""
        path = os.path.join(AZURE_TEMPLATES_PATH, 'processors', 'default_processor', 'process.py')
        with open(path, 'r') as f:
            code = f.read()
        
        import ast
        tree = ast.parse(code)
        
        func_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
        assert 'process' in func_names


class TestAzureTemplateValidation:
    """Tests for Azure template function validation compatibility."""
    
    def test_event_feedback_has_process_arg(self):
        """Test event-feedback has process function with 1 arg."""
        # UPDATED: Checks process(payload)
        path = os.path.join(AZURE_TEMPLATES_PATH, 'event-feedback', 'process.py')
        with open(path, 'r') as f:
            code = f.read()
        
        import ast
        tree = ast.parse(code)
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == 'process':
                args = [arg.arg for arg in node.args.args]
                assert len(args) == 1
                # We enforce 'dict' type hint in zip_validator, but here we just check arg count
                return
        
        pytest.fail("process() function not found")
    
    def test_callback_has_main_req(self):
        """Test high-temperature-callback passes Azure validation (LEGACY)."""
        path = os.path.join(AZURE_TEMPLATES_PATH, 'event_actions', 'high-temperature-callback', 'function_app.py')
        if not os.path.exists(path):
            return

        with open(path, 'r') as f:
            code = f.read()
        
        import ast
        tree = ast.parse(code)
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == 'main':
                args = [arg.arg for arg in node.args.args]
                assert len(args) >= 1
                assert args[0] == 'req'
                return
        
        pytest.fail("main(req) function not found")
