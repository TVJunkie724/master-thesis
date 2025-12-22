"""
Comprehensive Azure Function ZIP validation test.

Validates:
1. All ZIPs build successfully
2. Required files present (function_app.py, host.json, requirements.txt, _shared/)
3. Blueprint pattern correct in submodules
4. FunctionApp pattern in main
5. No syntax errors in Python files
6. Expected functions are present
7. No module-level _require_env in user functions
"""
import sys
import io
import zipfile
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from src.providers.terraform.package_builder import (
    build_azure_l0_bundle,
    build_azure_l2_bundle,
    build_azure_user_bundle,
)


def validate_zip_structure(zip_bytes: bytes, zip_name: str, expected_functions: list):
    """Validate ZIP has required structure and files."""
    print(f"\n{'='*60}")
    print(f"Validating {zip_name}")
    print(f"{'='*60}")
    
    if not zip_bytes:
        print(f"❌ {zip_name}: No ZIP generated!")
        return False
    
    print(f"✓ ZIP size: {len(zip_bytes)} bytes")
    
    zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    files = zf.namelist()
    
    # Check required files
    required_files = ["function_app.py", "host.json", "requirements.txt"]
    for req_file in required_files:
        if req_file in files:
            print(f"✓ Has {req_file}")
        else:
            print(f"❌ Missing {req_file}")
            return False
    
    # Check _shared folder
    shared_files = [f for f in files if f.startswith("_shared/")]
    if shared_files:
        print(f"✓ Has _shared/ folder ({len(shared_files)} files)")
    else:
        print(f"❌ Missing _shared/ folder")
        return False
    
    # Validate requirements.txt content
    req_content = zf.read("requirements.txt").decode("utf-8")
    if "azure-functions" in req_content:
        print("✓ requirements.txt has azure-functions")
    else:
        print("❌ requirements.txt missing azure-functions dependency")
        return False
    
    # Validate host.json structure
    import json
    host_content = zf.read("host.json").decode("utf-8")
    try:
        host_json = json.loads(host_content)
        if "version" in host_json:
            print(f"✓ host.json valid (version: {host_json['version']})")
        else:
            print("❌ host.json missing 'version' field")
            return False
    except json.JSONDecodeError as e:
        print(f"❌ host.json is not valid JSON: {e}")
        return False
    
    # Validate main function_app.py
    main_content = zf.read("function_app.py").decode("utf-8")
    if "app = func.FunctionApp()" in main_content:
        print("✓ Main uses FunctionApp()")
    else:
        print("❌ Main doesn't use FunctionApp()")
        return False
    
    if "app.register_functions(" in main_content:
        print("✓ Main registers blueprints")
    else:
        print("❌ Main doesn't register blueprints")
        return False
    
    # Validate submodule function_app.py files
    submodule_files = [f for f in files if f.endswith("/function_app.py") and f != "function_app.py"]
    print(f"✓ Found {len(submodule_files)} submodule function_app.py files")
    
    for submodule in submodule_files:
        content = zf.read(submodule).decode("utf-8")
        module_name = submodule.split('/')[0]
        
        # Check Blueprint pattern
        if "bp = func.Blueprint()" not in content:
            print(f"  ❌ {module_name}: Missing Blueprint pattern")
            return False
        
        # Check @bp decorators
        if "@bp." not in content:
            print(f"  ❌ {module_name}: Missing @bp decorators")
            return False
        
        # Check for module-level _require_env (only for user functions)
        if zip_name == "User Functions":
            module_level_require = re.findall(r'^[A-Z][A-Z_]+ = _require_env', content, re.MULTILINE)
            if module_level_require:
                print(f"  ❌ {module_name}: Module-level _require_env found: {module_level_require}")
                return False
        
        # Syntax check
        try:
            compile(content, submodule, 'exec')
        except SyntaxError as e:
            print(f"  ❌ {module_name}: Syntax error: {e}")
            return False
    
    print(f"✓ All {len(submodule_files)} submodules use Blueprint pattern")
    
    # Check expected functions
    found_functions = set()
    for submodule in submodule_files:
        func_name = submodule.split('/')[0].replace('_', '-')
        found_functions.add(func_name)
    
    missing = set(expected_functions) - found_functions
    extra = found_functions - set(expected_functions)
    
    if missing:
        print(f"⚠ Missing expected functions: {missing}")
    if extra:
        print(f"⚠ Extra functions (not expected): {extra}")
    
    for func in expected_functions:
        func_normalized = func.replace('-', '_')
        if func_normalized in [f.replace('-', '_') for f in found_functions]:
            print(f"  ✓ {func}")
        else:
            print(f"  ❌ Missing: {func}")
            return False
    
    print(f"\n✅ {zip_name} validation PASSED")
    return True


def test_all_zips():
    """Build and validate all Azure function ZIPs."""
    project_path = "/app/upload/template"
    
    # Multicloud providers config for L0
    providers_config = {
        "layer_1_provider": "gcp",
        "layer_2_provider": "azure",
        "layer_3_hot_provider": "aws",
        "layer_3_cold_provider": "aws",
        "layer_4_provider": "azure",
        "layer_5_provider": "azure"
    }
    
    all_passed = True
    
    # Test L0 Glue Functions
    print("\n" + "="*60)
    print("Building L0 Glue Functions ZIP...")
    print("="*60)
    l0_path = build_azure_l0_bundle(Path(project_path), providers_config)
    l0_bytes = l0_path.read_bytes() if l0_path else None
    expected_l0 = ["ingestion", "adt-pusher", "hot-reader", "hot-reader-last-entry"]
    if not validate_zip_structure(l0_bytes, "L0 Glue Functions", expected_l0):
        all_passed = False
    
    # Test L2 Processor Functions
    print("\n" + "="*60)
    print("Building L2 Processor Functions ZIP...")
    print("="*60)
    l2_path = build_azure_l2_bundle(Path(project_path))
    l2_bytes = l2_path.read_bytes() if l2_path else None
    expected_l2 = ["persister", "event-checker"]
    if not validate_zip_structure(l2_bytes, "L2 Processor Functions", expected_l2):
        all_passed = False
    
    # Test User Functions
    print("\n" + "="*60)
    print("Building User Functions ZIP...")
    print("="*60)
    providers = {"layer_2_provider": "azure"}
    user_zip_path = build_azure_user_bundle(Path(project_path), providers)
    if user_zip_path:
        user_bytes = user_zip_path.read_bytes()
    else:
        user_bytes = None
    expected_user = ["event_feedback", "default_processor", "temperature_sensor_2", "high_temperature_callback", "high_temperature_callback_2"]
    if not validate_zip_structure(user_bytes, "User Functions", expected_user):
        all_passed = False
    
    # Final summary
    print("\n" + "="*60)
    print("FINAL SUMMARY")
    print("="*60)
    if all_passed:
        print("✅ ALL ZIP VALIDATIONS PASSED!")
        print("\nAll Azure function ZIPs are deployment-ready:")
        print(f"  • L0 Glue: {len(l0_bytes)} bytes")
        print(f"  • L2 Processor: {len(l2_bytes)} bytes")
        print(f"  • User Functions: {len(user_bytes)} bytes")
        return 0
    else:
        print("❌ SOME VALIDATIONS FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(test_all_zips())
