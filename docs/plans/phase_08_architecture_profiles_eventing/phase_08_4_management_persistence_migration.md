---
title: "Phase 8.4: Management Persistence And API Migration"
description: "Implementation plan for normalized architecture selection and immutable resolved-architecture persistence in the Management API."
tags: [architecture, management-api, persistence, migration, api, issue-142]
lastUpdated: "2026-07-20"
version: "1.1"
---

<!-- SOURCES:
- GitHub issue #142
- Phase 8.2 architecture contracts and Phase 8.3 provider/catalog registries
- twin2multicloud_backend models, migrations, repositories, services, routes, and OpenAPI
- Existing durable calculation-run and resolved-deployment-specification persistence
- User-approved server-derived profile-change preview and stale-digest protection
EXTRACTED: 2026-07-20 | VERSION: 1.1
-->

# Phase 8.4: Management Persistence And API Migration

## 0. Metadata

| Field | Value |
|---|---|
| Issue | [#142 Persist resolved Twin architectures and migrate fixed layer assignments](https://github.com/TVJunkie724/master-thesis/issues/142) |
| Milestone | Phase 8 - Twin Architecture Profiles & Eventing |
| Recommended branch | `codex/phase-8-management-architecture` |
| Base branch | `master` |
| Blocked by | Phase 8.3 / #150 |
| Produces | Persistence/API foundation for Optimizer and Flutter phases |
| Live cloud E2E | Forbidden |

Every model, constraint, migration, projection, route, authorization rule,
error code, and test in this plan is mandatory.

## Corrective Selection Addendum

Migration 022 and existing `@1` selections remain immutable historical state.
No newly created Twin may receive `five-layer-baseline@1` as a selectable
execution default. Until `five-layer-baseline@2` activates, the architecture
API may correctly return no active profile and the UI must show its blocking
empty state. Phase 8.9A atomically establishes `@2` as the new default without
rewriting historical Twins, runs, or resolutions.

## 1. Outcome

The Management API must become the runtime SSOT for:

- the reviewed architecture profile selected for a Twin draft;
- one immutable `ResolvedTwinArchitecture` per optimizer calculation run;
- queryable component assignments and resolved edges;
- current deployment selection through the existing selected-run lifecycle;
- explicit legacy resolution compatibility.

Repository profile/catalog files remain the definition SSOT. They are not
copied into the database. The database stores only pinned references and
concrete run/Twin resolution evidence.

### Scope Boundary

| Included | Excluded |
|---|---|
| Normalized models, migration 022, repositories/services, profile list/detail/select/preview APIs, immutable resolution ingestion, compatibility projection, ownership/audit/error handling, and OpenAPI | Optimizer candidate logic, provider catalog authoring, Deployer graph/package/Terraform execution, Flutter rendering, Eventing implementation, and live cloud execution |

## 2. Current State

The current Management model stores provider choices in fixed columns:

```text
OptimizerConfiguration
  cheapest_l1
  cheapest_l2
  cheapest_l3_hot
  cheapest_l3_cool
  cheapest_l3_archive
  cheapest_l4
  cheapest_l5
```

`CostCalculationRun` stores a frozen resolved-deployment specification and
result JSON, while deployment, simulator, verification, export, credential
selection, and Flutter projections still read fixed fields.

This phase adds the normalized architecture model and API compatibility layer.
Phase 8.5 implements Optimizer emission dark; Phase 8.6 keeps deployment
compilation dark; architecture-aware calculation and deployment consumption
activate together in Phase 8.9A.

Phase 8.4 stages the `ready` selected-run invariant and enforces it whenever a
run already carries architecture metadata. The existing live Optimizer path
still creates `legacy_not_resolvable` runs while Phase 8.5 integrates the
atomic ingestion boundary dark. Phase 8.9A activates that boundary only after
the complete AWS/Azure/provider-hosted-GCP profiles, storage routes, and typed
Deployer graph compiler are jointly supported. The temporary compatibility
path is audited and is not an architecture-ready deployment claim.

## 3. Persistence Model

Add:

```text
twin2multicloud_backend/src/models/architecture_profile.py
twin2multicloud_backend/src/repositories/architecture_repository.py
twin2multicloud_backend/src/services/architecture_profile_service.py
twin2multicloud_backend/src/services/resolved_architecture_service.py
twin2multicloud_backend/src/schemas/architecture_profile.py
twin2multicloud_backend/src/api/routes/architecture_profiles.py
twin2multicloud_backend/migrations/add_resolved_twin_architecture.py
```

Register migration (the earlier #113 prerequisite already owns migration 021):

```text
022_resolved_twin_architecture
```

### 3.1 `TwinArchitectureSelection`

One row per Twin:

| Column | Rule |
|---|---|
| `id` | UUID primary key |
| `twin_id` | Unique FK to `digital_twins`, cascade delete |
| `user_id` | Owner FK and index |
| `profile_id` | Stable reviewed profile ID |
| `profile_version` | Positive version string |
| `profile_digest` | Exact active definition digest |
| `revision` | Positive optimistic-concurrency integer |
| `selected_at` / `updated_at` | UTC timestamps |
| `selected_by_user_id` | Audit owner |

The selection references a repository definition but does not copy its content.
Changing profile increments `revision`, clears the selected calculation run,
and invalidates deployment readiness in one transaction. It does not delete
historical runs or resolutions.

### 3.2 `ResolvedTwinArchitectureRecord`

One row per calculation run:

| Column | Rule |
|---|---|
| `id` | `resolution_id`, UUID primary key |
| `calculation_run_id` | Unique FK, cascade delete |
| `twin_id` / `user_id` | Indexed ownership FKs |
| `schema_version` | `resolved-twin-architecture.v1` |
| `profile_id` / `profile_version` / `profile_digest` | Pinned profile identity |
| `optimization_bundle_digest` | Pinned strategy bundle |
| `workload_contract_id` / `workload_contract_version` / `workload_digest` | Frozen workload |
| `deployment_specification_version` / `deployment_specification_digest` | Exact referenced deployment selection |
| `total_monthly_cost` / `currency` | Canonical decimal string and currency |
| `functional_completeness_status` | `complete` only for persisted v1 |
| `canonical_json` | Exact canonical contract JSON |
| `content_digest` | Unique immutable digest |
| `origin` | `native_v1` or `reconstructed_v1` |
| `created_at` | UTC timestamp |

`canonical_json` is the immutable audit SSOT for the resolution. Child rows are
transactionally derived query projections and must reproduce the canonical
component/edge arrays exactly.

Add these fields to `CostCalculationRun`:

- `architecture_compatibility_status`: `ready` or
  `legacy_not_resolvable`;
- `resolved_architecture_version`;
- `resolved_architecture_digest`.

Only `ready` runs own a `ResolvedTwinArchitectureRecord`. A
`legacy_not_resolvable` run has no fabricated resolution row.

### 3.3 `ResolvedArchitectureComponentAssignment`

Required columns:

- UUID primary key;
- `resolved_architecture_id` FK, cascade delete;
- unique `assignment_id` per resolution;
- responsibility/logical component/provider/deployment component/service IDs;
- provider profile ID/version;
- region;
- deployment-specification component IDs as canonical JSON;
- cost contribution as canonical decimal string;
- capability, pricing, formula, and evidence references as canonical JSON;
- deterministic ordinal.

Indexes:

- resolution plus responsibility;
- resolution plus provider;
- deployment component ID;
- service ID.

### 3.4 `ResolvedArchitectureEdge`

Required columns:

- UUID primary key;
- `resolved_architecture_id` FK, cascade delete;
- unique `resolved_edge_id` per resolution;
- logical edge ID;
- source/destination assignment and port IDs;
- edge implementation ID;
- mechanism;
- transfer route ID;
- cost contribution as canonical decimal string;
- binding, trust, observability, formula, and evidence refs as canonical JSON;
- deterministic ordinal.

Foreign-key-like assignment references must be validated in the service before
insert; both assignment IDs must exist in the same resolution.

### 3.5 Extension Bindings

Reuse `TwinExtensionBinding` from #113. The resolved architecture stores the
pinned artifact, slot, and non-secret configuration references in
`canonical_json`.
Do not create a second mutable extension-binding table.

## 4. Immutability And Constraints

- `ResolvedTwinArchitectureRecord` and child rows are insert-only.
- SQLAlchemy listeners reject updates to every semantic field.
- The service rejects a second resolution for one calculation run.
- Canonical JSON is parsed and validated before persistence.
- The content digest is recomputed server-side and compared.
- Child projections are built server-side; clients and the Optimizer cannot
  submit projection row IDs or ordinals.
- Persisting the resolution and all child rows is one transaction.
- Selecting a run does not mutate the resolution.
- A selected `ready` run must own one `complete` resolution and matching
  deployment specification digest. Phase 8.9A removes the temporary legacy
  selection compatibility path when it activates complete `@2` output.
- Delete occurs only through calculation-run/Twin cascade or explicit
  retention policy outside this phase.

## 5. API Contract

Add authenticated Management API routes:

```text
GET /architecture-profiles
GET /architecture-profiles/{profile_id}/versions/{profile_version}

GET /twins/{twin_id}/architecture-profile
POST /twins/{twin_id}/architecture-profile/change-preview
PUT /twins/{twin_id}/architecture-profile

GET /twins/{twin_id}/resolved-architecture
GET /optimizer-runs/{run_id}/resolved-architecture
```

### 5.1 Profile Summary/Detail

The list returns only `active` reviewed profiles:

- ID/version/digest;
- display name and description;
- responsibility and capability summary;
- supported workload contract;
- available/unsupported provider summary;
- extension slot summary;
- lifecycle status.

The v1 catalog is bounded to 32 active profile versions. The route returns a
deterministically sorted array and does not paginate. Exceeding the bound is a
server configuration failure, not a truncated response.

Detail additionally returns logical components, edges, and a read-only
visualization projection. It excludes raw catalog Terraform/package metadata.

### 5.2 Profile Change Preview

The client must request a server-derived preview before changing an existing
profile selection:

```json
{
  "profile_id": "five-layer-baseline",
  "profile_version": "1",
  "expected_revision": 3
}
```

The response contains:

- current and target profile references;
- safe IDs and display labels of workload fields that become incompatible;
- extension slot bindings that become incompatible and will be unbound;
- selected calculation run ID that will be deselected;
- deployment-readiness sections that will be invalidated;
- a deterministic `invalidation_digest` over the current revision, target
  profile digest, and exact invalidation set.

The preview never returns workload values, artifact source, credentials,
secret material, provider evidence, or infrastructure identifiers. An
idempotent same-profile preview returns an empty invalidation set and a digest.

### 5.3 Profile Selection

Request:

```json
{
  "profile_id": "five-layer-baseline",
  "profile_version": "1",
  "expected_revision": 3,
  "invalidation_digest": "sha256:..."
}
```

The server resolves and pins the current active digest. The request must not
contain a digest, components, providers, services, edges, workload values,
costs, or infrastructure fields.

Response contains selection, new revision, invalidated selected run ID if any,
unbound extension slot IDs, cleared workload field IDs, and
deployment-readiness state.

Conflicting revision returns HTTP 409 with
`ARCH_SELECTION_REVISION_CONFLICT`. Selecting the same ID/version is
idempotent and does not increment revision. A same-profile selection accepts
only the matching empty-preview digest.

For a profile change, the service recomputes the invalidation set inside the
same transaction and compares its digest with the request. A mismatch returns
HTTP 409 with `ARCH_SELECTION_INVALIDATION_STALE`; the server changes nothing.
On success it clears only the previewed incompatible workload fields, unbinds
only incompatible extension slots, deselects the current run, resets derived
deployment readiness, updates the selection, and commits once.

Changing a profile must never delete a user-function artifact,
`CloudConnection`, pricing credential, or deployment credential. It removes
only Twin-scoped bindings/selections that the target profile cannot use.

### 5.4 Resolved Architecture Read

The read DTO exposes the typed canonical resolution and safe selection
metadata. It never returns database projection IDs, raw provider pricing
payloads, source code, secret values, physical cloud identifiers, or Terraform
values.

`GET /twins/{twin_id}/resolved-architecture` returns the architecture of the
currently selected calculation run. No selection returns 404
`ARCH_RESOLUTION_NOT_SELECTED`.

## 6. Internal Optimizer Ingestion Contract

Extend the existing optimizer calculation/run service boundary with one
server-only method:

```text
persist_successful_run(
  calculation_result,
  resolved_deployment_specification,
  resolved_twin_architecture
)
```

The Management API must:

1. allocate `calculation_run_id` before calling the Optimizer;
2. send that ID, selected profile ref, workload, and immutable extension
   bindings;
3. validate both returned contracts and their matching run/profile/spec refs;
4. persist run, deployment specification, architecture, components, edges, and
   result items atomically;
5. persist a failed run without a resolution when validation fails.

The public calculation-create request never accepts a resolved architecture.

Phase 8.4 implements the method and tests with fixtures. Phase 8.5 integrates
the Optimizer output behind a default-off activation gate; Phase 8.9A enables
the path after complete-provider deployment support exists.

## 7. Legacy Migration

Migration 022 must:

1. create all new tables, constraints, and indexes idempotently;
2. create a `TwinArchitectureSelection` for every existing Twin, pinned to
   `five-layer-baseline@1`;
3. load the active repository profile digest; abort the migration if the
   definition is unavailable or invalid;
4. inspect every `CostCalculationRun`;
5. reconstruct a v1 resolution only when the run has a valid v1 deployment
   specification, complete cheapest path, compatible profile, and all catalog
   references required for deterministic reconstruction;
6. verify reconstructed cost, provider assignments, deployment component refs,
   digests, and the still-executable fixed-field provider projection before
   insert;
7. mark all other runs `legacy_not_resolvable` without creating a resolution
   row or inventing data;
8. preserve every fixed `cheapest_l*` column and historical JSON field.

Migration creates historical `@1` selections only for Twins that existed at
the migration boundary. New Twins created before Phase 8.9A have no executable
profile selection. Phase 8.9A atomically establishes `@2` as the default for
new Twins after its complete-service gate; it does not backfill or rewrite
historical selections.

Legacy runs:

- remain readable with explicit migration status;
- can remain selected only if reconstructed and deployment-compatible;
- are deselected atomically if not resolvable;
- cannot be deployed/redeployed from fixed fields after Phase 8.9A;
- retain destroy/audit access through frozen historical operation evidence.

Do not silently derive a service, edge, formula, evidence, region, or component
from provider names alone.

## 8. Transitional Fixed-Field Projection

Until Phase 8.9A activates `@2`:

- existing `cheapest_l*` columns remain a derived compatibility projection for
  `five-layer-baseline@1`;
- for architecture-ready runs, only `ResolvedArchitectureService` may write
  them and values are derived from component assignments;
- the pre-8.5 live calculation/selection path remains an explicitly
  inventoried legacy writer until Optimizer architecture output is activated;
  those writes never create architecture evidence;
- a round-trip invariant proves projection equals resolution;
- non-baseline profiles cannot be projected and return
  `ARCH_LEGACY_PROJECTION_UNSUPPORTED`;
- all direct readers are inventoried and migrated in their owning later phase.

The tracked ownership and removal list is
[`phase_08_4_fixed_field_reader_inventory.md`](phase_08_4_fixed_field_reader_inventory.md).

After Phase 8.9A, fixed fields remain physically for non-destructive history
but are no longer an executable source.

## 9. Error Contract

Stable domain codes:

- `ARCH_PROFILE_NOT_FOUND`
- `ARCH_PROFILE_VERSION_UNSUPPORTED`
- `ARCH_PROFILE_NOT_ACTIVE`
- `ARCH_SELECTION_REVISION_CONFLICT`
- `ARCH_SELECTION_INVALIDATION_STALE`
- `ARCH_SELECTION_FORBIDDEN`
- `ARCH_RESOLUTION_INVALID`
- `ARCH_RESOLUTION_DUPLICATE`
- `ARCH_RESOLUTION_DIGEST_MISMATCH`
- `ARCH_RESOLUTION_REFERENCE_MISMATCH`
- `ARCH_RESOLUTION_INCOMPLETE`
- `ARCH_RESOLUTION_NOT_SELECTED`
- `ARCH_LEGACY_NOT_RESOLVABLE`
- `ARCH_LEGACY_PROJECTION_UNSUPPORTED`

Routes translate domain errors through the existing centralized API error
handler. Messages are bounded, stable, and safe. Full contract payloads,
provider evidence blobs, source, credentials, and database internals are never
logged or returned.

## 10. Authorization, Audit, And Observability

- Every Twin/run read or write verifies `user_id` ownership.
- Profile definitions are globally readable only after authentication and only
  when active.
- Profile select/change uses the existing authenticated request and correlation
  middleware. The codebase has no generic mutation limiter; the
  credential-specific limiter does not apply because this path accepts no
  credentials or secret material.
- Emit append-only audit events for profile select/change, run invalidation,
  native resolution persistence, reconstruction, legacy rejection, selection,
  and digest/reference failure.
- Audit data includes safe IDs, versions, digests, result code, user/Twin/run
  IDs, and correlation ID; it contains no payload or secret.
- Metrics count resolution validation/persistence/migration outcomes by safe
  code and profile version.

## 11. Implementation Slices

### Slice A: Models And Migration

Must add models, relationships, constraints, indexes, immutable listeners,
migration 022, and clean/populated/idempotent migration tests.

### Slice B: Repository And Services

Must implement thin repositories, transactional profile selection, canonical
resolution validation/persistence, server-derived invalidation preview and
digest verification, projection reconstruction, ownership, and stable errors.

### Slice C: Read APIs

Must add profile and resolved-architecture routes, Pydantic schemas, OpenAPI
contracts, authorization, bounded deterministic profile lists, and route
tests.

### Slice D: Calculation-Run Integration

Must add preallocated run IDs, fixture-based architecture ingestion, atomic
run/spec/resolution persistence, failed-run behavior, and selected-run
readiness invariants.

### Slice E: Transitional Consumers

Must route fixed baseline projection writes through the new service and add a
tracked inventory for readers migrated in Phases 8.5-8.7.

## 12. Test Plan

### Migration

- empty database;
- populated database with no optimizer result;
- valid all-AWS/all-Azure/mixed v1 runs;
- incomplete cheapest path;
- invalid/missing deployment specification;
- digest mismatch;
- fixed-field projection mismatch or missing Optimizer configuration;
- unsupported GCP L4 fixture;
- already-applied idempotence;
- failure rollback without partial rows;
- selected legacy run deselection.

### Service/Repository

- active profile select and idempotent reselect;
- stale revision conflict;
- inactive/unknown profile;
- ownership isolation;
- selection invalidates current run/readiness atomically;
- preview lists exactly the incompatible workload fields, extension bindings,
  selected run, and readiness sections;
- stale invalidation digest rejects the mutation without partial changes;
- profile changes preserve CloudConnections, artifacts, and compatible
  workload/bindings;
- canonical resolution persistence and deterministic child projection;
- duplicate/mutated resolution rejection;
- assignment/edge cross-resolution reference rejection;
- immutable row update rejection;
- fixed-field round-trip for baseline only.

### API/OpenAPI

- list/detail/preview/select/read happy paths;
- exact preview-to-selection digest round trip;
- unauthenticated requests return 401; cross-user Twin/run access returns 404
  to avoid resource enumeration;
- client-authored infrastructure/digest fields rejected with 422;
- stable error response codes;
- response redaction and bounded payloads;
- OpenAPI required fields/enums;
- profile detail visualization DTO consistency.

### Cross-Contract

- run ID/profile/spec/digest mismatch;
- functional completeness not `complete`;
- unresolved extension binding;
- deployment specification v1 compatibility;
- atomic failed-run persistence.

Safe verification:

```bash
docker exec -e PYTHONPATH=/app master-thesis-management-api-1 \
  python -m pytest \
    tests/test_resolved_twin_architecture_migration.py \
    tests/test_architecture_profile_service.py \
    tests/test_resolved_architecture_service.py \
    tests/test_architecture_profile_routes.py \
    tests/test_cost_calculation_runs.py -v
docker exec -e PYTHONPATH=/app master-thesis-management-api-1 \
  python -m pytest tests/ -v
python scripts/sync_architecture_profile_contracts.py --check
```

No Optimizer live HTTP, Deployer operation, Terraform, cloud credential, or
real E2E is required; downstream behavior uses canonical fixtures at this
phase.

## 13. Documentation

Update:

- `docs-site/docs/contracts-and-data-flow/state-ownership.md`;
- `docs-site/docs/contracts-and-data-flow/pricing-optimization.md`;
- `docs-site/docs/contracts-and-data-flow/contract-map.md`;
- Management API component/developer docs and migration guide;
- Phase 8 roadmap with full issue title and migration status;
- #142 with migration counts, compatibility classifications, test commands,
  and residual legacy risk.

Product docs describe only active endpoints and implemented persistence.
Research interpretation stays in `docs/research/`. Do not edit LaTeX.

## 14. Rollout And Rollback

Rollout:

1. deploy contract/catalog definitions;
2. run migration 022;
3. keep profile ingestion fixture-gated;
4. verify reconstruction counts and selected-run validity;
5. enable read APIs;
6. leave Optimizer and Deployer activation for later phases.

Rollback:

- disable new routes and architecture ingestion;
- preserve new rows and migration journal;
- continue reading legacy fixed fields only while Phase 8.9A has not removed
  executable fallback;
- never drop tables or overwrite legacy data automatically.

## 15. Definition Of Done

- [x] Repository definitions remain SSOT; DB stores only selections and
      concrete resolutions.
- [x] Migration 022 is idempotent, transactional, and non-destructive.
- [x] At the original migration boundary, migrated and then-new Twins received
      one pinned historical baseline selection; the corrective addendum assigns
      the new-Twin default change to Phase 8.9A without rewriting history.
- [x] Profile selection uses optimistic concurrency and atomically invalidates
      stale deployment selection.
- [x] Profile changes require a server-derived invalidation preview and matching
      digest; stale previews fail without mutation.
- [x] Profile changes clear only incompatible Twin-scoped fields/bindings and
      never delete CloudConnections, artifacts, or credentials.
- [x] One immutable, complete, digest-verified resolution can be stored per
      calculation run.
- [x] Component and edge projections reproduce canonical JSON exactly.
- [x] API clients cannot author assignments, provider services, edges,
      infrastructure values, evidence, or digests.
- [x] Every read/write path enforces ownership and safe errors.
- [x] Legacy runs are reconstructed only from sufficient evidence or explicitly
      classified `legacy_not_resolvable` without a resolution row.
- [x] Fixed fields on architecture-ready runs are derived baseline
      projections; the inventoried live legacy writers are removed by their
      owning dark/UI phases and final Phase 8.9A activation.
- [x] Architecture-ready selected runs require matching architecture and
      deployment specification; Phase 8.9A owns removal of the explicitly
      audited legacy-selection compatibility path at runtime activation.
- [x] Migration, model, repository, service, API, OpenAPI, security, redaction,
      and compatibility tests pass.
- [x] The full safe Management suite and contract sync gate pass.
- [x] No cloud, Terraform, downstream runtime, or live E2E action occurs.
- [x] Product docs, migration docs, roadmap, and #142 are updated.
- [x] Two reviews find no unresolved issue.
- [x] The structured commit references #142.

## 16. Completion Evidence

- Focused Management gate: 116 migration, profile, resolution, route,
  calculation-run, and Twin-lifecycle tests passed.
- Full Management regression: 994 tests passed in 206.55 seconds.
- Root contract/catalog gate: 50 tests and 488 subtests passed.
- Generated contract synchronization:
  `sha256:a832312a9cbb5381f4a1d714b6743c4164a1c76e38535bbbc46cbd905c81d766`
  across three service copies.
- Optimizer and Deployer generated-contract readers: 4 tests passed in each
  service.
- Catalog completeness: 22 components, 33 edges, 43 artifacts, and 51
  Terraform resource declarations.
- Architecture inventory: 11 responsibilities, 114 components, 64 artifacts,
  661 Terraform objects, 90 edges, 100 allowlisted compatibility anchors, and
  the one already-reviewed predecessor finding.
- Migration fixture matrix proves transactional rerun, all-AWS, all-Azure,
  mixed-provider reconstruction, conservative legacy classification,
  fixed-field mismatch rejection, rollback, and append-only triggers.
- `mkdocs build --strict`, Ruff, contract sync, catalog completeness, inventory,
  and `git diff --check` passed.
- Review 1 and Review 2 closed all findings for the completed migration. The
  remaining legacy selection path is historical and audited; the corrective
  new-Twin default change is owned by Phase 8.9A. Phase 8.5 integrates
  architecture emission dark and cannot bypass unsupported provider profiles.
