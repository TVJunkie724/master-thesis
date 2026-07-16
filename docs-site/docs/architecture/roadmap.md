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

## Current Focus

The active cross-cutting slice is
[#109 Establish Web and all-desktop Flutter support gates](https://github.com/TVJunkie724/master-thesis/issues/109)
in Phase 7. It makes Web, macOS, Windows, and Linux one explicit application
support contract with native build evidence. Phase 4 credential and Phase 6
pricing work remain independently tracked in their milestones.

## Backlog Rule

TODO and future-work files are historical inputs. New active work should be represented as GitHub Issues assigned to a Milestone, then linked from the relevant documentation page only when the context matters for thesis or development work.
