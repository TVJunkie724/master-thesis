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

## Current Workstreams

The latest Optimizer architecture slice is
[#68 Standardize optimizer LayerResult and layer calculator contracts](https://github.com/TVJunkie724/master-thesis/issues/68).
It establishes one validated result model, one calculator/capability boundary,
fail-closed unsupported-provider selection, and a complete provider-layer test
matrix. Phase 6 continues with provider capability modeling, traceability, and
expanded service/tier coverage. Credential, deployment, UI, and external
authentication work remains independently tracked in its GitHub milestone rather
than inferred from one global "current phase" label.

## Backlog Rule

TODO and future-work files are historical inputs. New active work should be represented as GitHub Issues assigned to a Milestone, then linked from the relevant documentation page only when the context matters for thesis or development work.
