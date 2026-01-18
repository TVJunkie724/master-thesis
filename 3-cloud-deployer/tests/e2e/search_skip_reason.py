"""
Search for test_07 failure details.
"""
import re

log_path = "/app/tests/e2e/multicloud/.build/e2e_output_deployer-aws-azure_latest.txt"

with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
    content = f.read()

# Find test_07 context
lines = content.split('\n')
for i, line in enumerate(lines):
    if "FAILED" in line or "AccessDeniedException" in line or "Error" in line or "DATAFLOW CRITICAL" in line:
        if "test_07" in line or "iot" in line.lower() or "publish" in line.lower():
            print(f"{i+1}: {line[:200]}")

print("\n=== Looking for AWS IoT error ===")
for i, line in enumerate(lines):
    if "AccessDenied" in line or "not authorized" in line.lower() or "botocore" in line.lower():
        start = max(0, i-2)
        end = min(len(lines), i+3)
        for j in range(start, end):
            print(f"{j+1}: {lines[j][:150]}")
        print()

print("\n=== Looking for topic name used ===")
for i, line in enumerate(lines):
    if "dt/" in line and "telemetry" in line and "topic" in line.lower():
        print(f"{i+1}: {line[:200]}")
