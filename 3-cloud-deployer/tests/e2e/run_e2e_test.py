"""
E2E Test Runner with Full Output Capture

Usage:
    python tests/e2e/run_e2e_test.py aws
    python tests/e2e/run_e2e_test.py gcp
    python tests/e2e/run_e2e_test.py azure

Output is saved to tests/e2e/<provider>/.build/e2e_output_<timestamp>.txt
"""
import subprocess
import sys
import os
from datetime import datetime
from pathlib import Path

def main():
    # Check for deprecated environment variable
    if os.environ.get("E2E_SKIP_CLEANUP", "").lower() == "true":
        print(f"\n{'!' * 60}")
        print("  WARNING: E2E_SKIP_CLEANUP environment variable is DEPRECATED!")
        print(f"{'!' * 60}")
        print("\nUse the --skip-cleanup flag instead:")
        print("  python tests/e2e/run_e2e_test.py <provider> --skip-cleanup")
        print("\nContinuing anyway (flag will be auto-added)...")
        print()
        # Auto-add the flag for backwards compatibility
        if "--skip-cleanup" not in sys.argv:
            sys.argv.append("--skip-cleanup")
    
    if len(sys.argv) < 2:
        print("Usage: python run_e2e_test.py <provider>")
        print("  Providers: aws, gcp, azure, multicloud, etc.")
        sys.exit(1)
    
    provider = sys.argv[1].lower()
    
    test_map = {
        "aws": ("tests/e2e/aws/test_aws_terraform_e2e.py", "tests/e2e/aws"),
        "aws-grafana": ("tests/e2e/aws/test_aws_grafana_e2e.py", "tests/e2e/aws"),
        "aws-stepfunctions": ("tests/e2e/aws/test_aws_stepfunctions_e2e.py", "tests/e2e/aws"),
        "aws-twinmaker-full": ("tests/e2e/aws/test_aws_twinmaker_integrated_e2e.py", "tests/e2e/aws"),
        "gcp": ("tests/e2e/gcp/test_gcp_terraform_e2e.py", "tests/e2e/gcp"),
        "azure": ("tests/e2e/azure_tests/test_azure_single_cloud_e2e.py", "tests/e2e/azure_tests"),
        "azure-adt-full": ("tests/e2e/azure_tests/test_azure_adt_integrated_e2e.py", "tests/e2e/azure_tests"),
        "azure-grafana": ("tests/e2e/azure_tests/test_azure_grafana_e2e.py", "tests/e2e/azure_tests"),
        "azure-logicapp-isolated": ("tests/e2e/azure_tests/test_azure_logicapp_isolated_e2e.py", "tests/e2e/azure_tests"),
        "azure-zip": ("tests/e2e/test_azure_functions_only.py", "tests/e2e"),
        "multicloud": ("tests/e2e/multicloud/test_multicloud_e2e.py", "tests/e2e/multicloud"),
        # Deployer scenario tests (one at a time)
        "deployer-gcp-azure": ("tests/e2e/multicloud/test_scenario_gcp_azure.py", "tests/e2e/multicloud"),
        "deployer-gcp-aws": ("tests/e2e/multicloud/test_scenario_gcp_aws.py", "tests/e2e/multicloud"),
        "deployer-aws-azure": ("tests/e2e/multicloud/test_scenario_aws_azure.py", "tests/e2e/multicloud"),
        "deployer-aws-gcp": ("tests/e2e/multicloud/test_scenario_aws_gcp.py", "tests/e2e/multicloud"),
        "deployer-azure-aws": ("tests/e2e/multicloud/test_scenario_azure_aws.py", "tests/e2e/multicloud"),
        "deployer-azure-gcp": ("tests/e2e/multicloud/test_scenario_azure_gcp.py", "tests/e2e/multicloud"),
    }
    
    if provider not in test_map:
        print(f"Unknown provider: {provider}")
        print(f"Available: {list(test_map.keys())}")
        sys.exit(1)
    
    test_file, output_dir = test_map[provider]
    
    # Create timestamped output filename in .build directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    build_dir = Path("/app") / output_dir / ".build"
    build_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = build_dir / f"e2e_output_{provider}_{timestamp}.txt"
    
    # Also keep a "latest" symlink/copy for convenience
    latest_file = build_dir / f"e2e_output_{provider}_latest.txt"
    
    print(f"=" * 60)
    print(f"  E2E Test Runner - {provider.upper()}")
    print(f"=" * 60)
    print(f"Test file: {test_file}")
    print(f"Output file: {output_file}")
    print(f"Started: {datetime.now().isoformat()}")
    print()
    
    # Run pytest
    cmd = [
        sys.executable, "-m", "pytest",
        test_file,
        "-v",
        "--tb=long",
        "-s",  # Don't capture stdout (show in real-time too)
    ]

    # Add any extra arguments passed to the script
    # Explicitly define known flags to prevent silent mistakes
    KNOWN_FLAGS = {
        "--skip-cleanup": "Skip cleanup after test (preserve infrastructure for investigation)",
        "--dry-run": "Show what would be done without actually doing it",
        "-k": "Only run tests matching expression (pytest -k)",
        "-x": "Stop on first failure (pytest -x)",
        "--pdb": "Drop into debugger on failures (pytest --pdb)",
        "-v": "Verbose output (already included)",
        "-vv": "Extra verbose output",
    }
    
    if len(sys.argv) > 2:
        extra_args = sys.argv[2:]
        
        # Check for unknown flags
        unknown_flags = []
        for arg in extra_args:
            if arg.startswith("-"):
                # Check if it's a known flag or starts with a known flag (for -k expr)
                is_known = any(
                    arg == flag or arg.startswith(flag.rstrip(":") + "=") or
                    (flag == "-k" and arg == "-k")  # -k needs next arg
                    for flag in KNOWN_FLAGS
                )
                if not is_known and not arg.startswith("-k"):  # -k value is handled
                    unknown_flags.append(arg)
        
        if unknown_flags:
            print(f"\n{'!' * 60}")
            print("  ERROR: Unknown flag(s) detected!")
            print(f"{'!' * 60}")
            print(f"\nUnknown: {unknown_flags}")
            print("\nKnown flags:")
            for flag, desc in KNOWN_FLAGS.items():
                print(f"  {flag:20} {desc}")
            print("\nIf you intended to use an environment variable, note that")
            print("E2E_SKIP_CLEANUP is DEPRECATED - use --skip-cleanup instead.")
            sys.exit(1)
        
        print(f"Adding extra arguments: {extra_args}")
        cmd.extend(extra_args)
    
    print(f"Command: {' '.join(cmd)}")
    print(f"\n{'=' * 60}\n")
    
    # Record start time for duration tracking
    start_time = datetime.now()
    
    # Open output files for streaming
    with open(output_file, "w") as f_out:
        # Write header
        header = [
            f"E2E Test Output - {provider.upper()}",
            f"Started: {start_time.isoformat()}",
            f"Test file: {test_file}",
            "=" * 60 + "\n",
        ]
        for line in header:
            print(line)  # Print to console
            f_out.write(line + "\n")
        f_out.flush()
        
        # Run pytest with real-time streaming output
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # Combine stderr into stdout
            text=True,
            bufsize=1,  # Line buffered
            cwd="/app"
        )
        
        # Stream output line by line
        stdout_lines = []
        for line in process.stdout:
            print(line, end="")  # Print to console (already has newline)
            f_out.write(line)
            f_out.flush()
            stdout_lines.append(line)
        
        # Wait for process to complete
        process.wait()
        returncode = process.returncode
    
    # Calculate duration
    end_time = datetime.now()
    duration = end_time - start_time
    duration_str = str(duration).split('.')[0]  # Remove microseconds for readability
    
    # Append footer to output file
    with open(output_file, "a") as f_out:
        footer = [
            "\n" + "=" * 60,
            f"Finished: {end_time.isoformat()}",
            f"Duration: {duration_str}",
            f"Exit code: {returncode}",
            "=" * 60,
        ]
        for line in footer:
            print(line)
            f_out.write(line + "\n")
    
    # Create latest file copy
    import shutil
    shutil.copy(output_file, latest_file)
    
    # Print summary
    print(f"\n{'=' * 60}")
    print(f"  COMPLETE")
    print(f"{'=' * 60}")
    print(f"Exit code: {returncode}")
    print(f"Duration: {duration_str}")
    print(f"Output saved to: {output_file}")
    print(f"Latest output: {latest_file}")
    print()
    print("To view full output:")
    print(f"  docker exec master-thesis-3cloud-deployer-1 cat {output_file}")
    print("To view latest output:")
    print(f"  docker exec master-thesis-3cloud-deployer-1 cat {latest_file}")
    print("To view last 100 lines:")
    print(f"  docker exec master-thesis-3cloud-deployer-1 tail -100 {latest_file}")
    
    sys.exit(returncode)


def run_with_error_handling():
    """Wrapper to capture any errors during test execution and write to output file."""
    import traceback
    
    try:
        main()
    except Exception as e:
        # If main() fails before writing output, capture the error
        error_msg = f"E2E Test Runner FAILED during initialization:\n\n"
        error_msg += f"Error: {type(e).__name__}: {e}\n\n"
        error_msg += "Traceback:\n"
        error_msg += traceback.format_exc()
        
        print(f"\n{'!' * 60}")
        print("  CRITICAL: Test runner failed during initialization!")
        print(f"{'!' * 60}")
        print(error_msg)
        
        # Try to write error to a file for debugging
        try:
            from pathlib import Path
            error_file = Path("/app/tests/e2e/multicloud/.build/e2e_runner_error.txt")
            error_file.parent.mkdir(parents=True, exist_ok=True)
            with open(error_file, "w") as f:
                f.write(f"E2E Test Runner Error - {datetime.now().isoformat()}\n")
                f.write("=" * 60 + "\n\n")
                f.write(error_msg)
            print(f"\nError details saved to: {error_file}")
        except Exception as write_error:
            print(f"Could not write error file: {write_error}")
        
        sys.exit(1)


if __name__ == "__main__":
    run_with_error_handling()

