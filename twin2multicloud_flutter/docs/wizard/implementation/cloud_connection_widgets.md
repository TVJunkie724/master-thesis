---
title: "Cloud Connection Widgets"
description: "Reference for the Flutter widgets used by Wizard Step 1 Cloud Connection binding."
tags: [flutter, widgets, wizard, cloud-connections]
lastUpdated: "2026-05-01"
version: "1.0"
---

<!-- SOURCES:
- twin2multicloud_flutter/implementation_plans/2026-05-01_credential_ssot_and_runtime_config.md
- twin2multicloud_flutter/lib/widgets/cloud_connections/
EXTRACTED: 2026-05-01 | VERSION: 1.0
-->

# Cloud Connection Widgets

| Widget | Responsibility |
|--------|----------------|
| `CloudConnectionsGroup` | Renders the provider sections and forwards user intent to `WizardBloc`. |
| `CloudConnectionSection` | Shows one provider selector, summary, validation state, and actions. |
| `CloudConnectionCreateDialog` | Captures temporary secret input and returns a create request. |
| `ProviderPayloadForm` | Builds provider-specific credential payloads without calling HTTP. |
| `CloudConnectionValidationStatus` | Displays validation state as text plus icon. |
| `LegacyCredentialFallbackBanner` | Shows migration-only legacy credential presence. |

Widgets are presentation-only. They do not call `ApiService`; all persistence and
validation side effects are owned by `WizardBloc`.
