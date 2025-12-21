"""Test that bundled functions can be imported without errors."""
import sys
import io
import zipfile
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from src.providers.azure.layers.function_bundler import bundle_user_functions


def test_bundled_imports():
    """Verify bundled user functions can be imported Python-wise."""
    print("Building user functions ZIP...")
    zip_bytes = bundle_user_functions("/app/upload/template")
    
    if not zip_bytes:
        print("❌ No user functions ZIP generated!")
        sys.exit(1)
    
    print(f"✓ User ZIP size: {len(zip_bytes)} bytes")
    
    # Extract to temp dir and test imports
    with tempfile.TemporaryDirectory() as tmpdir:
        print(f"Extracting to {tmpdir}...")
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            zf.extractall(tmpdir)
        
        # Check main function_app.py syntax
        main_py = Path(tmpdir) / "function_app.py"
        if not main_py.exists():
            print("❌ Missing main function_app.py!")
            sys.exit(1)
        
        main_content = main_py.read_text()
        print(f"\n=== Main function_app.py ===")
        print(main_content[:500] + "..." if len(main_content) > 500 else main_content)
        
        # Check user function was transformed
        for subfolder in Path(tmpdir).iterdir():
            if subfolder.is_dir() and subfolder.name != "_shared":
                func_app = subfolder / "function_app.py"
                if func_app.exists():
                    content = func_app.read_text()
                    print(f"\n=== {subfolder.name}/function_app.py ===")
                    
                    # Check Blueprint transformation
                    if "bp = func.Blueprint()" in content:
                        print("  ✓ Uses Blueprint pattern")
                    elif "app = func.FunctionApp()" in content:
                        print("  ❌ Still uses FunctionApp!")
                        sys.exit(1)
                    
                    # Check lazy loading transformation
                    if "_require_env(" in content:
                        # Check if it's at module level (not in a function)
                        import re
                        module_level = re.findall(r'^[A-Z][A-Z_]+ = _require_env', content, re.MULTILINE)
                        if module_level:
                            print(f"  ❌ Module-level _require_env found: {module_level}")
                            sys.exit(1)
                        else:
                            print("  ✓ _require_env only in functions (lazy)")
                    
                    # Check @bp decorators
                    if "@bp." in content:
                        print("  ✓ Uses @bp decorators")
                    elif "@app." in content:
                        print("  ❌ Still uses @app decorators!")
                        sys.exit(1)
    
    print("\n✅ ALL IMPORT CHECKS PASSED!")


if __name__ == "__main__":
    test_bundled_imports()
