# Resolved Deployment Specification Mini-Roadmap

**Parent issue:** [#118](https://github.com/TVJunkie724/master-thesis/issues/118)  
**Base branch:** `master`  
**Implementation branch:** `codex/pricing-tier-finalization`  
**Status:** Reviewed, implementation-ready, and required before Phase 8

## Purpose

The current five-layer baseline can select the cheapest provider path without
proving that Terraform deploys the resource configuration used by the cost
model. This roadmap closes that gap before architecture-profile work begins.

The target flow is:

```text
Optimizer winner
  -> ResolvedDeploymentSpecification v1
  -> Management API validation and immutable persistence
  -> DeploymentManifest v2
  -> Deployer preflight and typed tfvars
  -> provider Terraform resources
  -> read-only Flutter review
  -> no-apply cross-stack drift gate
```

## Phase Order

| Phase | Issue | Deliverable | Blocked By |
| --- | --- | --- | --- |
| 1 | [#127](https://github.com/TVJunkie724/master-thesis/issues/127) | Canonical contract, dimension registry, matrix, and fixtures | None |
| 2 | [#129](https://github.com/TVJunkie724/master-thesis/issues/129) | Optimizer emits an exact resolved specification | #127 |
| 3 | [#130](https://github.com/TVJunkie724/master-thesis/issues/130) | Management API validates, persists, freezes, and manifests it | #127, #129 |
| 4 | [#131](https://github.com/TVJunkie724/master-thesis/issues/131) | Deployer validates it and generates typed tfvars | #127, #130 |
| 5 | [#132](https://github.com/TVJunkie724/master-thesis/issues/132) | AWS Terraform alignment | #131 |
| 6 | [#133](https://github.com/TVJunkie724/master-thesis/issues/133) | Azure Terraform alignment | #131 |
| 7 | [#120](https://github.com/TVJunkie724/master-thesis/issues/120) | GCP Terraform alignment | #131 |
| 8 | [#134](https://github.com/TVJunkie724/master-thesis/issues/134) | Compact read-only Flutter review | #130 |
| 9 | [#128](https://github.com/TVJunkie724/master-thesis/issues/128) | Cross-stack no-apply drift gate and final audit | #120, #127, #129, #130, #131, #132, #133, #134 |

Provider phases 5-7 may be implemented after phase 4 in any order. Phase 9 is
the only completion gate for parent issue #118.

## Non-Negotiable Rules

1. A progressive usage tier is never converted into a Terraform SKU.
2. An account-scoped plan is never silently changed for one twin.
3. A deployable value must be the same value used by the active cost formula.
4. Missing or unknown mappings fail before Terraform side effects.
5. Legacy runs remain readable but are not deployment-compatible.
6. The specification contains no credentials, endpoints, tokens, or provider
   response payloads.
7. Flutter displays the frozen selection but cannot author provider values.
8. No live cloud apply or final E2E work is part of this roadmap.

## Completion Gate

The roadmap is complete only when one deterministic test path proves:

```text
Optimizer specification
  == persisted Management specification
  == DeploymentManifest specification
  == Deployer typed tfvars
  == asserted Terraform resource attributes
```

The comparison applies to every supported provider and baseline slot. Any
invariant that remains hardcoded must be explicitly classified, documented, and
covered by a source-contract test proving it matches the cost model.
