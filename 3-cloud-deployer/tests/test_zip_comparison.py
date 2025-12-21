#!/usr/bin/env python3
"""
Compare L0, L2, and User function ZIPs to verify structure is correct.
Also validates Blueprint merging in function_app.py files.
"""
import sys
import os
import zipfile
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from src.providers.azure.layers.function_bundler import (
    bundle_l0_functions,
    bundle_l2_functions,
    bundle_user_functions,
)

def extract_and_analyze(zip_bytes, label):
    """Extract ZIP and analyze contents."""
    print(f"\n{'='*60}")
    print(f"ANALYZING: {label}")
    print(f"{'='*60}")
    
    if not zip_bytes:
        print("  ⚠ No ZIP generated")
        return None
    
    print(f"ZIP Size: {len(zip_bytes)} bytes")
    
    results = {
        "size": len(zip_bytes),
        "files": [],
        "function_app_content": None,
        "modules": [],
        "has_blueprint_imports": False,
        "has_register_calls": False,
    }
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_zip = Path(temp_dir) / "test.zip"
        with open(temp_zip, "wb") as f:
            f.write(zip_bytes)
        
        with zipfile.ZipFile(temp_zip, 'r') as zf:
            results["files"] = zf.namelist()
            
            print(f"\nFiles ({len(results['files'])}):")
            for f in sorted(results["files"]):
                print(f"  - {f}")
            
            # Read main function_app.py
            if "function_app.py" in results["files"]:
                content = zf.read("function_app.py").decode("utf-8")
                results["function_app_content"] = content
                
                print(f"\n--- function_app.py ({len(content)} chars) ---")
                print(content[:1500])  # First 1500 chars
                if len(content) > 1500:
                    print(f"\n... [{len(content) - 1500} more chars] ...")
                
                # Check for Blueprint imports
                results["has_blueprint_imports"] = "import" in content and "_bp" in content
                results["has_register_calls"] = "register_functions" in content
                
                # Find module imports
                for line in content.split("\n"):
                    if "from " in line and "_bp" in line:
                        results["modules"].append(line.strip())
            
            # Check for module folders
            module_folders = set()
            for f in results["files"]:
                if "/" in f:
                    folder = f.split("/")[0]
                    if folder not in ("_shared", "__pycache__"):
                        module_folders.add(folder)
            
            print(f"\nFunction modules found: {sorted(module_folders)}")
            
            # Check Blueprint structure
            print(f"\nBlueprint Analysis:")
            print(f"  - Has Blueprint imports: {'✓' if results['has_blueprint_imports'] else '✗'}")
            print(f"  - Has register_functions calls: {'✓' if results['has_register_calls'] else '✗'}")
            if results["modules"]:
                print(f"  - Import statements:")
                for m in results["modules"]:
                    print(f"      {m}")
    
    return results


def main():
    print("\n" + "="*70)
    print("AZURE FUNCTION ZIP STRUCTURE COMPARISON")
    print("="*70)
    
    project_path = "/tmp/multicloud-e2e/mc-e2e-test"
    
    providers_config = {
        "layer_1_provider": "google",
        "layer_2_provider": "azure",
        "layer_3_hot_provider": "aws",
        "layer_3_cold_provider": "google",
        "layer_3_archive_provider": "azure",
        "layer_4_provider": "azure",
        "layer_5_provider": "aws",
    }
    
    # Build all ZIPs
    print("\nBuilding ZIPs...")
    
    l0_zip, l0_funcs = bundle_l0_functions(project_path, providers_config)
    l2_zip = bundle_l2_functions(project_path)
    user_zip = bundle_user_functions(project_path)
    
    # Analyze each
    l0_results = extract_and_analyze(l0_zip, f"L0 Glue Functions ({l0_funcs})")
    l2_results = extract_and_analyze(l2_zip, "L2 Functions (persister, event-checker)")
    user_results = extract_and_analyze(user_zip, "User Functions")
    
    # Critical comparison
    print("\n" + "="*70)
    print("CRITICAL REVIEW")
    print("="*70)
    
    all_passed = True
    issues = []
    
    # Check 1: All ZIPs have function_app.py at root
    for label, results in [("L0", l0_results), ("L2", l2_results), ("User", user_results)]:
        if results and "function_app.py" not in results["files"]:
            issues.append(f"{label}: Missing function_app.py at root!")
            all_passed = False
        elif results:
            print(f"✓ {label}: Has function_app.py at root")
    
    # Check 2: All multi-function ZIPs use Blueprint pattern
    for label, results in [("L0", l0_results), ("L2", l2_results), ("User", user_results)]:
        if results and len([f for f in results["files"] if f.endswith("/function_app.py") and f != "function_app.py"]) > 0:
            # Multi-function bundle - should have Blueprint
            if not results["has_blueprint_imports"]:
                issues.append(f"{label}: Multi-function bundle but no Blueprint imports!")
                all_passed = False
            elif not results["has_register_calls"]:
                issues.append(f"{label}: No register_functions() calls!")
                all_passed = False
            else:
                print(f"✓ {label}: Uses Blueprint pattern correctly")
    
    # Check 3: _shared folder present
    for label, results in [("L0", l0_results), ("L2", l2_results)]:
        if results:
            has_shared = any("_shared/" in f for f in results["files"])
            if not has_shared:
                issues.append(f"{label}: Missing _shared/ folder!")
                all_passed = False
            else:
                print(f"✓ {label}: Has _shared/ folder")
    
    # Check 4: Verify module structure matches imports
    for label, results in [("L0", l0_results), ("L2", l2_results), ("User", user_results)]:
        if results and results["function_app_content"]:
            content = results["function_app_content"]
            # Find imported modules
            imports = [line for line in content.split("\n") if line.strip().startswith("from ") and "_bp" in line]
            
            for imp in imports:
                # Extract module name from "from ingestion.function_app import bp as ingestion_bp"
                parts = imp.split()
                if len(parts) >= 2:
                    module_name = parts[1].split(".")[0]
                    # Check if module folder exists in ZIP
                    module_folder_exists = any(f.startswith(f"{module_name}/") for f in results["files"])
                    if not module_folder_exists:
                        issues.append(f"{label}: Import '{module_name}' but folder not in ZIP!")
                        all_passed = False
                    else:
                        print(f"✓ {label}: Module '{module_name}' folder matches import")
    
    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    
    print(f"\nZIP Sizes:")
    print(f"  L0 Glue:  {l0_results['size'] if l0_results else 'N/A':>10} bytes")
    print(f"  L2:       {l2_results['size'] if l2_results else 'N/A':>10} bytes")
    print(f"  User:     {user_results['size'] if user_results else 'N/A':>10} bytes")
    
    if issues:
        print(f"\n❌ ISSUES FOUND ({len(issues)}):")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print(f"\n✅ All checks passed!")
    
    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
