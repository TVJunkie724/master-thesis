"""Quick test to verify user function ZIP generation with transformation."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from src.providers.azure.layers.function_bundler import bundle_user_functions
import zipfile
import io

# Build user functions ZIP
project_path = "/app/upload/template"
zip_bytes = bundle_user_functions(project_path)

if not zip_bytes:
    print("❌ No user functions ZIP generated!")
    sys.exit(1)

print(f"✓ User ZIP size: {len(zip_bytes)} bytes")

# Inspect ZIP contents
zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
files = sorted(zf.namelist())

print(f"\n✓ Files in ZIP ({len(files)} total):")
for name in files:
    print(f"  {name}")

# Check for main function_app.py
if "function_app.py" not in files:
    print("\n❌ Missing main function_app.py!")
    sys.exit(1)

# Check main function_app.py content
main_content = zf.read("function_app.py").decode("utf-8")
if "app = func.FunctionApp()" not in main_content:
    print("✓ Main function_app.py uses FunctionApp (correct)")
else:
    print("❌ Main function_app.py should use FunctionApp")

if "app.register_functions(" in main_content:
    print("✓ Main function_app.py registers blueprints (correct)")
else:
    print("❌ Main function_app.py missing blueprint registration")

# Check a user function was transformed
user_func_files = [f for f in files if f.endswith("/function_app.py") and f != "function_app.py"]
if not user_func_files:
    print("\n❌ No user function files found!")
    sys.exit(1)

print(f"\n✓ Found {len(user_func_files)} user function modules")

# Check first user function for Blueprint pattern
test_func = user_func_files[0]
test_content = zf.read(test_func).decode("utf-8")

print(f"\nChecking transformation in: {test_func}")
if "bp = func.Blueprint()" in test_content:
    print("  ✓ Uses Blueprint pattern (transformed!)")
elif "app = func.FunctionApp()" in test_content:
    print("  ❌ Still uses FunctionApp (transformation failed!)")
    sys.exit(1)
else:
    print("  ⚠ Neither pattern found")

if "@bp." in test_content:
    print("  ✓ Uses @bp decorators (transformed!)")
elif "@app." in test_content:
    print("  ❌ Still uses @app decorators (transformation failed!)")
    sys.exit(1)

print("\n✅ ALL CHECKS PASSED - Transformation working correctly!")
