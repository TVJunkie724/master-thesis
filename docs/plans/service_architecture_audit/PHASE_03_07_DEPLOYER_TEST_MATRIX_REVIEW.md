---
title: "Phase 3.7 Review: Deployer Test Matrix"
description: "Final safe verification matrix for Deployer Phase 3 hardening."
tags: [deployer, tests, quality, security, review]
lastUpdated: "2026-06-21"
version: "1.0"
---

# Phase 3.7 Review: Deployer Test Matrix

## Result

Status: Complete.

Phase 3 now has safe regression coverage for API boundaries, provider cleanup
dispatch, Terraform workspace isolation, stream redaction, permission preflight,
and simulator utility behavior. Live cloud E2E remains explicitly excluded from
ordinary verification.

## Default Safe Commands

Targeted phase checks:

```bash
python -m pytest tests/unit/test_file_manager_crud.py::TestProjectFileBrowserSecurity tests/api/test_project_file_routes.py -q
python -m pytest tests/unit/providers/test_cleanup_registry.py tests/unit/core_tests/test_architecture_boundaries.py tests/unit/core_tests/test_deployment_contracts.py tests/api/test_deployment_routes.py -q
python -m pytest tests/unit/terraform/test_terraform_runner.py tests/unit/terraform/test_terraform_output_policy.py tests/unit/core_tests/test_deployment_paths.py -q
python -m pytest tests/unit/terraform/test_preflight_validation.py tests/unit/core_tests/test_deployment_contracts.py -q
python -m pytest tests/unit/test_simulator_api_boundaries.py tests/test_gcp_simulator.py tests/integration/azure/test_azure_simulator.py -q
```

Full safe Deployer gate:

```bash
python -m pytest tests/unit tests/api tests/integration tests/test_gcp_simulator.py -q
```

These commands exclude `tests/e2e/` and do not create cloud resources.

## Test-To-Risk Matrix

| Risk area | Safe tests | Evidence |
|---|---|---|
| Generic project file API leaks credentials | `tests/unit/test_file_manager_crud.py::TestProjectFileBrowserSecurity`, `tests/api/test_project_file_routes.py` | Runtime credential files are hidden/blocked; examples remain readable. |
| API routes bypass canonical deployment facade | `tests/api/test_deployment_routes.py`, `tests/unit/core_tests/test_deployment_contracts.py` | Deploy/destroy routes and stream contracts remain stable. |
| Provider cleanup signatures leak into orchestration | `tests/unit/providers/test_cleanup_registry.py`, `tests/unit/core_tests/test_architecture_boundaries.py` | Cleanup dispatch is centralized behind `cleanup_registry`. |
| Terraform artifacts leak into static template workspace | `tests/unit/terraform/test_terraform_runner.py`, `tests/unit/core_tests/test_deployment_paths.py` | Plan, state, and tfvars are project-scoped. |
| Terraform outputs expose secrets | `tests/unit/terraform/test_terraform_output_policy.py`, `tests/unit/core_tests/test_deployment_contracts.py` | Secret-classified outputs are redacted in stream events. |
| Deployment stream leaks secret-like log/error content | `tests/unit/core_tests/test_deployment_contracts.py`, `tests/api/test_deployment_routes.py` | Log/error messages and outputs are sanitized. |
| Deployment continues after partial/unknown preflight | `tests/unit/terraform/test_preflight_validation.py` | Non-`valid` checker statuses fail closed before Terraform starts. |
| GCP simulator alias and payload path mismatch | `tests/unit/test_simulator_api_boundaries.py`, `tests/test_gcp_simulator.py`, `tests/integration/azure/test_azure_simulator.py` | Simulator aliases and payload lookup are deterministic. |

## E2E Quarantine

Live E2E tests remain opt-in only:

```bash
python tests/e2e/run_e2e_test.py --provider aws
python tests/e2e/run_e2e_test.py --provider azure
python tests/e2e/run_e2e_test.py --provider gcp
```

Rules:

- Run only after explicit user approval.
- Expect real cloud resources and possible cost.
- Capture and review `e2e_output.txt` before continuing.

## Remaining High-Risk Gaps

| Gap | Destination |
|---|---|
| Provider-specific least-privilege policies need live verification. | Future credential hardening issue. |
| Stream correlation fields for project/provider/layer/phase should be added after Management API stream consumption is finalized. | Management API + Flutter stream integration work. |
| Simulator diagnostics and Twin Overview simulator status need UI-level planning. | UI Delta Audit / simulator diagnostics issue. |
| Final user-facing versus internal Terraform output response profiles need cross-service agreement. | Phase 4 Service Quality Gate. |

## Verification Evidence

Latest full safe Docker gate:

```text
944 passed, 1 skipped, 1 warning
```

No live cloud E2E was executed.
