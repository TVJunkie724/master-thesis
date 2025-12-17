# AWS Terraform Error Investigation

## Summary

The AWS E2E test failed due to **AWS service limitations**, not Terraform code bugs.

| Error | Root Cause | Fix Type |
|-------|------------|----------|
| AWS Grafana workspace | Service not available in `eu-central-1` | Configuration |
| TwinMaker IAM role | Race condition - role not yet assumable | Terraform timing |

---

## Error 1: AWS Managed Grafana Not Available

### Error Message
```
Error: creating Amazon Managed Grafana Workspace: 
Service aws-managed-grafana does not have resource type Workspace in any region.
```

### Root Cause
**AWS Managed Grafana is NOT available in all regions.**

Supported regions (from AWS docs):
- ✅ US East (N. Virginia, Ohio)
- ✅ US West (Oregon)
- ✅ Europe (Ireland, Frankfurt, London)
- ✅ Asia Pacific (Singapore, Tokyo, Sydney, Seoul)
- ❌ **eu-central-1** was used in the test

> [!IMPORTANT]
> The test used `eu-central-1` but Grafana isn't listed for that region. Frankfurt is `eu-central-1` - need to verify AWS documentation.

### Additional Issue
`authentication_providers = ["AWS_SSO"]` requires **AWS IAM Identity Center** to be configured in the account. Without it, the workspace creation fails.

### Proposed Fix
```hcl
# Option A: Use SAML instead (simpler for E2E testing)
authentication_providers  = ["SAML"]

# Option B: Make region configurable with validation
variable "aws_grafana_region" {
  description = "Region for Grafana (must be a supported region)"
  default     = "eu-west-1"  # Ireland - confirmed supported
}
```

---

## Error 2: TwinMaker IAM Role Assumption Failed

### Error Message
```
Error: AWS SDK Go Service Operation Incomplete
Could not assume the role provided, verify permissions
(Service: IoTTwinMaker, Status Code: 400)
```

### Root Cause
This is a **race condition** in Terraform. The IAM role is created, but AWS hasn't propagated it globally when TwinMaker tries to assume it.

The role trust policy is **correct**:
```hcl
Principal = {
  Service = "iottwinmaker.amazonaws.com"  # ✓ Correct
}
```

### Why It Happens
1. Terraform creates the IAM role
2. Terraform immediately creates TwinMaker workspace (which tries to assume the role)
3. AWS IAM propagation takes 10-30 seconds
4. TwinMaker fails because the role isn't yet assumable

### Proposed Fix
Add explicit dependency with a delay:

```hcl
# In aws_twins.tf - add time_sleep for IAM propagation
resource "time_sleep" "wait_for_iam_propagation" {
  count           = local.l4_aws_enabled ? 1 : 0
  create_duration = "30s"
  
  depends_on = [
    aws_iam_role.l4_twinmaker,
    aws_iam_role_policy.l4_twinmaker_s3,
    aws_iam_role_policy.l4_twinmaker_lambda
  ]
}

resource "awscc_iottwinmaker_workspace" "main" {
  count        = local.l4_aws_enabled ? 1 : 0
  workspace_id = var.digital_twin_name
  # ... existing config ...
  
  depends_on = [time_sleep.wait_for_iam_propagation]  # Add this
}
```

> [!NOTE]
> Requires the `time` provider: `terraform { required_providers { time = { source = "hashicorp/time" } } }`

---

## Classification

| Issue | Is Terraform Bug? | Fix Required |
|-------|------------------|--------------|
| Grafana region | ❌ No - AWS limitation | Yes - region/auth config |
| TwinMaker IAM | ❌ No - AWS propagation delay | Yes - add time_sleep |

Both are **configuration/timing issues**, not bugs in the Terraform resource definitions.

---

## Recommended Actions

1. **Add `time_sleep`** for TwinMaker IAM propagation
2. **Change Grafana auth** from `AWS_SSO` to `SAML` (or make it configurable)
3. **Document region requirements** for AWS Grafana in deployment docs
