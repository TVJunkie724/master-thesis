---
title: "Wizard Roadmap"
description: "Roadmap for the Flutter Digital Twin wizard pillar."
tags: [flutter, wizard, roadmap]
lastUpdated: "2026-05-01"
version: "1.0"
---

<!-- SOURCES:
- FRONTEND_ARCHITECTURE.md Wizard Step 1-3 sections
- docs/plans/2026-04-26_runtime_credentials_deployment_state_hardening.md
- twin2multicloud_flutter/implementation_plans/2026-05-01_credential_ssot_and_runtime_config.md
EXTRACTED: 2026-05-01 | VERSION: 1.0
-->

# Wizard Roadmap

| Phase | Status | Document | Code Areas |
|-------|--------|----------|------------|
| Credential SSOT | In Progress | [PHASE_CREDENTIAL_SSOT.md](phases/PHASE_CREDENTIAL_SSOT.md) | `lib/screens/wizard/`, `lib/bloc/wizard/`, `lib/widgets/cloud_connections/`, `lib/services/`, `lib/models/` |

The Wizard pillar owns the interactive Digital Twin creation and edit workflow.
Flutter captures user intent and delegates persistence, validation, and
deployment orchestration to the Management API.
