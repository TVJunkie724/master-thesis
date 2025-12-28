"""
E2E Test Runner with Full Output Capture

Usage:
    python tests/e2e/run_e2e_test.py aws
    python tests/e2e/run_e2e_test.py gcp
    python tests/e2e/run_e2e_test.py azure

Output is saved to /app/e2e_output.txt
"""
import subprocess
import sys
from datetime import datetime
from pathlib import Path

def main():
    if len(sys.argv) < 2:
        print("Usage: python run_e2e_test.py <provider>")
        print("  Providers: aws, gcp, azure")
        sys.exit(1)
    
    provider = sys.argv[1].lower()
    
    test_map = {
        "aws": "tests/e2e/aws/test_aws_terraform_e2e.py",
        "aws-grafana": "tests/e2e/aws/test_aws_grafana_e2e.py",
        "aws-stepfunctions": "tests/e2e/aws/test_aws_stepfunctions_e2e.py",
        "gcp": "tests/e2e/gcp/test_gcp_terraform_e2e.py",
        "azure": "tests/e2e/azure/test_azure_single_cloud_e2e.py",
        "azure-grafana": "tests/e2e/azure/test_azure_grafana_e2e.py",
        "azure-logicapp": "tests/e2e/azure/test_azure_logicapp_e2e.py",
        "azure-zip": "tests/e2e/test_azure_functions_only.py",
        "multicloud": "tests/e2e/multicloud/test_multicloud_e2e.py",
    }
    
    if provider not in test_map:
        print(f"Unknown provider: {provider}")
        print(f"Available: {list(test_map.keys())}")
        sys.exit(1)
    
    test_file = test_map[provider]
    output_file = Path("/app/e2e_output.txt")
    
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
    
    # Run and capture output
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd="/app"
    )
    
    # Write full output to file
    with open(output_file, "w") as f:
        f.write(f"E2E Test Output - {provider.upper()}\n")
        f.write(f"Started: {datetime.now().isoformat()}\n")
        f.write(f"Test file: {test_file}\n")
        f.write(f"Exit code: {result.returncode}\n")
        f.write("=" * 60 + "\n\n")
        
        f.write("=== STDOUT ===\n")
        f.write(result.stdout or "(empty)")
        f.write("\n\n")
        
        f.write("=== STDERR ===\n")
        f.write(result.stderr or "(empty)")
        f.write("\n")
    
    # Print summary
    print(f"\n{'=' * 60}")
    print(f"  COMPLETE")
    print(f"{'=' * 60}")
    print(f"Exit code: {result.returncode}")
    print(f"Output saved to: {output_file}")
    print()
    print("To view full output:")
    print(f"  docker exec master-thesis-3cloud-deployer-1 cat {output_file}")
    print("To view last 100 lines:")
    print(f"  docker exec master-thesis-3cloud-deployer-1 tail -100 {output_file}")
    
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
