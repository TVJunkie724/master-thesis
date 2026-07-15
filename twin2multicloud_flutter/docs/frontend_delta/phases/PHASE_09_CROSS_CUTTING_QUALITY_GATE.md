---
title: "Phase 9: Cross-Cutting Quality Gate"
description: "Final frontend-wide architecture, contract, test, build, and thesis evidence gate."
tags: [flutter, frontend-delta, quality, tests, thesis]
lastUpdated: "2026-07-15"
version: "2.0"
---

# Phase 9: Cross-Cutting Quality Gate

**Status:** Done on 2026-07-15 through
[`#108`](https://github.com/TVJunkie724/master-thesis/issues/108).

## Outcome

Phase 9 adds one reproducible release gate for the accumulated Flutter work. It
does not add or redesign a product screen. It verifies the production and demo
composition, the Management API boundary, representative UI states, safe
diagnostics, tracked runtime configuration, and supported Web/macOS builds.

The binding implementation contract is
[`2026-07-15_frontend_delta_phase_09_quality_gate.md`](../../../implementation_plans/2026-07-15_frontend_delta_phase_09_quality_gate.md).

## Verification Evidence

All commands ran from the repository root on 2026-07-15.

| Gate | Command | Result |
|---|---|---|
| Checker self-tests | `python3 -m unittest scripts.tests.test_check_flutter_architecture` | 11 passed |
| Architecture/security scan | `python3 scripts/check_flutter_architecture.py` | Passed, no findings |
| Shell syntax | `bash -n thesis.sh` | Passed |
| Formatting | `dart format --output=none --set-exit-if-changed lib test integration_test` | 276 files, no changes |
| Static analysis | `flutter analyze` | No issues |
| Unit/widget/demo suite | `flutter test` through `./thesis.sh test frontend` | 549 passed |
| Web artifact | `flutter build web --release --dart-define-from-file=config/dev.example.json` | Passed |
| macOS artifact | `flutter build macos --debug --dart-define-from-file=config/dev.example.json` | Passed |
| Local contract integration | `THESIS_DOCKER_CONTEXT=orbstack ./thesis.sh test frontend-integration` | 8 passed |
| Diff hygiene | `git diff --check` | Passed |

The full static, test, and build sequence is available as:

```bash
./thesis.sh test frontend
```

## Local Integration Matrix

The integration command starts or reuses the credential-free local stack and
performs read-only requests through the real Flutter `ApiService`.

| Contract | Evidence |
|---|---|
| Runtime URL | HTTP(S) Management API origin comes from Dart defines; no fixed port assertion |
| `GET /dashboard/stats` | Typed, non-negative lifecycle and cost invariants |
| `GET /cloud-access` | Exact `cloud-access-inventory.v1` and exact AWS/Azure/GCP provider set |
| `GET /cloud-connections/` | Typed provider/purpose/display metadata and raw-response secret-key scan |
| `GET /optimizer/pricing-health` | Exact `pricing-health.v1` and complete provider readiness metadata |
| Protected endpoint without auth | Rejected with 401/403 |
| Authenticated unknown route | Rejected with 404 |
| Diagnostics | Response bodies and headers are suppressed from failures |

Raw JSON from Cloud Connections, Cloud Access, and Pricing Health is scanned
recursively before model decoding. This prevents unknown credential fields from
being hidden by a permissive DTO parser.

## Architecture Rules

The dependency-free checker fails closed with sanitized path/line diagnostics:

| Rule | Enforced boundary |
|---|---|
| `FLUTTER-DIRECT-SERVICE` | Flutter cannot contact Optimizer or Deployer directly |
| `FLUTTER-PRESENTATION-HTTP` | Presentation code cannot import/use HTTP infrastructure |
| `FLUTTER-DIAGNOSTIC` | No production debug output or unresolved TODO/FIXME/HACK markers |
| `FLUTTER-SECRET-LITERAL` | No concrete secret payloads or credential-file values in UI/demo source |
| `FLUTTER-RUNTIME-CONFIG` | Runtime URLs/tokens stay in the approved configuration boundary |
| `FLUTTER-SOURCE-READ` | Unreadable/non-UTF-8 scanned sources fail safely |

Secret findings never print the matched source value.

## UI And Accessibility Evidence

The complete suite covers production and offline demo composition, every app
route, `showcase`/`empty`/`degraded` scenarios, compact layouts down to the
supported 640 px boundary, and wide desktop layouts. Focused tests additionally
cover keyboard focus, Escape cancellation, semantic labels, destructive and
sensitive-download confirmations, disabled reasons, pricing evidence collapsed
by default, output redaction, and configuration Save/Discard/Cancel behavior.

This is automated accessibility evidence, not a claim of full WCAG
certification. Manual screen-reader and platform-specific assistive-technology
validation remains outside this phase.

## Findings And Remediations

1. The previous integration test asserted a literal localhost port and covered
   only one Cloud Connection list call. It was replaced by the versioned,
   runtime-configured contract matrix above.
2. The first new draft scanned only deserialized Cloud Connection models.
   Review found that unknown secret fields could be discarded by parsing. Raw
   response trees are now scanned before typed assertions.
3. The architecture audit previously depended on ad-hoc `rg` commands. It is
   now an exact, unit-tested, redaction-safe checker exposed through the root
   entrypoint.

No unresolved Critical, Major, or Minor finding remains in this phase.

## Residual Warnings And Deferred Work

- Flutter reports newer dependency versions outside current constraints. No
  dependency upgrade was part of this quality gate.
- `file_saver` does not yet support Swift Package Manager for macOS; Flutter
  warns that this may become an error in a future SDK.
- The macOS integration runner printed `Failed to foreground app; open returned
  1` in the non-interactive terminal, then executed all tests successfully.
- Live provider validation, price refresh, deployment, destroy, simulator cloud
  execution, and billing verification were deliberately not run. They may
  create resources or incur costs.
- General dev-auth hardening remains tracked by
  [`#71`](https://github.com/TVJunkie724/master-thesis/issues/71).
- Remaining non-critical dynamic-map reduction remains tracked by
  [`#72`](https://github.com/TVJunkie724/master-thesis/issues/72).
- Final deployment lifecycle integration remains tracked by
  [`#39`](https://github.com/TVJunkie724/master-thesis/issues/39).

## Safe Commands

```bash
# Offline, no Docker and no cloud access
./thesis.sh test frontend

# Local Docker contracts only; no credential overlay and no cloud mutations
THESIS_DOCKER_CONTEXT=orbstack ./thesis.sh test frontend-integration
```

The integration target never enables test endpoints, never uses the credential
overlay, and does not call refresh, validation, bootstrap, deployment, destroy,
simulator, or other mutation routes.

## Roadmap Anchor

Roadmap: [Frontend Delta Roadmap](../ROADMAP_FRONTEND_DELTA.md)
