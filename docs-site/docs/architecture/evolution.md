# Original To Current State

Twin2MultiCloud did not begin as one application. The Optimizer (`2-twin2clouds`) and
Deployer (`3-cloud-deployer`) originated as separate Bachelor-project codebases with
standalone assumptions, file-oriented workflows, independent documentation, and
direct operational entrypoints. The thesis integration introduced the Management API
and Flutter UI, then progressively replaced accidental coupling with explicit contracts.

## Material Transformations

| Original state | Problem identified | Current state | Why it changed |
|---|---|---|---|
| Standalone services and direct UI/service calls | no stable application boundary | Flutter calls only the Management API | one authorization, lifecycle, persistence, and error boundary |
| Interactive CLI and legacy layer endpoints | multiple competing deployment paths | canonical manifest-backed operation API | deterministic validation and one auditable workflow |
| mutable `upload/template` used as template and runtime project | source and runtime data could contaminate each other | protected template, runtime project storage, operation packages, ephemeral workspaces | reproducibility, concurrency, and credential safety |
| cloud credentials copied across workspace/files/containers | duplicated plaintext and unclear ownership | encrypted user-scoped CloudConnections plus transient bootstrap input | reusable SSOT, redaction, ownership, auditability |
| per-twin credential blobs | duplication and difficult account reuse | twin binds connection IDs; pricing uses user defaults | account-level reuse without exposing secrets |
| pricing selected through fragile strings/keywords | provider catalog drift could silently choose wrong rows | editable intent/mapping registry, evidence, deterministic candidates, review decisions, publication gates | traceability and explicit ambiguity handling |
| cost formulas loosely coupled to fetched keys | fetch, units, formulas, and optimization could drift | optimization bundle binds metric, intents, provider contracts, formula set, model, and scoring | executable consistency across the whole cost path |
| only cost hard-coded into orchestration | difficult future research extension | enabled cost profile plus disabled typed extension declarations | thesis scope stays bounded while architecture remains extensible |
| route handlers owned DB queries and orchestration | large god routes and inconsistent errors | repositories, application services, typed clients, lifecycle/orchestrator services | testability and separation of concerns |
| Flutter god screens and ad-hoc API access | long forms, duplicated state, fragile workflows | runtime adapters, Riverpod composition, workflow BLoCs, typed models, configuration workspace | clear state ownership and testable UX |
| scattered HTML documentation | stale, duplicated, disconnected from integrated system | central MkDocs site with provenance register | one usable handbook while retaining research history |

## What Was Preserved

- the five-layer Digital Twin model;
- provider-specific infrastructure implementations and user functions where still valid;
- the core idea of cost-aware cross-provider placement;
- the original papers, diagrams, and historical implementation explanations;
- Terraform as the declarative infrastructure execution mechanism.

Preservation does not mean verbatim reuse. Provider behavior, permissions, pricing,
and deployment contracts are revalidated against the current implementation.

## What Remains Open

The current architecture is substantially cleaner, but several claims still require
external or live evidence: production UIBK authentication, final provider-specific
least privilege, and full cloud deployment verification. Provider feature parity also
varies, especially for cross-cloud functions and managed Digital Twin equivalents.

The [Source Provenance Appendix](../references/source-provenance.md) explains how the
historical sources were evaluated. The
[Refactoring Roadmap](refactoring-roadmap.md) links active and completed work.
