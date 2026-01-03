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
from datetime import datetime
from pathlib import Path

def main():
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
        "azure": ("tests/e2e/azure/test_azure_single_cloud_e2e.py", "tests/e2e/azure"),
        "azure-adt-full": ("tests/e2e/azure/test_azure_adt_integrated_e2e.py", "tests/e2e/azure"),
        "azure-grafana": ("tests/e2e/azure/test_azure_grafana_e2e.py", "tests/e2e/azure"),
        "azure-logicapp": ("tests/e2e/azure/test_azure_logicapp_e2e.py", "tests/e2e/azure"),
        "azure-logicapp-isolated": ("tests/e2e/azure/test_azure_logicapp_isolated_e2e.py", "tests/e2e/azure"),
        "azure-zip": ("tests/e2e/test_azure_functions_only.py", "tests/e2e"),
        "multicloud": ("tests/e2e/multicloud/test_multicloud_e2e.py", "tests/e2e/multicloud"),
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
    if len(sys.argv) > 2:
        extra_args = sys.argv[2:]
        print(f"Adding extra arguments: {extra_args}")
        cmd.extend(extra_args)
    
    print(f"Command: {' '.join(cmd)}")
    print(f"\n{'=' * 60}\n")
    
    # Record start time for duration tracking
    start_time = datetime.now()
    
    # Run and capture output
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd="/app"
    )
    
    # Calculate duration
    end_time = datetime.now()
    duration = end_time - start_time
    duration_str = str(duration).split('.')[0]  # Remove microseconds for readability
    
    # Prepare output content
    output_content = []
    output_content.append(f"E2E Test Output - {provider.upper()}")
    output_content.append(f"Started: {start_time.isoformat()}")
    output_content.append(f"Finished: {end_time.isoformat()}")
    output_content.append(f"Duration: {duration_str}")
    output_content.append(f"Test file: {test_file}")
    output_content.append(f"Exit code: {result.returncode}")
    output_content.append("=" * 60 + "\n")
    output_content.append("=== STDOUT ===")
    output_content.append(result.stdout or "(empty)")
    output_content.append("\n=== STDERR ===")
    output_content.append(result.stderr or "(empty)")
    output_content.append("\n" + "=" * 60)
    output_content.append(f"TEST DURATION: {duration_str}")
    output_content.append("=" * 60)
    
    full_output = "\n".join(output_content)
    
    # Write to timestamped file
    with open(output_file, "w") as f:
        f.write(full_output)
    
    # Write to latest file (overwrite)
    with open(latest_file, "w") as f:
        f.write(full_output)
    
    # Print summary
    print(f"\n{'=' * 60}")
    print(f"  COMPLETE")
    print(f"{'=' * 60}")
    print(f"Exit code: {result.returncode}")
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
    
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()

