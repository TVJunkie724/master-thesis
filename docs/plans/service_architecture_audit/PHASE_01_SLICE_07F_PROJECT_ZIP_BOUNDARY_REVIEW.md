---
title: "Phase 1 Slice 7f Review: Project ZIP Extraction Boundary"
description: "Audit review for extracting project.zip validation/extraction proxying, validation context construction, and embedded GLB handling from the Management API deployer route."
tags: [management-api, deployer, project-zip, service-boundary, tests, issue-102]
lastUpdated: "2026-06-21"
version: "1.0"
---

<!-- SOURCES:
- docs/plans/service_architecture_audit/PHASE_01_02_MANAGEMENT_SERVICE_BOUNDARY_REVIEW.md
- twin2multicloud_backend/src/api/routes/deployer.py
- twin2multicloud_backend/src/services/project_zip_extraction_service.py
- twin2multicloud_backend/src/services/scene_glb_service.py
- twin2multicloud_backend/tests/test_project_zip_extraction_service.py
- twin2multicloud_backend/tests/test_scene_glb_service.py
- twin2multicloud_backend/tests/test_error_handling.py
EXTRACTED: 2026-06-21 | VERSION: 1.0
-->

# Phase 1 Slice 7f Review: Project ZIP Extraction Boundary

## Review Result

Slice 7f is implemented. Project ZIP upload/extraction behavior now lives in
`ProjectZipExtractionService`. The FastAPI route reads the uploaded request
body, delegates to the service, and maps typed service errors to the existing
HTTP contract.

This completes the deployer route thinning cluster for config CRUD, validation,
direct GLB storage, and ZIP extraction. `deployer.py` no longer owns direct
downstream validation calls, ZIP extraction proxying, local GLB file writes, or
deployer config DB flag persistence for these flows.

## Boundary Decisions

| Concern | Owner After Slice 7f |
|---|---|
| Twin ownership lookup | `ProjectZipExtractionService` through `TwinRepository` |
| ZIP size-limit enforcement | `ProjectZipExtractionService` |
| ValidationContext construction | `ProjectZipExtractionService` |
| Optimizer provider fallback from `result_json.calculationResult` | `ProjectZipExtractionService` |
| Deployer `/validate/zip/extract` HTTP call | `ProjectZipExtractionService` |
| Stable empty error response shape | `ProjectZipExtractionService` |
| Embedded GLB base64 decoding and content stripping | `ProjectZipExtractionService` |
| Local extracted GLB storage | `SceneGlbService` |
| HTTP 404 and 413 mapping | `src/api/routes/deployer.py` |

## Implementation Evidence

Files changed:

- `twin2multicloud_backend/src/services/project_zip_extraction_service.py`
- `twin2multicloud_backend/src/api/routes/deployer.py`
- `twin2multicloud_backend/tests/test_project_zip_extraction_service.py`

Behavior preserved:

- `POST /twins/{twin_id}/deployer/upload-zip` still proxies to
  `Deployer /validate/zip/extract`.
- `include_credentials=false` remains enforced.
- `validation_context.skip_credentials=true` and
  `validation_context.skip_config_files=[]` remain enforced.
- `l2_provider` and `l4_provider` are sourced from cheapest columns first and
  fall back to `result_json.calculationResult`.
- Non-200 Deployer responses still return the stable `success=false` response
  shape with `files`, `functions`, `assets`, and `warnings`.
- Embedded binary `scene_glb` content is saved locally, stripped from the
  response, and replaced with `{exists: true, saved: true, is_binary: true,
  content: null}`.
- Oversized ZIP files still return HTTP 413.

## Test Coverage

New tests cover:

- Validation context generation from optimizer cheapest columns.
- Validation context fallback from optimizer `result_json`.
- Embedded GLB save through `SceneGlbService` and base64 content stripping.
- Stable Deployer error response shape.
- Oversized ZIP rejection before downstream calls.
- Missing twin handling.
- Route-level response preservation.

Focused verification:

```text
python -m pytest tests/test_project_zip_extraction_service.py tests/test_scene_glb_service.py tests/test_error_handling.py -q
41 passed, 3 warnings
```

## Review Findings

| Finding | Resolution |
|---|---|
| `deployer.py` still contained route-level ZIP `httpx`, JSON context construction, base64 decoding, file writes, and DB flag persistence. | Moved to `ProjectZipExtractionService` and reused `SceneGlbService` for local GLB persistence. |
| There were no existing backend tests for `/upload-zip`. | Added service and route tests for success, error shape, provider context, oversized upload, missing twin, and embedded GLB handling. |

## Residual Risk

The ZIP extraction contract still depends on the Deployer response schema. The
new tests pin the Management API behavior around that schema, but a future
contract test against Deployer-side fixtures should be added when the Deployer
ZIP extraction service is audited.
