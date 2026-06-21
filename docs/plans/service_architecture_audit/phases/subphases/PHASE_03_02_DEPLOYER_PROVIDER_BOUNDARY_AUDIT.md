---
title: "Phase 3.2: Deployer Provider Boundary Audit"
description: "Audit AWS, Azure, and GCP provider responsibilities, naming, cleanup, layers, and shared helper duplication."
tags: [deployer, providers, aws, azure, gcp]
lastUpdated: "2026-06-21"
version: "1.1"
---

<!-- SOURCES:
- docs/plans/service_architecture_audit/phases/PHASE_03_DEPLOYER_AUDIT.md
- 3-cloud-deployer/src/providers/
- 3-cloud-deployer/src/core/
EXTRACTED: 2026-06-21 | VERSION: 1.1
-->

# Phase 3.2: Deployer Provider Boundary Audit

## Purpose

Make provider-specific deployer behavior consistent without flattening real AWS,
Azure, and GCP differences.

Status: Complete.

## Scope

| In scope | Out of scope |
|---|---|
| Provider/layer responsibility review | Provider feature parity by force |
| Naming and cleanup boundary review | Live cloud cleanup |
| Shared helper duplication | Replacing Terraform |

## Deliverables

- [x] Provider responsibility matrix for deploy, destroy, validate, package,
  cleanup, outputs, naming, and preflight.
- [x] Shared-helper duplication list.
- [x] Provider-specific exception list for real cloud differences.
- [x] Extraction plan for files over the agreed size/risk threshold.
- [x] Central cleanup registry implemented for SDK fallback cleanup dispatch.

## Acceptance Criteria

- [x] Provider contracts are consistent where behavior is conceptually shared.
- [x] Provider differences are explicit, tested, and documented.
- [x] Cleanup behavior is separated from deployment planning.

## Verification

- [x] Static provider import/dependency review.
- [x] Unit test inventory for provider boundaries.
- [x] No live cloud calls.
- [x] Docker targeted tests:
  `python -m pytest tests/unit/providers/test_cleanup_registry.py tests/unit/core_tests/test_architecture_boundaries.py tests/unit/core_tests/test_deployment_contracts.py tests/api/test_deployment_routes.py -q`

## Review Artifact

[Phase 3.2 Review: Deployer Provider Boundary](../../PHASE_03_02_DEPLOYER_PROVIDER_BOUNDARY_REVIEW.md)

## Parent Phase

[Phase 3: Deployer Audit](../PHASE_03_DEPLOYER_AUDIT.md)
