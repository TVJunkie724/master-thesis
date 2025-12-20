"""Run pytest and save output to file."""
import subprocess
import sys

result = subprocess.run(
    [sys.executable, "-m", "pytest", 
     "tests/e2e/gcp/test_gcp_terraform_e2e.py::TestGCPTerraformE2E::test_01_terraform_outputs_present",
     "-v", "-m", "live", "--tb=short"],
    capture_output=True,
    text=True,
    cwd="/app"
)

# Write to file
with open("/app/tests/e2e/gcp/test_output.txt", "w") as f:
    f.write("=== STDOUT ===\n")
    f.write(result.stdout)
    f.write("\n\n=== STDERR ===\n")
    f.write(result.stderr)
    f.write(f"\n\n=== RETURN CODE: {result.returncode} ===\n")

print("Output saved to /app/tests/e2e/gcp/test_output.txt")
