---
title: "Phase 4.2: Cross-Service Test Gate"
description: "Run and record safe Management API, Optimizer, and Deployer test suites without live cloud E2E."
tags: [quality, tests, management-api, optimizer, deployer]
lastUpdated: "2026-06-21"
version: "1.0"
---

# Phase 4.2: Cross-Service Test Gate

## Purpose

Prove that the completed service refactors pass their safe unit, API, and
integration suites together.

## Deliverables

- Dockerized safe test command matrix for all three services.
- Verification evidence for Management API, Optimizer, and Deployer.
- Explicit quarantine list for live cloud E2E tests.
- Follow-up findings for flaky, missing, or too-broad tests.

## Acceptance Criteria

- Default commands do not deploy cloud resources or require admin credentials.
- Every command is reproducible from a clean Docker runtime.
- Failures are fixed or recorded as explicit residual risks with issue links.

## Parent Phase

[Phase 4: Service Quality Gate](../PHASE_04_SERVICE_QUALITY_GATE.md)
