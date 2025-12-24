"""
Azure Function Bundler - Provider-specific bundling logic.

This module handles Azure-specific bundling requirements:
- Blueprint pattern for multi-function apps
- Import cleanup (removing sys.path manipulation)
- FunctionApp to Blueprint conversion
- Lazy loading of environment variables

Uses the function registry to determine which functions to bundle.
"""
import os
import io
import json
import zipfile
import logging
import re
from pathlib import Path
from typing import Optional, Tuple, List

from src.function_registry import (
    Layer, FunctionDefinition, PROVIDER_PATHS,
    get_by_layer, get_l0_for_config, get_function_path
)

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
    
    # Fallback to core system functions
    core_functions_dir = Path(__file__).parent / "azure_functions"
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


def _clean_function_app_imports(content: str) -> str:
    """
    Clean up a function_app.py file for bundling.
    
    Removes the try/except import block and sys.path manipulation that is used
    for local development but breaks when functions are bundled into a single ZIP.
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
                skip_until_unindent = False
                in_try_except_block = False
            else:
                i += 1
                continue
        
        # Skip standalone sys.path manipulation
        if '_func_dir = os.path.dirname' in line:
            i += 1
            while i < len(lines) and ('sys.path' in lines[i] or 'if _func_dir' in lines[i]):
                i += 1
            continue
        
        cleaned_lines.append(line)
        i += 1
    
    # Reconstruct content and add deduplicated imports
    if not seen_shared_imports:
        return '\n'.join(cleaned_lines)
    
    final_lines = []
    last_import_idx = -1
    
    # Find the last import line at module level
    for idx, line in enumerate(cleaned_lines):
        stripped = line.strip()
        if stripped and not line.startswith(' ') and not line.startswith('\t'):
            if stripped.startswith('import ') or stripped.startswith('from '):
                if '_shared' not in stripped:
                    last_import_idx = idx
    
    # Insert _shared imports after the last regular import
    for idx, line in enumerate(cleaned_lines):
        final_lines.append(line)
        if idx == last_import_idx:
            for imp in sorted(seen_shared_imports):
                final_lines.append(imp)
    
    # If no imports found, add at the beginning after docstring
    if last_import_idx == -1:
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
    
    Transforms:
        app = func.FunctionApp()  →  bp = func.Blueprint()
        @app.function_name(...)   →  @bp.function_name(...)
    """
    content = re.sub(
        r'\bapp\s*=\s*func\.FunctionApp\(\)',
        'bp = func.Blueprint()',
        content
    )
    content = re.sub(r'@app\.', '@bp.', content)
    return content


def _extract_function_names(content: str) -> List[str]:
    """
    Extract Azure function names from function_app.py content.
    
    Matches patterns like:
        @app.function_name(name="my-function")
        @bp.function_name(name="my-function")
    """
    pattern = r'@(?:app|bp)\.function_name\s*\(\s*name\s*=\s*["\']([^"\']+)["\']\s*\)'
    return re.findall(pattern, content)


def _validate_no_duplicate_function_names(
    func_dirs: List[Path],
    processed_contents: dict[str, str]
) -> None:
    """
    Validate that no duplicate Azure function names exist across all functions.
    
    Args:
        func_dirs: List of function directories being bundled
        processed_contents: Dict mapping module_name -> processed function_app.py content
    
    Raises:
        BundleError: If duplicate function names are detected
    """
    seen_names: dict[str, str] = {}  # function_name -> module_name that declared it
    duplicates: List[str] = []
    
    for module_name, content in processed_contents.items():
        func_names = _extract_function_names(content)
        for func_name in func_names:
            if func_name in seen_names:
                duplicates.append(
                    f"Function name '{func_name}' is declared in both "
                    f"'{seen_names[func_name]}' and '{module_name}'"
                )
            else:
                seen_names[func_name] = module_name
    
    if duplicates:
        error_msg = "Duplicate Azure function names detected:\n" + "\n".join(f"  - {d}" for d in duplicates)
        logger.error(error_msg)
        raise BundleError(error_msg)


def _convert_require_env_to_lazy(content: str) -> str:
    """
    Convert module-level require_env calls to lazy loading pattern.
    
    Module-level require_env() fails at import time during Azure function
    discovery if the env var is missing. Convert to lazy getter functions.
    
    NOTE: This only converts simple `CONST = require_env("ENV")` patterns.
    Complex patterns like `json.loads(require_env("ENV"))` should be manually
    refactored in the source files to use lazy loading.
    """
    patterns = [
        r'^([A-Z][A-Z0-9_]*)\s*=\s*_require_env\(["\']([^"\']+)["\']\)\s*$',
        r'^([A-Z][A-Z0-9_]*)\s*=\s*require_env\(["\']([^"\']+)["\']\)\s*$',
    ]
    
    lines = content.split('\n')
    new_lines = []
    var_map = {}
    # Store env_name -> placeholder to protect from replacement
    env_placeholders = {}
    placeholder_counter = 0
    
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
                
                # Create a unique placeholder for the env var name
                placeholder = f"__ENV_PLACEHOLDER_{placeholder_counter}__"
                env_placeholders[placeholder] = env_name
                placeholder_counter += 1
                
                new_lines.extend([
                    f"{private_var} = None",
                    f"def {getter_name}():",
                    f"    global {private_var}",
                    f"    if {private_var} is None:",
                    f'        {private_var} = require_env("{placeholder}")',
                    f"    return {private_var}",
                ])
                matched = True
                break
        
        if not matched:
            new_lines.append(line)
    
    content = '\n'.join(new_lines)
    
    # Replace usages of const names with getter calls
    for const_name, getter_call in var_map.items():
        content = re.sub(rf'\b{const_name}\b', getter_call, content)
    
    # Restore the actual env var names from placeholders
    for placeholder, env_name in env_placeholders.items():
        content = content.replace(placeholder, env_name)
    
    return content


def _merge_function_files(zf: zipfile.ZipFile, func_dirs: List[Path], 
                          azure_functions_dir: Path) -> None:
    """
    Create a main function_app.py that imports and registers Blueprints.
    
    Azure Functions v2 Python model supports Blueprints for modular organization.
    Validates that no duplicate function names exist before writing to ZIP.
    """
    if not func_dirs:
        return
    
    # First pass: collect and process all function_app.py files
    processed_contents: dict[str, str] = {}  # module_name -> processed content
    other_files: List[Tuple[Path, str, str]] = []  # (file_path, arcname, module_name)
    
    for func_dir in func_dirs:
        func_name = func_dir.name
        module_name = func_name.replace("-", "_")
        
        for root, _, files in os.walk(func_dir):
            for file in files:
                if "__pycache__" in root or file.endswith(".pyc") or file == "__init__.py":
                    continue
                file_path = Path(root) / file
                
                rel_path = file_path.relative_to(func_dir)
                arcname = f"{module_name}/{rel_path}"
                
                # For function_app.py files, process and store for validation
                if file == "function_app.py":
                    content = file_path.read_text(encoding="utf-8")
                    content = _clean_function_app_imports(content)
                    content = _convert_functionapp_to_blueprint(content)
                    content = _convert_require_env_to_lazy(content)
                    processed_contents[module_name] = content
                else:
                    other_files.append((file_path, arcname, module_name))
    
    # VALIDATE: Check for duplicate function names before writing anything
    _validate_no_duplicate_function_names(func_dirs, processed_contents)
    
    # Second pass: write validated content to ZIP
    for func_dir in func_dirs:
        func_name = func_dir.name
        module_name = func_name.replace("-", "_")
        
        # Add __init__.py to make folder a Python package
        zf.writestr(f"{module_name}/__init__.py", "# Auto-generated to make this folder a Python package\n")
        
        # Write the processed function_app.py
        if module_name in processed_contents:
            zf.writestr(f"{module_name}/function_app.py", processed_contents[module_name])
    
    # Write other files
    for file_path, arcname, _ in other_files:
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

Generated by azure_bundler.py
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
    
    Uses the function registry to determine which glue functions are needed.
    """
    if not project_path:
        raise ValueError("project_path is required")
    
    azure_functions_dir = Path(__file__).parent / "azure_functions"
    
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

    # Use registry to get L0 functions
    functions_to_include = get_l0_for_config(providers_config, "azure")
    
    if not functions_to_include:
        logger.info("No L0 glue functions needed (single-cloud deployment)")
        return None, []
    
    logger.info(f"Bundling L0 glue functions: {functions_to_include}")
    
    is_single = len(functions_to_include) == 1
    
    # Create ZIP
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        _add_shared_files(zf, azure_functions_dir)
        
        func_dirs = []
        for func_name in functions_to_include:
            func_dir = azure_functions_dir / func_name
            if func_dir.exists():
                func_dirs.append(func_dir)
            else:
                logger.warning(f"L0 function not found: {func_name}")
        
        # For multi-function bundles, merge function_app.py files
        if is_single and func_dirs:
            # Single function: add directly
            for root, _, files in os.walk(func_dirs[0]):
                for file in files:
                    if "__pycache__" in root or file.endswith(".pyc"):
                        continue
                    file_path = Path(root) / file
                    if file == "function_app.py":
                        arcname = "function_app.py"
                    else:
                        arcname = str(file_path.relative_to(azure_functions_dir))
                    zf.write(file_path, arcname)
        else:
            _merge_function_files(zf, func_dirs, azure_functions_dir)
    
    return zip_buffer.getvalue(), functions_to_include


def bundle_l1_functions(project_path: str) -> bytes:
    """Bundle L1 functions (dispatcher) using Blueprint pattern."""
    if not project_path:
        raise ValueError("project_path is required")
    
    core_functions_dir = Path(__file__).parent / "azure_functions"
    
    if not core_functions_dir.exists():
        raise BundleError(f"Core azure_functions directory not found: {core_functions_dir}")
    
    # Use registry
    l1_funcs = get_by_layer(Layer.L1_ACQUISITION)
    functions = [f.get_dir_name() for f in l1_funcs if "azure" in f.providers]
    
    logger.info(f"Bundling L1 functions from {core_functions_dir}: {functions}")
    
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        _add_shared_files(zf, core_functions_dir)
        
        func_dirs = []
        for func_name in functions:
            func_dir = core_functions_dir / func_name
            if func_dir.exists():
                func_dirs.append(func_dir)
            else:
                raise BundleError(f"L1 function not found: {func_dir}")
        
        # Always use Blueprint pattern
        _merge_function_files(zf, func_dirs, core_functions_dir)
    
    return zip_buffer.getvalue()


def bundle_l2_functions(project_path: str) -> bytes:
    """Bundle L2 functions (persister, event-checker)."""
    if not project_path:
        raise ValueError("project_path is required")
    
    core_functions_dir = Path(__file__).parent / "azure_functions"
    
    if not core_functions_dir.exists():
        raise BundleError(f"Core azure_functions directory not found: {core_functions_dir}")
    
    # Use registry
    l2_funcs = get_by_layer(Layer.L2_PROCESSING)
    functions = []
    for f in l2_funcs:
        if "azure" in f.providers:
            func_dir = core_functions_dir / f.get_dir_name()
            if func_dir.exists() or not f.is_optional:
                functions.append(f.get_dir_name())
    
    logger.info(f"Bundling L2 functions from {core_functions_dir}: {functions}")
    
    is_single = len(functions) == 1
    
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        _add_shared_files(zf, core_functions_dir)
        
        func_dirs = []
        for func_name in functions:
            func_dir = core_functions_dir / func_name
            if func_dir.exists():
                func_dirs.append(func_dir)
            else:
                raise BundleError(f"L2 function not found: {func_dir}")
        
        if not is_single:
            _merge_function_files(zf, func_dirs, core_functions_dir)
        else:
            # Single function bundling (shouldn't happen for L2 but handle it)
            _merge_function_files(zf, func_dirs, core_functions_dir)
    
    return zip_buffer.getvalue()


def bundle_l3_functions(project_path: str) -> bytes:
    """Bundle L3 functions (hot-reader, movers)."""
    if not project_path:
        raise ValueError("project_path is required")
    
    core_functions_dir = Path(__file__).parent / "azure_functions"
    
    if not core_functions_dir.exists():
        raise BundleError(f"Core azure_functions directory not found: {core_functions_dir}")
    
    # Use registry
    l3_funcs = get_by_layer(Layer.L3_STORAGE)
    functions = []
    for f in l3_funcs:
        if "azure" in f.providers:
            func_dir = core_functions_dir / f.get_dir_name()
            if func_dir.exists():
                functions.append(f.get_dir_name())
            elif not f.is_optional:
                logger.warning(f"L3 function not found (optional): {f.get_dir_name()}")
    
    logger.info(f"Bundling L3 functions from {core_functions_dir}: {functions}")
    
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        _add_shared_files(zf, core_functions_dir)
        
        func_dirs = []
        for func_name in functions:
            func_dir = core_functions_dir / func_name
            if func_dir.exists():
                func_dirs.append(func_dir)
        
        _merge_function_files(zf, func_dirs, core_functions_dir)
    
    return zip_buffer.getvalue()


def bundle_l4_functions(project_path: str) -> bytes:
    """Bundle L4 functions (ADT-related)."""
    if not project_path:
        raise ValueError("project_path is required")
    
    azure_functions_dir = _get_azure_functions_dir(project_path)
    
    # Use registry
    l4_funcs = get_by_layer(Layer.L4_MANAGEMENT)
    functions = [f.get_dir_name() for f in l4_funcs if "azure" in f.providers]
    
    logger.info(f"Bundling L4 functions: {functions}")
    
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        _add_shared_files(zf, azure_functions_dir)
        
        func_dirs = []
        for func_name in functions:
            func_dir = azure_functions_dir / func_name
            if func_dir.exists():
                func_dirs.append(func_dir)
            else:
                logger.warning(f"L4 function not found: {func_name}")
        
        if func_dirs:
            _merge_function_files(zf, func_dirs, azure_functions_dir)
    
    return zip_buffer.getvalue()


def bundle_user_functions(project_path: str) -> Optional[bytes]:
    """
    Bundle user-customizable functions from upload/<project>/azure_functions/.
    
    User functions are discovered from the filesystem, not the registry.
    """
    if not project_path:
        raise ValueError("project_path is required")
    
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
            # Direct function_app.py
            if (folder_path / "function_app.py").exists():
                found_folders.append(folder_path)
            else:
                # Nested subfolders
                for subfolder in folder_path.iterdir():
                    if subfolder.is_dir() and (subfolder / "function_app.py").exists():
                        found_folders.append(subfolder)
    
    if not found_folders:
        logger.info(f"No user functions found in {user_funcs_dir}")
        return None
    
    logger.info(f"Bundling user functions: {found_folders}")
    
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        # Add shared files from the CORE azure_functions directory (not project path)
        # This ensures _shared/ utilities (env_utils.py, etc.) are always included
        core_azure_funcs = Path(__file__).parent / "azure_functions"
        _add_shared_files(zf, core_azure_funcs)
        
        # Add each user function folder
        func_dirs = []
        for func_dir in found_folders:
            func_dirs.append(func_dir)
        
        # Create main function_app.py that registers all Blueprints
        _merge_function_files(zf, func_dirs, user_funcs_dir)
    
    return zip_buffer.getvalue()
