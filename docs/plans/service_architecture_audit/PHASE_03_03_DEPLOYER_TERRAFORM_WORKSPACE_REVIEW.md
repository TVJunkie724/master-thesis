---
title: "Phase 3.3 Review: Deployer Terraform Workspace"
description: "Review evidence and implementation outcome for Terraform workspace isolation and output classification."
tags: [deployer, terraform, workspace, outputs, review]
lastUpdated: "2026-06-21"
version: "1.0"
---

# Phase 3.3 Review: Deployer Terraform Workspace

## Result

Status: Complete.

Terraform runtime files now have an explicit per-project workspace contract.
`generated.tfvars.json`, `terraform.tfstate`, and default `tfplan` are all owned
by `upload/<project>/terraform/`. The static `src/terraform/` directory remains
the read-only Terraform configuration source.

## Dataflow

```text
Management API / Deployer API request
        |
        v
DeploymentContext(project_name, project_path, config, credentials)
        |
        v
upload/<project>/config*.json  ----->  tfvars_generator
        |                                  |
        |                                  v
        |                         upload/<project>/terraform/generated.tfvars.json
        |                                  |
        v                                  v
src/terraform/*.tf  ------------->  TerraformRunner(-chdir=src/terraform)
                                           |
                                           v
                         upload/<project>/terraform/terraform.tfstate
                         upload/<project>/terraform/tfplan
                                           |
                                           v
                              Terraform outputs + output policy
```

## Runtime File Inventory

| File class | Location | Owner | Boundary rule |
|---|---|---|---|
| Terraform configuration | `3-cloud-deployer/src/terraform/*.tf` | Deployer source code | Read-only template; never stores project secrets. |
| Project manifest/config | `3-cloud-deployer/upload/<project>/config*.json` | Project runtime workspace | Explicit input to tfvars generation. |
| Generated tfvars | `3-cloud-deployer/upload/<project>/terraform/generated.tfvars.json` | `tfvars_generator` | Recreated from project config before deploy. |
| Terraform state | `3-cloud-deployer/upload/<project>/terraform/terraform.tfstate` | `TerraformRunner` | Always passed via `-state` for stateful commands. |
| Terraform plan | `3-cloud-deployer/upload/<project>/terraform/tfplan` | `TerraformRunner.plan()` | Default path is project-scoped when `state_path` exists. |
| Credential examples | `config_credentials*.example` | Docs/UI examples | Readable through safe file APIs. |
| Runtime credentials | `config_credentials*.json` | Credential boundary | Forbidden through generic file APIs from Phase 3.1. |

## Implemented Boundary

### Project-Scoped Planfile

`TerraformRunner.plan()` previously defaulted to `src/terraform/tfplan`, which
could mix plans across projects. The default now follows the runner workspace:

- with `state_path`: `state_path.parent / "tfplan"`,
- without `state_path`: legacy `terraform_dir / "tfplan"` compatibility.

Explicit `out_file` paths still work and their parent directory is created.

### Deployment Path Contract

`DeploymentPaths` now includes `plan_path` next to `tfvars_path` and
`state_path`, making the project workspace contract visible to tests and future
callers.

### Terraform Output Policy

`terraform_output_policy.py` introduces a conservative output classification:

| Visibility | Rule |
|---|---|
| `redacted` | Names containing `api_key`, `connection_string`, `password`, `secret`, or `token`. |
| `safe` | Explicit public metadata, URLs, endpoints, hostnames, names, and instruction fields. |
| `internal_only` | Infrastructure identifiers such as ARNs, IDs, account IDs, client IDs, and unknown outputs. |

The policy does not change response payloads in this slice. It creates a tested
contract that Phase 3.4 can apply to logs, traces, and user-facing output
surfaces without guessing.

## Files Changed

| File | Change |
|---|---|
| `3-cloud-deployer/src/core/paths.py` | Added `plan_path` to deployment path resolution. |
| `3-cloud-deployer/src/terraform_runner.py` | Default Terraform plan output is project-scoped when `state_path` is set. |
| `3-cloud-deployer/src/terraform_output_policy.py` | Added Terraform output visibility classification contract. |
| `3-cloud-deployer/tests/unit/core_tests/test_deployment_paths.py` | Added plan-path assertion. |
| `3-cloud-deployer/tests/unit/terraform/test_terraform_runner.py` | Added planfile workspace tests. |
| `3-cloud-deployer/tests/unit/terraform/test_terraform_output_policy.py` | Added output classification tests using real output names. |

## Verification

Targeted Docker verification:

```bash
docker run --rm \
  -v /Users/caroline/.codex/worktrees/01ff/master-thesis/3-cloud-deployer:/app \
  -w /app \
  -e PYTHONPATH=/app \
  3cloud-deployer:latest \
  python -m pytest \
    tests/unit/terraform/test_terraform_runner.py \
    tests/unit/terraform/test_terraform_output_policy.py \
    tests/unit/core_tests/test_deployment_paths.py \
    -q
```

Result:

```text
10 passed
```

## Review Findings

No open findings remain for Phase 3.3.

Residual work is intentionally assigned to later subphases:

- Applying output policy to deployment logs and SSE trace surfaces: Phase 3.4.
- Validating permission/preflight behavior against generated tfvars and provider
  credential contracts: Phase 3.5.
