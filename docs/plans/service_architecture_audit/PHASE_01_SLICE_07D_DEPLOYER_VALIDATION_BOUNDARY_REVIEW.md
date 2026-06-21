---
title: "Phase 1 Slice 7d Review: Deployer Validation Boundary"
description: "Audit review for extracting Step-3 deployer validation proxying and validation flag persistence from the Management API deployer route."
tags: [management-api, deployer-validation, service-boundary, tests, issue-102]
lastUpdated: "2026-06-21"
version: "1.0"
---

<!-- SOURCES:
- docs/plans/service_architecture_audit/PHASE_01_02_MANAGEMENT_SERVICE_BOUNDARY_REVIEW.md
- twin2multicloud_backend/src/api/routes/deployer.py
- twin2multicloud_backend/src/services/deployer_config_validation_service.py
- twin2multicloud_backend/tests/test_deployer_config_validation_service.py
- twin2multicloud_backend/tests/test_error_handling.py
EXTRACTED: 2026-06-21 | VERSION: 1.0
-->

# Phase 1 Slice 7d Review: Deployer Validation Boundary

## Review Result

Slice 7d is implemented. Step-3 deployer validation logic now lives in
`DeployerConfigValidationService`. The FastAPI route only delegates to the
service and maps typed service errors to the existing HTTP contract.

This keeps validation behavior separate from deployer config CRUD. It also
keeps GLB upload/delete and project ZIP upload for later slices because those
endpoints combine file IO, persistence, and downstream parsing in ways that need
their own tests.

## Boundary Decisions

| Concern | Owner After Slice 7d |
|---|---|
| Supported validation config types | `DeployerConfigValidationService` |
| Provider-required checks for L2 and L4 validation | `DeployerConfigValidationService` |
| Deployer validation HTTP request construction | `DeployerConfigValidationService` |
| State-machine JSON/YAML upload filename detection | `DeployerConfigValidationService` |
| Scene-config validation hierarchy pairing | `DeployerConfigValidationService` |
| Non-L2 validation flag persistence | `DeployerConfigValidationService` |
| Invalid config type and missing provider HTTP mapping | `src/api/routes/deployer.py` |
| GLB upload/delete and project ZIP extraction | Still in `src/api/routes/deployer.py`; later slices |

## Implementation Evidence

Files changed:

- `twin2multicloud_backend/src/services/deployer_config_validation_service.py`
- `twin2multicloud_backend/src/api/routes/deployer.py`
- `twin2multicloud_backend/tests/test_deployer_config_validation_service.py`
- `twin2multicloud_backend/tests/test_error_handling.py`

Behavior preserved:

- `POST /twins/{twin_id}/deployer/validate/{config_type}` still returns a
  `ConfigValidationResponse` with `valid` and `message`.
- Invalid config types still return HTTP 400 with the existing message shape.
- L2 and L4 validation still require a provider.
- L2 validation still does not persist validation flags.
- Section 2, L1, and L4 validation successes still persist the corresponding
  validation flag.
- Deployer connection and request failures still normalize to `valid=false`
  responses instead of leaking raw exceptions.

## Test Coverage

New service tests cover:

- Section-2 validation success persists the correct flag.
- L2 function-code validation does not create or mutate deployer config.
- YAML state-machine content uploads with `.yaml`.
- Scene-config validation sends both scene content and existing hierarchy.
- Downstream validation errors become `valid=false`.
- Missing provider and missing twin raise typed service errors.

Regression route tests were kept and pointed at the new service boundary:

```text
python -m pytest tests/test_deployer_config_validation_service.py tests/test_error_handling.py -q
35 passed, 3 warnings
```

## Review Findings

| Finding | Resolution |
|---|---|
| Existing route tests mocked the old route-level `httpx.AsyncClient`. | Updated tests to mock `src.services.deployer_config_validation_service.httpx.AsyncClient`, which is the new downstream boundary. |
| Route scan still shows direct `httpx`, `get_user_twin`, and `db.commit` in `deployer.py`. | Accepted for this slice because those remaining occurrences belong to GLB upload/delete and project ZIP upload, not validation. |

## Residual Risk

GLB upload/delete still performs file-system writes and DB flag changes directly
inside `deployer.py`. Project ZIP upload still performs downstream parsing,
temporary file handling, response assembly, and validation-context construction
inside the route. These remain the next deployer route thinning targets.
