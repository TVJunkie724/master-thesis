# AWS Permissions Checker Feature

## Overview

This implementation plan details the creation of an endpoint/CLI command that validates whether provided AWS credentials have the necessary permissions to run the full deployer functionality. The feature will also be designed to support future Azure and GCP credential validation.

## Problem Statement

Before deploying cloud infrastructure, users need to know if their credentials have sufficient permissions. Currently, deployments fail mid-way if permissions are missing. This feature enables pre-flight validation.

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Credential Source** | **Option C: Both** | Accept from request body (stateless) OR read from project's `config_credentials.json` |
| **Layer Filtering** | **Always All Layers** | Check all L1-L5 permissions every time - no per-layer filtering |
| **Documentation** | **Full Update** | Update README, API/CLI reference, deployment docs with permissions section |

---

## Approach: List & Compare

**Strategy**: Retrieve the policies/permissions attached to the given credentials and compare them against a hardcoded list of required permissions.

**Steps**:
1. **Validate credentials** - Call `sts:GetCallerIdentity` to confirm credentials are valid
2. **Get identity type** - Determine if it's an IAM User or an IAM Role (from assumed credentials)
3. **List attached policies** - Get all managed and inline policies attached to the principal
4. **Extract permissions** - Parse policy documents to extract allowed actions
5. **Compare** - Match extracted permissions against hardcoded required permissions (ALL layers)
6. **Return results** - Categorized list of valid/missing permissions per layer AND per service

> [!NOTE]
> If the credentials lack permission to list their own policies, this is returned as a valid result with the specific missing permission identified (e.g., `iam:ListAttachedUserPolicies` or `iam:ListAttachedRolePolicies`).

---

## Required AWS Permissions (Hardcoded List)

Based on analysis of all deployer layer files:

### Layer 1 - IoT Data Acquisition
| Service | Required Actions |
|---------|------------------|
| **IAM** | `iam:CreateRole`, `iam:DeleteRole`, `iam:GetRole`, `iam:AttachRolePolicy`, `iam:DetachRolePolicy`, `iam:ListAttachedRolePolicies`, `iam:ListRolePolicies`, `iam:DeleteRolePolicy`, `iam:ListInstanceProfilesForRole`, `iam:RemoveRoleFromInstanceProfile` |
| **Lambda** | `lambda:CreateFunction`, `lambda:DeleteFunction`, `lambda:GetFunction`, `lambda:AddPermission`, `lambda:RemovePermission` |
| **IoT** | `iot:CreateThing`, `iot:DeleteThing`, `iot:DescribeThing`, `iot:CreateKeysAndCertificate`, `iot:CreatePolicy`, `iot:DeletePolicy`, `iot:AttachThingPrincipal`, `iot:DetachThingPrincipal`, `iot:AttachPolicy`, `iot:DetachPolicy`, `iot:UpdateCertificate`, `iot:DeleteCertificate`, `iot:ListThingPrincipals`, `iot:ListAttachedPolicies`, `iot:ListPolicyVersions`, `iot:DeletePolicyVersion`, `iot:CreateTopicRule`, `iot:DeleteTopicRule`, `iot:DescribeEndpoint` |
| **STS** | `sts:GetCallerIdentity` |

### Layer 2 - Compute/Processing
| Service | Required Actions |
|---------|------------------|
| **IAM** | `iam:PutRolePolicy`, `iam:UpdateAssumeRolePolicy` |
| **Lambda** | (same as L1) |
| **Step Functions** | `states:CreateStateMachine`, `states:DeleteStateMachine`, `states:DescribeStateMachine` |

### Layer 3 - Storage
| Service | Required Actions |
|---------|------------------|
| **DynamoDB** | `dynamodb:CreateTable`, `dynamodb:DeleteTable`, `dynamodb:CreateBackup`, `dynamodb:DescribeBackup` |
| **S3** | `s3:CreateBucket`, `s3:DeleteBucket`, `s3:PutBucketCors`, `s3:GetBucketCors`, `s3:DeleteBucketCors`, `s3:ListBucket`, `s3:DeleteObject` |
| **EventBridge** | `events:PutRule`, `events:DeleteRule`, `events:DescribeRule`, `events:PutTargets`, `events:RemoveTargets`, `events:ListTargetsByRule` |

### Layer 4 - TwinMaker
| Service | Required Actions |
|---------|------------------|
| **IoT TwinMaker** | `iottwinmaker:CreateWorkspace`, `iottwinmaker:DeleteWorkspace`, `iottwinmaker:GetWorkspace`, `iottwinmaker:ListEntities`, `iottwinmaker:DeleteEntity`, `iottwinmaker:ListScenes`, `iottwinmaker:DeleteScene`, `iottwinmaker:ListComponentTypes`, `iottwinmaker:DeleteComponentType`, `iottwinmaker:CreateComponentType`, `iottwinmaker:GetComponentType`, `iottwinmaker:UpdateEntity`, `iottwinmaker:GetEntity` |

### Layer 5 - Grafana
| Service | Required Actions |
|---------|------------------|
| **Grafana** | `grafana:CreateWorkspace`, `grafana:DeleteWorkspace`, `grafana:DescribeWorkspace`, `grafana:ListWorkspaces` |

---

## Proposed Changes

### Shared Credentials Module (in /api)

#### [NEW] [credentials_checker.py](file:///d:/Git/master-thesis/3-cloud-deployer/api/credentials_checker.py)

Shared module used by both REST API and CLI:

```python
"""
AWS Credentials Permission Checker

Validates if provided AWS credentials have the required permissions
for the deployer by listing attached policies and comparing against
a hardcoded list of required actions.
"""
import boto3
from botocore.exceptions import ClientError

# Hardcoded required permissions by layer/service (ALL layers always checked)
REQUIRED_AWS_PERMISSIONS = {
    "layer_1": {
        "iam": ["iam:CreateRole", "iam:DeleteRole", "iam:GetRole", ...],
        "lambda": ["lambda:CreateFunction", ...],
        "iot": ["iot:CreateThing", ...],
        "sts": ["sts:GetCallerIdentity"]
    },
    "layer_2": { ... },
    "layer_3": { ... },
    "layer_4": { ... },
    "layer_5": { ... }
}

def check_aws_credentials(credentials: dict) -> dict:
    """
    Main entry point. Validates AWS credentials against ALL required permissions.
    
    Args:
        credentials: Dict with aws_access_key_id, aws_secret_access_key, aws_region, 
                     and optionally aws_session_token
    
    Returns:
        Dict with status, caller_identity, and permission results by layer and service
    """
    pass

def check_aws_credentials_from_config(project_name: str = None) -> dict:
    """
    Validate credentials from the project's config_credentials.json.
    
    Args:
        project_name: Optional project name. Uses active project if not specified.
    
    Returns:
        Same format as check_aws_credentials()
    """
    pass
```

---

### API Router

#### [NEW] [credentials.py](file:///d:/Git/master-thesis/3-cloud-deployer/api/credentials.py)

REST API endpoints supporting both credential sources:

```python
from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import Optional
from api.credentials_checker import check_aws_credentials, check_aws_credentials_from_config

router = APIRouter(prefix="/credentials", tags=["Credentials"])

class AWSCredentialsRequest(BaseModel):
    aws_access_key_id: str
    aws_secret_access_key: str
    aws_region: str
    aws_session_token: Optional[str] = None  # Optional for temporary credentials

@router.post("/check/aws")
async def check_aws_from_body(request: AWSCredentialsRequest):
    """
    Validate AWS credentials from request body against all required permissions.
    Returns a categorized list of valid and missing permissions by layer and service.
    """
    return check_aws_credentials(request.model_dump())

@router.get("/check/aws")
async def check_aws_from_config(project: Optional[str] = Query(None, description="Project name. Uses active project if not specified.")):
    """
    Validate AWS credentials from project's config_credentials.json.
    Returns a categorized list of valid and missing permissions by layer and service.
    """
    return check_aws_credentials_from_config(project)
```

---

#### [MODIFY] [rest_api.py](file:///d:/Git/master-thesis/3-cloud-deployer/rest_api.py)

Register the new credentials router.

---

### CLI Command

#### [MODIFY] [main.py](file:///d:/Git/master-thesis/3-cloud-deployer/src/main.py)

Add new CLI command (uses active project's credentials):

```
check_credentials aws
```

Uses credentials from `config_credentials.json` for the active project.

---

## Response Format

Results are organized **by layer** with services nested inside, AND **by service** with layer references.

```json
{
  "status": "valid" | "partial" | "invalid" | "check_failed",
  "message": "All required permissions are present.",
  "caller_identity": {
    "account": "123456789012",
    "arn": "arn:aws:iam::123456789012:user/deployer",
    "user_id": "AIDAEXAMPLE"
  },
  "can_list_policies": true,
  "by_layer": {
    "layer_1": {
      "status": "valid",
      "services": {
        "iam": { "valid": [...], "missing": [] },
        "lambda": { "valid": [...], "missing": [] },
        "iot": { "valid": [...], "missing": [] }
      }
    },
    "layer_2": { ... },
    "layer_3": { ... },
    "layer_4": { ... },
    "layer_5": { ... }
  },
  "by_service": {
    "iam": {
      "valid": [...],
      "missing": [],
      "used_in_layers": ["layer_1", "layer_2"]
    },
    "lambda": { ... },
    "iot": { ... }
  },
  "summary": {
    "total_required": 75,
    "valid": 72,
    "missing": 3
  }
}
```

### Special Case: Cannot List Policies

```json
{
  "status": "check_failed",
  "message": "Cannot determine permissions - credentials lack access to list their own policies.",
  "caller_identity": { ... },
  "can_list_policies": false,
  "missing_check_permission": "iam:ListAttachedUserPolicies",
  "by_layer": {},
  "by_service": {},
  "summary": { "total_required": 0, "valid": 0, "missing": 0 }
}
```

---

## Documentation Updates

### [MODIFY] [README.md](file:///d:/Git/master-thesis/3-cloud-deployer/README.md)

Add section about prerequisite permissions and the check command.

---

### [MODIFY] [docs-api-reference.html](file:///d:/Git/master-thesis/3-cloud-deployer/docs/docs-api-reference.html)

Add documentation for new endpoints:
- `POST /credentials/check/aws` - Check with body credentials
- `GET /credentials/check/aws` - Check with config credentials

---

### [MODIFY] [docs-cli-reference.html](file:///d:/Git/master-thesis/3-cloud-deployer/docs/docs-cli-reference.html)

Add documentation for new CLI command:
- `check_credentials aws`

---

### [MODIFY] [docs-aws-deployment.html](file:///d:/Git/master-thesis/3-cloud-deployer/docs/docs-aws-deployment.html)

Add new section: **"Required AWS Permissions"**
- List all required permissions by layer
- Explain how to verify credentials before deployment
- Link to the check_credentials command/endpoint

---

## File Structure After Implementation

```
3-cloud-deployer/
├── api/
│   ├── credentials.py          # [NEW] REST API endpoints
│   ├── credentials_checker.py  # [NEW] Shared logic (API + CLI)
│   └── ...
├── src/
│   └── main.py                 # [MODIFY] Add CLI command
├── docs/
│   ├── docs-api-reference.html # [MODIFY] Add endpoint docs
│   ├── docs-cli-reference.html # [MODIFY] Add CLI command docs
│   └── docs-aws-deployment.html # [MODIFY] Add permissions section
├── README.md                   # [MODIFY] Add permissions info
└── rest_api.py                 # [MODIFY] Register router
```

---

## Verification Plan

### Automated Tests

Create `tests/test_credentials_checker.py`:

1. **Test valid credentials with full access** - Mock all permissions granted
2. **Test partial permissions** - Some missing permissions
3. **Test cannot list policies** - AccessDenied, verify correct permission reported
4. **Test invalid credentials** - Invalid access key
5. **Test session token handling** - Temporary credentials
6. **Test from-config path** - Load from config_credentials.json
7. **Test response structure** - Verify both by_layer and by_service populated

```bash
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python -m pytest tests/test_credentials_checker.py -v
```

### Manual Verification

1. Test with real AWS admin credentials
2. Test with restricted IAM user
3. Test with temporary STS credentials
4. Test GET endpoint with project parameter
5. Test CLI command

---

## Task Checklist

### Implementation
- [ ] Create `api/credentials_checker.py` with hardcoded permissions and comparison logic
- [ ] Create `api/credentials.py` with REST endpoints (POST + GET)
- [ ] Register router in `rest_api.py`
- [ ] Add CLI command `check_credentials` in `main.py`
- [ ] Update `help_menu()` with new command
- [ ] Create `tests/test_credentials_checker.py`

### Documentation
- [ ] Update `README.md` with permissions info and check command
- [ ] Update `docs/docs-api-reference.html` with new endpoints
- [ ] Update `docs/docs-cli-reference.html` with new CLI command
- [ ] Update `docs/docs-aws-deployment.html` with new "Required Permissions" section
