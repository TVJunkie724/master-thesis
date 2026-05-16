---
title: "Implementation Plan: Typed Wizard Configuration Contract"
description: "Plan for turning the Flutter wizard configuration flow into a typed, backend-owned contract across API DTOs, persistence, and DeploymentManifest generation."
tags: [implementation-plan, backend, flutter, wizard, configuration, database, deployment-manifest]
lastUpdated: "2026-05-14"
version: "0.1"
---

<!-- SOURCES:
- GitHub Issue #76 "Define typed wizard configuration contract and DB schema cleanup"
- ASSESSMENT.md Phase 4 and Phase 7 roadmap entries
- twin2multicloud_backend/src/api/routes/config.py
- twin2multicloud_backend/src/api/routes/deployer.py
- twin2multicloud_backend/src/api/routes/optimizer_config.py
- twin2multicloud_backend/src/models/twin_config.py
- twin2multicloud_backend/src/models/optimizer_config.py
- twin2multicloud_backend/src/models/deployer_config.py
- twin2multicloud_backend/src/services/deployment_service.py
- twin2multicloud_flutter/lib/bloc/wizard/wizard_bloc.dart
- twin2multicloud_flutter/lib/bloc/wizard/wizard_state.dart
- twin2multicloud_flutter/lib/services/api_service.dart
EXTRACTED: 2026-05-14 | VERSION: 0.1
-->

# Implementation Plan: Typed Wizard Configuration Contract

**Date:** 2026-05-14  
**Scope:** `twin2multicloud_backend`, `twin2multicloud_flutter`, deployment
package generation boundary  
**GitHub issue:** [#76](https://github.com/TVJunkie724/master-thesis/issues/76)  
**Base branch:** `master`  
**Implementation branch:** `codex/flutter-credential-ssot-runtime-config`  
**Plan status:** Approved

**Implementation status:** Completed

**Progress log:**

- 2026-05-14: Slice 1 completed. Backend and Flutter tests pin current wizard
  configuration persistence for CloudConnection selection, legacy credential
  clearing, optimizer/deployer payload shape, and Step 3 draft persistence.
- 2026-05-14: Slice 2 backend service boundary implemented. Config update and
  deployer update semantics now run through `WizardConfigurationService`, with
  explicit omitted/value/null behavior covered by route and service tests.
- 2026-05-14: Slice 3 backend read model stabilized. Config and deployer
  responses now expose explicit `twin_state`, credential source metadata,
  secret-safe bound CloudConnection summaries, configured provider lists, and
  deployer section/validation summaries for deterministic Flutter hydration.
- 2026-05-15: Slice 4 Flutter typed save requests implemented. Wizard save and
  finish flows now use typed request DTOs and a dedicated request builder
  instead of hand-building broad dynamic maps in `WizardBloc`.
- 2026-05-16: Slice 5 deployment package boundary implemented. Package
  generation now materializes a typed `DeploymentPackage` from persisted backend
  state, keeps Deployer file names stable, records secret-bearing file metadata
  in a secrets-free manifest, and fails closed on invalid JSON artifacts or
  missing managed scene binaries.
- 2026-05-16: Slice 6 migration and documentation check completed. No database
  migration was needed for Slice 5 because it changed service/package
  materialization only. Runtime and cloud setup docs now describe the
  CloudConnection-first SSOT, encrypted legacy fallback, bootstrap credential
  discard model, and secrets-free deployment manifest boundary.

---

## 1. Why This Phase Exists

The wizard currently works, but its persistence contract is still a transition
between three different shapes:

- Flutter state and UI maps.
- Management API persistence fields.
- Deployer input files and generated deployment package structure.

Recent fixes hardened concrete bugs around credential clearing and Step 3 draft
persistence. Those bugs had the same root cause: the contract between UI intent,
API update semantics, DB state, and deployer artifacts is not explicit enough.

This phase turns wizard configuration into a typed backend-owned contract. The
goal is not a large UI redesign. The goal is to make the current thesis workflow
predictable, auditable, and ready for the later DeploymentManifest and Flutter
feature-slicing work.

---

## 2. Target State

The Management API owns the canonical wizard configuration contract.

Flutter sends typed user intent:

- selected Cloud Connections,
- optimizer parameters and accepted optimizer result,
- deployer configuration values and user-authored artifacts,
- explicit clear/update operations.

The backend persists this intent with clear semantics:

- omitted field means unchanged,
- explicit `null` means clear where clearing is allowed,
- generated deployer/Terraform file structure is not the API contract,
- deployment package generation reads from canonical backend state,
- secrets are referenced through Cloud Connections or encrypted legacy fallback
  during migration only.

Flutter no longer needs to hand-build broad `Map<String, dynamic>` payloads for
the main wizard save paths. The API service can expose typed request objects
that make accidental stale fields, missing clears, and file-shaped payloads much
harder to introduce.

---

## 3. Field Matrix

### Step 1: Twin And Credentials

| Field group | Current storage | Target classification | Target storage |
|-------------|-----------------|-----------------------|----------------|
| Twin name | `digital_twins.name` | User intent | Structured column |
| Twin lifecycle state | `digital_twins.state` | Derived lifecycle state | Structured column, lifecycle service owned |
| Debug mode | `twin_configurations.debug_mode` | User preference/runtime hint | Structured column |
| Highest step reached | `twin_configurations.highest_step_reached` | UI progress metadata | Structured column |
| AWS/Azure/GCP Cloud Connection IDs | `twin_configurations.*_cloud_connection_id` | Credential reference | Structured foreign keys |
| Legacy AWS credentials | encrypted columns | Migration fallback | Keep temporarily, explicit clear semantics |
| Legacy Azure credentials | encrypted columns | Migration fallback | Keep temporarily, explicit clear semantics |
| Legacy GCP credentials | encrypted columns + public project/region | Migration fallback | Keep temporarily, require service account key |
| Provider regions | provider-specific columns | Deployment intent metadata | Structured columns or provider config document |

### Step 2: Optimizer

| Field group | Current storage | Target classification | Target storage |
|-------------|-----------------|-----------------------|----------------|
| Calculation params | `optimizer_configurations.params` JSON | User intent | Versioned typed JSON document |
| Full optimizer result | `optimizer_configurations.result_json` JSON | Accepted calculation result | Versioned typed JSON document |
| Cheapest path | derived columns | Deployment-critical derived state | Structured columns, derived from accepted result |
| Pricing snapshots | `pricing_*_snapshot` JSON | Audit evidence | Versioned JSON snapshots |
| Pricing timestamps | `pricing_*_updated_at` | Audit evidence | Structured timestamps |
| Calculated timestamp | `calculated_at` | Audit evidence | Structured timestamp |

### Step 3: Deployment Configuration And User Artifacts

| Field group | Current storage | Target classification | Target storage |
|-------------|-----------------|-----------------------|----------------|
| Deployer digital twin name | `deployer_configurations.deployer_digital_twin_name` | Deployment naming intent | Structured column |
| Events config | `config_events_json` text | User-authored config artifact | Versioned JSON document or text with validation |
| IoT devices config | `config_iot_devices_json` text | User-authored config artifact | Versioned JSON document or text with validation |
| Payloads | `payloads_json` text | Simulator/user-authored artifact | Versioned JSON document or text with validation |
| Processor functions | `processor_contents` JSON map | User-authored code artifact | Artifact document keyed by device id |
| Processor requirements | `processor_requirements` JSON map | User-authored dependency artifact | Artifact document keyed by device id |
| Event feedback function | `event_feedback_content` text | User-authored code artifact | Artifact document |
| Event feedback requirements | `event_feedback_requirements` text | User-authored dependency artifact | Artifact document |
| Event action functions | `event_action_contents` JSON map | User-authored code artifact | Artifact document keyed by function name |
| Event action requirements | `event_action_requirements` JSON map | User-authored dependency artifact | Artifact document keyed by function name |
| State machine | `state_machine_content` text | User-authored workflow artifact | Artifact document |
| Hierarchy | `hierarchy_content` text | User-authored twin graph artifact | Artifact document |
| GLB scene file | disk file + `scene_glb_uploaded` flag | Binary artifact | Managed artifact reference, file storage remains transitional |
| Scene config | `scene_config_content` text | User-authored visualization artifact | Artifact document |
| User config | `user_config_content` text | User-authored platform user config | Artifact document |
| Validation flags | `*_validated` columns/text maps | Derived validation state | Validation result records or typed validation state |

---

## 4. API Contract Decisions

### Update Semantics

The contract must distinguish:

| Client shape | Meaning |
|--------------|---------|
| Field omitted | Keep existing value unchanged |
| Field present with value | Replace existing value |
| Field present as `null` | Clear existing value if field is clearable |
| Empty string | Store as empty user input only where empty is valid; otherwise reject |
| Empty map/list | Store empty collection when collection is valid |

For Pydantic models, implementation must use `model_fields_set` for partial
updates so explicit nulls are never confused with omitted fields.

### Endpoint Shape

Prefer typed subcontracts over one large unstructured update payload:

- `PATCH /twins/{id}/config/profile` for debug/progress metadata.
- `PATCH /twins/{id}/config/cloud-connections` for provider references.
- `PATCH /twins/{id}/optimizer-config/params` for optimizer input.
- `PUT /twins/{id}/optimizer-config/result` for accepted calculation result.
- `PATCH /twins/{id}/deployer/config` for deployment user intent.
- Existing endpoints may remain as compatibility adapters during migration.

The first implementation slice may keep existing paths and introduce typed
request builders internally. Route path cleanup can come later if it would
create too much churn.

---

## 5. Persistence Model Decisions

### Keep As Structured Columns

- user id, twin id, twin state,
- Cloud Connection foreign keys,
- provider region/project metadata needed for queries or deployment gating,
- cheapest path columns,
- validation/lifecycle timestamps.

### Keep As Versioned JSON/Text Documents For Now

- optimizer params,
- optimizer result,
- pricing snapshots,
- deployer config JSON files,
- user function content maps,
- requirements maps,
- state machine / hierarchy / scene/user configs.

The thesis project does not need a full artifact store immediately. However,
every JSON/text document should be accessed through typed request/response
models and helper methods instead of raw route-level `json.dumps` /
`json.loads` scattered across the codebase.

### Transitional Compatibility

Legacy encrypted credential columns stay until CloudConnection-only flow is
fully proven. They must remain:

- encrypted at rest,
- never returned in responses,
- clearable through explicit null semantics,
- lower priority than CloudConnection references during credential resolution.

---

## 6. Implementation Slices

### Slice 1: Contract Inventory And Tests

**Files:**

- `twin2multicloud_backend/tests/test_config_routes.py`
- `twin2multicloud_backend/tests/test_deployer_config_contract.py`
- `twin2multicloud_flutter/test/bloc/wizard_cloud_connections_test.dart`
- `twin2multicloud_backend/tests/test_wizard_configuration_contract.py`

**Work:**

- Add explicit backend tests for omitted vs null vs empty values.
- Add deployer config round-trip tests for payload-only, function-only,
  hierarchy-only, and scene/user config-only saves.
- Add Flutter tests for typed payload builders before changing API service.

**Acceptance criteria:**

- Existing behavior is pinned before refactor.
- Known transitional behavior is documented in test names.

### Slice 2: Backend Typed Contract Helpers

**Files:**

- `src/schemas/twin_config.py`
- `src/schemas/deployer_config.py`
- `src/schemas/optimizer_config.py`
- new `src/services/wizard_configuration_service.py`

**Work:**

- Introduce typed internal command objects for wizard profile, credentials,
  optimizer, and deployer config updates.
- Move update/clear semantics out of route handlers into service methods.
- Centralize JSON document serialization/deserialization.

**Acceptance criteria:**

- Route handlers become thin HTTP adapters.
- Service methods can be unit-tested without TestClient.
- Clear/omit/update semantics are identical across providers and config groups.

### Slice 3: Backend Read Model Stabilization

**Files:**

- `src/schemas/twin_config.py`
- `src/schemas/deployer_config.py`
- `src/api/routes/config.py`
- `src/api/routes/deployer.py`

**Work:**

- Define one canonical response shape for wizard reload.
- Ensure response never returns secrets.
- Include enough typed metadata for Flutter to restore state without guessing.
- Keep compatibility fields where current Flutter needs them.

**Acceptance criteria:**

- Flutter edit-mode hydration no longer depends on missing-field defaults for
  expected data.
- Round-trip tests prove save -> reload -> save is stable.

### Slice 4: Flutter Typed Save Requests

**Files:**

- `twin2multicloud_flutter/lib/models/`
- `twin2multicloud_flutter/lib/services/api_service.dart`
- `twin2multicloud_flutter/lib/bloc/wizard/helpers/`
- `twin2multicloud_flutter/lib/bloc/wizard/wizard_bloc.dart`

**Work:**

- Add typed request builders for wizard config save.
- Replace duplicated `Map<String, dynamic>` construction in `_onSaveDraft` and
  `_onFinish`.
- Keep BLoC state immutable and UI-facing; move API payload knowledge out of
  the BLoC.

**Acceptance criteria:**

- `WizardBloc` no longer hand-builds broad dynamic maps for main save flows.
- Tests verify payloads for CloudConnection-only, legacy credential, clear, and
  Step 3 artifact-only updates.

### Slice 5: Deployment Package Boundary

**Files:**

- `src/services/deployment_service.py`
- deployment manifest tests
- existing credential resolution tests

**Work:**

- Make deployment package generation consume typed backend config helpers.
- Keep current file output names where the Deployer still requires them.
- Ensure `DeploymentManifest` describes canonical backend state and file
  materialization, not Flutter payload shape.

**Acceptance criteria:**

- Deployment package generation does not depend on route-level request shape.
- Manifest tests prove package content can be reconstructed from persisted DB
  state and CloudConnection references.

### Slice 6: Migration And Documentation

**Files:**

- idempotent migration scripts if DB shape changes.
- `docs-site/docs/runtime/` or architecture docs only if user-facing behavior
  changes.

**Work:**

- Add migrations only for actual schema changes.
- Document transitional legacy credential behavior.
- Update issue #76 with final verification evidence.

**Acceptance criteria:**

- Local dev DBs can upgrade idempotently.
- Documentation explains the final contract without preserving stale legacy
  implementation details as design.

---

## 7. Test Strategy

### Backend

- Unit tests for service-level command handling.
- TestClient route tests for compatibility and API status codes.
- Migration tests for schema changes.
- Deployment package tests for persisted config -> manifest/package output.
- Security tests for secret redaction and no credential response leakage.

### Flutter

- Request builder unit tests.
- Wizard BLoC tests for save draft and finish flows.
- Hydration tests for edit mode reload.
- Widget tests only where UX/state behavior changes.

### Integration-Style Check

At least one end-to-end local test should prove:

1. create twin,
2. bind Cloud Connections or legacy test credentials,
3. save optimizer params/result,
4. save Step 3 artifacts,
5. reload wizard config,
6. build deployment package input without missing required fields.

---

## 8. Risks And Mitigations

| Risk | Mitigation |
|------|------------|
| Too much API churn breaks Flutter | Keep existing endpoints as compatibility adapters until Flutter typed requests are in place. |
| JSON document typing grows too large | Type only API/service boundaries first; avoid over-normalizing the DB for thesis scope. |
| Legacy credential fallback obscures SSOT | Keep Cloud Connections higher priority and add tests for fallback-only behavior. |
| Deployment package changes break Deployer | Preserve file names and paths while changing only the source of truth behind generation. |
| Validation state becomes stale | Define explicit invalidation rules for updates that affect dependent artifacts. |

---

## 9. Done Definition

- [x] Field matrix exists and is reflected in tests.
- [x] Explicit null/omit/update semantics are implemented through typed helpers.
- [x] Backend routes delegate wizard persistence to services.
- [x] Flutter main save flows use typed request builders.
- [x] Deployment package generation reads from canonical backend state.
- [x] Secret fields are never exposed in API responses or logs.
- [x] Round-trip persistence tests exist for Step 1, Step 2, and Step 3.
- [x] GitHub Issue #76 is referenced by implementation commits.
- [x] Backend and Flutter test suites pass.

**Verification commands:**

```bash
docker exec -e PYTHONPATH=/app master-thesis-management-api-1 pytest tests -q

cd twin2multicloud_flutter && flutter test

docker exec -e PYTHONPATH=/app master-thesis-management-api-1 python -m bandit -q /app/src

git diff --check
```
