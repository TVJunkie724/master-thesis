# Credentials Checker for 2-twin2clouds

## Goal

Add credential validation endpoints to the 2-twin2clouds cost optimizer that verify whether cloud credentials can successfully access the pricing APIs.

## Background

The 2-twin2clouds project fetches pricing data from three cloud providers:
- **AWS**: Uses boto3 `pricing` client - requires IAM credentials
- **Azure**: Uses public REST API (`prices.azure.com`) - **no credentials required for pricing**
- **GCP**: Uses `google.cloud.billing_v1.CloudCatalogClient` - **requires service account credentials**

Credentials are loaded from `/config/config_credentials.json` inside the container.

---

## Part 1: API Directory Refactoring

> Refactor `rest_api.py` to match the 3-cloud-deployer pattern with a separate `/api` directory.

### New Directory Structure

```
2-twin2clouds/
├── api/                           # NEW directory
│   ├── __init__.py
│   ├── pricing.py                 # /api/fetch_pricing/* endpoints
│   ├── regions.py                 # /api/fetch_regions/* endpoints
│   ├── file_status.py             # /api/*_age endpoints
│   ├── calculation.py             # /api/calculate endpoint
│   └── credentials.py             # /api/credentials/* endpoints (NEW)
├── backend/
│   ├── credentials_checker.py     # Core validation logic (NEW)
│   └── ...
├── rest_api.py                    # Refactored - only app init + router includes
```

### rest_api.py Modernization Notes

The current `rest_api.py` uses deprecated `@app.on_event("startup")`. 
Update to use the modern **lifespan context manager** pattern (like 3-cloud-deployer):

```python
# OLD (deprecated)
@app.on_event("startup")
def startup_event():
    logger.info("✅ API ready.")

# NEW (modern)
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("✅ API ready.")
    yield
    # Shutdown (if needed)

app = FastAPI(..., lifespan=lifespan)
```

---

## Part 2: Credential Checker Implementation

### Required Permissions by Provider

#### AWS
| Permission | Purpose |
|------------|---------|
| `sts:GetCallerIdentity` | Validate credentials are valid |
| `pricing:DescribeServices` | List available AWS services |
| `pricing:GetProducts` | Retrieve products matching filters |
| `pricing:GetAttributeValues` | Get attribute values for products |

#### GCP
- Requires valid service account JSON file
- Must be able to create `billing_v1.CloudCatalogClient`
- Test by calling `list_services()` to verify access

#### Azure
- Config structure check (subscription_id, client_id, etc.)
- Note: Pricing API is public, but validate credentials are present for future use

---

### New Endpoints (in api/credentials.py)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/credentials/check/aws` | Validate AWS credentials from config |
| POST | `/api/credentials/check/aws` | Validate AWS credentials from body |
| GET | `/api/credentials/check/gcp` | Validate GCP credentials from config |
| POST | `/api/credentials/check/gcp` | Validate GCP credentials from body |
| GET | `/api/credentials/check/azure` | Validate Azure credentials from config |
| POST | `/api/credentials/check/azure` | Validate Azure credentials from body |

---

### Response Format

For all providers:
```json
{
  "status": "valid" | "invalid" | "error" | "missing",
  "message": "Descriptive message",
  "provider": "aws" | "gcp" | "azure",
  "config_present": true,
  "credentials_valid": true,
  "can_fetch_pricing": true,
  "identity": {
    "account": "123456789012",       // AWS
    "arn": "arn:aws:...",            // AWS
    "project_id": "my-project"       // GCP
  },
  "required_permissions": ["pricing:DescribeServices", "..."],  // AWS only
  "note": "Azure pricing API is publicly accessible"            // Azure only
}
```

---

## Part 3: Documentation Updates

### README.md Updates

1. **Architecture section** (line 66-86): Update path references
   - Change `py/calculation/engine.py` → `backend/calculation/engine.py`
   - Add `api/` directory description
   - Add `backend/credentials_checker.py` description

2. **API Endpoints section** (line 110-116): Add new credentials endpoints
   ```markdown
   - `GET /api/credentials/check/{provider}` - Validate cloud credentials
   - `POST /api/credentials/check/{provider}` - Validate credentials from body
   ```

3. **New "Credential Validation" section** (after Quick Start):
   ```markdown
   ### Verify Credentials (Recommended)
   Before fetching pricing data, verify your credentials are valid:
   ```bash
   curl http://localhost:5003/api/credentials/check/aws
   curl http://localhost:5003/api/credentials/check/gcp
   curl http://localhost:5003/api/credentials/check/azure
   ```
   ```

### docs-api-reference.html Updates

Add new **Credentials Endpoints** card after Pricing & Data Endpoints:

```html
<!-- Credentials Validation -->
<h4 class="mt-4 text-danger"><i class="fa-solid fa-key me-2"></i>Credential Validation</h4>
<p>Verify cloud provider credentials before fetching pricing data.</p>
<table class="table ...">
  <tr>
    <td><span class="badge bg-success">GET</span></td>
    <td>/api/credentials/check/{provider}</td>
    <td>Validate credentials from config file</td>
  </tr>
  <tr>
    <td><span class="badge bg-primary">POST</span></td>
    <td>/api/credentials/check/{provider}</td>
    <td>Validate credentials from request body</td>
  </tr>
</table>
```

### docs-setup-usage.html Updates

Add credential validation step in **Configuration section** (after credentials config):

```html
<h3>3. Verify Credentials (Recommended)</h3>
<p>After configuring credentials, verify they are valid:</p>
<pre class="p-3 rounded"><code>curl http://localhost:5003/api/credentials/check/aws
curl http://localhost:5003/api/credentials/check/gcp
curl http://localhost:5003/api/credentials/check/azure</code></pre>
<p>This confirms your credentials can access the pricing APIs.</p>
```

---

## Implementation Details

### File: backend/credentials_checker.py

Core validation logic (separate from API router):

```python
"""
Credential validation logic for all cloud providers.
"""
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from google.cloud import billing_v1
from google.oauth2 import service_account
from backend.logger import logger
import backend.config_loader as config_loader
import backend.constants as CONSTANTS

# =============================================================================
# Constants
# =============================================================================

REQUIRED_AWS_PERMISSIONS = [
    "pricing:DescribeServices",
    "pricing:GetProducts", 
    "pricing:GetAttributeValues"
]

REQUIRED_AZURE_CONFIG_FIELDS = [
    "azure_subscription_id",
    "azure_client_id", 
    "azure_client_secret",
    "azure_tenant_id",
    "azure_region"
]

REQUIRED_GCP_CONFIG_FIELDS = [
    "gcp_project_id",
    "gcp_credentials_file",
    "gcp_region"
]

# =============================================================================
# AWS
# =============================================================================

def check_aws_credentials(credentials: dict = None) -> dict:
    """
    Validate AWS credentials.
    1. Check config/credentials present
    2. Call STS GetCallerIdentity
    3. Test pricing:DescribeServices access
    """
    ...

def check_aws_credentials_from_config() -> dict:
    """Load from config and validate."""
    credentials = config_loader.load_aws_credentials()
    return check_aws_credentials(credentials)

# =============================================================================
# GCP
# =============================================================================

def check_gcp_credentials(credentials_file: str = None) -> dict:
    """
    Validate GCP credentials.
    1. Check service account file exists
    2. Load credentials from file
    3. Create CloudCatalogClient and test list_services()
    """
    ...

def check_gcp_credentials_from_config() -> dict:
    """Load from config and validate."""
    ...

# =============================================================================
# Azure
# =============================================================================

def check_azure_credentials(credentials: dict = None) -> dict:
    """
    Validate Azure credentials.
    1. Check config fields present
    2. Validate credential format
    3. Note: Pricing API is public, but credentials validated for completeness
    """
    ...

def check_azure_credentials_from_config() -> dict:
    """Load from config and validate."""
    ...
```

### File: api/credentials.py

FastAPI router (thin layer):

```python
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from backend import credentials_checker

router = APIRouter(prefix="/api/credentials", tags=["Credentials"])

# Request Models
class AWSCredentialsRequest(BaseModel):
    aws_access_key_id: str
    aws_secret_access_key: str
    aws_region: str = "eu-central-1"
    aws_session_token: Optional[str] = None

class GCPCredentialsRequest(BaseModel):
    gcp_credentials_file: str
    gcp_project_id: str
    gcp_region: str = "europe-west1"

class AzureCredentialsRequest(BaseModel):
    azure_subscription_id: str
    azure_client_id: str
    azure_client_secret: str
    azure_tenant_id: str
    azure_region: str = "westeurope"

# Endpoints
@router.get("/check/aws")
def check_aws_from_config():
    return credentials_checker.check_aws_credentials_from_config()

@router.post("/check/aws")
def check_aws_from_body(request: AWSCredentialsRequest):
    return credentials_checker.check_aws_credentials(request.dict())

@router.get("/check/gcp")
def check_gcp_from_config():
    return credentials_checker.check_gcp_credentials_from_config()

@router.post("/check/gcp")
def check_gcp_from_body(request: GCPCredentialsRequest):
    return credentials_checker.check_gcp_credentials(request.gcp_credentials_file)

@router.get("/check/azure")
def check_azure_from_config():
    return credentials_checker.check_azure_credentials_from_config()

@router.post("/check/azure")
def check_azure_from_body(request: AzureCredentialsRequest):
    return credentials_checker.check_azure_credentials(request.dict())
```

---

## Verification Plan

### Automated Tests

**New test file: `tests/test_credentials_checker.py`**

```bash
docker exec -e PYTHONPATH=/app master-thesis-2twin2clouds-1 python -m pytest tests/test_credentials_checker.py -v
```

Tests to implement:
- AWS: valid credentials, invalid credentials, missing credentials, pricing access
- GCP: valid service account, invalid file, missing file, billing access
- Azure: config present, config missing, field validation
- All providers: response structure validation

### Regression Tests

```bash
# Run all existing tests after refactoring
docker exec -e PYTHONPATH=/app master-thesis-2twin2clouds-1 python -m pytest tests/ -v
```

### Integration Test

```bash
curl http://localhost:5003/api/credentials/check/aws
curl http://localhost:5003/api/credentials/check/gcp
curl http://localhost:5003/api/credentials/check/azure
```
