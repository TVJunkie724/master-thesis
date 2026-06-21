---
title: "Phase 3.5: Deployer Permissions Preflight Audit"
description: "Audit Deployer permission checkers, preflight behavior, bootstrap assumptions, and least-privilege gaps."
tags: [deployer, permissions, preflight, security]
lastUpdated: "2026-06-21"
version: "1.1"
---

<!-- SOURCES:
- docs/plans/service_architecture_audit/phases/PHASE_03_DEPLOYER_AUDIT.md
- 3-cloud-deployer/src/api/credentials_checker.py
- 3-cloud-deployer/src/api/azure_credentials_checker.py
- 3-cloud-deployer/src/api/gcp_credentials_checker.py
- 3-cloud-deployer/src/api/verify.py
EXTRACTED: 2026-06-21 | VERSION: 1.1
-->

# Phase 3.5: Deployer Permissions Preflight Audit

## Purpose

Separate deployer permission readiness from actual deployment and prepare
least-privilege hardening without requiring final live-cloud proof yet.

Status: Complete.

## Scope

| In scope | Out of scope |
|---|---|
| Permission checker architecture | Final least-privilege confirmation |
| Fake/no-live credential test plan | Persisting admin credentials |
| Bootstrap/preflight assumptions | Running real deployments |

## Deliverables

- [x] AWS/Azure/GCP permission checker matrix.
- [x] Preflight result contract with missing permission, unknown permission, and
  unsupported capability states.
- [x] Credential-purpose mapping for deployment and pricing access.
- [x] Least-privilege gap register for future live verification.
- [x] Fail-closed deployment preflight for every configured provider.

## Acceptance Criteria

- [x] Preflight can fail safely before deployment starts.
- [x] Permission messages are actionable and sanitized.
- [x] Admin bootstrap credentials remain out of persistent storage unless separately
  approved by credential architecture.

## Verification

- [x] Static permission-checker review.
- [x] Fake/no-live credential test plan.
- [x] No live cloud deployment.
- [x] Docker targeted tests:
  `python -m pytest tests/unit/terraform/test_preflight_validation.py tests/unit/core_tests/test_deployment_contracts.py -q`

## Review Artifact

[Phase 3.5 Review: Deployer Permissions Preflight](../../PHASE_03_05_DEPLOYER_PERMISSIONS_PREFLIGHT_REVIEW.md)

## Parent Phase

[Phase 3: Deployer Audit](../PHASE_03_DEPLOYER_AUDIT.md)
