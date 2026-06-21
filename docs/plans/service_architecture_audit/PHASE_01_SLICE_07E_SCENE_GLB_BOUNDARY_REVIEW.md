---
title: "Phase 1 Slice 7e Review: Scene GLB Storage Boundary"
description: "Audit review for extracting scene.glb upload/delete file storage and DB flag persistence from the Management API deployer route."
tags: [management-api, deployer, scene-glb, service-boundary, tests, issue-102]
lastUpdated: "2026-06-21"
version: "1.0"
---

<!-- SOURCES:
- docs/plans/service_architecture_audit/PHASE_01_02_MANAGEMENT_SERVICE_BOUNDARY_REVIEW.md
- twin2multicloud_backend/src/api/routes/deployer.py
- twin2multicloud_backend/src/services/scene_glb_service.py
- twin2multicloud_backend/tests/test_scene_glb_service.py
- twin2multicloud_backend/tests/test_error_handling.py
EXTRACTED: 2026-06-21 | VERSION: 1.0
-->

# Phase 1 Slice 7e Review: Scene GLB Storage Boundary

## Review Result

Slice 7e is implemented. Direct `scene.glb` upload/delete behavior now lives in
`SceneGlbService`. The FastAPI route reads the uploaded request body, delegates
to the service, and maps typed service errors to the existing HTTP contract.

This slice intentionally does not extract ZIP upload. The ZIP flow can also save
a GLB extracted from the Deployer response, but it combines downstream ZIP
parsing, validation context construction, base64 decoding, and response shaping.
That needs a separate slice and can reuse `SceneGlbService` once the ZIP boundary
is extracted.

## Boundary Decisions

| Concern | Owner After Slice 7e |
|---|---|
| Twin ownership lookup | `SceneGlbService` through `TwinRepository` |
| GLB size limit enforcement | `SceneGlbService` |
| Upload directory creation | `SceneGlbService` |
| `scene.glb` file write/delete | `SceneGlbService` |
| `scene_glb_uploaded` DB flag mutation | `SceneGlbService` |
| DB rollback and file cleanup on storage failure | `SceneGlbService` |
| HTTP status mapping | `src/api/routes/deployer.py` |
| GLB extracted from ZIP response | Still in ZIP route; next ZIP slice |

## Implementation Evidence

Files changed:

- `twin2multicloud_backend/src/services/scene_glb_service.py`
- `twin2multicloud_backend/src/services/service_errors.py`
- `twin2multicloud_backend/src/api/routes/deployer.py`
- `twin2multicloud_backend/tests/test_scene_glb_service.py`

Behavior preserved:

- `POST /twins/{twin_id}/deployer/upload-glb` still returns
  `GLB file uploaded successfully` and `size_mb`.
- Oversized files still return HTTP 400 with the existing size-limit wording.
- Successful upload creates `UPLOAD_DIR/{twin_id}/scene.glb`.
- Successful upload creates deployer config if missing and sets
  `scene_glb_uploaded=true`.
- `DELETE /twins/{twin_id}/deployer/upload-glb` deletes the file when present,
  removes an empty twin directory, and clears `scene_glb_uploaded` when a config
  exists.

## Test Coverage

New tests cover:

- Service upload writes the file and marks config uploaded.
- Service upload rejects oversized content without writing a file.
- Service delete removes the file and clears the config flag.
- Missing twin handling.
- Route-level upload contract with a temporary upload directory.
- Route-level delete contract with a temporary upload directory.

Focused verification:

```text
python -m pytest tests/test_scene_glb_service.py tests/test_error_handling.py -q
34 passed, 3 warnings
```

## Review Findings

| Finding | Resolution |
|---|---|
| The old route leaked raw storage exception text in HTTP 500 responses. | Replaced with typed `StorageError` and a sanitized public message. |
| ZIP upload still writes `scene.glb` directly in `deployer.py`. | Accepted for this slice; ZIP upload is a separate boundary with downstream and response-shaping concerns. |

## Residual Risk

`upload_project_zip` still performs GLB base64 decoding, local storage writes,
and DB flag mutation directly inside the route. The next ZIP extraction slice
must move this into a dedicated service and reuse `SceneGlbService` for the file
storage sub-step.
