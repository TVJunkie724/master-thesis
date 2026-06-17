---
title: "Frontend Delta Phase 1 Contract Baseline Implementation Plan"
description: "Implementation-ready plan and contract audit for stabilizing the Management API contracts required by the Flutter frontend delta roadmap."
tags: [flutter, management-api, contracts, frontend-delta, dto, pricing, credentials, deployment]
lastUpdated: "2026-06-17"
version: "1.0"
---

<!-- SOURCES:
- FRONTEND_ARCHITECTURE.md architecture overview, Management API boundary, Digital Twin states
- integration_vision.md Management Platform vision and workflow
- ONBOARDING.md source-of-truth, Docker, credential, and test rules
- twin2multicloud_flutter/README.md runtime config and quality checks
- twin2multicloud_flutter/docs/frontend_delta/ROADMAP_FRONTEND_DELTA.md
- twin2multicloud_flutter/docs/frontend_delta/phases/PHASE_01_CONTRACT_BASELINE.md
- docs/plans/provider_access_pricing_review/README.md
- docs/plans/provider_access_pricing_review/phase_01_credential_purpose_model.md
- docs/plans/provider_access_pricing_review/phase_04_dashboard_pricing_health_row.md
- docs/plans/provider_access_pricing_review/phase_05_reviewed_decisions_persistence.md
- docs/plans/provider_access_pricing_review/phase_06_pricing_review_center_ui.md
- docs/plans/2026-06-06_pricing_catalog_reliability.md
- twin2multicloud_backend/src/api/routes/cloud_connections.py
- twin2multicloud_backend/src/api/routes/optimizer.py
- twin2multicloud_backend/src/api/routes/deployer.py
- twin2multicloud_backend/src/api/routes/twins.py
- twin2multicloud_backend/src/api/routes/sse.py
- twin2multicloud_backend/src/schemas/cloud_connection.py
- twin2multicloud_backend/src/schemas/pricing_review.py
- twin2multicloud_flutter/lib/services/api_service.dart
- twin2multicloud_flutter/lib/services/sse_service.dart
- twin2multicloud_flutter/lib/models/cloud_connection.dart
- twin2multicloud_flutter/lib/models/pricing_review_state.dart
- GitHub issues #72, #73, #77, #84, #100
EXTRACTED: 2026-06-17 | VERSION: 1.0
-->

# Implementation Plan: Frontend Delta Phase 1 Contract Baseline

## 0. Git Branch

- **Branch name:** `codex/frontend-contract-baseline`
- **Base branch:** `master` after the current planning branch is merged.
- **Current planning branch:** `codex/gcp-tiering-calculation-hardening`.
- **Merge strategy:** Merge commit only, no rebase.
- **Session ID:** n/a; use conventional commit messages.
- **GitHub anchors:** #72 for typed Flutter/API contracts, #73 for Twin Overview operations, #77 for the architecture roadmap epic, #100 for pricing traceability.
- **Status:** In progress. FD-CB-001 is implemented; remaining gaps still need
  focused implementation slices.

## 1. Summary

Phase 1 freezes the contract baseline for the Flutter frontend delta roadmap.
It does not build the Profile, Dashboard, Pricing Review, Wizard, or Twin
Overview screens yet. Its job is to create an implementation-ready API and DTO
boundary so later phases do not depend on log parsing, raw dynamic maps, or
direct Optimizer/Deployer details.

This phase matters because the current state is mixed:

- Several stable Management API routes already exist.
- Flutter already has typed models for Cloud Connections and pricing review
  state.
- Many core UI flows still receive `Map<String, dynamic>` payloads.
- Some routes needed by Flutter are planned but missing.
- One Flutter client method points to a route that is not present in the
  Management API source.

The output of this phase is a reviewed contract evidence pack:

- Management API contract inventory.
- Backend gap list classified as bug or feature work.
- Flutter DTO readiness matrix.
- Target response shapes for missing or partial routes.
- Test and verification gates for all downstream UI phases.

Non-goals:

- Do not implement the downstream Profile, Dashboard, Pricing Review, Wizard,
  or Twin Overview screens.
- Do not run live cloud deployment E2E.
- Do not persist admin/bootstrap credentials.
- Do not introduce RBAC before the platform has a real role model.
- Do not make Flutter call Optimizer or Deployer directly.

## 2. Visual Layout (ASCII)

Phase 1 introduces no runtime user screen. The "layout" is the contract package
that every later Flutter phase must consume.

```text
Frontend Delta Contract Baseline
|
|-- Contract Inventory
|   |-- existing Management API routes
|   |-- partial routes needing additive fields
|   `-- missing routes needing backend work
|
|-- DTO Readiness Matrix
|   |-- existing Dart models
|   |-- new Dart model contracts
|   `-- dynamic Map boundaries to remove later
|
|-- Backend Gap Register
|   |-- feature requests
|   |-- bugs
|   `-- linked GitHub issues
|
`-- Verification Gate
    |-- OpenAPI/schema check
    |-- backend route/schema tests
    |-- Flutter model parse tests
    `-- no direct 5003/5004 Flutter calls
```

Downstream screen dependency map:

```text
Phase 1 Contracts
|
|-- /cloud-access
|   `-- Phase 2 Settings/Profile Cloud Accounts
|
|-- /optimizer/pricing-health
|   `-- Phase 3 Dashboard Pricing Health
|
|-- /optimizer/pricing-refresh + /pricing-review + trace contracts
|   `-- Phase 4 Pricing Review Center
|
|-- /twins/{id}/config + /optimizer-config + typed deployer config
|   |-- Phase 5 Wizard Step 1 Boundary
|   |-- Phase 6 Wizard Step 2 Cleanup
|   `-- Phase 7 Wizard Step 3 Schema
|
`-- /twins/{id}/deployment-status + logs + verify + simulator
    `-- Phase 8 Twin Overview Operations
```

Web/Desktop contract evidence view for docs and handoff:

```text
Implementation Plan Document
+------------------------------------------------------------------+
| Section 10: Integration Points                                   |
|                                                                  |
| Contract                         Status     Consumer Phase       |
| GET /cloud-access                Missing    Phase 2              |
| GET /optimizer/pricing-health    Missing    Phase 3              |
| GET /optimizer/pricing-review... Partial    Phase 4              |
| GET /twins/{id}/logs             Missing    Phase 8              |
|                                                                  |
| Section 11: Test Plan                                            |
| - backend route tests                                             |
| - Dart model parsing tests                                        |
| - integration smoke, no live cloud E2E                            |
+------------------------------------------------------------------+
```

## 3. Widget Tree

No runtime widgets are introduced in Phase 1. Later screen phases must not
create widgets until the contracts below are stable.

The future widget consumers are:

```text
SettingsScreen [MODIFY IN PHASE 2]
`-- CloudAccessSection [NEW IN PHASE 2]
    `-- consumes CloudAccessInventory DTO from GET /cloud-access

DashboardScreen [MODIFY IN PHASE 3]
`-- PricingDataHealthSection [NEW IN PHASE 3]
    `-- consumes PricingHealth DTO from GET /optimizer/pricing-health

PricingReviewScreen [NEW IN PHASE 4]
`-- PricingReviewBlocProvider [NEW IN PHASE 4]
    |-- consumes PricingRefreshRun DTO
    |-- consumes PricingCandidateReport DTO
    `-- consumes PricingTrace DTO

WizardScreen [MODIFY IN PHASES 5-7]
|-- Step1Configuration [MODIFY IN PHASE 5]
|-- Step2Optimizer [MODIFY IN PHASE 6]
`-- Step3Deployer [MODIFY IN PHASE 7]
    `-- consumes typed config/readiness DTOs

TwinOverviewScreen [MODIFY IN PHASE 8]
`-- TwinOverviewBloc [MODIFY IN PHASE 8]
    |-- consumes DeploymentStatus DTO
    |-- consumes DeploymentLogPage DTO
    |-- consumes DeploymentOutput DTO
    |-- consumes VerificationResult DTO
    `-- consumes SimulatorPackage/Trace operation DTOs
```

## 4. Component Specifications

Phase 1 creates or updates documentation and contract DTO specifications. It
does not add production widgets.

### Contract Audit Document [NEW]

Path:
`twin2multicloud_flutter/implementation_plans/2026-06-17_frontend_delta_phase_01_contract_baseline.md`

Must contain:

- route inventory,
- route status (`existing`, `partial`, `missing`),
- downstream consumer phase,
- required response shape,
- redaction requirements,
- issue linkage,
- verification commands.

### Flutter DTO Contract Set [PLANNED]

The builder must not create these DTOs until the backend contract is either
implemented or explicitly versioned as a stable draft. Once available, add:

```text
lib/models/cloud_access.dart              [NEW]
lib/models/pricing_health.dart            [NEW]
lib/models/pricing_review_contracts.dart  [NEW]
lib/models/deployment_operations.dart     [NEW]
lib/models/deployer_config_contract.dart  [NEW OR SPLIT]
```

Each DTO file must:

- use `Equatable`,
- expose explicit enum/value objects where the backend has finite states,
- convert snake_case response fields in one place,
- reject unparseable required fields with test-covered errors,
- never include secret fields, local credential file paths, OpenAI keys, or
  admin/bootstrap material.

### Management API Schema Set [PLANNED]

The backend implementation must add Pydantic schemas before route logic:

```text
twin2multicloud_backend/src/schemas/cloud_access.py       [NEW]
twin2multicloud_backend/src/schemas/pricing_health.py     [NEW]
twin2multicloud_backend/src/schemas/pricing_review.py     [EXTEND]
twin2multicloud_backend/src/schemas/deployment_read.py    [NEW]
twin2multicloud_backend/src/schemas/deployer_config.py    [EXTEND]
```

Each schema must include `schema_version` when it is a frontend read model.

## 5. Responsive Behavior

Phase 1 has no runtime layout. Downstream contracts still need responsive
requirements because they drive later screen shapes:

| Breakpoint | Width | Contract implication |
|---|---:|---|
| Wide Desktop | >= 1440px | DTOs may expose detail fields; UI decides density. |
| Narrow Desktop / Web | 800-1439px | DTOs must contain short labels and summaries so cards can wrap cleanly. |
| Compact Web | < 800px | DTOs must contain concise `primary_message`/`status_label`; Flutter must not derive user-facing text from raw logs. |

No mobile target is introduced.

## 6. State Flow (BLoC)

Phase 1 does not introduce a new feature BLoC. It defines the read-model flows
that later BLoCs must implement.

Contract verification flow:

```text
Builder
  -> inspect Management API routes and Pydantic schemas
  -> update contract matrix
  -> add backend schemas/routes or mark gap with issue
  -> add Flutter DTO parse tests
  -> run no-direct-port static check
  -> phase can unblock downstream UI plan
```

Future UI state flow shape:

```text
Screen
  -> FeatureEvent
  -> FeatureBloc
  -> FeatureService
  -> ApiService
  -> Management API :5005
  -> typed response DTO
  -> FeatureState.copyWith(...)
  -> dumb widgets render state
```

Forbidden flow:

```text
Widget or Bloc
  -> http://localhost:5003 or :5004
  -> Optimizer/Deployer
```

## 7. Design Tokens

No token changes are allowed in Phase 1.

Downstream plans must reuse:

- `lib/theme/colors.dart` for provider and semantic colors,
- `lib/theme/spacing.dart` for spacing and layout constants,
- `Theme.of(context).textTheme` for typography,
- Material `Icons` only.

## 8. Interactions & Animations

No runtime interaction or animation is implemented in Phase 1.

The contracts must support later interaction states:

- loading,
- loaded,
- empty,
- partial failure,
- total failure,
- blocked/action required,
- stale/review required,
- active operation,
- completed operation,
- recoverable error.

Every response shape consumed by Flutter must give enough typed data for these
states without parsing free-text logs.

## 9. Accessibility

No runtime UI is added in Phase 1. The contract baseline must still preserve
accessibility by requiring:

- short status labels,
- detailed but optional diagnostic messages,
- deterministic severity/state enums,
- user-actionable remediation strings,
- no reliance on color as the only state carrier.

Downstream widgets must use semantic labels and keyboard traversal in their own
implementation plans.

## 10. Integration Points

### 10.1 Existing Route Audit

| Contract | Current route/status | Consumer | Finding |
|---|---|---|---|
| CloudConnection list/create/update/delete | `GET/POST/PATCH/DELETE /cloud-connections` exists | Phase 2, Phase 5 | Existing response is secret-free but lacks purpose/default-pricing/in-use aggregate needed by Profile. |
| CloudConnection validation | `POST /cloud-connections/{id}/validate` exists | Phase 2 | Existing route returns optimizer/deployer validation summaries. Must remain redacted. |
| CloudConnection preflight | `POST /cloud-connections/{id}/preflight` exists | Phase 8 | Existing route returns ready/checks/permission-set status. Needs consumer mapping in Twin Overview. |
| Pricing raw freshness | `GET /optimizer/pricing-status` exists | Legacy Step 2 | Too raw for final Dashboard. Keep as backend/internal compatibility. |
| Pricing review state | `GET /optimizer/pricing-review-state?twin_id=` exists | Phase 3/6 partial | Typed and useful, but does not include provider access identity/credential confirmation metadata. |
| Pricing refresh | `POST /optimizer/refresh-pricing/{provider}?twin_id=` exists | Phase 4 partial | Synchronous route uses twin-bound credentials. Target Review Center needs user-scoped pricing credential confirmation and run identity. |
| Pricing refresh SSE | `GET /optimizer/stream/refresh-pricing/{provider}?twin_id=` exists | Phase 4 partial | Streams logs, but logs must stay diagnostic and not be business state. Needs refresh-run result contract. |
| Pricing export | `GET /optimizer/pricing/export/{provider}` exists | Legacy snapshotting | Useful internally; not enough for candidate review. |
| Cost calculation | `PUT /optimizer/calculate` exists | Phase 6 | Existing calculation route is fine as Management API boundary. Later DTO hardening belongs to #72. |
| Optimizer config | `GET/PUT /twins/{id}/optimizer-config/...` exists | Phase 6/8 | Currently consumed through dynamic maps in Flutter. Needs typed DTO plan under #72. |
| Deployer config | `GET/PUT /twins/{id}/deployer/config` exists | Phase 7/8 | Response exists but Flutter uses dynamic map traversal. Needs typed deployer config contract. |
| Deployer config validation | `POST /twins/{id}/deployer/validate/{type}` exists | Phase 7 | Existing validation can stay, but returned errors must be typed for field-level UI. |
| Deploy/destroy | `POST /twins/{id}/deploy`, `POST /twins/{id}/destroy` exist | Phase 8 | Existing response returns `session_id` and `sse_url`. Good baseline. |
| Deployment SSE | `GET /sse/deploy/{session_id}` exists | Phase 8 | Existing route supports reconnect with `last_event_id`. Good baseline. |
| Deployment status | `GET /twins/{id}/deployment-status` exists | Phase 8 | Existing response includes state, active session, latest deployment. Needs Flutter DTO. |
| Deployment outputs | `GET /twins/{id}/outputs` exists | Phase 8 | Existing route returns outputs/deployed_at. Needs typed display schema. |
| Deployment history | `GET /twins/{id}/deployments` exists | Phase 8 | Existing route is useful for audit/history. Needs typed DTO. |
| Log trace | `POST /twins/{id}/log-trace/start`, `GET /twins/{id}/log-trace/stream/{trace_id}` exist | Phase 8 | Existing routes support testing utilities. UI must keep diagnostics collapsed. |
| Infrastructure verification | `POST /twins/{id}/verify/infrastructure` exists | Phase 8 | Existing route supports structured verification. Needs typed DTO and UI mapping. |
| Data flow verification | `POST /twins/{id}/verify/dataflow` exists | Phase 8 | Existing route starts SSE verification. Needs typed request/response and no live-cloud default tests. |
| Simulator download | `GET /twins/{id}/simulator/download` exists | Phase 8 | Existing route returns ZIP bytes. Good baseline. |
| Deployment log catchup | Flutter calls `GET /twins/{id}/logs` | Phase 8 | Backend route was not found in source. This is a bug-level contract gap. |

### 10.2 Required Target Contracts

#### Cloud Access Inventory

```http
GET /cloud-access
```

Target response:

```json
{
  "schema_version": "cloud-access-inventory.v1",
  "providers": {
    "aws": {
      "pricing": {
        "connection_id": "cc-aws-pricing",
        "provider": "aws",
        "purpose": "pricing",
        "scope": "user",
        "identity_label": "t2mc-pricing-reader",
        "provider_account_id": "123456789012",
        "is_default_for_pricing": true,
        "status": "active",
        "last_validated_at": "2026-06-17T00:00:00Z",
        "last_used_at": null
      },
      "deployment": [
        {
          "connection_id": "cc-aws-deploy",
          "provider": "aws",
          "purpose": "deployment",
          "scope": "twin",
          "identity_label": "t2mc-deployer",
          "provider_account_id": "123456789012",
          "bound_twin_count": 1,
          "bound_twin_labels": ["Factory Twin"],
          "permission_set_status": "matched",
          "status": "active"
        }
      ]
    },
    "azure": {
      "pricing": {
        "connection_id": null,
        "provider": "azure",
        "purpose": "pricing",
        "scope": "public",
        "identity_label": "Azure Retail Prices API",
        "status": "active"
      },
      "deployment": []
    }
  }
}
```

Rules:

- No secret payloads.
- No local file paths.
- No admin/bootstrap material.
- Deployment access returns `bound_twin_count` and safe display labels, not raw
  ids, so the UI can explain blocked deletion without exposing unnecessary
  identifiers.

#### Pricing Health

```http
GET /optimizer/pricing-health
```

Target response:

```json
{
  "schema_version": "pricing-health.v1",
  "providers": {
    "gcp": {
      "provider": "gcp",
      "state": "review_required",
      "severity": "warning",
      "review_required": true,
      "can_calculate": true,
      "calculation_source": "last_known_good",
      "pricing_freshness": "last_known_good",
      "age": "15 days",
      "last_fetched_at": "2026-06-02T00:00:00Z",
      "source_label": "Project thesis-demo",
      "credential_summary": {
        "connection_id": "cc-gcp-pricing",
        "provider": "gcp",
        "purpose": "pricing",
        "identity_label": "pricing-reader@thesis-demo",
        "provider_project_id": "thesis-demo",
        "status": "active"
      },
      "primary_message": "Review required before publishing new pricing decisions",
      "actions": ["open_pricing_review"]
    }
  }
}
```

Rules:

- Dashboard consumes this aggregate route, not raw Optimizer logs.
- This route may compose existing `/optimizer/pricing-review-state` and
  `/cloud-access`, but Flutter must not do that composition.

#### Pricing Refresh Run

```http
POST /optimizer/pricing-refresh/{provider}
GET /optimizer/pricing-refresh/{refresh_run_id}
GET /optimizer/pricing-refresh/{refresh_run_id}/stream
```

Target request:

```json
{
  "pricing_connection_id": "cc-aws-pricing",
  "force": true
}
```

Target start response:

```json
{
  "schema_version": "pricing-refresh-run.v1",
  "refresh_run_id": "run-123",
  "provider": "aws",
  "status": "queued",
  "credential_summary": {
    "connection_id": "cc-aws-pricing",
    "identity_label": "t2mc-pricing-reader",
    "provider_account_id": "123456789012"
  },
  "sse_url": "/optimizer/pricing-refresh/run-123/stream"
}
```

Rules:

- Azure may pass `pricing_connection_id: null` because current Azure pricing is
  public API based.
- SSE is operational progress only.
- The final run state links to candidate report ids and health state refresh.

#### Pricing Candidate Review

```http
GET /optimizer/pricing-review/{provider}/candidate-reports?refresh_run_id=...
GET /optimizer/pricing-review/candidate-reports/{report_id}
POST /optimizer/pricing-review/decisions
GET /optimizer/pricing-review/decisions
```

Target candidate report fields:

```json
{
  "schema_version": "pricing-candidate-report.v1",
  "report_id": "report-123",
  "provider": "aws",
  "refresh_run_id": "run-123",
  "intent_id": "l1.iot_message_ingest",
  "expected_model": "per_message",
  "expected_unit": "message",
  "deterministic_selection": {
    "candidate_id": "cand-a",
    "selectable": true,
    "confidence_label": "exact_contract_match"
  },
  "ai_suggestion": {
    "enabled": true,
    "candidate_id": "cand-a",
    "rationale": "Matches service, region, tier, and unit."
  },
  "candidates": [],
  "rejected_candidates": [],
  "review_state": "needs_review"
}
```

Rules:

- AI is optional and configured through backend environment only.
- AI may preselect in UI, but persistence requires explicit user approval.
- Backend revalidates candidate contract gates on approval.
- Flutter cannot write source-controlled registry files.

#### Pricing Trace / Evidence

```http
GET /optimizer/pricing-review/candidate-reports/{report_id}/trace
```

Target trace fields:

```json
{
  "schema_version": "pricing-trace.v1",
  "report_id": "report-123",
  "provider": "aws",
  "intent": {},
  "query_scope": {},
  "selected_candidate": {},
  "close_candidates": [],
  "rejected_candidates": [],
  "hard_checks": [],
  "normalization": {},
  "formula_ref": "cost.v1.l1.iot_ingest",
  "sanitization": {
    "bounded": true,
    "secret_free": true,
    "omitted_raw_rows": 42
  }
}
```

Rules:

- Trace is collapsed by default in Flutter.
- Trace is bounded and secret-free before Flutter receives it.
- Raw unbounded provider payloads are never sent to Flutter.

#### Deployment Log Catchup

```http
GET /twins/{twin_id}/logs?session_id=&after_event_id=&limit=100
```

Target response:

```json
{
  "schema_version": "deployment-log-page.v1",
  "twin_id": "twin-123",
  "session_id": "session-123",
  "events": [
    {
      "event_id": 42,
      "level": "info",
      "message": "Terraform apply complete",
      "operation_type": "deploy",
      "timestamp": "2026-06-17T00:00:00Z"
    }
  ],
  "has_more": false
}
```

Rules:

- This is a bug fix because Flutter already calls the route.
- The response must be paginated and owner-scoped.
- It must not expose raw secrets from deployer output.

### 10.3 Gap Register

| Gap ID | Type | Area | Description | Suggested issue |
|---|---|---|---|---|
| FD-CB-001 | feature | backend/flutter | Add `GET /cloud-access` with credential purpose/default/in-use metadata. | Implemented in first backend slice; continue Flutter DTO work under #72. |
| FD-CB-002 | feature | backend/flutter | Add `GET /optimizer/pricing-health` aggregate read model. | Link/update #33 and #72. |
| FD-CB-003 | feature | backend/optimizer/flutter | Replace twin-bound pricing refresh UI contract with provider refresh run ids and credential confirmation. | Link/update #72 and #100. |
| FD-CB-004 | feature | backend/optimizer/flutter | Add candidate report, reviewed decision, and sanitized trace read routes. | Link/update #100. |
| FD-CB-005 | bug | backend/flutter | Implement or remove Flutter dependency on missing `GET /twins/{id}/logs` route. | Link/update #73. |
| FD-CB-006 | feature | backend/flutter | Define typed deployer config read model and Dart DTOs. | Link/update #72 and #76 context. |
| FD-CB-007 | feature | backend/flutter | Add typed deployment operation DTOs for status, history, outputs, verification, simulator, and log trace. | Link/update #73. |

### 10.4 Implementation Evidence

FD-CB-001 backend contract is implemented as:

- `GET /cloud-access`
- `CloudAccessInventoryResponse`
- `schema_version`: `cloud-access-inventory.v1`
- service boundary: `CloudAccessInventoryService`

Current behavior:

- Azure pricing is represented as active public pricing access.
- AWS/GCP pricing are represented as missing until purpose-aware pricing
  CloudConnections are implemented.
- Existing CloudConnections are represented as deployment access.
- Deployment entries include safe provider identity metadata, permission-set
  status, and `bound_twin_count`/`bound_twin_labels`.
- Responses do not decrypt or expose credential payloads.

Verification:

```bash
docker compose run --rm management-api sh -lc 'cd /app && PYTHONPATH=/app python -m pytest tests/test_cloud_access.py tests/test_cloud_connections.py tests/test_config_routes.py -q'
curl -fsS http://localhost:5005/openapi.json | python3 -m json.tool >/tmp/t2mc-openapi.json
rg -n 'cloud-access|getCloudAccessInventory|cloud-access-inventory.v1' /tmp/t2mc-openapi.json
```

## 11. Test Plan

### Unit and schema tests

| # | Type | Test description | Expected outcome |
|---|---|---|---|
| 1 | Happy | `CloudAccessInventory` serializes AWS pricing and deployment entries. | No secret fields; purpose/scope/default fields parse correctly. |
| 2 | Happy | `PricingHealthResponse` serializes fresh/stale/review-required provider states. | Dashboard-ready labels, severity, and actions are present. |
| 3 | Unhappy | Cloud access inventory attempts to include a secret-like key. | Test fails or redaction strips the key before response. |
| 4 | Unhappy | Pricing health cannot reach Optimizer. | Response or HTTP error is typed and renderable, not raw traceback/log text. |
| 5 | Edge | Azure pricing has no credential id. | DTO accepts public pricing capability without treating it as missing secret. |
| 6 | Edge | Multiple AWS pricing credentials exist. | Exactly one default is returned, or response reports blocked/default-required state. |
| 7 | Edge | CloudConnection is bound to twins. | Delete metadata exposes blocked/in-use state without leaking secrets. |
| 8 | Edge | Pricing trace has more raw rows than UI limit. | Response is bounded and reports omitted count. |
| 9 | Edge | SSE deployment session has completed before reconnect. | Log catchup and final event can be read deterministically. |
| 10 | Edge | Legacy draft has dynamic config fields. | Contract marks read/migration compatibility and blocks new writes of legacy-only fields. |

### Flutter model tests

Required once DTOs are added:

```bash
cd twin2multicloud_flutter
flutter test test/models
```

Must cover:

- `cloud_access.dart`,
- `pricing_health.dart`,
- `pricing_review_contracts.dart`,
- `deployment_operations.dart`,
- `deployer_config_contract.dart`.

Every test must assert exact field values and failure behavior. Silent parse
tests are not allowed.

### Backend tests

Required once backend routes are added:

```bash
docker compose up -d management-api 2twin2clouds 3cloud-deployer
docker exec -e PYTHONPATH=/app master-thesis-management-api-1 python -m pytest tests/ -q
```

Route-level tests must cover:

- auth ownership,
- no secret output,
- missing/partial provider data,
- Optimizer unavailable,
- Deployer unavailable where relevant,
- pagination for deployment logs,
- stable `schema_version` fields.

### Contract smoke

When the local stack is running:

```bash
curl -s http://localhost:5005/openapi.json > /tmp/t2mc-openapi.json
python -m json.tool /tmp/t2mc-openapi.json >/dev/null
rg -n 'cloud-access|pricing-health|pricing-refresh|pricing-review|/logs' /tmp/t2mc-openapi.json
```

### Flutter static checks

```bash
rg -n 'localhost:5003|localhost:5004|:5003|:5004' twin2multicloud_flutter/lib
rg -n 'OPENAI_API_KEY|service_account|private_key|credentials.json' twin2multicloud_flutter/lib
```

These checks pass only when they return no matches.

### Full frontend gate

```bash
cd twin2multicloud_flutter
flutter pub get
flutter analyze
flutter test
flutter build web --dart-define-from-file=config/dev.json
```

No real cloud deployment E2E is part of this phase.

## 12. Definition of Done

- [ ] Contract inventory in Section 10 is updated against current route source
      and, when available, `/openapi.json`.
- [ ] Every downstream frontend delta phase references either an existing route
      or an approved backend implementation plan.
- [ ] Gap register entries are linked to existing GitHub issues or split into
      new focused issues.
- [ ] `GET /cloud-access` target shape is approved.
- [ ] `GET /optimizer/pricing-health` target shape is approved.
- [ ] Pricing refresh run, candidate report, reviewed decision, and trace
      contracts are approved.
- [ ] Deployment log catchup route gap is classified as bug and tracked.
- [ ] Typed deployer config and deployment operation DTO boundaries are
      approved.
- [ ] All response contracts are secret-free by construction.
- [ ] No contract requires Flutter to parse raw logs for business state.
- [ ] No contract requires Flutter to call Optimizer or Deployer directly.
- [ ] Test plan includes backend schema/route tests, Flutter model tests,
      static direct-port checks, and no live cloud E2E.
- [ ] Roadmap/phase docs link back to this implementation plan.
- [ ] Plan is reviewed with architect and builder perspectives before code
      implementation starts.
