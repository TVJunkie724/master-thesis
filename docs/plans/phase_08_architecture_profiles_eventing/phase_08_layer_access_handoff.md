---
title: "Phase 8 Six-Layer Access Handoff"
description: "PoC boundary for post-deployment L4 and L5 browser access."
tags: [architecture, flutter, deployment, digital-twin, grafana, phase-8]
lastUpdated: "2026-08-26"
version: "2.0"
---

# Phase 8 Six-Layer Access Handoff

This boundary applies only to `six-layer-eventing@1`.

After a successful deployment, Twin Overview may expose one L4 semantic Twin
surface and one L5 raw/rollup visualization surface. Each surface reports its
provider, service, safe URL, authentication method, readiness, and limitation.
Flutter consumes this data only through Management and never reads Terraform
state or contacts a provider directly.

The deployment credential is the preconfigured PoC administrator credential
defined in `docs/plans/2026-08-26_poc_credentials.md`. Interactive browser
access remains a separate runtime concern: the deployment may bind an existing
operator principal or create a bounded resource-local viewer credential where
the selected service requires one. Such a viewer credential is not a generated
deployment identity and does not grant infrastructure administration.

The offline implementation covers all three single-cloud and all six
`L3-hot == L5 != L4` placements. It validates secret-free persistence,
redaction, destroyed-state behavior, and one-time reveal handling. It does not
prove provider-console sign-in, live content, capacity, or a successful
Terraform apply; those remain supervised live checks.

Out of scope are an enterprise access portal, custom RBAC administration,
automated browser login, custom domains, high availability, L4-to-L5 Twin
context, scenes, and 3D visualization.
