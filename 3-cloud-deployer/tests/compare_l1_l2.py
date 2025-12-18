"""Comprehensive comparison of L1 (dispatcher) vs L2 (persister/event-checker)."""
import sys
sys.path.insert(0, '/app/src')
from providers.azure.layers.function_bundler import bundle_l1_functions, bundle_l2_functions
import zipfile
import io

def compare_structure(name, zip_bytes):
    """Print ZIP structure and key file contents."""
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")
    
    if not zip_bytes:
        print("  ERROR: No ZIP bytes returned!")
        return
    
    zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    
    print(f"\n  Files ({len(zf.namelist())}):")
    for name in sorted(zf.namelist()):
        info = zf.getinfo(name)
        print(f"    {name:<45} ({info.file_size:>5} bytes)")
    
    # Check required files
    print("\n  Required Files Check:")
    required = ['function_app.py', 'host.json', 'requirements.txt']
    for r in required:
        if r in zf.namelist():
            print(f"    ✓ {r}")
        else:
            print(f"    ✗ {r} MISSING!")
    
    # Check for __init__.py in subfolders
    print("\n  Subfolders with __init__.py:")
    folders = set()
    for name in zf.namelist():
        if '/' in name:
            folder = name.split('/')[0]
            folders.add(folder)
    
    for folder in sorted(folders):
        init_file = f"{folder}/__init__.py"
        has_init = init_file in zf.namelist()
        has_func = f"{folder}/function_app.py" in zf.namelist()
        if has_func:
            status = "✓" if has_init else "✗ MISSING __init__.py!"
            print(f"    {status} {folder}/")
    
    # Print main function_app.py
    print("\n  Main function_app.py:")
    content = zf.read('function_app.py').decode('utf-8')
    for line in content.strip().split('\n'):
        print(f"    | {line}")
    
    # Check for Blueprint pattern in subfolders
    print("\n  Blueprint check in submodules:")
    for folder in sorted(folders):
        func_file = f"{folder}/function_app.py"
        if func_file in zf.namelist():
            content = zf.read(func_file).decode('utf-8')
            has_blueprint = 'bp = func.Blueprint()' in content
            has_app = 'app = func.FunctionApp()' in content
            has_lazy = '_digital_twin_info = None' in content or 'lazy' in content.lower()
            has_try_except = 'except ModuleNotFoundError:' in content
            
            print(f"    {folder}/function_app.py:")
            print(f"      - Blueprint (bp = func.Blueprint()): {'✓' if has_blueprint else '✗'}")
            print(f"      - Legacy app (app = func.FunctionApp()): {'✗ FOUND!' if has_app else '✓ not present'}")
            print(f"      - Lazy loading pattern: {'✓' if has_lazy else '?'}")
            print(f"      - Has try/except import: {'✓' if has_try_except else '✗'}")

    return zf


print("\n" + "="*70)
print("  COMPREHENSIVE L1 vs L2 COMPARISON")
print("="*70)

# Build ZIPs
l1_bytes = bundle_l1_functions('/app/upload/template')
l2_bytes = bundle_l2_functions('/app/upload/template')

# Compare
zf1 = compare_structure("L1 Bundle (dispatcher)", l1_bytes)
zf2 = compare_structure("L2 Bundle (persister/event-checker) - WORKING", l2_bytes)

# Direct content comparison of key difference
print("\n" + "="*70)
print("  KEY DIFFERENCES")
print("="*70)

if zf1 and zf2:
    print("\n  Blueprint registration patterns:")
    print("\n    L1 main function_app.py imports:")
    l1_main = zf1.read('function_app.py').decode('utf-8')
    for line in l1_main.split('\n'):
        if 'import' in line or 'register' in line:
            print(f"      {line}")
    
    print("\n    L2 main function_app.py imports:")
    l2_main = zf2.read('function_app.py').decode('utf-8')
    for line in l2_main.split('\n'):
        if 'import' in line or 'register' in line:
            print(f"      {line}")

print("\n" + "="*70)
print("  DONE")
print("="*70)
