# Architecture Roadmap

The active architecture-debt roadmap is tracked in GitHub Issues and Milestones. `ASSESSMENT.md` remains the repository-local narrative source for the roadmap, while GitHub is the operational backlog.

For the issue-numbered refactoring index, see [Refactoring Roadmap](refactoring-roadmap.md).

## Phase Order

| Phase | Goal |
|-------|------|
| Phase 0 | Freeze the architecture-debt assessment and move active backlog tracking to GitHub Issues. |
| Phase 1 | Canonicalize the Deployer around one productive provider/Terraform path. |
| Phase 2 | Harden Deployer deploy/destroy contracts, SSE event shapes, path resolution, and error boundaries. |
| Phase 3 | Separate documentation, template ownership, runtime artifacts, and deployer input material. |
| Phase 4 | Establish credential source of truth, Compose profile separation, deployment manifests, and ephemeral workspaces. |
| Phase 5 | Disentangle backend orchestration into repositories, services, typed clients, and orchestrators. |
| Phase 6 | Stabilize Optimizer layer contracts, pricing reliability, and provider capability modeling. |
| Phase 7 | Slice Flutter wizard and twin views into testable feature-owned surfaces. |
| Phase 8 | Freeze a hardened five-layer baseline, introduce closed-world architecture profiles, and evaluate a bounded Eventing and Messaging extension. |

## Current Workstreams

Phase 8 has started. The source-backed current deployment graph in #144, the
complete `five-layer-baseline@1` target decision in #139, the four drift-gated
architecture-profile contracts in #149, the deterministic user-function
prerequisite #113, and the exact provider/component catalog in #150 are locally
implemented and reviewed. Phase 8.4 adds migration 022, revisioned Management
profile selection/invalidation, immutable resolved-architecture persistence,
owner-scoped APIs, and audited compatibility projections. Optimizer resolution
in Phase 8.5 is next and remains dark until joint Phase 8.6 activation;
Deployer and Flutter activation also remain dark. Credential, remaining
Optimizer coverage, manual UI audit, and external authentication work remain
independently tracked in their GitHub milestones rather than inferred from one
global "current phase" label.

## Backlog Rule

TODO and future-work files are historical inputs. New active work should be represented
as GitHub Issues assigned to a Milestone, then linked from the relevant documentation
page only when the context matters for current users, operators, or developers.
