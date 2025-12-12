"""
Tests for GCP Core Cloud Functions.

Tests the cloud functions in src/providers/gcp/cloud_functions/.
"""
import pytest
import os
import ast
import sys


# Path to GCP cloud functions
GCP_FUNCTIONS_PATH = os.path.join(
    os.path.dirname(__file__), 
    '..', '..', '..', 'src', 'providers', 'gcp', 'cloud_functions'
)


class TestGCPSharedModule:
    """Tests for _shared/inter_cloud.py module."""
    
    def test_inter_cloud_syntax(self):
        """Test inter_cloud.py has valid syntax."""
        path = os.path.join(GCP_FUNCTIONS_PATH, '_shared', 'inter_cloud.py')
        with open(path, 'r') as f:
            code = f.read()
        
        # Should parse without error
        tree = ast.parse(code)
        
        # Should have key functions
        func_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
        assert 'build_envelope' in func_names
        assert 'post_to_remote' in func_names
        assert 'post_raw' in func_names
        assert 'validate_token' in func_names
        assert 'build_auth_error_response' in func_names
    
    def test_build_envelope_source_cloud(self):
        """Test that build_envelope uses 'gcp' as source_cloud."""
        path = os.path.join(GCP_FUNCTIONS_PATH, '_shared', 'inter_cloud.py')
        with open(path, 'r') as f:
            code = f.read()
        
        # Should have source_cloud="gcp" as default
        assert 'source_cloud: str = "gcp"' in code


class TestGCPL1Functions:
    """Tests for L1 - Data Acquisition functions."""
    
    def test_dispatcher_syntax(self):
        """Test dispatcher/main.py has valid syntax and uses shared env_utils."""
        path = os.path.join(GCP_FUNCTIONS_PATH, 'dispatcher', 'main.py')
        with open(path, 'r') as f:
            code = f.read()
        
        tree = ast.parse(code)
        func_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
        assert 'main' in func_names
        # Verify uses shared env_utils instead of local _require_env
        assert 'from _shared.env_utils import require_env' in code
    
    def test_connector_syntax(self):
        """Test connector/main.py has valid syntax and uses shared env_utils."""
        path = os.path.join(GCP_FUNCTIONS_PATH, 'connector', 'main.py')
        with open(path, 'r') as f:
            code = f.read()
        
        tree = ast.parse(code)
        func_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
        assert 'main' in func_names
        # Verify uses shared env_utils instead of local _require_env
        assert 'from _shared.env_utils import require_env' in code


class TestGCPL2Functions:
    """Tests for L2 - Data Processing functions."""
    
    def test_ingestion_syntax(self):
        """Test ingestion/main.py has valid syntax."""
        path = os.path.join(GCP_FUNCTIONS_PATH, 'ingestion', 'main.py')
        with open(path, 'r') as f:
            code = f.read()
        
        tree = ast.parse(code)
        func_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
        assert 'main' in func_names
    
    def test_processor_wrapper_syntax(self):
        """Test processor_wrapper/main.py has valid syntax."""
        path = os.path.join(GCP_FUNCTIONS_PATH, 'processor_wrapper', 'main.py')
        with open(path, 'r') as f:
            code = f.read()
        
        tree = ast.parse(code)
        func_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
        assert 'main' in func_names
    
    def test_default_processor_syntax(self):
        """Test default-processor/main.py has valid syntax."""
        path = os.path.join(GCP_FUNCTIONS_PATH, 'default-processor', 'main.py')
        with open(path, 'r') as f:
            code = f.read()
        
        tree = ast.parse(code)
        func_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
        assert 'main' in func_names
        assert 'process' in func_names
    
    def test_persister_syntax(self):
        """Test persister/main.py has valid syntax."""
        path = os.path.join(GCP_FUNCTIONS_PATH, 'persister', 'main.py')
        with open(path, 'r') as f:
            code = f.read()
        
        tree = ast.parse(code)
        func_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
        assert 'main' in func_names
        assert '_is_multi_cloud_storage' in func_names
        assert '_get_firestore_client' in func_names
    
    def test_event_checker_syntax(self):
        """Test event-checker/main.py has valid syntax."""
        path = os.path.join(GCP_FUNCTIONS_PATH, 'event-checker', 'main.py')
        with open(path, 'r') as f:
            code = f.read()
        
        tree = ast.parse(code)
        func_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
        assert 'main' in func_names
        assert '_evaluate_condition' in func_names
        assert '_trigger_action' in func_names


class TestGCPL3Functions:
    """Tests for L3 - Storage functions."""
    
    def test_hot_writer_syntax(self):
        """Test hot-writer/main.py has valid syntax."""
        path = os.path.join(GCP_FUNCTIONS_PATH, 'hot-writer', 'main.py')
        with open(path, 'r') as f:
            code = f.read()
        
        tree = ast.parse(code)
        func_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
        assert 'main' in func_names
        assert '_get_firestore_client' in func_names
    
    def test_hot_reader_syntax(self):
        """Test hot-reader/main.py has valid syntax."""
        path = os.path.join(GCP_FUNCTIONS_PATH, 'hot-reader', 'main.py')
        with open(path, 'r') as f:
            code = f.read()
        
        tree = ast.parse(code)
        func_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
        assert 'main' in func_names
    
    def test_hot_reader_last_entry_syntax(self):
        """Test hot-reader-last-entry/main.py has valid syntax."""
        path = os.path.join(GCP_FUNCTIONS_PATH, 'hot-reader-last-entry', 'main.py')
        with open(path, 'r') as f:
            code = f.read()
        
        tree = ast.parse(code)
        func_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
        assert 'main' in func_names
    
    def test_hot_to_cold_mover_syntax(self):
        """Test hot-to-cold-mover/main.py has valid syntax."""
        path = os.path.join(GCP_FUNCTIONS_PATH, 'hot-to-cold-mover', 'main.py')
        with open(path, 'r') as f:
            code = f.read()
        
        tree = ast.parse(code)
        func_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
        assert 'main' in func_names
        assert '_is_multi_cloud_cold' in func_names
        assert '_chunk_items' in func_names
        assert '_write_to_local_gcs' in func_names
    
    def test_cold_writer_syntax(self):
        """Test cold-writer/main.py has valid syntax."""
        path = os.path.join(GCP_FUNCTIONS_PATH, 'cold-writer', 'main.py')
        with open(path, 'r') as f:
            code = f.read()
        
        tree = ast.parse(code)
        func_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
        assert 'main' in func_names
        assert '_get_storage_client' in func_names
    
    def test_cold_to_archive_mover_syntax(self):
        """Test cold-to-archive-mover/main.py has valid syntax."""
        path = os.path.join(GCP_FUNCTIONS_PATH, 'cold-to-archive-mover', 'main.py')
        with open(path, 'r') as f:
            code = f.read()
        
        tree = ast.parse(code)
        func_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
        assert 'main' in func_names
        assert '_is_multi_cloud_archive' in func_names
    
    def test_archive_writer_syntax(self):
        """Test archive-writer/main.py has valid syntax."""
        path = os.path.join(GCP_FUNCTIONS_PATH, 'archive-writer', 'main.py')
        with open(path, 'r') as f:
            code = f.read()
        
        tree = ast.parse(code)
        func_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
        assert 'main' in func_names


class TestGCPL4Functions:
    """Tests for L4 - Digital Twin functions."""
    
    def test_digital_twin_data_connector_syntax(self):
        """Test digital-twin-data-connector/main.py has valid syntax."""
        path = os.path.join(GCP_FUNCTIONS_PATH, 'digital-twin-data-connector', 'main.py')
        with open(path, 'r') as f:
            code = f.read()
        
        tree = ast.parse(code)
        func_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
        assert 'main' in func_names
        assert '_is_multi_cloud_reader' in func_names
    
    def test_digital_twin_data_connector_last_entry_syntax(self):
        """Test digital-twin-data-connector-last-entry/main.py has valid syntax."""
        path = os.path.join(GCP_FUNCTIONS_PATH, 'digital-twin-data-connector-last-entry', 'main.py')
        with open(path, 'r') as f:
            code = f.read()
        
        tree = ast.parse(code)
        func_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
        assert 'main' in func_names
        assert '_is_multi_cloud_reader' in func_names


class TestGCPFunctionDecorators:
    """Tests for functions_framework.http decorator usage."""
    
    def test_all_functions_use_http_decorator(self):
        """Test that all main.py files use @functions_framework.http decorator."""
        function_dirs = [
            'dispatcher', 'connector', 'ingestion', 'processor_wrapper',
            'default-processor', 'persister', 'event-checker',
            'hot-writer', 'hot-reader', 'hot-reader-last-entry',
            'hot-to-cold-mover', 'cold-writer', 'cold-to-archive-mover',
            'archive-writer', 'digital-twin-data-connector',
            'digital-twin-data-connector-last-entry'
        ]
        
        for func_dir in function_dirs:
            path = os.path.join(GCP_FUNCTIONS_PATH, func_dir, 'main.py')
            with open(path, 'r') as f:
                code = f.read()
            
            # Should import functions_framework
            assert 'import functions_framework' in code, f"{func_dir} missing functions_framework import"
            
            # Should use @functions_framework.http decorator
            assert '@functions_framework.http' in code, f"{func_dir} missing @functions_framework.http decorator"


class TestGCPFunctionCount:
    """Test that we have the expected number of functions."""
    
    def test_17_functions_exist(self):
        """Test that all 17 GCP cloud functions exist."""
        expected_dirs = [
            '_shared',
            'dispatcher',
            'connector',
            'ingestion',
            'processor_wrapper',
            'default-processor',
            'persister',
            'event-checker',
            'hot-writer',
            'hot-reader',
            'hot-reader-last-entry',
            'hot-to-cold-mover',
            'cold-writer',
            'cold-to-archive-mover',
            'archive-writer',
            'digital-twin-data-connector',
            'digital-twin-data-connector-last-entry'
        ]
        
        for dir_name in expected_dirs:
            dir_path = os.path.join(GCP_FUNCTIONS_PATH, dir_name)
            assert os.path.isdir(dir_path), f"Missing directory: {dir_name}"
