# Roadmap vs Terraform Implementation Gap Analysis

## Executive Summary

> [!CAUTION]
> **Critical Documentation Issue**: The AWS and Azure roadmaps describe an **obsolete SDK-based architecture**. Per `future-work.md`, Terraform is the **permanent and only** deployment implementation. The roadmaps must be rewritten, not just patched.

---

## Key Finding

The roadmaps reference Python layer files that:
1. **Don't exist** in the current codebase
2. **Will never exist** - Terraform is the permanent architecture (per `future-work.md`)

| What Roadmap Says | Reality |
|-------------------|---------|
| `layer_setup_aws.py` (3 functions) | ❌ Terraform only (`aws_setup.tf`) |
| `layer_0_glue.py` (30-43 functions) | ❌ Terraform only (`aws_glue.tf`, `azure_glue.tf`) |
| `layer_2_compute.py` (42 functions) | ❌ Terraform only (`*_compute.tf`) |
| `layer_3_storage.py` (54 functions) | ❌ Terraform only (`*_storage.tf`) |

---

## What Actually Exists

### Terraform Files (Complete ✅)
Both AWS and Azure have all required `.tf` files:
- `*_setup.tf` - Resource groups, identity, storage
- `*_glue.tf` - L0 cross-cloud receivers
- `*_iot.tf` - L1 IoT infrastructure
- `*_compute.tf` - L2 processing
- `*_storage.tf` - L3 storage tiers
- `*_twins.tf` - L4 digital twins
- `*_grafana.tf` - L5 visualization

### Python Layer Files (SDK-Managed Resources Only)

**AWS** (`src/providers/aws/layers/`):
- `layer_1_iot.py` - IoT device registration, `info_l1()`
- `layer_4_twinmaker.py` - TwinMaker entities, `info_l4()`
- `layer_5_grafana.py` - Grafana dashboards, `info_l5()`

**Azure** (`src/providers/azure/layers/`):
- `layer_1_iot.py` - IoT device registration, `info_l1()`
- `layer_4_adt.py` - ADT models/twins, `info_l4()`
- `layer_5_grafana.py` - Grafana dashboards, `info_l5()`
- `deployment_helpers.py` - Kudu deployment
- `function_bundler.py` - Function ZIP packaging

---

## Roadmap Fixes Needed

### AWS Roadmap (`docs-aws-deployment.html`)

| Section | Current (Wrong) | Should Be |
|---------|-----------------|-----------|
| Setup Layer | `src/providers/aws/layers/layer_setup_aws.py` | Terraform (`aws_setup.tf`) |
| L0 Glue | `src/providers/aws/layers/layer_0_glue.py` | Terraform (`aws_glue.tf`) |
| L1 | Python SDK deployment | Terraform + `layer_1_iot.py` for devices |
| L2 | 42 functions | Terraform (`aws_compute.tf`) |
| L3 | 54 functions | Terraform (`aws_storage.tf`) |
| L4 | Python SDK | Terraform + `layer_4_twinmaker.py` for entities |
| L5 | Python SDK | Terraform + `layer_5_grafana.py` for dashboards |

### Azure Roadmap (`docs-azure-deployment.html`)

Same pattern - all "Source Module" references to Python files are wrong.

---

## Alignment with future-work.md

| Future Work Item | Gap Analysis Finding |
|------------------|---------------------|
| ✅ "Terraform-only for GCP" | Confirms Terraform-only is permanent |
| ✅ "Remove `deploy_all_sdk()`" | Roadmaps still describe SDK deployment |
| ⚠️ "Update architecture docs with Terraform-first approach" | **This is the gap** - roadmaps not updated |

---

## Other Issues Found

### TODOs
- `adt-pusher/function_app.py:59` - "TODO is this intentional to be optional?"

### NotImplementedError
- `deployer.py:162` - Event checker redeployment AWS-only
- `gcp/provider.py` - All methods are stubs

---

## Recommendation

**Rewrite both roadmap sections** to reflect the actual Terraform-first architecture:

```html
<h3>Architecture: Terraform + SDK Hybrid</h3>
<ul>
  <li><strong>Terraform creates:</strong> All infrastructure (IAM, Lambda/Functions, 
      IoT Hub/Core, DynamoDB/Cosmos, S3/Blob, TwinMaker/ADT, Grafana)</li>
  <li><strong>Python SDK deploys:</strong> Function code (ZIP), IoT devices, 
      Digital Twin models/entities, Grafana dashboards</li>
</ul>
```

This aligns with `future-work.md` item: "Update architecture docs with Terraform-first approach"
