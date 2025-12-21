"""
Azure Function Bundler - Per-App ZIP Packaging.

This module bundles multiple Azure Functions into single ZIP files
per Function App, for use with Terraform-based deployment.

Each bundle method:
1. Checks config_providers.json for conditional deployment
2. Collects all function folders for the app
3. Adds shared files (requirements.txt, host.json)
4. Returns a single ZIP bytes object

Usage:
    from function_bundler import bundle_l0_functions, bundle_l1_functions
    
    # For L0 glue (per-boundary conditional)
    zip_bytes, functions = bundle_l0_functions(project_path, providers_config)
    
    # For L1-L3 (layer-conditional)
    zip_bytes = bundle_l1_functions(project_path)
"""

import os
import io
import json
import zipfile
import logging
from pathlib import Path
from typing import Optional, Tuple, List

logger = logging.getLogger(__name__)


class BundleError(Exception):
    """Raised when function bundling fails."""
    pass


def _get_azure_functions_dir(project_path: str) -> Path:
    """
    Get the azure_functions directory path for core system functions.
    
    Priority:
    1. Project path's azure_functions/ directory (if exists) - for testing/overrides
    2. Core src/providers/azure/azure_functions/ - for production deployment
    
    For user functions, use the project path azure_functions/ directory.
    """
    # First check project path (allows testing with mock data)
    project_functions_dir = Path(project_path) / "azure_functions"
    if project_functions_dir.exists():
        return project_functions_dir
    
    # Fallback to core system functions in src/providers/azure/azure_functions/
    # This is where dispatcher, persister, etc. live
    core_functions_dir = Path(__file__).parent.parent / "azure_functions"
    if core_functions_dir.exists():
        return core_functions_dir
    
    # Last resort: return the project path even if it doesn't exist (will error later)
    return project_functions_dir


def _add_shared_files(zf: zipfile.ZipFile, azure_functions_dir: Path) -> None:
    """Add shared files (requirements.txt, host.json, _shared/) to ZIP."""
    # Add requirements.txt (or create default)
    requirements_path = azure_functions_dir / "requirements.txt"
    if requirements_path.exists():
        zf.write(requirements_path, "requirements.txt")
    else:
        # Create minimal requirements.txt for Azure Functions
        default_requirements = "azure-functions\n"
        zf.writestr("requirements.txt", default_requirements)
    
    # Add host.json (or create default for v2)
    host_path = azure_functions_dir / "host.json"
    if host_path.exists():
        zf.write(host_path, "host.json")
    else:
        # Create minimal host.json for Azure Functions v2
        default_host = json.dumps({
            "version": "2.0",
            "logging": {
                "applicationInsights": {
                    "samplingSettings": {
                        "isEnabled": True
                    }
                }
            },
            "extensionBundle": {
                "id": "Microsoft.Azure.Functions.ExtensionBundle",
                "version": "[4.*, 5.0.0)"
            }
        }, indent=2)
        zf.writestr("host.json", default_host)
    
    # Add _shared directory if exists
    shared_dir = azure_functions_dir / "_shared"
    if shared_dir.exists() and shared_dir.is_dir():
        for root, _, files in os.walk(shared_dir):
            for file in files:
                # Skip __pycache__
                if "__pycache__" in root or file.endswith(".pyc"):
                    continue
                file_path = Path(root) / file
                arcname = file_path.relative_to(azure_functions_dir)
                zf.write(file_path, str(arcname))


def _add_function_dir(zf: zipfile.ZipFile, func_dir: Path, azure_functions_dir: Path, 
                       is_single_function: bool = True) -> None:
    """
    Add a function directory to the ZIP.
    
    For Azure Functions v2 (Python programming model v2):
    - Single function: function_app.py goes at ZIP root
    - Multiple functions: function_app.py is SKIPPED here (handled by _merge_function_files)
    
    Args:
        zf: ZipFile to write to
        func_dir: Path to the function directory
        azure_functions_dir: Base azure_functions directory
        is_single_function: If True, place function_app.py at root; if False, skip it
    """
    if not func_dir.exists():
        logger.warning(f"Function directory does not exist: {func_dir}")
        return
    
    for root, _, files in os.walk(func_dir):
        for file in files:
            # Skip __pycache__ and .pyc files
            if "__pycache__" in root or file.endswith(".pyc"):
                continue
            file_path = Path(root) / file
            
            if file == "function_app.py":
                if is_single_function:
                    # Single function: place at ZIP root
                    arcname = "function_app.py"
                else:
                    # Multi-function: skip, _merge_function_files will handle it
                    continue
            else:
                # Other files keep relative path within function folder
                arcname = str(file_path.relative_to(azure_functions_dir))
            
            zf.write(file_path, arcname)


def _clean_function_app_imports(content: str) -> str:
    """
    Clean up a function_app.py file for bundling.
    
    Removes the try/except import block and sys.path manipulation that is used
    for local development but breaks when functions are bundled into a single ZIP.
    
    Specifically removes patterns like:
        # Handle import path for shared module
        try:
            from _shared.env_utils import require_env
        except ModuleNotFoundError:
            _func_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if _func_dir not in sys.path:
                sys.path.insert(0, _func_dir)
            from _shared.env_utils import require_env
    
    And replaces with simple imports:
        from _shared.env_utils import require_env
    
    Args:
        content: The original function_app.py content
        
    Returns:
        Cleaned content with simple imports
    """
    lines = content.split('\n')
    cleaned_lines = []
    skip_until_unindent = False
    in_try_except_block = False
    seen_shared_imports = set()
    
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        
        # Detect start of the try/except block for imports
        if '# Handle import path for shared module' in line:
            in_try_except_block = True
            i += 1
            continue
        
        # Skip try: line
        if in_try_except_block and stripped == 'try:':
            i += 1
            continue
        
        # Collect _shared imports from inside try block
        if in_try_except_block and 'from _shared.' in line and 'import' in line:
            # Extract and save the import (we'll add it once at the end)
            import_match = line.strip()
            if import_match not in seen_shared_imports:
                seen_shared_imports.add(import_match)
            i += 1
            continue
        
        # Skip except and its contents
        if in_try_except_block and stripped.startswith('except'):
            skip_until_unindent = True
            i += 1
            continue
        
        # Skip lines inside except block
        if skip_until_unindent:
            if line and not line[0].isspace():
                # Unindented line, end of except block
                skip_until_unindent = False
                in_try_except_block = False
                # Don't skip this line, process it normally
            else:
                i += 1
                continue
        
        # Skip standalone sys.path manipulation
        if '_func_dir = os.path.dirname' in line:
            # Skip this and next 2 lines (if/sys.path.insert block)
            i += 1
            while i < len(lines) and ('sys.path' in lines[i] or 'if _func_dir' in lines[i]):
                i += 1
            continue
        
        cleaned_lines.append(line)
        i += 1
    
    # Reconstruct content and add deduplicated imports
    # Find the right place to insert imports (after last standard import)
    if not seen_shared_imports:
        return '\n'.join(cleaned_lines)
    
    final_lines = []
    last_import_idx = -1
    
    # Find the last import line at module level (not indented)
    for idx, line in enumerate(cleaned_lines):
        stripped = line.strip()
        if stripped and not line.startswith(' ') and not line.startswith('\t'):
            if stripped.startswith('import ') or stripped.startswith('from '):
                if '_shared' not in stripped:  # Skip existing _shared imports
                    last_import_idx = idx
    
    # Insert our _shared imports after the last regular import
    for idx, line in enumerate(cleaned_lines):
        final_lines.append(line)
        if idx == last_import_idx:
            # Add _shared imports right after this line
            for imp in sorted(seen_shared_imports):
                final_lines.append(imp)
    
    # If no imports found, add at the beginning after docstring
    if last_import_idx == -1:
        # Find first non-docstring, non-empty line
        insert_idx = 0
        in_docstring = False
        for idx, line in enumerate(final_lines):
            stripped = line.strip()
            if stripped.startswith('"""') or stripped.startswith("'''"):
                if in_docstring:
                    insert_idx = idx + 1
                    break
                elif stripped.count('"""') == 2 or stripped.count("'''") == 2:
                    insert_idx = idx + 1
                    continue
                else:
                    in_docstring = True
            elif not in_docstring and stripped and not stripped.startswith('#'):
                insert_idx = idx
                break
        
        for i, imp in enumerate(sorted(seen_shared_imports)):
            final_lines.insert(insert_idx + i, imp)
    
    return '\n'.join(final_lines)


def _convert_functionapp_to_blueprint(content: str) -> str:
    """
    Convert FunctionApp pattern to Blueprint for multi-function bundles.
    
    User functions use app = func.FunctionApp() for standalone testing,
    but bundling requires bp = func.Blueprint() for registration.
    
    Transforms:
        app = func.FunctionApp()  →  bp = func.Blueprint()
        @app.function_name(...)   →  @bp.function_name(...)
        @app.route(...)           →  @bp.route(...)
    
    Args:
        content: The original function_app.py content
        
    Returns:
        Transformed content with Blueprint pattern
    """
    import re
    # Use regex with word boundaries to avoid matching unrelated code (e.g., email_app.send())
    content = re.sub(
        r'\bapp\s*=\s*func\.FunctionApp\(\)',
        'bp = func.Blueprint()',
        content
    )
    content = re.sub(r'@app\.', '@bp.', content)
    return content


def _convert_require_env_to_lazy(content: str) -> str:
    """
    Convert module-level _require_env calls to lazy loading pattern.
    
    Module-level _require_env() fails at import time during Azure function
    discovery if the env var is missing. Convert to lazy getter functions.
    
    Transforms:
        VAR_NAME = _require_env("ENV_NAME")
    To:
        _var_name = None
        def _get_var_name():
            global _var_name
            if _var_name is None:
                _var_name = _require_env("ENV_NAME")
            return _var_name
    
    Args:
        content: Original function_app.py content
        
    Returns:
        Transformed content with lazy loading
    """
    import re
    
    # Patterns: Handle both _require_env and require_env (no underscore)
    # CONST_NAME = _require_env("ENV_NAME") or CONST_NAME = require_env("ENV_NAME")
    # at module level (not indented)
    patterns = [
        r'^([A-Z][A-Z0-9_]*)\s*=\s*_require_env\(["\']([^"\']+)["\']\)\s*$',
        r'^([A-Z][A-Z0-9_]*)\s*=\s*require_env\(["\']([^"\']+)["\']\)\s*$',
    ]
    
    lines = content.split('\n')
    new_lines = []
    var_map = {}  # CONST_NAME -> getter_call
    
    for line in lines:
        matched = False
        for pattern in patterns:
            match = re.match(pattern, line)
            if match:
                const_name = match.group(1)
                env_name = match.group(2)
                private_var = f"_{const_name.lower()}"
                getter_name = f"_get{private_var}"
                var_map[const_name] = f"{getter_name}()"
                
                # Replace with lazy getter definition
                new_lines.extend([
                    f"{private_var} = None",
                    f"def {getter_name}():",
                    f"    global {private_var}",
                    f"    if {private_var} is None:",
                    f'        {private_var} = _require_env("{env_name}")',
                    f"    return {private_var}",
                ])
                matched = True
                break
        
        if not matched:
            new_lines.append(line)
    
    content = '\n'.join(new_lines)
    
    # Replace usages: CONST_NAME → getter_call()
    for const_name, getter_call in var_map.items():
        content = re.sub(rf'\b{const_name}\b', getter_call, content)
    
    return content


def _merge_function_files(zf: zipfile.ZipFile, func_dirs: List[Path], 
                          azure_functions_dir: Path) -> None:
    """
    Create a main function_app.py that imports and registers Blueprints.
    
    Azure Functions v2 Python model supports Blueprints for modular organization.
    Each function folder contains a Blueprint that is registered with the main app.
    
    Strategy:
    1. Copy each function folder to ZIP (with function_app.py containing Blueprint)
    2. Clean up import paths in each function_app.py (remove sys.path manipulation)
    3. Create main function_app.py at ZIP root that imports and registers Blueprints
    
    Expected ZIP structure after bundling:
    
        deployment.zip/
        ├── function_app.py           ← Main entry (imports from subfolder modules)
        ├── dispatcher/
        │   ├── __init__.py           ← Auto-generated for Python package
        │   └── function_app.py       ← Has: bp = func.Blueprint()
        ├── _shared/
        │   ├── __init__.py
        │   └── env_utils.py
        ├── host.json
        └── requirements.txt
    
    Args:
        zf: ZipFile to write to
        func_dirs: List of function directory paths
        azure_functions_dir: Base azure_functions directory
    """
    if not func_dirs:
        return  # No functions to bundle
    
    # Copy function folders to ZIP (including their function_app.py files)
    for func_dir in func_dirs:
        func_name = func_dir.name
        # Convert folder name for Python import (e.g., "event-checker" -> "event_checker")
        module_name = func_name.replace("-", "_")
        
        # Add __init__.py to make folder a Python package (required for imports)
        zf.writestr(f"{module_name}/__init__.py", "# Auto-generated to make this folder a Python package\n")
        
        for root, _, files in os.walk(func_dir):
            for file in files:
                # Skip __pycache__, .pyc files, and __init__.py (we create our own)
                if "__pycache__" in root or file.endswith(".pyc") or file == "__init__.py":
                    continue
                file_path = Path(root) / file
                
                # Place function folder in ZIP using Python-safe name
                rel_path = file_path.relative_to(func_dir)
                arcname = f"{module_name}/{rel_path}"
                
                # For function_app.py files, clean up import paths and convert to Blueprint
                if file == "function_app.py":
                    content = file_path.read_text(encoding="utf-8")
                    content = _clean_function_app_imports(content)
                    content = _convert_functionapp_to_blueprint(content)
                    content = _convert_require_env_to_lazy(content)
                    zf.writestr(arcname, content)
                else:
                    zf.write(file_path, arcname)
    
    # Generate main function_app.py with Blueprint registrations
    import_lines = []
    register_lines = []
    
    for func_dir in func_dirs:
        func_name = func_dir.name
        module_name = func_name.replace("-", "_")
        bp_alias = f"{module_name}_bp"
        
        import_lines.append(f"from {module_name}.function_app import bp as {bp_alias}")
        register_lines.append(f"app.register_functions({bp_alias})")
    
    imports_section = "\n".join(import_lines)
    register_section = "\n".join(register_lines)
    func_names = ", ".join([d.name for d in func_dirs])
    
    main_content = f'''"""
Auto-generated main function_app.py for Azure Functions Bundle.

This file registers Blueprints from individual function modules.
Functions included: {func_names}

Generated by function_bundler.py
"""
import azure.functions as func

# Import Blueprints from function modules
{imports_section}

# Create the main Function App and register Blueprints
app = func.FunctionApp()
{register_section}
'''
    
    zf.writestr("function_app.py", main_content.strip())


def bundle_l0_functions(
    project_path: str,
    providers_config: dict
) -> Tuple[Optional[bytes], List[str]]:
    """
    Bundle L0 Glue functions based on cross-cloud boundaries.
    
    Only includes functions for boundaries that cross clouds:
    - ingestion: L1 → L2 (if L1 != L2 provider)
    - hot-writer: L2 → L3_hot (if L2 != L3_hot provider)
    - hot-reader: L3_hot → L4/L5 (if L3_hot != L4 or L3_hot != L5)
    
    Args:
        project_path: Absolute path to project directory
        providers_config: Provider configuration dict from config_providers.json
    
    Returns:
        Tuple of (zip_bytes, list_of_included_functions)
        Returns (None, []) if no glue functions needed
    
    Raises:
        BundleError: If bundling fails
    """
    if not project_path:
        raise ValueError("project_path is required")
    
    # L0 glue functions are CORE SYSTEM functions - always use src/providers/azure/azure_functions/
    # This matches the pattern used by bundle_l1_functions and bundle_l2_functions
    azure_functions_dir = Path(__file__).parent.parent / "azure_functions"
    
    if not azure_functions_dir.exists():
        raise BundleError(f"azure_functions directory not found: {azure_functions_dir}")
    
    # Validate required provider configuration
    required_keys = [
        "layer_1_provider",
        "layer_2_provider",
        "layer_3_hot_provider",
        "layer_4_provider",
        "layer_5_provider"
    ]
    
    for key in required_keys:
        if key not in providers_config:
            raise ValueError(f"Missing required provider config: {key}")
    
    l1 = providers_config["layer_1_provider"]
    l2 = providers_config["layer_2_provider"]
    l3_hot = providers_config["layer_3_hot_provider"]
    l4 = providers_config["layer_4_provider"]
    l5 = providers_config["layer_5_provider"]
    
    functions_to_include = []
    
    # L1 → L2 boundary: ingestion function on L2's cloud
    if l1 != l2 and l2 == "azure":
        functions_to_include.append("ingestion")
    
    # L2 → L3_hot boundary: hot-writer function on L3's cloud
    if l2 != l3_hot and l3_hot == "azure":
        functions_to_include.append("hot-writer")
    
    # L3_hot → L4 boundary: data connector (if needed)
    if l3_hot != l4 and l4 == "azure":
        functions_to_include.append("adt-pusher")
    
    # L3_hot → L5 boundary: hot-reader on L5's cloud
    if l3_hot != l5 and l5 == "azure":
        functions_to_include.append("hot-reader")
        functions_to_include.append("hot-reader-last-entry")
    
    # Also add hot-reader if L4 needs to read from different cloud
    if l3_hot != l4 and l4 == "azure" and "hot-reader" not in functions_to_include:
        functions_to_include.append("hot-reader")
        functions_to_include.append("hot-reader-last-entry")
    
    if not functions_to_include:
        logger.info("No L0 glue functions needed (single-cloud deployment)")
        return None, []
    
    logger.info(f"Bundling L0 glue functions: {functions_to_include}")
    
    # Determine if single or multi-function
    is_single = len(functions_to_include) == 1
    
    # Create ZIP
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        _add_shared_files(zf, azure_functions_dir)
        
        # Collect existing function directories
        func_dirs = []
        for func_name in functions_to_include:
            func_dir = azure_functions_dir / func_name
            if func_dir.exists():
                func_dirs.append(func_dir)
                _add_function_dir(zf, func_dir, azure_functions_dir, is_single_function=is_single)
            else:
                logger.warning(f"L0 function not found: {func_name}")
        
        # For multi-function bundles, merge function_app.py files
        if not is_single:
            _merge_function_files(zf, func_dirs, azure_functions_dir)
    
    return zip_buffer.getvalue(), functions_to_include


def bundle_l1_functions(project_path: str) -> bytes:
    """
    Bundle L1 functions (dispatcher) using Blueprint pattern.
    
    NOTE: L1 functions are CORE SYSTEM functions from src/providers/azure/azure_functions/,
    NOT user functions from the project directory.
    
    Creates a ZIP with:
    - function_app.py (main, registers dispatcher blueprint)
    - dispatcher/ (module with bp = func.Blueprint())
    - _shared/
    - host.json, requirements.txt
    
    Args:
        project_path: Absolute path to project directory (used for shared config only)
    
    Returns:
        ZIP bytes for L1 Function App
    
    Raises:
        BundleError: If bundling fails
    """
    if not project_path:
        raise ValueError("project_path is required")
    
    # L1 dispatcher is a CORE SYSTEM function - always use src/providers/azure/azure_functions/
    core_functions_dir = Path(__file__).parent.parent / "azure_functions"
    
    if not core_functions_dir.exists():
        raise BundleError(f"Core azure_functions directory not found: {core_functions_dir}")
    
    functions = ["dispatcher"]
    
    logger.info(f"Bundling L1 functions from {core_functions_dir}: {functions}")
    
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        _add_shared_files(zf, core_functions_dir)
        
        # Collect function directories
        func_dirs = []
        for func_name in functions:
            func_dir = core_functions_dir / func_name
            if func_dir.exists():
                func_dirs.append(func_dir)
            else:
                raise BundleError(f"L1 function not found: {func_dir}")
        
        # Always use Blueprint pattern - even for single function
        # This ensures consistent structure and proper function discovery
        _merge_function_files(zf, func_dirs, core_functions_dir)
    
    return zip_buffer.getvalue()


def bundle_l2_functions(project_path: str) -> bytes:
    """
    Bundle L2 functions (persister, event-checker).
    
    NOTE: L2 functions are CORE SYSTEM functions from src/providers/azure/azure_functions/,
    NOT user functions from the project directory.
    
    Args:
        project_path: Absolute path to project directory (used for shared config only)
    
    Returns:
        ZIP bytes for L2 Function App
    
    Raises:
        BundleError: If bundling fails
    """
    if not project_path:
        raise ValueError("project_path is required")
    
    # L2 functions are CORE SYSTEM functions - always use src/providers/azure/azure_functions/
    core_functions_dir = Path(__file__).parent.parent / "azure_functions"
    
    if not core_functions_dir.exists():
        raise BundleError(f"Core azure_functions directory not found: {core_functions_dir}")
    
    # Core functions
    functions = ["persister"]
    
    # Optional: event-checker if exists
    event_checker_dir = core_functions_dir / "event-checker"
    if event_checker_dir.exists():
        functions.append("event-checker")
    
    logger.info(f"Bundling L2 functions from {core_functions_dir}: {functions}")
    
    # Determine if this is a single or multi-function bundle
    is_single = len(functions) == 1
    
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        _add_shared_files(zf, core_functions_dir)
        
        # Collect existing function directories
        func_dirs = []
        for func_name in functions:
            func_dir = core_functions_dir / func_name
            if func_dir.exists():
                func_dirs.append(func_dir)
                _add_function_dir(zf, func_dir, core_functions_dir, is_single_function=is_single)
            else:
                raise BundleError(f"L2 function not found: {func_dir}")
        
        # For multi-function bundles, merge function_app.py files
        if not is_single:
            _merge_function_files(zf, func_dirs, core_functions_dir)
    
    return zip_buffer.getvalue()


def bundle_l3_functions(project_path: str) -> bytes:
    """
    Bundle L3 functions (hot-reader, movers).
    
    NOTE: L3 functions are CORE SYSTEM functions from src/providers/azure/azure_functions/,
    NOT user functions from the project directory.
    
    Args:
        project_path: Absolute path to project directory (used for shared config only)
    
    Returns:
        ZIP bytes for L3 Function App
    
    Raises:
        BundleError: If bundling fails
    """
    if not project_path:
        raise ValueError("project_path is required")
    
    # L3 functions are CORE SYSTEM functions - always use src/providers/azure/azure_functions/
    core_functions_dir = Path(__file__).parent.parent / "azure_functions"
    
    if not core_functions_dir.exists():
        raise BundleError(f"Core azure_functions directory not found: {core_functions_dir}")
    
    # Core functions for L3
    functions = [
        "hot-reader",
        "hot-reader-last-entry",
        "hot-to-cold-mover",
        "cold-to-archive-mover"
    ]
    
    logger.info(f"Bundling L3 functions from {core_functions_dir}: {functions}")
    
    # L3 always has multiple functions
    is_single = len(functions) == 1
    
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        _add_shared_files(zf, core_functions_dir)
        
        # Collect existing function directories
        func_dirs = []
        for func_name in functions:
            func_dir = core_functions_dir / func_name
            if func_dir.exists():
                func_dirs.append(func_dir)
                _add_function_dir(zf, func_dir, core_functions_dir, is_single_function=is_single)
            else:
                logger.warning(f"L3 function not found (optional): {func_name}")
        
        # For multi-function bundles, merge function_app.py files
        if not is_single:
            _merge_function_files(zf, func_dirs, core_functions_dir)
    
    return zip_buffer.getvalue()


def bundle_l4_functions(project_path: str) -> bytes:
    """
    Bundle L4 functions (ADT-related).
    
    Note: L4 may not need a separate Function App if ADT updates
    are done via Python SDK directly from L2/L3.
    
    Args:
        project_path: Absolute path to project directory
    
    Returns:
        ZIP bytes for L4 Function App
    
    Raises:
        BundleError: If bundling fails
    """
    if not project_path:
        raise ValueError("project_path is required")
    
    azure_functions_dir = _get_azure_functions_dir(project_path)
    
    # L4 functions - optional ADT updater
    functions = ["adt-updater"]
    
    logger.info(f"Bundling L4 functions: {functions}")
    
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        _add_shared_files(zf, azure_functions_dir)
        
        for func_name in functions:
            func_dir = azure_functions_dir / func_name
            if func_dir.exists():
                _add_function_dir(zf, func_dir, azure_functions_dir)
            else:
                logger.warning(f"L4 function not found: {func_name}")
    
    return zip_buffer.getvalue()


def bundle_user_functions(project_path: str) -> Optional[bytes]:
    """
    Bundle user-customizable functions from upload/<project>/azure_functions/.
    
    User functions are:
    - processors/: Custom data processing logic (wraps user code with Azure trigger)
    - event_actions/: Event-triggered actions (threshold checks, alerts)
    - event-feedback/: Event feedback handlers (device control responses)
    
    These functions are deployed to a separate Function App (user-functions)
    to allow independent updates without redeploying core infrastructure.
    
    Args:
        project_path: Absolute path to project directory (upload/<project>)
    
    Returns:
        ZIP bytes for user Function App, or None if no user functions found
    
    Raises:
        BundleError: If bundling fails
    """
    if not project_path:
        raise ValueError("project_path is required")
    
    # User functions should be in the upload template's azure_functions directory
    user_funcs_dir = Path(project_path) / "azure_functions"
    
    if not user_funcs_dir.exists():
        logger.info(f"No user functions directory at {user_funcs_dir}")
        return None
    
    # User function folders
    user_function_folders = ["processors", "event_actions", "event-feedback"]
    
    # Check if any user functions exist
    found_folders = []
    for folder_name in user_function_folders:
        folder_path = user_funcs_dir / folder_name
        if folder_path.exists() and folder_path.is_dir():
            # Direct function_app.py (e.g., event-feedback/)
            if (folder_path / "function_app.py").exists():
                found_folders.append(folder_path)
            else:
                # Nested subfolders (e.g., processors/sensor-1/, event_actions/callback/)
                for subfolder in folder_path.iterdir():
                    if subfolder.is_dir() and (subfolder / "function_app.py").exists():
                        found_folders.append(subfolder)
    
    if not found_folders:
        logger.info(f"No user functions found in {user_funcs_dir}")
        return None
    
    logger.info(f"Bundling user functions: {found_folders}")
    
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        # Add shared files from the core azure_functions directory
        # (requirements.txt, host.json, _shared/)
        core_azure_funcs = Path(__file__).parent.parent / "azure_functions"
        _add_shared_files(zf, core_azure_funcs)
        
        # Add each user function folder
        func_dirs = []
        for func_dir in found_folders:
            func_dirs.append(func_dir)
            _add_function_dir(zf, func_dir, user_funcs_dir, is_single_function=False)
        
        # Create main function_app.py that registers all Blueprints
        _merge_function_files(zf, func_dirs, user_funcs_dir)
    
    return zip_buffer.getvalue()

