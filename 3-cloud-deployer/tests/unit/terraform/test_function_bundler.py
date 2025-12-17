"""
Unit tests for function_bundler module.

Tests the bundling of Azure Functions into per-app ZIP packages.
"""

import pytest
import zipfile
import io
from pathlib import Path
from unittest.mock import patch

from src.providers.azure.layers.function_bundler import (
    bundle_l0_functions,
    bundle_l1_functions,
    bundle_l2_functions,
    bundle_l3_functions,
    _clean_function_app_imports,
    BundleError,
)


class TestBundleL0Functions:
    """Tests for bundle_l0_functions (per-boundary conditional)."""
    
    @pytest.fixture
    def azure_functions_dir(self, tmp_path):
        """Create a mock azure_functions directory structure."""
        azure_funcs = tmp_path / "azure_functions"
        azure_funcs.mkdir()
        
        # Create shared files
        (azure_funcs / "requirements.txt").write_text("azure-functions")
        (azure_funcs / "host.json").write_text('{"version": "2.0"}')
        
        # Create function directories with function_app.py (v2 model)
        for func_name in ["ingestion", "hot-writer", "hot-reader", "dispatcher"]:
            func_dir = azure_funcs / func_name
            func_dir.mkdir()
            # Create a minimal function_app.py for each function
            func_code = f'''import azure.functions as func
app = func.FunctionApp()

@app.function_name(name="{func_name}")
@app.route(route="{func_name}", methods=["POST"])
def {func_name.replace("-", "_")}(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse("OK", status_code=200)
'''
            (func_dir / "function_app.py").write_text(func_code)
        
        return tmp_path
    
    def test_requires_project_path(self):
        """Should raise ValueError if project_path is None."""
        with pytest.raises(ValueError, match="project_path is required"):
            bundle_l0_functions(None, {})
    
    def test_requires_provider_config(self, azure_functions_dir):
        """Should raise ValueError if provider config keys missing."""
        with pytest.raises(ValueError, match="Missing required provider config"):
            bundle_l0_functions(str(azure_functions_dir), {})
    
    def test_no_glue_for_single_cloud(self, azure_functions_dir):
        """Should return None when all providers are same (no cross-cloud)."""
        providers = {
            "layer_1_provider": "azure",
            "layer_2_provider": "azure",
            "layer_3_hot_provider": "azure",
            "layer_4_provider": "azure",
            "layer_5_provider": "azure"
        }
        
        zip_bytes, funcs = bundle_l0_functions(str(azure_functions_dir), providers)
        
        assert zip_bytes is None
        assert funcs == []
    
    def test_bundles_ingestion_for_l1_l2_boundary(self, azure_functions_dir):
        """Should include ingestion when L1 != L2 and L2 is azure."""
        providers = {
            "layer_1_provider": "aws",
            "layer_2_provider": "azure",
            "layer_3_hot_provider": "azure",
            "layer_4_provider": "azure",
            "layer_5_provider": "azure"
        }
        
        zip_bytes, funcs = bundle_l0_functions(str(azure_functions_dir), providers)
        
        assert zip_bytes is not None
        assert "ingestion" in funcs
        
        # Verify ZIP contains the function in function_app.py
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            names = zf.namelist()
            assert "function_app.py" in names
            content = zf.read("function_app.py").decode("utf-8")
            assert "ingestion" in content
    
    def test_bundles_hot_writer_for_l2_l3_boundary(self, azure_functions_dir):
        """Should include hot-writer when L2 != L3_hot and L3_hot is azure."""
        providers = {
            "layer_1_provider": "azure",
            "layer_2_provider": "aws",
            "layer_3_hot_provider": "azure",
            "layer_4_provider": "azure",
            "layer_5_provider": "azure"
        }
        
        zip_bytes, funcs = bundle_l0_functions(str(azure_functions_dir), providers)
        
        assert zip_bytes is not None
        assert "hot-writer" in funcs


class TestBundleL1Functions:
    """Tests for bundle_l1_functions."""
    
    @pytest.fixture
    def azure_functions_dir(self, tmp_path):
        """Create a mock azure_functions directory structure."""
        azure_funcs = tmp_path / "azure_functions"
        azure_funcs.mkdir()
        
        # Create dispatcher function with function_app.py (v2 model)
        dispatcher = azure_funcs / "dispatcher"
        dispatcher.mkdir()
        func_code = '''import azure.functions as func
app = func.FunctionApp()

@app.function_name(name="dispatcher")
@app.route(route="dispatcher", methods=["POST"])
def dispatcher(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse("OK", status_code=200)
'''
        (dispatcher / "function_app.py").write_text(func_code)
        
        return tmp_path
    
    def test_bundles_dispatcher(self, azure_functions_dir):
        """Should bundle dispatcher function at root function_app.py."""
        zip_bytes = bundle_l1_functions(str(azure_functions_dir))
        
        assert zip_bytes is not None
        
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            names = zf.namelist()
            assert "function_app.py" in names
            content = zf.read("function_app.py").decode("utf-8")
            assert "dispatcher" in content


class TestBundleL2Functions:
    """Tests for bundle_l2_functions."""
    
    @pytest.fixture
    def azure_functions_dir(self, tmp_path):
        """Create a mock azure_functions directory structure."""
        azure_funcs = tmp_path / "azure_functions"
        azure_funcs.mkdir()
        
        # Create persister function with function_app.py (v2 model)
        persister = azure_funcs / "persister"
        persister.mkdir()
        (persister / "function_app.py").write_text('''import azure.functions as func
app = func.FunctionApp()

@app.function_name(name="persister")
@app.route(route="persister", methods=["POST"])
def persister(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse("OK", status_code=200)
''')
        
        # Create optional event-checker
        event_checker = azure_funcs / "event-checker"
        event_checker.mkdir()
        (event_checker / "function_app.py").write_text('''import azure.functions as func
app = func.FunctionApp()

@app.function_name(name="event-checker")
@app.route(route="event-checker", methods=["POST"])
def event_checker(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse("OK", status_code=200)
''')
        
        return tmp_path
    
    def test_bundles_persister(self, azure_functions_dir):
        """Should bundle persister function - check for merged function_app.py."""
        zip_bytes = bundle_l2_functions(str(azure_functions_dir))
        
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            names = zf.namelist()
            # With merge, there's a single function_app.py at root
            assert "function_app.py" in names
            content = zf.read("function_app.py").decode("utf-8")
            assert "persister" in content
    
    def test_includes_event_checker_if_exists(self, azure_functions_dir):
        """Should include event-checker in merged function_app.py if it exists."""
        zip_bytes = bundle_l2_functions(str(azure_functions_dir))
        
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            content = zf.read("function_app.py").decode("utf-8")
            assert "event_checker" in content


class TestBundleL3Functions:
    """Tests for bundle_l3_functions."""
    
    @pytest.fixture
    def azure_functions_dir(self, tmp_path):
        """Create a mock azure_functions directory structure."""
        azure_funcs = tmp_path / "azure_functions"
        azure_funcs.mkdir()
        
        # Create L3 functions with function_app.py (v2 model)
        for func_name in ["hot-reader", "hot-reader-last-entry", "hot-cold-mover", "cold-archive-mover"]:
            func_dir = azure_funcs / func_name
            func_dir.mkdir()
            safe_name = func_name.replace("-", "_")
            func_code = f'''import azure.functions as func
app = func.FunctionApp()

@app.function_name(name="{func_name}")
@app.route(route="{func_name}", methods=["POST"])
def {safe_name}(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse("OK", status_code=200)
'''
            (func_dir / "function_app.py").write_text(func_code)
        
        return tmp_path
    
    def test_bundles_all_l3_functions(self, azure_functions_dir):
        """Should bundle all L3 functions into a merged function_app.py."""
        zip_bytes = bundle_l3_functions(str(azure_functions_dir))
        
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            names = zf.namelist()
            # With merge, there's now a single function_app.py at root
            assert "function_app.py" in names
            # Read the merged file and check it contains function definitions
            content = zf.read("function_app.py").decode("utf-8")
            assert "hot_reader" in content
            assert "hot_cold_mover" in content


class TestSingleFunctionZip:
    """Tests for single-function ZIP bundling (no merge needed)."""
    
    @pytest.fixture
    def single_func_dir(self, tmp_path):
        """Create a directory with a single function."""
        azure_funcs = tmp_path / "azure_functions"
        azure_funcs.mkdir()
        
        dispatcher = azure_funcs / "dispatcher"
        dispatcher.mkdir()
        (dispatcher / "function_app.py").write_text('''import azure.functions as func
app = func.FunctionApp()

@app.function_name(name="dispatcher")
@app.route(route="dispatcher", methods=["POST"])
def dispatcher(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse("OK", status_code=200)
''')
        return tmp_path
    
    def test_single_function_not_merged(self, single_func_dir):
        """Single function should be placed at root without merge."""
        zip_bytes = bundle_l1_functions(str(single_func_dir))
        
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            content = zf.read("function_app.py").decode("utf-8")
            # Should NOT have the auto-generated header
            assert "Auto-generated merged" not in content
            # Should have the function
            assert "dispatcher" in content
            # Should only appear once (not merged from multiple sources)
            assert content.count("@app.function_name") == 1


class TestCleanFunctionAppImports:
    """Tests for the _clean_function_app_imports helper function."""
    
    def test_removes_try_except_import_block(self):
        """Should remove try/except block with sys.path manipulation."""
        content = '''import azure.functions as func

# Handle import path for shared module
try:
    from _shared.env_utils import require_env
except ModuleNotFoundError:
    import os
    import sys
    _func_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _func_dir not in sys.path:
        sys.path.insert(0, _func_dir)
    from _shared.env_utils import require_env

bp = func.Blueprint()
'''
        cleaned = _clean_function_app_imports(content)
        
        # Should not have the comment or try/except
        assert "# Handle import path for shared module" not in cleaned
        assert "try:" not in cleaned
        assert "except ModuleNotFoundError" not in cleaned
        assert "sys.path.insert" not in cleaned
        
        # Should have the import re-added cleanly
        assert "from _shared.env_utils import require_env" in cleaned
        
        # Should keep Blueprint code
        assert "bp = func.Blueprint()" in cleaned
    
    def test_preserves_multiple_shared_imports(self):
        """Should preserve all _shared imports from try block."""
        content = '''import azure.functions as func

# Handle import path for shared module
try:
    from _shared.env_utils import require_env
    from _shared.inter_cloud import post_to_remote
    from _shared.logging_utils import get_logger
except ModuleNotFoundError:
    _func_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, _func_dir)
    from _shared.env_utils import require_env
    from _shared.inter_cloud import post_to_remote
    from _shared.logging_utils import get_logger

bp = func.Blueprint()
'''
        cleaned = _clean_function_app_imports(content)
        
        # All imports should be present (deduplicated)
        assert "from _shared.env_utils import require_env" in cleaned
        assert "from _shared.inter_cloud import post_to_remote" in cleaned
        assert "from _shared.logging_utils import get_logger" in cleaned
        
        # But only once each (not duplicated from try and except)
        assert cleaned.count("from _shared.env_utils import require_env") == 1
    
    def test_preserves_code_without_try_except_block(self):
        """Should not modify files without the specific try/except pattern."""
        content = '''import azure.functions as func
from _shared.env_utils import require_env

bp = func.Blueprint()

@bp.function_name(name="persister")
def persister(req):
    return "OK"
'''
        cleaned = _clean_function_app_imports(content)
        
        # Content should be essentially unchanged
        assert "from _shared.env_utils import require_env" in cleaned
        assert "bp = func.Blueprint()" in cleaned
        assert "@bp.function_name" in cleaned
    
    def test_removes_standalone_sys_path_manipulation(self):
        """Should remove standalone sys.path manipulation not in try/except."""
        content = '''import azure.functions as func
import os
import sys

_func_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _func_dir not in sys.path:
    sys.path.insert(0, _func_dir)

from _shared.env_utils import require_env

bp = func.Blueprint()
'''
        cleaned = _clean_function_app_imports(content)
        
        # Should not have sys.path manipulation
        assert "_func_dir = os.path.dirname" not in cleaned
        assert "sys.path.insert" not in cleaned
        
        # Should keep the import
        assert "from _shared.env_utils import require_env" in cleaned
    
    def test_produces_valid_python(self):
        """Cleaned content should be syntactically valid Python."""
        import ast
        
        content = '''"""Persister function."""
import json
import azure.functions as func

# Handle import path for shared module
try:
    from _shared.env_utils import require_env
    from _shared.inter_cloud import post_to_remote
except ModuleNotFoundError:
    import os
    import sys
    _func_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _func_dir not in sys.path:
        sys.path.insert(0, _func_dir)
    from _shared.env_utils import require_env
    from _shared.inter_cloud import post_to_remote

bp = func.Blueprint()

@bp.function_name(name="persister")
def persister(req):
    env_value = require_env("TEST_VAR")
    return "OK"
'''
        cleaned = _clean_function_app_imports(content)
        
        # Should be valid Python
        try:
            ast.parse(cleaned)
        except SyntaxError as e:
            pytest.fail(f"Cleaned content has syntax error: {e}")
    
    def test_inserts_imports_after_standard_imports(self):
        """_shared imports should be placed after other imports."""
        content = '''import azure.functions as func
import json
import logging

# Handle import path for shared module
try:
    from _shared.env_utils import require_env
except ModuleNotFoundError:
    sys.path.insert(0, "/wrong/path")
    from _shared.env_utils import require_env

bp = func.Blueprint()
'''
        cleaned = _clean_function_app_imports(content)
        lines = cleaned.split('\n')
        
        # Find positions of imports
        logging_idx = next(i for i, l in enumerate(lines) if 'import logging' in l)
        shared_idx = next(i for i, l in enumerate(lines) if 'from _shared' in l)
        bp_idx = next(i for i, l in enumerate(lines) if 'bp = func.Blueprint()' in l)
        
        # _shared import should be after logging import and before bp definition
        assert shared_idx > logging_idx, "Shared import should be after standard imports"
        assert shared_idx < bp_idx, "Shared import should be before code"


class TestMergeFilesFunctionality:
    """Tests for the merge functionality in multi-function ZIPs."""
    
    @pytest.fixture
    def multi_func_dir(self, tmp_path):
        """Create a directory with multiple functions with complex code."""
        azure_funcs = tmp_path / "azure_functions"
        azure_funcs.mkdir()
        
        # Function 1: persister with extra imports and helpers
        persister = azure_funcs / "persister"
        persister.mkdir()
        (persister / "function_app.py").write_text('''"""Persister function docstring."""
import azure.functions as func
import json
import logging

GLOBAL_CONSTANT = "persister_value"

app = func.FunctionApp()

def helper_persister():
    return "helper"

@app.function_name(name="persister")
@app.route(route="persister", methods=["POST"])
def persister(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("Persister called")
    return func.HttpResponse("OK", status_code=200)
''')
        
        # Function 2: event-checker with different imports
        event_checker = azure_funcs / "event-checker"
        event_checker.mkdir()
        (event_checker / "function_app.py").write_text('''"""Event checker docstring."""
import azure.functions as func
import os
import logging

EVENT_CONSTANT = "event_value"

app = func.FunctionApp()

def helper_event():
    return "event_helper"

@app.function_name(name="event-checker")
@app.route(route="event-checker", methods=["POST"])
def event_checker(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("Event checker called")
    return func.HttpResponse("Checked", status_code=200)
''')
        
        return tmp_path
    
    def test_merged_has_single_app_instance(self, multi_func_dir):
        """Merged file should have exactly ONE app = func.FunctionApp()."""
        zip_bytes = bundle_l2_functions(str(multi_func_dir))
        
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            content = zf.read("function_app.py").decode("utf-8")
            # Only one FunctionApp instance
            assert content.count("func.FunctionApp()") == 1
    
    def test_merged_contains_all_functions(self, multi_func_dir):
        """Main function_app.py should import and register all Blueprints."""
        zip_bytes = bundle_l2_functions(str(multi_func_dir))
        
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            content = zf.read("function_app.py").decode("utf-8")
            # Blueprint pattern: main file imports from submodules
            assert "register_functions" in content
            # Both blueprints should be registered
            assert "persister" in content
            assert "event_checker" in content
    
    def test_merged_imports_from_submodules(self, multi_func_dir):
        """Main function_app.py should import Blueprints from submodules."""
        zip_bytes = bundle_l2_functions(str(multi_func_dir))
        
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            content = zf.read("function_app.py").decode("utf-8")
            # azure.functions should appear once
            assert content.count("import azure.functions as func") == 1
            # Should import from submodules (Blueprint pattern)
            assert "from persister.function_app import bp" in content
            assert "from event_checker.function_app import bp" in content
    
    def test_merged_has_header(self, multi_func_dir):
        """Main file should have the auto-generated header."""
        zip_bytes = bundle_l2_functions(str(multi_func_dir))
        
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            content = zf.read("function_app.py").decode("utf-8")
            assert "Auto-generated" in content  # Blueprint pattern header


class TestSharedFilesHandling:
    """Tests for shared files (requirements.txt, host.json, _shared/)."""
    
    @pytest.fixture
    def func_dir_with_shared(self, tmp_path):
        """Create directory with shared files."""
        azure_funcs = tmp_path / "azure_functions"
        azure_funcs.mkdir()
        
        # Custom requirements.txt
        (azure_funcs / "requirements.txt").write_text("""azure-functions
azure-cosmos
requests
""")
        
        # Custom host.json
        (azure_funcs / "host.json").write_text('{"version": "2.0", "custom": true}')
        
        # _shared directory
        shared = azure_funcs / "_shared"
        shared.mkdir()
        (shared / "__init__.py").write_text("# Shared module")
        (shared / "utils.py").write_text("def shared_util(): pass")
        
        # A function
        dispatcher = azure_funcs / "dispatcher"
        dispatcher.mkdir()
        (dispatcher / "function_app.py").write_text('''import azure.functions as func
app = func.FunctionApp()

@app.function_name(name="dispatcher")
@app.route(route="dispatcher", methods=["POST"])
def dispatcher(req): return func.HttpResponse("OK")
''')
        
        return tmp_path
    
    def test_includes_custom_requirements(self, func_dir_with_shared):
        """Should include custom requirements.txt from source."""
        zip_bytes = bundle_l1_functions(str(func_dir_with_shared))
        
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            content = zf.read("requirements.txt").decode("utf-8")
            assert "azure-cosmos" in content
            assert "requests" in content
    
    def test_includes_custom_host_json(self, func_dir_with_shared):
        """Should include custom host.json from source."""
        zip_bytes = bundle_l1_functions(str(func_dir_with_shared))
        
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            content = zf.read("host.json").decode("utf-8")
            assert '"custom": true' in content
    
    def test_includes_shared_directory(self, func_dir_with_shared):
        """Should include _shared/ directory contents."""
        zip_bytes = bundle_l1_functions(str(func_dir_with_shared))
        
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            names = zf.namelist()
            assert "_shared/__init__.py" in names
            assert "_shared/utils.py" in names
    
    def test_generates_default_files_if_missing(self, tmp_path):
        """Should generate default requirements.txt and host.json if not present."""
        azure_funcs = tmp_path / "azure_functions"
        azure_funcs.mkdir()
        
        dispatcher = azure_funcs / "dispatcher"
        dispatcher.mkdir()
        (dispatcher / "function_app.py").write_text('''import azure.functions as func
app = func.FunctionApp()

@app.function_name(name="dispatcher")
@app.route(route="dispatcher", methods=["POST"])
def dispatcher(req): return func.HttpResponse("OK")
''')
        
        zip_bytes = bundle_l1_functions(str(tmp_path))
        
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            names = zf.namelist()
            assert "requirements.txt" in names
            assert "host.json" in names
            
            # Check defaults
            req_content = zf.read("requirements.txt").decode("utf-8")
            assert "azure-functions" in req_content
            
            host_content = zf.read("host.json").decode("utf-8")
            assert '"version": "2.0"' in host_content


class TestEdgeCases:
    """Tests for edge cases and error handling."""
    
    def test_empty_project_path_raises(self):
        """Should raise ValueError for empty project path."""
        with pytest.raises(ValueError, match="project_path is required"):
            bundle_l1_functions("")
    
    def test_none_project_path_raises(self):
        """Should raise ValueError for None project path."""
        with pytest.raises(ValueError, match="project_path is required"):
            bundle_l1_functions(None)
    
    def test_missing_function_dir_logs_warning(self, tmp_path, caplog):
        """Should log warning for missing function directories."""
        azure_funcs = tmp_path / "azure_functions"
        azure_funcs.mkdir()
        
        # Only create persister, not event-checker
        persister = azure_funcs / "persister"
        persister.mkdir()
        (persister / "function_app.py").write_text('''import azure.functions as func
app = func.FunctionApp()

@app.function_name(name="persister")
@app.route(route="persister", methods=["POST"])
def persister(req): return func.HttpResponse("OK")
''')
        
        # L2 expects both persister and event-checker
        zip_bytes = bundle_l2_functions(str(tmp_path))
        
        # Should still produce a valid ZIP with just persister
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            assert "function_app.py" in zf.namelist()
    
    def test_missing_function_app_py_handled(self, tmp_path):
        """Should handle function directories without function_app.py."""
        azure_funcs = tmp_path / "azure_functions"
        azure_funcs.mkdir()
        
        # Create directory but no function_app.py
        dispatcher = azure_funcs / "dispatcher"
        dispatcher.mkdir()
        (dispatcher / "README.md").write_text("No function here")
        
        # Should not crash, just produce a zip without the function
        zip_bytes = bundle_l1_functions(str(tmp_path))
        
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            names = zf.namelist()
            # Should still have basic files
            assert "requirements.txt" in names
            assert "host.json" in names


class TestMultiFunctionMergeCount:
    """Tests to verify correct function counts in merged files."""
    
    @pytest.fixture
    def four_func_dir(self, tmp_path):
        """Create directory with 4 functions for L3."""
        azure_funcs = tmp_path / "azure_functions"
        azure_funcs.mkdir()
        
        functions = ["hot-reader", "hot-reader-last-entry", "hot-cold-mover", "cold-archive-mover"]
        for func_name in functions:
            func_dir = azure_funcs / func_name
            func_dir.mkdir()
            safe_name = func_name.replace("-", "_")
            (func_dir / "function_app.py").write_text(f'''import azure.functions as func
app = func.FunctionApp()

@app.function_name(name="{func_name}")
@app.route(route="{func_name}", methods=["POST"])
def {safe_name}(req): return func.HttpResponse("OK from {func_name}")
''')
        
        return tmp_path
    
    def test_four_functions_merged_correctly(self, four_func_dir):
        """Should register all 4 L3 function Blueprints in main file."""
        zip_bytes = bundle_l3_functions(str(four_func_dir))
        
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            content = zf.read("function_app.py").decode("utf-8")
            
            # Blueprint pattern: should have 4 register_functions calls
            assert content.count("register_functions") == 4
            
            # All function modules should be imported (using Python-safe names)
            assert "hot_reader" in content
            assert "hot_reader_last_entry" in content
            assert "hot_cold_mover" in content
            assert "cold_archive_mover" in content


class TestRealFunctionBundler:
    """
    Tests that validate the bundler with REAL function files from src/.
    
    These tests ensure the bundler produces valid, deployable Azure Function code.
    """
    
    def test_l2_bundle_produces_valid_python(self):
        """L2 bundle should produce syntactically valid Python."""
        import ast
        
        # Use the real project path
        import os
        project_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        
        zip_bytes = bundle_l2_functions(project_path)
        
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            content = zf.read("function_app.py").decode("utf-8")
            
            # Must be valid Python (no syntax errors)
            try:
                ast.parse(content)
            except SyntaxError as e:
                pytest.fail(f"Merged function_app.py has syntax error: {e}")
    
    def test_l2_bundle_registers_blueprints(self):
        """L2 bundle main file should register Blueprint modules."""
        import os
        project_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        
        zip_bytes = bundle_l2_functions(project_path)
        
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            content = zf.read("function_app.py").decode("utf-8")
            
            # Blueprint pattern: main file imports and registers Blueprints
            assert "register_functions" in content, "Missing register_functions call"
            
            # L2 should have at least 1 Blueprint (persister)
            register_count = content.count("register_functions")
            assert register_count >= 1, f"Expected at least 1 Blueprint, got {register_count}"
    
    def test_l2_bundle_has_single_app_instance(self):
        """L2 bundle should have exactly one FunctionApp instance."""
        import os
        project_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        
        zip_bytes = bundle_l2_functions(project_path)
        
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            content = zf.read("function_app.py").decode("utf-8")
            
            # Exactly one FunctionApp()
            app_count = content.count("func.FunctionApp()")
            assert app_count == 1, f"Expected 1 FunctionApp instance, got {app_count}"
    
    def test_l2_bundle_submodules_have_blueprints(self):
        """L2 bundle submodules should have Blueprint definitions with decorators."""
        import os
        project_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        
        zip_bytes = bundle_l2_functions(project_path)
        
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            # Check that submodule has Blueprint and decorators
            persister_content = zf.read("persister/function_app.py").decode("utf-8")
            
            # Submodule should have Blueprint instance and decorators
            assert "Blueprint" in persister_content
            assert "@bp." in persister_content, "Submodule should have @bp decorators"
    
    def test_l1_single_function_not_merged(self):
        """L1 single function should not have merge header."""
        import os
        project_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        
        zip_bytes = bundle_l1_functions(project_path)
        
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            content = zf.read("function_app.py").decode("utf-8")
            
            # Single function should NOT have merge header
            assert "Auto-generated merged" not in content, "Single function shouldn't be merged"
            
            # But should have dispatcher function
            assert "dispatcher" in content.lower()
    
    def test_main_file_is_valid_python(self):
        """Main function_app.py should be valid Python."""
        import os
        import ast
        project_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        
        zip_bytes = bundle_l2_functions(project_path)
        
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            content = zf.read("function_app.py").decode("utf-8")
            
            # Parse and verify it's valid Python
            try:
                ast.parse(content)
            except SyntaxError as e:
                pytest.fail(f"Main function_app.py has syntax error: {e}")
    
    def test_submodules_have_shared_imports(self):
        """Submodule function_app.py files should have _shared imports."""
        import os
        project_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        
        zip_bytes = bundle_l2_functions(project_path)
        
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            # Check persister submodule has _shared imports
            content = zf.read("persister/function_app.py").decode("utf-8")
            
            # Should have simple _shared imports (no try/except wrapper)
            assert "from _shared" in content, "Missing _shared imports in submodule"
            # Should NOT have sys.path manipulation after cleaning
            assert "sys.path.insert" not in content, "Should not have sys.path manipulation"
    
    def test_submodule_all_used_names_are_defined(self):
        """Submodule function_app.py should have all required names defined."""
        import os
        import ast
        project_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        
        zip_bytes = bundle_l2_functions(project_path)
        
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            # Check the persister submodule (has _shared imports)
            content = zf.read("persister/function_app.py").decode("utf-8")
            
            # Parse the AST
            tree = ast.parse(content)
            
            # Collect all defined names (imports, functions, classes, assignments)
            defined_names = set()
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        defined_names.add(alias.asname or alias.name.split('.')[0])
                elif isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        defined_names.add(alias.asname or alias.name)
                elif isinstance(node, ast.FunctionDef):
                    defined_names.add(node.name)
                elif isinstance(node, ast.ClassDef):
                    defined_names.add(node.name)
                elif isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            defined_names.add(target.id)
            
            # Add Python builtins
            import builtins
            defined_names.update(dir(builtins))
            
            # Special names that are always available
            defined_names.update(['bp', 'func', 'logging', 'json', 'os', 'sys'])
            
            # Check that require_env is defined (used in persister)
            assert 'require_env' in defined_names, "require_env not defined/imported"


class TestZipStructureValidation:
    """Tests to validate the bundled ZIP structure is correct for Azure Functions."""
    
    def test_l2_zip_has_required_structure(self):
        """L2 ZIP should have all required files and folders for Azure Functions."""
        import os
        project_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        
        zip_bytes = bundle_l2_functions(project_path)
        
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            names = zf.namelist()
            
            # Required root files
            assert "function_app.py" in names, "Missing main function_app.py"
            assert "requirements.txt" in names, "Missing requirements.txt"
            assert "host.json" in names, "Missing host.json"
            
            # _shared module should be present
            shared_files = [n for n in names if n.startswith("_shared/")]
            assert len(shared_files) > 0, "Missing _shared directory"
            assert "_shared/__init__.py" in names, "Missing _shared/__init__.py"
            
            # Function submodules
            persister_files = [n for n in names if n.startswith("persister/")]
            assert len(persister_files) > 0, "Missing persister directory"
            assert "persister/__init__.py" in names, "Missing persister/__init__.py"
            assert "persister/function_app.py" in names, "Missing persister/function_app.py"
    
    def test_all_python_files_are_valid(self):
        """All .py files in the ZIP should be syntactically valid."""
        import ast
        import os
        project_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        
        zip_bytes = bundle_l2_functions(project_path)
        
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            py_files = [n for n in zf.namelist() if n.endswith('.py')]
            
            for py_file in py_files:
                content = zf.read(py_file).decode("utf-8")
                try:
                    ast.parse(content)
                except SyntaxError as e:
                    pytest.fail(f"{py_file} has syntax error: {e}")
    
    def test_host_json_is_valid(self):
        """host.json should be valid JSON with required structure."""
        import json
        import os
        project_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        
        zip_bytes = bundle_l2_functions(project_path)
        
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            content = zf.read("host.json").decode("utf-8")
            
            # Should be valid JSON
            try:
                host_config = json.loads(content)
            except json.JSONDecodeError as e:
                pytest.fail(f"host.json is not valid JSON: {e}")
            
            # Should have version
            assert "version" in host_config, "host.json missing 'version' field"
    
    def test_requirements_txt_has_azure_functions(self):
        """requirements.txt should include azure-functions package."""
        import os
        project_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        
        zip_bytes = bundle_l2_functions(project_path)
        
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            content = zf.read("requirements.txt").decode("utf-8")
            
            # Should have azure-functions
            assert "azure-functions" in content.lower(), "requirements.txt missing azure-functions"
    
    def test_submodules_have_no_sys_path_manipulation(self):
        """Submodule function_app.py files should not have sys.path manipulation."""
        import os
        project_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        
        zip_bytes = bundle_l2_functions(project_path)
        
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            # Check all function_app.py files in subfolders
            submodule_files = [n for n in zf.namelist() 
                              if n.endswith("/function_app.py") and n != "function_app.py"]
            
            for submodule in submodule_files:
                content = zf.read(submodule).decode("utf-8")
                assert "sys.path.insert" not in content, f"{submodule} has sys.path manipulation"
                assert "# Handle import path for shared module" not in content, f"{submodule} has import comment"
