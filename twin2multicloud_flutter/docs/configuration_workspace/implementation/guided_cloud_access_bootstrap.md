---
title: "Guided Cloud Access Bootstrap Implementation"
description: "Implemented offline PoC boundary for request-only bootstrap authority, bounded deployment CloudConnections, and the shared Flutter flow."
tags: [flutter, bootstrap, cloud-connections, security, phase-8]
lastUpdated: "2026-08-24"
version: "1.4"
---

# Guided Cloud Access Bootstrap Implementation

## Outcome

Phase 9 and the cross-stack #154 prerequisite are implemented for the
credential-free thesis PoC. Settings and Prepare deployment open one shared
feature. The user reviews provider-owned preparation steps and both permission
packs before entering one credential. That credential belongs only to the
synchronous execute request; Flutter never emits it into BLoC state, and
Management never persists it.

The safe result is a validated, encrypted, user-owned
`purpose=deployment` CloudConnection with `thesis-demo-v2`. The implementation
distinguishes provider revocation, provider expiry, manual revocation,
application release after failure, and an existing credential that remains
user-managed. The active guide pins AWS/Azure admin-v2 and GCP admin-v3
authority packs. GCP v3 also pins and displays the fixed 19-service Phase 8
API baseline for one existing project; organization/project creation fails
closed. AWS also pins `aws.thesis-demo-v2.iam-user-v1`, so its
IAM-user/access-key identity and customer-managed-policy attachment are part of
the reviewed contract rather than inferred from the permission inventory.
Azure similarly pins `azure.thesis-demo-v2.service-principal-v1` for its
service-principal/client-secret path and the three ARM metadata reads required
by Deployer self-inspection.

## Implemented Boundary

| Area | Implementation |
|---|---|
| Contracts | Synchronized strict `cloud-bootstrap-guide.v1` and `cloud-bootstrap-session.v1` schemas, fixtures, active provider authority packs, deployment-pack references, the GCP API baseline, and the AWS/Azure deployment-identity bindings |
| Management | Owner-scoped safe sessions, scope uniqueness, optimistic revision, create/execute idempotency, stale-lease reconciliation, cancel, recheck, manual-revocation acknowledgement, audit events, and encrypted generated CloudConnection persistence |
| Adapters | Deterministic no-cloud AWS, Azure, and GCP lifecycle adapters; production default is disabled. The synchronized `supervised_live` mode is represented explicitly but remains blocked by an unconfigured fail-closed adapter. |
| Deployer | Generated `thesis-demo-v2` connections select the exact synchronized provider pack; AWS/Azure identity bindings cover checker metadata reads. GCP checks all 19 baseline services and fails closed when one is absent; active v2 Terraform never enables project services. Live provider evidence is not claimed. |
| Flutter | Strict response models, one-use request object, route-scoped BLoC, shared dialog composition, provider target/guide/authority/result steps, resume/recheck/cancel/start-new, explicit manual cleanup, and GCP existing-project/API-baseline disclosure |
| Entry points | Settings refreshes Cloud Accounts; Prepare deployment reloads and selects the returned connection for the active Twin draft |
| Compatibility | Existing manual plan/script/import endpoints and advanced raw deployment-connection import remain available |

The presentation layer depends on typed callbacks and feature composition, not
on the concrete HTTP service. Flutter calls the Management API only. Official
provider links are rendered from the strict guide/finding contract.

## Secret Boundary

- Provider fields are created only from guide metadata and are obscured when
  secret or JSON-bearing.
- The credential map is copied into a one-use
  `CloudBootstrapExecuteRequest`, consumed exactly once by the HTTP adapter,
  and cleared on success and failure.
- Session state contains only safe scope, pack, finding, disposal, identifier,
  revision, timestamp, and connection-summary data.
- Execute request bodies are tagged as sensitive and are excluded from
  application diagnostics. Backend schemas redact validation errors.
- Integration tests scan Management logs and SQLite database/WAL/SHM files for
  a submitted sentinel.

This is non-persistence and no deliberate retention, not a cryptographic
managed-runtime memory-zeroization claim.

## Runtime Truth

`deterministic_fake` is an offline simulation. It exercises the complete
lifecycle and persists synthetic generated deployment credentials, but creates
no provider identity or cloud resource. Production uses `disabled` and fails
closed. Canonical contracts, Management, OpenAPI, and Flutter also recognize
`supervised_live`; this mode currently returns a blocking guide finding and its
adapter refuses execution until reviewed provider implementations are wired
in. Any supervised live-cloud evidence requires separate authorization and
review. The version-aware Deployer checker
path is implemented and tested offline, but G2-G5 have not contacted any
provider. The versioned manual scripts remain the current supervised provider
path. GCP API ownership is resolved offline: bootstrap v3 enables the fixed
baseline, generated v2 access verifies it, and Terraform does not mutate it.
G6/G7 remain blocked because G2-G5 supervised provider evidence is absent.

## Verification

The completed branch passed:

- 43 focused Flutter model/API/BLoC/widget/demo tests after the final parser and
  demo-parity corrections;
- all 806 Flutter unit/widget tests, analyzer, architecture guard, Web release,
  and macOS debug build;
- all four real-Management Flutter integration files in the isolated OrbStack
  project, including three guided-bootstrap tests and the log/SQLite sentinel
  scan;
- all 1,038 Management tests;
- the complete 14-stage deployment drift gate: Phase 8 evidence, synchronized
  contracts, 885 Optimizer tests, 1,038 Management tests, 1,875 passed plus one
  intentionally skipped Deployer test, 806 Flutter tests, MkDocs strict, static
  checks, and isolated cleanup.

The 2026-08-24 API-ownership revision additionally passed synchronized
contract/setup-gate tests, focused Deployer permission/Terraform and Management
guide tests, Flutter analysis plus model/demo/widget tests, and the
credential-free deployment-contract gate. It did not run a provider adapter.

No cloud credential, live provider operation, deployment, paid resource, or
LaTeX source was used or changed.

## Review Record

The first final review covered Flutter architecture, state transitions,
write-only credential ownership, strict response parsing, both entry points,
responsive behavior, and deterministic demo parity. Earlier findings about a
presentation-to-service dependency, ambiguous cross-entry resume, visible GCP
JSON, stale retry context, provider mismatch disposal, and demo lifecycle drift
were corrected before the zero-finding result.

The second final review covered cross-stack contract drift, owner/provider/Twin
scope admission, generated connection permissions, manual cleanup guidance,
secret persistence, full regression suites, and documentation. A 10 ms
unrelated Deployer concurrency-test race surfaced in the first full run; the
test retained its concurrency assertion with a bounded 200 ms budget, passed
ten repeated focused runs, and then the complete 14-stage gate passed with no
remaining finding.

## Commit Trail

- `2f6333e1` contracts and provider authority boundary
- `1a7c386b` bootstrap-origin timing correction
- `a07baa58` canonical cross-service pack digests
- `0b86afd3` safe session persistence
- `bf39aade` guided Management lifecycle
- `d1704166` generated v2 Deployer admission
- `7358fb8d` isolated local deterministic-adapter wiring
- `fa9a077f` shared Flutter flow and real integration gate
- `e15c36ae` manual cleanup guidance and Twin-provider admission review fix
- `8279f3b1` deterministic concurrency-gate stabilization

Later Phase 8.9 activation work published Five-layer v2 and Six-layer v1. This
bootstrap slice itself still makes no live-provider or architecture-capacity
claim.
