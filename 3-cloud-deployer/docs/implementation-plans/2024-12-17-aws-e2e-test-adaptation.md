# AWS E2E Test Adaptation

## Executive Summary

**Problem:** The current AWS E2E test (`test_aws_terraform_e2e.py`) needs to be updated to:
1. Match the new Terraform layer structure (Setup layer + L1-L5)
2. Align with Azure E2E test patterns (cleanup, error handling, streaming output)
3. Test Lambda ZIP packaging functionality

**Solution:** Create a new simple Lambda ZIP test and update the existing AWS E2E test with improved patterns.

---

## User Review Required

> [!IMPORTANT]
> The E2E tests will deploy **REAL AWS resources** that incur costs. You will be asked for explicit confirmation before running any E2E tests.

> [!NOTE]
> The template project credentials in `upload/template/config_credentials.json` are gitignored. Please confirm these contain valid AWS credentials before running tests.

---

## Proposed Changes

### Component: E2E Test Fixtures

#### [MODIFY] conftest.py

Add AWS credentials fixture (currently missing):

```python
@pytest.fixture(scope="session")
def aws_credentials(template_project_path):
    """
    Load AWS credentials from config_credentials.json.
    
    Falls back to environment variables if file not found.
    """
    creds_path = template_project_path / "config_credentials.json"
    
    if creds_path.exists():
        with open(creds_path, "r") as f:
            all_creds = json.load(f)
        
        aws_creds = all_creds.get("aws", {})
        
        if aws_creds.get("aws_access_key_id") and aws_creds.get("aws_secret_access_key"):
            print("[E2E] Using credentials from config_credentials.json")
            
            # Set environment variables for Terraform
            os.environ["AWS_ACCESS_KEY_ID"] = aws_creds["aws_access_key_id"]
            os.environ["AWS_SECRET_ACCESS_KEY"] = aws_creds["aws_secret_access_key"]
            os.environ["AWS_REGION"] = aws_creds.get("aws_region", "eu-west-1")
            
            return {
                "auth_type": "access_key",
                "region": aws_creds.get("aws_region", "eu-west-1"),
            }
    
    # Fallback: Check for environment variables
    if os.environ.get("AWS_ACCESS_KEY_ID") and os.environ.get("AWS_SECRET_ACCESS_KEY"):
        print("[E2E] Using AWS credentials from environment variables")
        return {"auth_type": "access_key"}
    
    pytest.skip("AWS credentials not configured.")
```

Also add `aws_terraform_e2e_test_id` and `aws_terraform_e2e_project_path` fixtures similar to the Azure ones.

---

### Component: Simple Lambda ZIP Test

#### [NEW] test_aws_lambda_zip_e2e.py

A simple E2E test that:
1. Uses `package_builder.py` to create a Lambda ZIP
2. Deploys a single Lambda function via Terraform
3. Invokes the Lambda to verify it works
4. Cleans up resources

This minimal test validates the zipping functionality without deploying the full pipeline.

Key features (matching Azure patterns):
- Streaming console output with `print()` statements
- GUARANTEED cleanup via `request.addfinalizer()`
- Proper error handling and fail-fast behavior
- Resource naming with test ID prefix

---

### Component: Updated AWS E2E Test

#### [MODIFY] test_aws_terraform_e2e.py

Update to match Azure E2E patterns:

1. **Layer-by-layer deployment tracking:**
   ```python
   deployed_layers: List[str] = []
   failed_layer: Optional[str] = None
   deployment_success = False
   ```

2. **Partial cleanup pattern** (only destroy failed layer, preserve successful ones for resumption)

3. **Streaming output** with consistent formatting:
   ```python
   print("\n[DEPLOY] === Setup Layer ===")
   print("[DEPLOY] ✓ Setup layer deployed")
   ```

4. **Test structure matching new layers:**
   - `test_01_setup_layer_deployed` - Resource Group exists
   - `test_02_l1_iot_deployed` - IoT Core, Dispatcher Lambda
   - `test_03_l2_compute_deployed` - Persister Lambda
   - `test_04_l3_storage_deployed` - DynamoDB, S3
   - `test_05_l4_twins_deployed` - TwinMaker workspace
   - `test_06_l5_grafana_deployed` - Grafana workspace

---

## Verification Plan

### Automated Tests

> [!CAUTION]
> E2E tests deploy real AWS resources and cost money. Only run when explicitly requested.

**1. Simple Lambda ZIP Test:**
```bash
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python -m pytest tests/e2e/aws/test_aws_lambda_zip_e2e.py -v -m live
```

**2. Full AWS E2E Test:**
```bash
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python -m pytest tests/e2e/aws/test_aws_terraform_e2e.py -v -m live
```

### Manual Verification

After running the Lambda ZIP test, verify in AWS Console:
1. Lambda function appears in Lambda console with correct name
2. Lambda can be invoked from console and returns expected response
3. Resources are cleaned up after test completes

---

## Implementation Phases

| Phase | Files | Description |
|-------|-------|-------------|
| 1 | `conftest.py` | Add AWS credentials fixture |
| 2 | `test_aws_lambda_zip_e2e.py` | Create simple Lambda ZIP test |
| 3 | `test_aws_terraform_e2e.py` | Update full E2E test with new patterns |
