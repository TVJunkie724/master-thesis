---
title: "Phase 4.1: Cross-Service Contract Gate"
description: "Generate and review API contracts and Management API downstream client boundaries as reproducible service quality evidence."
tags: [quality, contracts, openapi, management-api, optimizer, deployer]
lastUpdated: "2026-06-26"
version: "1.1"
---

<!-- SOURCES:
- docs/plans/service_architecture_audit/phases/PHASE_04_SERVICE_QUALITY_GATE.md
- twin2multicloud_backend/src/main.py
- 2-twin2clouds/rest_api.py
- 3-cloud-deployer/rest_api.py
- scripts/service_quality_gate/export_openapi.py
EXTRACTED: 2026-06-21 | VERSION: 1.0
-->

# Phase 4.1: Cross-Service Contract Gate

## Purpose

Create a reproducible contract baseline for the three Python services before
the service layer is declared thesis-ready.

## Scope

| In scope | Out of scope |
|---|---|
| Dockerized OpenAPI snapshot generation | Changing endpoint behavior |
| Entrypoint verification for all services | Flutter UI integration |
| Contract evidence for later diff review | Live cloud E2E |
| Raw/dynamic response risk register | Provider permission hardening |
| Typed Management API downstream client-surface gate | Replacing provider APIs or IaC tooling |

## Deliverables

- Versioned OpenAPI snapshots for Management API, Optimizer, and Deployer.
- A deterministic export tool with explicit service entrypoints.
- A review artifact documenting endpoint counts, raw/dynamic risk areas, and
  follow-up gates.
- A Management API test gate that keeps Optimizer/Deployer HTTP access inside
  typed clients and makes the public downstream client method surface explicit.

## Acceptance Criteria

- Snapshots are generated from the same Docker images used by development.
- Management API test-only endpoints are excluded by default.
- No snapshot contains credential material or live deployment artifacts.
- Contract drift can be detected through ordinary Git diffs.
- Direct downstream HTTP calls from Management API routes/services fail tests.
- New OptimizerClient/DeployerClient public methods require an explicit
  contract-test update.

## Verification

- Run the three Dockerized `export_openapi.py` commands documented in
  `docs/contracts/openapi/README.md`.
- Validate each output as JSON.
- Inspect snapshot summaries for expected title/version/path counts.
- Run `pytest twin2multicloud_backend/tests/test_management_contracts.py`.
- Run focused client and credential/config validation tests when the downstream
  client boundary changes.

## Review Artifact

[Phase 4.1 Review: Cross-Service Contract Gate](../../PHASE_04_01_CONTRACT_GATE_REVIEW.md)

## Parent Phase

[Phase 4: Service Quality Gate](../PHASE_04_SERVICE_QUALITY_GATE.md)
