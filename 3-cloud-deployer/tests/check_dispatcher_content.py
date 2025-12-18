"""Check exact bundled dispatcher content."""
import sys
sys.path.insert(0, '/app/src')
from providers.azure.layers.function_bundler import bundle_l1_functions
import zipfile
import io

print("="*70)
print("  BUNDLED DISPATCHER/FUNCTION_APP.PY CONTENT")
print("="*70)

l1_bytes = bundle_l1_functions('/app/upload/template')
if l1_bytes:
    zf = zipfile.ZipFile(io.BytesIO(l1_bytes))
    content = zf.read('dispatcher/function_app.py').decode('utf-8')
    
    # Print first 100 lines
    lines = content.split('\n')
    print(f"\n  First 80 lines of dispatcher/function_app.py:\n")
    for i, line in enumerate(lines[:80], 1):
        print(f"    {i:3d}| {line}")
    
    # Check for problematic patterns
    print("\n  ISSUE CHECKS:")
    if 'sys.path.insert' in content:
        print("    ✗ PROBLEM: sys.path.insert FOUND - this will break!")
    else:
        print("    ✓ No sys.path.insert")
    
    if 'except ModuleNotFoundError' in content:
        print("    ✗ PROBLEM: try/except import pattern FOUND - may break!")
    else:
        print("    ✓ No try/except import pattern")
    
    if 'bp = func.Blueprint()' in content:
        print("    ✓ Blueprint pattern present")
    else:
        print("    ✗ PROBLEM: Blueprint pattern MISSING")
    
    if 'app = func.FunctionApp()' in content:
        print("    ✗ PROBLEM: Legacy FunctionApp() in submodule!")
    else:
        print("    ✓ No legacy FunctionApp()")
    
    if 'from _shared' in content:
        print("    ✓ Clean _shared import")
