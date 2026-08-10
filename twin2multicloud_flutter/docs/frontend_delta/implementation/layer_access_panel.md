---
title: "Layer Access Panel"
description: "Implemented Twin Overview L4/L5 access widgets, state, API, and secret boundary."
tags: [flutter, twin-overview, layer-access, deployment]
lastUpdated: "2026-08-11"
version: "1.0"
---

# Layer Access Panel

## Public Widgets

- `LayerAccessPanel` renders the section phase and orders exactly one L4 card
  before one L5 card.
- `LayerAccessCard` renders provider, service, readiness, authentication,
  capabilities, limitations, Open, and the optional GCP L5 rotation action.

Both widgets are presentation-only. `TwinOverviewBloc` owns API calls,
generation/race handling, refresh, destroy clearing, and the transient
credential lifecycle. External navigation uses the screen's injected launcher.

## State Phases

| Phase | Presentation |
|---|---|
| `idle` | Access becomes available only after deployment |
| `loading` | Inline progress without blocking other Twin actions |
| `ready` | Ordered L4/L5 cards with independent readiness |
| `unsupported` | Historical Five-layer v1 explanation and zero links |
| `failed` | Safe isolated error and explicit retry |

Open requires only `resource=ready` and `access_binding=ready`. Content and
data-probe failure remain visible but do not prevent inspection of an otherwise
accessible provider surface. Browser sign-in is `unverified` until a supervised
live check.

## Management API

```text
GET  /twins/{id}/deployment-access
POST /twins/{id}/deployment-access/l5/credentials:rotate
```

Flutter calls no Deployer, Optimizer, Terraform, Kubernetes, or provider API.
The mutating rotation is never automatically retried.

## Provider And Authentication Matrix

| Layer | AWS | Azure | GCP |
|---|---|---|---|
| L4 | IoT TwinMaker / Identity Center | Azure Digital Twins / Entra ID | Twin Explorer / IAP |
| L5 | Managed Grafana / Identity Center | Managed Grafana / Entra ID | Grafana OSS on GKE / generated Viewer |

The available Five-layer v2 response always contains exactly one surface for
each layer. All nine provider pairs use the same DTO and widget tree.

## Secret Boundary

`deployment-access.v1` contains no password, token, provider credential,
reader key, certificate material, Terraform state, or internal evidence
reference. Generic deployment outputs remain a separate redacted card.

Only GCP L5 can return `deployment-access-credential.v1`. The password is
captured by the screen listener, consumed from BLoC state immediately, shown
obscured in a one-time dialog, and discarded on close. It is excluded from
Equatable properties and string representation and is never copied
automatically. Management persists only rotation time and fingerprint.

## Responsive And Verification Boundary

Cards are side by side from 900 px and stacked below 900 px. Tests cover 640 px
at 200% text scale, keyboard/focus order, semantics, light/dark themes, blocked
partial readiness, external launch failure, and one-time reveal behavior.

`integration_test/twin_layer_access_flow_test.dart` calls an isolated real
local Management API for ten cases, including all nine placements and
concurrent rotation. The test adapter is available only with
`ENABLE_TEST_ENDPOINTS=true`, uses a temporary SQLite database, accepts no
cloud credentials, and performs no cloud deployment. Provider browser sign-in
and live capacity are not proven by this gate.
