# Complete Project Documentation Plan

**Status:** Implemented and verified

**Date:** 2026-07-16

**Base branch:** `master`

**Implementation branch:** `codex/complete-project-documentation`
**Scope:** Entire integrated platform except the LaTeX thesis source

## 1. Objective

Create a complete, code-verified documentation site from which a new user can:

- understand the platform, its five-layer Digital Twin model, and every project boundary;
- install, configure, start, use, test, inspect, and troubleshoot the application;
- trace data, credentials, pricing evidence, configuration, deployment state, logs, and outputs;
- find supported extension points and the verification required for an extension;
- distinguish implemented behavior from external dependencies and planned work;
- reconstruct the original Bachelor-project state, the identified architecture debt, the resulting target state, and the reasoning behind each material transformation.

The documentation serves three audiences without maintaining three competing sources:

| Audience | Primary need |
|---|---|
| Platform user | Start the application and complete supported workflows safely. |
| Developer/operator | Understand ownership, contracts, configuration, persistence, tests, and extension points. |
| Thesis reader/evaluator | Understand provenance, engineering decisions, trade-offs, evidence, and remaining limitations. |

## 2. Scope And Boundaries

Document completely:

- repository-level startup and Compose runtime;
- `twin2multicloud_flutter`;
- `twin2multicloud_backend`;
- `2-twin2clouds`;
- `3-cloud-deployer`;
- `docs-site` itself;
- AWS, Azure, and GCP setup boundaries relevant to pricing and deployment;
- historical HTML and Markdown sources as provenance.

The LaTeX project is excluded from detailed component documentation. Root command references may mention the separate `thesis.sh latex` workflow only to explain that it is outside application startup.

The work does not:

- run live-cloud deployments or cost-incurring E2E tests;
- publish real credentials, account identifiers, secret values, or ignored local files;
- claim production readiness for functionality that still depends on external identity-provider setup or supervised live-cloud verification;
- turn implementation plans into current architecture documentation without checking them against code.

## 3. Source Hierarchy

Documentation claims are resolved in this order:

1. current code, schemas, configuration, migrations, and executable contracts;
2. current tests and safe runtime verification;
3. merged implementation plans and closed GitHub issues as decision evidence;
4. legacy HTML/Markdown and the original papers as historical evidence only.

When sources disagree, the documentation records the disagreement and uses the current executable contract as the present-state truth. Historical material is never silently rewritten as if it had always described the current architecture.

## 4. Information Architecture

The MkDocs site will use the following product-oriented navigation:

1. **Getting Started**: prerequisites, fresh clone, runtime profiles, first start, demo.
2. **User Guide**: dashboard, cloud accounts, configuration workspace, pricing review, deployment and operations.
3. **Architecture**: system context, responsibilities, data ownership, trust boundaries, end-to-end flows, persistence, evolution.
4. **Components**: complete guides for Flutter, Management API, Optimizer, and Deployer.
5. **Operations**: Compose topology, configuration reference, secrets, database/migrations, logging, troubleshooting.
6. **Cloud Setup**: credential categories, bootstrap flow, AWS, Azure, GCP, least-privilege status.
7. **Developer Guide**: repository map, contracts, API discovery, tests/quality gates, extension guides.
8. **Thesis And Evolution**: original state, architecture debt, decisions, resulting state, limitations.
9. **References**: papers, contextual diagrams, a concise source-provenance appendix, and external sources.

Diagrams remain next to the explanation they support. ASCII diagrams are preferred for source-controlled flows and boundaries; existing raster diagrams remain where they provide historical or visual value.

## 5. Per-Project Documentation Contract

Every project guide must contain:

1. purpose and owned responsibilities;
2. explicit non-responsibilities and upstream/downstream boundaries;
3. entrypoints and a focused directory map;
4. architecture and internal separation of concerns;
5. data models, state, files, and persistence owned by the project;
6. runtime configuration and security-sensitive settings;
7. API or adapter contracts;
8. principal workflows and failure paths;
9. logging, error handling, and security controls;
10. safe tests and quality gates;
11. supported extension points and required evidence;
12. implemented limitations and linked GitHub work;
13. original state, transformation, rationale, and resulting state.

The `docs-site` guide follows the same contract where applicable and additionally
documents navigation ownership, authoring conventions, asset placement, external
links, local preview, strict builds, and the provenance-update workflow.

The repository/runtime guide inventories every durable and ephemeral state
boundary: SQLite tables, bind mounts, named volumes, generated Flutter config,
runtime secrets, pricing registry files, fetched pricing artifacts, deployer
templates, staged operation packages, ephemeral workspaces, and synchronized
runtime outputs.

## 6. Canonical Cross-Project Flows

The documentation must trace at least:

- startup and runtime composition;
- authentication/runtime-mode selection;
- user-scoped CloudConnection creation, validation, binding, and redaction;
- configuration workspace persistence and twin lifecycle transitions;
- provider pricing refresh, raw evidence, intent matching, review, publication, and cost calculation;
- optimization bundle selection from metric through formula and scoring strategy;
- deployment manifest creation, archive validation, operation-package staging, ephemeral workspace execution, output synchronization, logs, and verification;
- offline demo composition and its strict no-network boundary.

Each flow identifies the system of record and the owner of every state transition.

## 7. Status And Gap Vocabulary

Current documentation uses exactly these labels:

- **Implemented**: present in current code and covered by safe verification.
- **Externally gated**: implemented boundary exists, but completion requires an external system or administrator.
- **Verification pending**: code exists, but final supervised/live evidence is intentionally outstanding.
- **Planned**: not implemented; represented by a GitHub issue.
- **Historical**: retained only to explain provenance or a superseded design.

No planned capability may be described in present tense. Every material gap includes its operational effect and, where available, its GitHub issue.

## 8. Historical Evolution And Provenance

Replace the migration-only view with a thesis-facing evolution narrative. Material
changes record original state, debt, resulting architecture, rationale, trade-offs, and
evidence in their actual architectural context. A short appendix records the source
families and evaluation hierarchy without duplicating each explanation in a matrix.

## 9. API Documentation Strategy

- FastAPI OpenAPI documents are the endpoint-level source of truth.
- The docs site explains ownership, workflow, authentication, failure semantics, and how to open the live schemas.
- High-value cross-service contracts are summarized manually, but exhaustive request/response field copies are avoided because they drift.
- Public Management API usage is separated from internal Optimizer and Deployer APIs.
- Flutter-to-Optimizer or Flutter-to-Deployer calls are documented as prohibited boundaries.

## 10. Security And Safety Rules

- Use example schemas only; never read or reproduce ignored credential contents.
- Separate runtime encryption/signing keys, cloud bootstrap credentials, stored CloudConnections, pricing credentials, and deployment credentials.
- Mark the development token and local file overlays as development-only.
- Explain HTTPS/proxy trust, rate limiting, audit events, secret redaction, credential deletion constraints, and rotation limitations.
- Mark provider permission policies as baselines until supervised least-privilege verification is complete.
- Clearly separate safe tests from live-cloud E2E operations.

## 11. Implementation Slices

### Slice 1: Foundation And Navigation

- Replace shallow landing/navigation pages with audience-oriented entrypoints.
- Add status vocabulary, documentation scope, and reading paths.
- Preserve external-link new-tab behavior and Material light/dark mode.

### Slice 2: Architecture And Evolution

- Document system context, component/container boundaries, data ownership, trust boundaries, and cross-project flows.
- Add the original-to-current architecture narrative and decision table.

### Slice 3: Complete Component Guides

- Flutter: runtime composition, Riverpod/BLoC split, screens, demo adapters, API boundary, extension points.
- Management API: routes/services/repositories/clients, data model, lifecycle, security, migrations, orchestration.
- Optimizer: pricing registry, evidence pipeline, matching/review/publication, calculations, optimization bundles, provider behavior.
- Deployer: manifests, archive policy, storage, operation packages, ephemeral workspaces, Terraform/provider lifecycle, simulator, verification.
- Docs site: authoring, navigation, references, provenance maintenance, preview, and validation.

### Slice 4: User, Setup, And Operations

- Fresh-clone and runtime-profile procedures.
- End-user workflows and state-dependent actions.
- Compose topology, ports, volumes, secrets, migrations, logs, backups, troubleshooting.

### Slice 5: Cloud Setup And Security

- Credential model and bootstrap sequence.
- Provider-specific AWS/Azure/GCP setup boundaries.
- Explicit current least-privilege and live-validation status.

### Slice 6: Developer And Extension Guides

- API discovery and contract ownership.
- Test matrix and safe command reference.
- Extension paths for UI features, Management API workflows, optimization objectives/formulas/pricing mappings, deployer providers/functions.

### Slice 7: Provenance Closure

- Record source families and evidence hierarchy in a concise appendix.
- Explain material original-to-current transformations in architecture/component pages.
- Keep historical files until a credential-safe archive and cleanup are verifiable.

### Slice 8: Verification And Review

- Build MkDocs in strict mode.
- Check all internal Markdown links and referenced assets.
- Verify documented commands against `thesis.sh`, Compose config, and package scripts.
- Compare route/module/test inventories against the documentation coverage matrix.
- Review every page for present-vs-planned wording, secret leakage, and cross-project ownership errors.

## 12. Definition Of Done

- [x] Every in-scope project satisfies the per-project documentation contract.
- [x] Every durable, generated, and ephemeral data/file boundary has one documented owner and lifecycle.
- [x] A fresh-clone user has one tested path to development and one tested offline demo path.
- [x] All supported user workflows and their failure/recovery behavior are documented.
- [x] All canonical cross-project flows identify state owner and system of record.
- [x] Authentication and cloud-provider gaps are explicit and not overstated.
- [x] Every historical source family has a documented current treatment and evidence rule.
- [x] No public migration tracker duplicates contextual architecture/evolution documentation.
- [x] Every diagram is contextual and readable in source form or preserved as a referenced asset.
- [x] MkDocs strict build and link verification pass.
- [x] Real credentials and ignored local data remain untouched.
- [x] Documentation changes are committed separately from unrelated user work.
