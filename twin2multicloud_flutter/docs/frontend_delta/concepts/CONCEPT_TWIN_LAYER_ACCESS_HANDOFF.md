---
title: "Concept: Twin Layer Access Handoff"
description: "Post-deployment L4 and L5 access in the existing Twin Overview."
tags: [flutter, frontend-delta, twin-overview, layer-access]
lastUpdated: "2026-07-31"
version: "1.0"
---

# Concept: Twin Layer Access Handoff

## User Outcome

After a successful Five-layer v2 deployment, the researcher can open and
inspect both scientific presentation surfaces from Twin Overview:

- L4 semantic Twin state and relationships;
- L5 raw telemetry and hourly-rollup dashboards.

The page explains that the two surfaces are intentionally independent. It does
not suggest that Grafana visualizes L4 or that L4 stores raw history.

## Scope

| In scope | Out of scope |
|---|---|
| Two typed access cards on deployed Twins | New top-level route or access-administration screen |
| Provider/service/link/auth/readiness/content summary | Direct cloud, Optimizer, Deployer, or Terraform-state calls |
| External browser launch | Embedded provider consoles or webviews |
| Retry after read-model failure | Browser-session automation |
| One-time GCP Grafana Viewer rotation/reveal | Rendering any provider, reader, or Admin secret |
| Desktop and compact Web layout | Mobile targets, scenes, 3D, custom Twin Grafana panels |

## Information Hierarchy

The section appears after Deployment Readiness and before Deployment Actions.
This answers “where can I inspect the result?” before presenting another
infrastructure action. Two sibling cards remain equally prominent: L4 is not a
detail of L5 and L5 is not a detail of L4.

Each card shows, in order:

1. layer purpose;
2. provider and concrete service;
3. aggregate readiness;
4. primary Open action;
5. interactive identity/authentication explanation;
6. available content and explicit limitations;
7. remediation/retry or GCP-only Viewer rotation when applicable.

The generic Terraform Outputs card remains lower on the page as technical
evidence.

## States

| State | Presentation |
|---|---|
| Loading | One section card with progress and stable height |
| Ready | Two cards; Open actions enabled |
| Partially blocked | Both cards remain visible; affected Open action disabled with exact remediation, unaffected card usable |
| Read-model error | Inline error in the section with Retry; deployment operations remain usable |
| Unsupported historical profile | Honest explanatory empty state; no fabricated links |
| Destroyed/not deployed | Section absent and access state cleared |
| Credential rotation | GCP L5 card busy; one-time reveal dialog on success; inline safe error on failure |

## Boundaries And Dependencies

- `TwinOverviewBloc` owns access loading/retry/rotation state and invokes the
  Management API.
- Riverpod continues to inject the existing `ManagementApi` and external
  launcher into the screen composition boundary; no new state-management
  package is introduced.
- Presentation widgets receive typed state and callbacks only.
- [FR-001](../../feature-requests/FR_001_DEPLOYMENT_LAYER_ACCESS_READ_MODEL.md)
  is a hard dependency.
- Provider/Terraform feasibility is controlled by
  [`phase_08_layer_access_handoff.md`](../../../../docs/plans/phase_08_architecture_profiles_eventing/phase_08_layer_access_handoff.md).

## Acceptance

- A deployed Five-layer v2 Twin shows exactly one L4 and one L5 card.
- All nine placements use the same UI contract; only provider/service/auth data
  changes.
- External links are absolute HTTPS and opened only through the injected
  launcher.
- The UI never infers access from generic Terraform output keys.
- No secret is persisted in BLoC state after the one-time dialog closes.
- Keyboard, screen-reader, compact Web, loading, error, partial, and empty
  behavior are specified before implementation.

## Roadmap Anchor

[Frontend Delta Roadmap](../ROADMAP_FRONTEND_DELTA.md), subphase 8.6.

