---
title: "Phase 3.5: Deployer Permissions Preflight Audit"
description: "Audit Deployer permission checkers, preflight behavior, bootstrap assumptions, and least-privilege gaps."
tags: [deployer, permissions, preflight, security]
lastUpdated: "2026-06-19"
version: "1.0"
---

<!-- SOURCES:
- docs/plans/service_architecture_audit/phases/PHASE_03_DEPLOYER_AUDIT.md
- 3-cloud-deployer/src/api/credentials_checker.py
- 3-cloud-deployer/src/api/azure_credentials_checker.py
- 3-cloud-deployer/src/api/gcp_credentials_checker.py
- 3-cloud-deployer/src/api/verify.py
EXTRACTED: 2026-06-19 | VERSION: 1.0
-->

# Phase 3.5: Deployer Permissions Preflight Audit

## Purpose

Separate deployer permission readiness from actual deployment and prepare
least-privilege hardening without requiring final live-cloud proof yet.

## Scope

| In scope | Out of scope |
|---|---|
| Permission checker architecture | Final least-privilege confirmation |
| Fake/no-live credential test plan | Persisting admin credentials |
| Bootstrap/preflight assumptions | Running real deployments |

## Deliverables

- AWS/Azure/GCP permission checker matrix.
- Preflight result contract with missing permission, unknown permission, and
  unsupported capability states.
- Credential-purpose mapping for deployment and pricing access.
- Least-privilege gap register for future live verification.

## Acceptance Criteria

- Preflight can fail safely before deployment starts.
- Permission messages are actionable and sanitized.
- Admin bootstrap credentials remain out of persistent storage unless separately
  approved by credential architecture.

## Verification

- Static permission-checker review.
- Fake/no-live credential test plan.
- No live cloud deployment.

## Parent Phase

[Phase 3: Deployer Audit](../PHASE_03_DEPLOYER_AUDIT.md)
