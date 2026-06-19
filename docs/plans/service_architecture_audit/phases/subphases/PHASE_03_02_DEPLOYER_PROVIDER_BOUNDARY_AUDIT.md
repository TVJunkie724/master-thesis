---
title: "Phase 3.2: Deployer Provider Boundary Audit"
description: "Audit AWS, Azure, and GCP provider responsibilities, naming, cleanup, layers, and shared helper duplication."
tags: [deployer, providers, aws, azure, gcp]
lastUpdated: "2026-06-19"
version: "1.0"
---

<!-- SOURCES:
- docs/plans/service_architecture_audit/phases/PHASE_03_DEPLOYER_AUDIT.md
- 3-cloud-deployer/src/providers/
- 3-cloud-deployer/src/core/
EXTRACTED: 2026-06-19 | VERSION: 1.0
-->

# Phase 3.2: Deployer Provider Boundary Audit

## Purpose

Make provider-specific deployer behavior consistent without flattening real AWS,
Azure, and GCP differences.

## Scope

| In scope | Out of scope |
|---|---|
| Provider/layer responsibility review | Provider feature parity by force |
| Naming and cleanup boundary review | Live cloud cleanup |
| Shared helper duplication | Replacing Terraform |

## Deliverables

- Provider responsibility matrix for deploy, destroy, validate, package,
  cleanup, outputs, naming, and preflight.
- Shared-helper duplication list.
- Provider-specific exception list for real cloud differences.
- Extraction plan for files over the agreed size/risk threshold.

## Acceptance Criteria

- Provider contracts are consistent where behavior is conceptually shared.
- Provider differences are explicit, tested, and documented.
- Cleanup behavior is separated from deployment planning.

## Verification

- Static provider import/dependency review.
- Unit test inventory for provider boundaries.
- No live cloud calls.

## Parent Phase

[Phase 3: Deployer Audit](../PHASE_03_DEPLOYER_AUDIT.md)
