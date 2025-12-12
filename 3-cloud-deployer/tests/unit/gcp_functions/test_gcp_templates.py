"""
Tests for GCP Template Functions.

Tests the user-uploadable template functions in upload/template/cloud_functions/.
"""
import pytest
import json
import sys
import os
from unittest.mock import patch, MagicMock

# Path to GCP template functions
GCP_TEMPLATES_PATH = os.path.join(
    os.path.dirname(__file__), 
    '..', '..', '..', 'upload', 'template', 'cloud_functions'
)


@pytest.fixture(autouse=True)
def setup_gcp_paths():
    """Add GCP template paths to sys.path for imports."""
    original_path = sys.path.copy()
    
    # Add template directories
    event_feedback_path = os.path.join(GCP_TEMPLATES_PATH, 'event-feedback')
    callback_path = os.path.join(GCP_TEMPLATES_PATH, 'event_actions', 'high-temperature-callback')
    callback2_path = os.path.join(GCP_TEMPLATES_PATH, 'event_actions', 'high-temperature-callback-2')
    processor_path = os.path.join(GCP_TEMPLATES_PATH, 'processors', 'default_processor')
    temp_sensor_path = os.path.join(GCP_TEMPLATES_PATH, 'processors', 'temperature-sensor-2')
    
    for path in [event_feedback_path, callback_path, callback2_path, processor_path, temp_sensor_path]:
        if path not in sys.path:
            sys.path.insert(0, path)
    
    yield
    
    # Restore original path
    sys.path[:] = original_path


class TestGCPTemplateProcessLogic:
    """Tests for default_processor/process.py logic."""
    
    def test_process_passthrough(self):
        """Test that default process() returns event unchanged."""
        from process import process
        
        event = {"iotDeviceId": "sensor-1", "temperature": 25}
        result = process(event)
        
        assert result == event
    
    def test_process_with_complex_event(self):
        """Test process with complex event data."""
        from process import process
        
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


class TestGCPTemplateSyntax:
    """Tests for GCP template function syntax validity."""
    
    def test_event_feedback_syntax(self):
        """Test event-feedback main.py has valid syntax."""
        path = os.path.join(GCP_TEMPLATES_PATH, 'event-feedback', 'main.py')
        with open(path, 'r') as f:
            code = f.read()
        
        # Should parse without error
        import ast
        tree = ast.parse(code)
        
        # Should have main function
        func_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
        assert 'main' in func_names
    
    def test_high_temperature_callback_syntax(self):
        """Test high-temperature-callback has valid syntax."""
        path = os.path.join(GCP_TEMPLATES_PATH, 'event_actions', 'high-temperature-callback', 'main.py')
        with open(path, 'r') as f:
            code = f.read()
        
        import ast
        tree = ast.parse(code)
        
        func_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
        assert 'main' in func_names
    
    def test_high_temperature_callback_2_syntax(self):
        """Test high-temperature-callback-2 has valid syntax."""
        path = os.path.join(GCP_TEMPLATES_PATH, 'event_actions', 'high-temperature-callback-2', 'main.py')
        with open(path, 'r') as f:
            code = f.read()
        
        import ast
        tree = ast.parse(code)
        
        func_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
        assert 'main' in func_names
    
    def test_temperature_sensor_2_syntax(self):
        """Test temperature-sensor-2 processor has valid syntax."""
        path = os.path.join(GCP_TEMPLATES_PATH, 'processors', 'temperature-sensor-2', 'main.py')
        with open(path, 'r') as f:
            code = f.read()
        
        import ast
        tree = ast.parse(code)
        
        func_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
        assert 'main' in func_names
    
    def test_default_processor_syntax(self):
        """Test default_processor/process.py has valid syntax."""
        path = os.path.join(GCP_TEMPLATES_PATH, 'processors', 'default_processor', 'process.py')
        with open(path, 'r') as f:
            code = f.read()
        
        import ast
        tree = ast.parse(code)
        
        func_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
        assert 'process' in func_names


class TestGCPTemplateValidation:
    """Tests for GCP template function validation compatibility."""
    
    def test_event_feedback_has_main(self):
        """Test event-feedback has main function for GCP validation."""
        path = os.path.join(GCP_TEMPLATES_PATH, 'event-feedback', 'main.py')
        with open(path, 'r') as f:
            code = f.read()
        
        import ast
        tree = ast.parse(code)
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == 'main':
                # GCP functions take 'request' parameter
                args = [arg.arg for arg in node.args.args]
                assert len(args) >= 1
                assert args[0] == 'request'
                return
        
        pytest.fail("main(request) function not found")
    
    def test_callback_has_main(self):
        """Test high-temperature-callback has main function."""
        path = os.path.join(GCP_TEMPLATES_PATH, 'event_actions', 'high-temperature-callback', 'main.py')
        with open(path, 'r') as f:
            code = f.read()
        
        import ast
        tree = ast.parse(code)
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == 'main':
                args = [arg.arg for arg in node.args.args]
                assert len(args) >= 1
                assert args[0] == 'request'
                return
        
        pytest.fail("main(request) function not found")
