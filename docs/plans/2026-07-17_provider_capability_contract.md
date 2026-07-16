---
title: "Provider Capability Contract"
description: "Implementation contract for fail-closed provider-layer capability discovery, aggregation, enforcement, and presentation."
tags: [architecture, capabilities, optimizer, deployer, management-api, flutter]
lastUpdated: "2026-07-17"
version: "1.0"
---

<!-- SOURCES:
- GitHub issue #70 "Model provider capabilities and intentionally unsupported layers"
- 2-twin2clouds/backend/calculation_v2/layers/contracts.py
- 3-cloud-deployer/src/providers/ and src/providers/terraform/
- twin2multicloud_backend/src/clients/ and src/services/provider_contract.py
- twin2multicloud_flutter/lib/bloc/wizard/ and lib/widgets/step3/info_cards.dart
- docs-site/docs/architecture/refactoring-roadmap.md
- User decision on 2026-07-17 to defer final live E2E until after UI and Twin architecture audits
EXTRACTED: 2026-07-17 | VERSION: 1.0
-->

# Provider Capability Contract

**Issue:** [#70 Model provider capabilities and intentionally unsupported layers](https://github.com/TVJunkie724/master-thesis/issues/70)  
**Base branch:** `master`  
**Feature branch:** `codex/provider-capability-contract`  
**Status:** Approved for implementation  
**Live-cloud E2E:** Explicitly deferred

## Objective

Expose one fail-closed platform view of which provider-layer combinations the
Optimizer can calculate and the Deployer can provision. Unsupported paths must
remain visible and actionable without being selectable or silently treated as
zero-cost alternatives.

The contract describes implementation capability. It does not claim that a path
has completed final supervised cloud verification.

## Scope

| In scope | Out of scope |
|---|---|
| Optimizer calculation capability registry and read endpoint | Implementing missing provider services |
| Deployer provisioning capability registry, endpoint, and validation | Changing optimization formulas or pricing inputs |
| Management API contract aggregation and typed errors | Final supervised live-cloud E2E |
| Flutter typed consumption and existing wizard availability messages | A visual redesign of the configuration workspace |
| Demo parity, tests, docs, and roadmap traceability | Mobile targets or direct Flutter-to-service calls |

## Ownership Model

A single static matrix would hide an important boundary: calculation and
deployment are different capabilities owned by different services. The final
state therefore uses federated ownership with one aggregated platform view:

```text
Optimizer code and tests                 Deployer code and tests
        |                                       |
        v                                       v
calculation capability endpoint       deployment capability endpoint
        |                                       |
        +------------------+--------------------+
                           v
                  Management API aggregator
                  - validates both contracts
                  - rejects version/identity drift
                  - derives platform availability
                           |
                           v
                    Flutter read model
```

- The Optimizer is the source of truth for calculation support.
- The Deployer is the source of truth for deployment support.
- The Management API response is the source of truth for platform consumers.
- Flutter contains no provider-name capability exceptions.
- The shared wire format and derivation rules are versioned and contract-tested.

This avoids copied capability data while ensuring that disagreement cannot remain
silent.

## Canonical Identity

Provider IDs are lowercase: `aws`, `azure`, `gcp`.

Layer IDs are:

| ID | Meaning |
|---|---|
| `l1` | acquisition |
| `l2` | processing and orchestration |
| `l3_hot` | hot operational storage |
| `l3_cool` | cool/cold storage |
| `l3_archive` | archive storage |
| `l4` | Digital Twin management and visualization model |
| `l5` | operational visualization |

`google` and `layer_3_cold` are adapter aliases only. They may be accepted at an
existing legacy boundary but never appear in the capability API.

## Service Capability Contract

Both internal services expose `GET /capabilities/providers` with schema
`provider-service-capabilities.v1`:

```json
{
  "schema_version": "provider-service-capabilities.v1",
  "service": "optimizer",
  "generated_from": "runtime_registry",
  "providers": [
    {
      "provider": "gcp",
      "layers": [
        {
          "layer": "l4",
          "availability": "unsupported",
          "roadmap": "planned",
          "reason_code": "DEPLOYMENT_PATH_NOT_IMPLEMENTED",
          "reason": "GCP L4 is outside the implemented thesis deployment path.",
          "verification_level": "not_verified"
        }
      ]
    }
  ]
}
```

### Availability

| Value | Meaning | Selectable |
|---|---|---|
| `available` | An executable implementation exists in this service. | yes, subject to the other service |
| `disabled` | An implementation exists but runtime policy or configuration disables it. | no |
| `unsupported` | No executable implementation exists in the current product scope. | no |

Roadmap intent is deliberately separate:

| Value | Meaning |
|---|---|
| `none` | No committed future implementation is represented. |
| `planned` | Future work exists; this does not make the capability selectable. |

### Verification Level

| Value | Meaning |
|---|---|
| `contract_tested` | Deterministic unit/integration and package-contract evidence exists. |
| `live_verified` | A supervised provider run has supplied current evidence. |
| `not_verified` | Neither gate has been satisfied. |

An `available` capability may be only `contract_tested`. UI and documentation must
not translate that into a live-cloud production guarantee.

### Invariants

- Every provider contains every canonical layer exactly once.
- Unknown providers, layers, enum values, duplicate entries, and empty reasons are
  contract violations.
- `available` requires no reason and may not be marked `planned`.
- `disabled` and `unsupported` require stable `reason_code` and user-safe `reason`.
- `unsupported` may be `planned`; `disabled` may not use roadmap state to bypass
  runtime policy.
- The endpoint is side-effect free and contains no credentials or environment
  values.

## Initial Matrix

The initial matrix reflects implemented paths, not ideal provider equivalence:

| Provider | Optimizer | Deployer | Platform |
|---|---|---|---|
| AWS | L1-L5 and all L3 tiers | L1-L5 and all L3 tiers | available |
| Azure | L1-L5 and all L3 tiers | L1-L5 and all L3 tiers | available |
| GCP | L1-L3 and all L3 tiers | L1-L3 and all L3 tiers | available |
| GCP | L4-L5 unsupported, planned | L4-L5 unsupported, planned | unsupported, planned |

All initially available rows use `contract_tested`. Final `live_verified` evidence
is deferred until the later E2E phase.

## Management API Contract

The authenticated `GET /platform/provider-capabilities` endpoint returns
`platform-provider-capabilities.v1`.

For each provider-layer row it includes:

- `availability`, `roadmap`, `reason_code`, `reason`;
- `selectable` as a derived boolean;
- aggregate `verification_level` using the weaker source level;
- `sources.optimizer` and `sources.deployer` for diagnostics;
- `sources_agree` and `restriction_source` so both agreement and the effective
  restriction boundary are explicit;
- source health metadata at response level.

Derivation rules are deterministic:

1. The row is `available` only when both services report `available`.
2. `disabled` wins over `available` and `unsupported` because it represents an
   intentional runtime policy boundary.
3. Otherwise any `unsupported` source makes the platform row `unsupported`.
4. `roadmap=planned` when any non-available source is planned.
5. `selectable` is true only for aggregate `available`.
6. Verification is the weaker of `not_verified`, `contract_tested`, and
   `live_verified`.

Malformed, incomplete, or identity-mismatched upstream contracts produce a typed
`PROVIDER_CAPABILITY_CONTRACT_INVALID` 502 response. An unavailable source produces
the existing sanitized 503 external-service response. The aggregator never guesses,
uses stale implicit defaults, or returns a partially selectable matrix.

The Management API service owns parsing and aggregation. Routes remain thin HTTP
adapters and clients own transport only.

## Enforcement

Read models alone are insufficient. Each execution boundary validates its own
selection:

- Optimizer selection reads calculator capabilities and excludes unsupported rows.
- Deployer package/config validation rejects unsupported provider-layer choices
  before Terraform initialization with error code `CAPABILITY_UNAVAILABLE`.
- Management orchestration preserves the typed error and does not convert it into a
  generic deployment failure.

The Deployer validation reports every unsupported row in one response, including
canonical provider, layer, availability, reason code, and remediation. It must not
create a workspace or invoke provider SDK/Terraform for such a request.

## Flutter Contract And UX

Flutter adds immutable typed models for the platform response and retrieves them
through `ManagementApi`. `ApiService` and `DemoManagementApi` implement the same
contract.

The configuration workspace:

- derives unsupported messages from the platform contract;
- removes hard-coded `GCP` L4/L5 branches;
- presents unavailable architecture choices as disabled with the service-provided
  reason;
- distinguishes `unsupported` from `disabled` and indicates planned scope without
  presenting it as promised availability;
- keeps verification status diagnostic and does not use it as a selection rule.

Capability loading failure is explicit and fail-closed. Existing persisted
architectures remain readable, but deployment actions are unavailable until the
capability contract can be validated.

Demo scenarios use deterministic capability fixtures and include the GCP L4/L5
unsupported state. No demo adapter may silently support a path that production
rejects.

### Existing Screen Layout

This issue modifies only the capability state inside the existing deployment task.
It does not add a screen, modal, navigation destination, or new configuration step.
Desktop and Web use the same responsive workspace shell:

```text
Wide desktop / Web
+----------------------+-----------------------------------------------+
| Existing task        | Existing deployment layer overview            |
| sidebar              |                                               |
|                      | L1  [existing editor]                          |
|                      | L2  [existing editor]                          |
|                      | L3  [auto-configured]                          |
|                      | L4  [editor OR capability status] [MODIFY]     |
|                      | L5  [editor OR capability status] [MODIFY]     |
+----------------------+-----------------------------------------------+

Constrained desktop / Web
+---------------------------------------------------------------------+
| Existing task selector                                               |
+---------------------------------------------------------------------+
| Existing deployment layer overview                                   |
| L1 [existing editor]                                                 |
| L2 [existing editor]                                                 |
| L3 [auto-configured]                                                 |
| L4 [editor OR capability status] [MODIFY]                             |
| L5 [editor OR capability status] [MODIFY]                             |
+---------------------------------------------------------------------+
```

### Widget And State Tree

```text
ConfigurationWorkspace [REUSE]
`-- BlocProvider<WizardBloc> [MODIFY initialization only]
    `-- ConfigurationWorkspaceShell [REUSE]
        `-- DeploymentLayerOverview [MODIFY]
            |-- ArchitectureLayerBuilder [REUSE]
            |-- existing L1-L3 editors [REUSE]
            |-- L4 editor [REUSE when selectable]
            |-- CapabilityStatusCard [NEW shared replacement]
            |   `-- existing theme typography/icons/tokens [REUSE]
            `-- L5 editor [REUSE when selectable]

WizardBloc [MODIFY]
|-- ManagementApi.getProviderCapabilities() [NEW port method]
|-- WizardState.providerCapabilities [NEW immutable state]
|-- loading/error/ready capability states [NEW]
`-- existing initialization handlers [MODIFY]

ApiService [MODIFY] ----------> Management API :5005 only
DemoManagementApi [MODIFY] ---> DemoStore capability fixture
```

`CapabilityStatusCard` is justified because the current `l4Info` and `l5Info`
methods duplicate presentation while embedding provider truth. Existing generic
empty/dependency cards cannot distinguish availability, roadmap, verification, and
reason codes. The new shared widget receives a fully derived presentation model and
contains no provider logic.

All spacing and colors must use `lib/theme/` tokens; typography must derive from
`ThemeData`; icons must use Material `Icons`. User-facing capability strings must be
grouped in the existing configuration string boundary rather than scattered inline.
Widgets must not call services. `WizardBloc` owns loading and state transitions while
`ManagementApi` adapters own transport.

## Implementation Slices

### Slice 1: Contract Plan And Service Registries

1. Add this reviewed plan and update roadmap traceability.
2. Add immutable capability value objects and registries to Optimizer and Deployer.
3. Generate complete provider-layer documents from executable registries.
4. Add side-effect-free capability endpoints and OpenAPI response models.
5. Add Deployer preflight validation for selected architecture providers.

### Slice 2: Management Aggregation

1. Add strict Pydantic upstream and platform DTOs.
2. Extend typed service clients with capability reads.
3. Implement deterministic aggregation and contract-drift errors.
4. Expose the authenticated platform endpoint.
5. Preserve typed unavailability through deployment validation/orchestration.

### Slice 3: Flutter Consumer And Documentation

1. Add strict Dart models and API methods.
2. Add demo fixtures for healthy and unsupported capability states.
3. Replace provider-name presentation branches with capability lookups.
4. Update component, architecture, setup, extension-point, and limitation docs.
5. Update issue and roadmap status only after all default gates pass.

Every numbered implementation step in all slices is mandatory and must not be
skipped. Any necessary deviation requires an update to this plan and corresponding
verification evidence before implementation continues.

## Verification Gates

### Optimizer

- registry completeness: 3 providers x 7 layers;
- contract serialization and enum validation;
- capability endpoint response schema;
- matrix equality with calculator `supported_layers`;
- unsupported rows cannot participate in scoring;
- no credentials or dynamic provider calls occur.

### Deployer

- registry completeness: 3 providers x 7 layers;
- endpoint contract and canonical IDs;
- package-builder/registry parity;
- single and multiple unsupported-row validation;
- rejection precedes workspace and Terraform/provider calls;
- aliases normalize only at adapters.

### Management API

- 3 x 7 successful aggregation matrix;
- every availability precedence combination;
- roadmap and weakest-verification derivation;
- duplicate, missing, unknown, malformed, mismatched, unavailable, and timeout cases;
- typed route errors contain no upstream payload leakage;
- authentication is required.

### Flutter

- strict parser rejects malformed/partial contracts;
- real and demo API adapters satisfy the interface;
- unavailable and planned states render correctly;
- capability fetch failure disables deployment actions without hiding saved data;
- existing AWS/Azure and GCP L1-L3 behavior remains available;
- widget tests cover light/dark and constrained widths where UI changes.

The user explicitly deferred final application E2E until after the manual visual UI
audit and the Twin architecture audit. Therefore this slice must run unit, widget,
analyzer, build, backend contract-integration, and Compose smoke gates, but must not
add or execute `flutter test integration_test/`. The later E2E issue must exercise the
real Management API; it may not replace it with a mocked HTTP adapter.

### Repository Gates

- Python format/lint/type checks used by each touched project;
- full non-E2E test suites for Optimizer, Deployer, and Management API;
- Flutter analyze and full test suite;
- docs build with strict link validation;
- Docker Compose build/start smoke check without cloud credentials;
- no live cloud E2E and no billable provider operation in this issue.

## Documentation Deliverables

- architecture data-flow and capability ownership;
- provider/layer matrix with scope and verification semantics;
- component API and extension-point instructions;
- developer procedure for adding a provider or layer without creating drift;
- thesis-facing distinction between bachelor baseline, implemented thesis scope,
  planned capability, and live verification;
- limitations linked to the relevant GitHub issues, including GCP L4/L5 #54.

## Definition Of Done

- [ ] All 21 provider-layer combinations are explicit in both internal services and in
  the aggregate platform response.
- [ ] Unsupported combinations fail before deployment side effects with typed,
  actionable errors.
- [ ] Optimizer and Deployer disagreement is detected and cannot become selectable.
- [ ] Flutter has no provider-name capability truth.
- [ ] Demo and production adapters expose the same capability contract.
- [ ] Documentation and roadmap reflect the implemented state and deferred live gates.
- [ ] All default non-E2E verification gates pass.
