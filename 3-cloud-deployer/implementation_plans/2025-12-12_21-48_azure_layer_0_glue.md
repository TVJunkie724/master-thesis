# Azure Layer 0 (Glue Layer) Implementation Plan

## 1. Executive Summary

### The Problem
The Azure provider has complete function code (`azure_functions/`) but lacks the **deployer infrastructure** to provision Azure resources programmatically. Unlike AWS which has `layer_0_glue.py` (999 lines), `l0_adapter.py` (352 lines), and `naming.py` (309 lines), Azure only has stub files.

### The Solution
Mirror the AWS Layer 0 deployer pattern for Azure using Azure SDK:
- **Azure Functions** (via `azure-mgmt-web`) instead of AWS Lambda
- **Resource Group** as foundation (deployed in Setup Layer)
- Built-in HTTP routes (no separate Function URLs needed)

### Impact
- Azure will have full Layer 0 multi-cloud receiver support
- Cross-cloud deployments from/to Azure will work

---

## 2. Azure Setup Layer (Pre-Requisite)

> [!WARNING]
> **Azure requires a Resource Group before ANY resources can be created.** This is a fundamental difference from AWS.

```
AWS Deployment Order:      Azure Deployment Order:
L0 (Glue) → L1 → L2...    Setup → L0 (Glue) → L1 → L2...
```

**Setup Layer Components**:
| Resource | Purpose | Created When |
|----------|---------|--------------| 
| Resource Group | Container for ALL twin resources | Always (first step) |
| User-Assigned Managed Identity | Shared identity for all Function Apps | Always (second step) |
| Storage Account | Required for Function App | Before L0/L2 |

> [!NOTE]
> The Resource Group setup will be part of a **separate `layer_setup_azure.py`** module, called BEFORE L0. L0 only deploys if multi-cloud boundaries exist, but Resource Group is ALWAYS needed.

---

## 3. Managed Identity - Revised Recommendation

**Clarification: What is a "Digital Twin"?**
- **One Digital Twin = One complete deployment** (Resource Group + Setup + L0-L5)
- All resources in a digital twin are in the **same Resource Group**
- There may be multiple Function Apps (L0 glue, L2 compute, etc.) within one digital twin

**Revised Recommendation: User-Assigned Managed Identity**

| Aspect | System-Assigned | User-Assigned (Recommended) |
|--------|-----------------|-----------------------------|
| Lifecycle | Tied to each Function App | Created once in Setup, persists |
| Sharing | One per Function App | One for entire digital twin |
| Cleanup | Auto-deleted with each resource | Deleted when Resource Group deleted |
| Setup | Enable on each Function App | Create once, assign to all |

**Why User-Assigned is BETTER for this project:**
1. **Aligns with digital twin concept** - One identity represents the entire twin
2. **Simpler RBAC** - Grant permissions once to one identity, not to each Function App
3. **Created in Setup Layer** - Pre-exists before any Function App, easier deployment order
4. **Cleaner management** - Single identity to audit/monitor for the whole deployment

**Security Analysis (User-Assigned):**
- ✅ **NOT a concern** - All Function Apps in the same digital twin need access to the SAME resources (Cosmos DB, Blob, IoT Hub)
- ✅ **Same attack surface** - If attacker compromises any function, they need the same permissions regardless
- ✅ **Least privilege still applies** - The shared identity only gets permissions it needs
- ✅ **Audit simplicity** - One identity = one audit trail for the entire twin

**Final Design: One User-Assigned Identity Per Digital Twin**
```
Setup Layer creates: {twin-name}-identity
   ↓ assigned to ↓
┌─────────────────────────────────────────────┐
│  Resource Group: rg-{twin-name}             │
│  ┌──────────────┐  ┌──────────────┐         │
│  │ L0 Func App  │  │ L2 Func App  │ ...     │
│  │ (uses ident) │  │ (uses ident) │         │
│  └──────────────┘  └──────────────┘         │
│         ↓ accesses ↓                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │Cosmos DB │  │Blob Store│  │ IoT Hub  │  │
│  └──────────┘  └──────────┘  └──────────┘  │
└─────────────────────────────────────────────┘
```

**Deployment Order for Permissions:**
1. Setup Layer creates identity (no permissions yet)
2. When L3 creates Cosmos DB → grants identity "Cosmos DB Data Contributor" role
3. When L3 creates Blob Storage → grants identity "Storage Blob Data Contributor" role
4. etc. (permissions added as resources are created)

> [!NOTE]
> **This is the standard Azure pattern** - identity exists first, permissions granted when resources are created.

**Function-to-Function Authentication: Final Decision**

| Option | How it works | Security Level | Cross-Cloud? | Setup Complexity |
|--------|--------------|----------------|--------------|------------------|
| **A. Custom Token** (`X-Inter-Cloud-Token`) | Header with shared secret, validated in code | Basic | ✅ Yes | Simple |
| **B. Function Keys** | Azure-managed keys, `x-functions-key` header | Basic+ | ❌ Azure only | Simpler |
| **C. Azure AD** (Managed Identity) | OAuth tokens via Azure AD | Enterprise | ❌ Azure only | More complex |

**Final Decision: Hybrid Approach**

```
┌─────────────────────────────────────────────────────────┐
│ Cross-cloud calls (AWS↔Azure↔GCP):                      │
│   → Custom Token (X-Inter-Cloud-Token)                  │
├─────────────────────────────────────────────────────────┤
│ Azure-only calls:                                       │
│   → Function Keys (Azure-managed, simpler)              │
└─────────────────────────────────────────────────────────┘
```

> [!NOTE]
> **Future Enhancement**: Azure AD auth can be added later for stronger security on Azure-only paths. Details documented in `docs-azure-deployment.html` → Future Work section.

---

## 4. Azure vs AWS Service Mapping (Layer 0)

| AWS Service | Azure Equivalent | Notes |
|-------------|------------------|-------|
| N/A (no equivalent) | Resource Group | Azure-specific container for all resources |
| AWS Lambda | Azure Functions | Function App hosts multiple functions |
| IAM Role | Managed Identity | User-assigned identity on Function App |
| Lambda Function URL | Function HTTP Route | Built into Function App (no extra config) |
| Lambda `add_permission` | N/A | Azure Functions use app-level auth settings |
| boto3 | azure-mgmt-*, azure-identity | Multiple SDK packages |

> [!IMPORTANT]
> **Key Difference**: Azure Functions are grouped in a **Function App**. One Function App hosts all L0 functions (ingestion, hot-writer, etc.) vs AWS where each is a separate Lambda.

---

## 5. Proposed Changes

### Component: Azure Provider (`src/providers/azure/`)

#### [NEW] [naming.py](file:///d:/Git/master-thesis/3-cloud-deployer/src/providers/azure/naming.py) ✅ CREATED
- **Description**: Resource naming conventions for Azure
- **Pattern**: Mirror AWS `AWSNaming` class structure
- **Key Methods**:
  - `resource_group()` → `rg-{twin_name}`
  - `glue_function_app()` → `{twin_name}-l0-functions`
  - `cosmos_account()` → `{twin_name}-cosmos`
  - `storage_account()` → `{twin_name}storage` (no hyphens for storage)
  - `iot_hub()` → `{twin_name}-iothub`

---

#### [NEW] [layers/layer_setup_azure.py](file:///d:/Git/master-thesis/3-cloud-deployer/src/providers/azure/layers/layer_setup_azure.py)
- **Description**: Foundational resources (mirrors AWS `layer_X_*.py` pattern)
- **Functions**:
  - `create_resource_group()` / `destroy_resource_group()` / `check_resource_group()`
  - `create_managed_identity()` / `destroy_managed_identity()` / `check_managed_identity()`
  - `create_storage_account()` / `destroy_storage_account()` / `check_storage_account()`

#### [NEW] [layers/l_setup_adapter.py](file:///d:/Git/master-thesis/3-cloud-deployer/src/providers/azure/layers/l_setup_adapter.py)
- **Description**: Orchestrates setup deployment (mirrors AWS `l0_adapter.py` pattern)
- **Functions**: `deploy_setup()`, `destroy_setup()`, `info_setup()`

---

#### [NEW] [layers/layer_0_glue.py](file:///d:/Git/master-thesis/3-cloud-deployer/src/providers/azure/layers/layer_0_glue.py)
- **Description**: Deploy/destroy/check functions for all L0 components
- **Structure**: Mirror AWS with Azure SDK equivalents

**Functions (following AWS pattern):**
- `create_glue_function_app()` / `destroy_glue_function_app()` / `check_glue_function_app()`
- `deploy_ingestion_function()` / `destroy_ingestion_function()` / `check_ingestion_function()`
- `deploy_hot_writer_function()` / `destroy_hot_writer_function()` / `check_hot_writer_function()`
- `deploy_cold_writer_function()` / `destroy_cold_writer_function()` / `check_cold_writer_function()`
- `deploy_archive_writer_function()` / `destroy_archive_writer_function()` / `check_archive_writer_function()`
- `create_hot_reader_endpoint()` / `destroy_hot_reader_endpoint()` / `check_hot_reader_endpoint()`

---

#### [NEW] [layers/l0_adapter.py](file:///d:/Git/master-thesis/3-cloud-deployer/src/providers/azure/layers/l0_adapter.py)
- **Description**: Orchestrates L0 deployment based on provider boundaries
- **Pattern**: Mirror AWS `l0_adapter.py` structure
- **Functions**: `deploy_l0()`, `destroy_l0()`, `info_l0()`

---

#### [MODIFY] [provider.py](file:///d:/Git/master-thesis/3-cloud-deployer/src/providers/azure/provider.py)
- **Description**: Initialize Azure SDK clients
- **Changes**:
  - Add `AzureNaming` instance
  - Initialize `WebSiteManagementClient`, `ResourceManagementClient`
  - Add credential handling via `azure-identity`

---

#### [MODIFY] [deployer_strategy.py](file:///d:/Git/master-thesis/3-cloud-deployer/src/providers/azure/deployer_strategy.py)
- **Description**: Wire L0 adapter functions
- **Changes**: Add `deploy_setup()`, `deploy_l0()`, `destroy_l0()`, `info_l0()` methods

---

## 6. Implementation Phases

### Phase 1: Foundation (Setup Layer)
| Step | File | Action |
|------|------|--------|
| 1.1 | `src/providers/azure/naming.py` | Create with all resource name methods ✅ |
| 1.2 | `src/providers/azure/layers/__init__.py` | Create empty package |
| 1.3 | `src/providers/azure/layers/layer_setup_azure.py` | Create Resource Group + Identity + Storage management |

### Phase 2: L0 Glue Functions
| Step | File | Action |
|------|------|--------|
| 2.1 | `src/providers/azure/layers/layer_0_glue.py` | Create with L0 Function App management |
| 2.2 | Same | Add Ingestion function deploy/destroy/check |
| 2.3 | Same | Add Hot Writer function deploy/destroy/check |
| 2.4 | Same | Add Cold/Archive Writer functions |
| 2.5 | Same | Add Hot Reader endpoint functions |

### Phase 3: Adapter & Integration
| Step | File | Action |
|------|------|--------|
| 3.1 | `src/providers/azure/layers/l0_adapter.py` | Create orchestration logic |
| 3.2 | `src/providers/azure/provider.py` | Add SDK clients and naming |
| 3.3 | `src/providers/azure/deployer_strategy.py` | Wire Setup + L0 adapters |

### Phase 4: Testing & Verification
| Step | File | Action |
|------|------|--------|
| 4.1 | `tests/unit/azure/test_azure_naming.py` | Create naming tests (~7 tests) |
| 4.2 | `tests/integration/azure/__init__.py` | Create package |
| 4.3 | `tests/integration/azure/test_setup_layer_edge_cases.py` | Create setup layer tests (~20 tests) |
| 4.4 | `tests/integration/azure/test_l0_glue_edge_cases.py` | Create L0 glue tests (~60 tests) |
| 4.5 | Same | Add Azure-specific edge case tests (~15 tests) |
| 4.6 | All existing tests | Run full suite, verify no regressions |

### Phase 5: AWS Test Gap Coverage
| Step | File | Action |
|------|------|--------|
| 5.1 | `tests/integration/aws/test_l0_glue_edge_cases.py` | Add `TestAWSSDKErrorHandling` (~4 tests) |
| 5.2 | Same | Add `TestIAMPolicyVerification` (~4 tests) |
| 5.3 | Same | Add `TestLambdaConfiguration` (~4 tests) |
| 5.4 | Same | Add Cold/Archive Writer token validation (~4 tests) |
| 5.5 | All existing tests | Run full suite, verify no regressions |

---

## 7. Testing & Verification Plan

> [!IMPORTANT]
> **AWS L0 tests have 921 lines across 14 test classes.** Azure tests MUST match or exceed this coverage.

### 7.1 Test File Structure

| AWS Test File | Azure Equivalent |
|---------------|------------------|
| `tests/integration/aws/test_l0_glue_edge_cases.py` (921 lines) | `tests/integration/azure/test_l0_glue_edge_cases.py` |
| N/A (AWS has no setup layer) | `tests/integration/azure/test_setup_layer_edge_cases.py` |
| `tests/unit/aws/test_aws_naming.py` | `tests/unit/azure/test_azure_naming.py` |

### 7.2 Test Count Summary

| Category | AWS Tests | Azure Tests (Planned) |
|----------|-----------|----------------------|
| Setup Layer | 0 | ~20 |
| Function App | 0 | ~7 |
| Ingestion | ~8 | ~10 |
| Hot Writer | ~6 | ~8 |
| Cold Writer | ~5 | ~6 |
| Archive Writer | ~5 | ~5 |
| Hot Reader URLs | ~8 | ~7 |
| Provider Boundary | ~5 | ~10 |
| Info Adapter | ~4 | ~4 |
| Azure-Specific | 0 | ~15 |
| Naming | ~10 | ~10 |
| **TOTAL** | **~51** | **~102** |

### 7.3 Test Commands

**Run all Azure tests:**
```bash
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python -m pytest tests/integration/azure/ tests/unit/azure/ -v
```

**Run full test suite:**
```bash
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python -m pytest tests/ -v --tb=short
```

---

## 8. User Review Required

> [!IMPORTANT]
> **Azure SDK Packages**: This implementation assumes the following packages are available:
> - `azure-identity`
> - `azure-mgmt-resource`
> - `azure-mgmt-web`
> - `azure-mgmt-storage`
> - `azure-mgmt-msi`
> 
> Please confirm these are in `requirements.txt` or should be added.

> [!CAUTION]
> **Scope Limitation**: This plan covers Layer 0 only. Layers 1-5 will be implemented in subsequent phases following the same pattern.

---

## 9. Design Decisions

1. **Single Function App for L0**: All L0 functions (ingestion, writers, readers) will be deployed to one Function App for simpler management
2. **User-Assigned Managed Identity**: Created in Setup Layer, shared by all Function Apps in the digital twin
3. **Function Keys for Azure-only calls**: Built-in Azure authentication mechanism
4. **Custom Tokens for cross-cloud**: `X-Inter-Cloud-Token` for AWS↔Azure↔GCP communication
5. **Naming Convention**: Follow Azure naming restrictions (lowercase for storage accounts, etc.)
