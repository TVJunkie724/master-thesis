---
title: "Credential SSOT Phase"
description: "Phase notes for binding Wizard Step 1 to Management API Cloud Connections."
tags: [flutter, wizard, credentials, cloud-connections]
lastUpdated: "2026-05-01"
version: "1.0"
---

<!-- SOURCES:
- docs/plans/2026-04-26_runtime_credentials_deployment_state_hardening.md
- twin2multicloud_flutter/implementation_plans/2026-05-01_credential_ssot_and_runtime_config.md
- twin2multicloud_backend/src/api/routes/cloud_connections.py
EXTRACTED: 2026-05-01 | VERSION: 1.0
-->

# Credential SSOT Phase

| In scope | Out of scope |
|----------|--------------|
| Runtime config through Dart defines | Admin credential bootstrap automation |
| User-scoped Cloud Connection selection and creation | Cloud-side role generation |
| Binding twins to Cloud Connection IDs | Removing backend legacy credential fallback |
| Stored Cloud Connection validation through Management API | Real cloud deployment E2E tests |

Wizard Step 1 now treats Management API Cloud Connections as the primary
credential source. A twin stores selected Cloud Connection IDs in its config,
while reusable encrypted credential payloads stay user-scoped in the backend.

Related implementation reference:
[cloud_connection_widgets.md](../implementation/cloud_connection_widgets.md).
