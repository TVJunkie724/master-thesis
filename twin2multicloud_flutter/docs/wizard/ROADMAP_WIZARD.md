---
title: "Wizard Roadmap"
description: "Roadmap for the Flutter Digital Twin wizard pillar."
tags: [flutter, wizard, roadmap]
lastUpdated: "2026-08-23"
version: "1.1"
---

<!-- SOURCES:
- FRONTEND_ARCHITECTURE.md Wizard Step 1-3 sections
- docs/plans/2026-04-26_runtime_credentials_deployment_state_hardening.md
- twin2multicloud_flutter/implementation_plans/2026-05-01_credential_ssot_and_runtime_config.md
- twin2multicloud_flutter/docs/configuration_workspace/ROADMAP_CONFIGURATION_WORKSPACE.md
- docs/plans/phase_08_architecture_profiles_eventing/phase_08_guided_cloud_bootstrap.md
EXTRACTED: 2026-08-23 | VERSION: 1.1
-->

# Wizard Roadmap

| Phase | Status | Document | Code Areas |
|-------|--------|----------|------------|
| Credential SSOT | Done; journey superseded | [PHASE_CREDENTIAL_SSOT.md](phases/PHASE_CREDENTIAL_SSOT.md) | CloudConnection creation, selection, validation, binding, deletion, and guided bootstrap are implemented; the user journey now lives in the Configuration Workspace. |

The Wizard pillar owns the interactive Digital Twin creation and edit workflow.
Flutter captures user intent and delegates persistence, validation, and
deployment orchestration to the Management API.

The historical three-step Wizard remains the internal BLoC and compatibility
name. The active user-facing flow is the
[Configuration Workspace](../configuration_workspace/ROADMAP_CONFIGURATION_WORKSPACE.md),
which requests deployment access only after the selected architecture resolves
the required provider scopes.
