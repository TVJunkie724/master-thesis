---
title: "Phase 9: Thesis Research Workflow Consolidation"
description: "Consolidate Flutter around the standalone Six-layer research workflow and its persisted evidence."
tags: [flutter, configuration-workspace, thesis, six-layer, evidence]
lastUpdated: "2026-08-27"
version: "1.0"
---

<!-- SOURCES:
- twin2multicloud_flutter/docs/configuration_workspace/concepts/CONCEPT_THESIS_RESEARCH_WORKFLOW.md
- docs/plans/2026-08-26_thesis_poc_execution_plan.md section 10
- twin2multicloud_flutter/docs/configuration_workspace/ROADMAP_CONFIGURATION_WORKSPACE.md
EXTRACTED: 2026-08-27 | VERSION: 1.0
-->

# Phase 9: Thesis Research Workflow Consolidation

**Status:** Approved for implementation through the user-authorized Thesis PoC
execution sequence.

## Outcome

Replace the accumulated product-oriented Flutter surfaces with one bounded
research workflow while preserving the reliability, portability, credential,
verification, and cleanup behavior required by the active Thesis PoC concept.

| In scope | Out of scope |
|---|---|
| Dashboard reduced to Twin experiments and portable actions | Aggregate fleet statistics or pricing health |
| Four responsibility groups in the Configuration Workspace | Profile and objective selection |
| Deployment-only CloudConnection inventory and file import | Pricing access management |
| Typed telemetry and cleanup evidence | New live-cloud behavior |
| Regression and supported-platform gates | Visual redesign outside touched surfaces |

## Required Deliverables

- A reviewed twelve-section implementation plan.
- Removal of the Pricing Review route and product Dashboard dependencies.
- A canonical-architecture Workspace journey without selectable profiles or
  pricing-maintenance tasks.
- Dashboard Duplicate, Export, and Import actions backed by the bounded Twin
  archive contract.
- Settings deployment-connection lists with typed entry, allowlisted file
  import, validation, and deletion.
- Twin Overview telemetry-history and cleanup-evidence presentation.
- Unit, BLoC, widget, demo, analyzer, architecture, and Web build evidence.

## Exit Criteria

- the concept acceptance criteria pass with hard assertions;
- no removed route or control remains reachable in production or demo mode;
- all retained backend interactions use typed Management API contracts;
- SSE reconnect/replay behavior remains unchanged and green;
- no live provider mutation is run; and
- the frontend is ready for the repository-wide offline and documentation gate.

## Roadmap Anchor

[Configuration Workspace Roadmap](../ROADMAP_CONFIGURATION_WORKSPACE.md)
