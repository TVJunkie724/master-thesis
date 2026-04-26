# Architecture Roadmap

The active architecture-debt roadmap is tracked in GitHub Issues and Milestones. `ASSESSMENT.md` remains the repository-local narrative source for the roadmap, while GitHub is the operational backlog.

## Phase Order

| Phase | Goal |
|-------|------|
| Phase 0 | Freeze the architecture-debt assessment and move active backlog tracking to GitHub Issues. |
| Phase 1 | Canonicalize the Deployer around one productive provider/Terraform path. |
| Phase 2 | Harden Deployer deploy/destroy contracts, SSE event shapes, path resolution, and error boundaries. |
| Phase 3 | Separate repository hygiene, template ownership, runtime artifacts, and published documentation. |
| Phase 4 | Establish credential source of truth, Compose profile separation, deployment manifests, and ephemeral workspaces. |
| Phase 5 | Disentangle backend orchestration into repositories, services, typed clients, and orchestrators. |
| Phase 6 | Stabilize Optimizer layer contracts, pricing reliability, and provider capability modeling. |
| Phase 7 | Slice Flutter wizard and twin views into testable feature-owned surfaces. |

## Current Phase

The current implementation focus is **Phase 3: Repository Hygiene & Docs Site**.

This phase creates the target documentation site, classifies legacy documentation and artifacts, adds non-destructive guardrails, and prepares the repository for the credential and deployment-state hardening work that follows.

## Backlog Rule

TODO and future-work files are historical inputs. New active work should be represented as GitHub Issues assigned to a Milestone.

The repository hygiene check reports remaining legacy backlog files until they are archived, deleted, or replaced by links to GitHub.
