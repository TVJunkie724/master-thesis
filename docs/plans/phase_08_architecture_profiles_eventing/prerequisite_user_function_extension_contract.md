---
title: "Prerequisite: User-Function Extension And Packaging Contract"
description: "Implementation contract for a deterministic, provider-neutral, non-secret user-function extension boundary required by Phase 8."
tags: [user-functions, packaging, security, deployer, management-api, flutter, contracts]
lastUpdated: "2026-07-19"
version: "1.0"
---

<!-- SOURCES:
- GitHub issue #113 and related issue #36
- 3-cloud-deployer/src/api/function_artifacts.py
- 3-cloud-deployer/src/api/function_build.py
- 3-cloud-deployer/src/function_registry.py
- 3-cloud-deployer/src/providers/terraform/package_builder.py
- twin2multicloud_backend/src
- twin2multicloud_flutter/lib/screens/wizard and twin2multicloud_flutter/lib/services
- User-approved v1 boundary that allows typed non-secret configuration and defers provider-managed user-function secrets
EXTRACTED: 2026-07-19 | VERSION: 1.0
-->

# Prerequisite: User-Function Extension And Packaging Contract

## 0. Metadata

| Field | Value |
|---|---|
| Issue | [#113 Define and harden the user-function extension and packaging contract](https://github.com/TVJunkie724/master-thesis/issues/113) |
| Milestone | Phase 4 - Runtime Credentials & Deployment State |
| Recommended branch | `codex/user-function-extension-contract` |
| Base branch | `master` |
| Blocked by | None |
| Status | Reviewed implementation plan; implementation pending |
| Blocks | Phase 8.3 extension-slot catalog binding |
| Related narrower issue | [#36 Validate user function requirements.txt before deployment](https://github.com/TVJunkie724/master-thesis/issues/36) |
| Later secret hardening | [#153 Design provider-managed secrets for user-function extensions](https://github.com/TVJunkie724/master-thesis/issues/153) |
| Flutter targets | Web, macOS, Windows, Linux |
| Live cloud E2E | Excluded |

Every section and Definition of Done item in this plan is mandatory. A builder
must not omit a slice because a provider appears to work with its current
template conventions.

## 1. Outcome

The platform exposes one provider-neutral, versioned user-function extension
contract. The user supplies approved domain logic, dependencies, typed
non-secret configuration. The platform owns handlers, wrappers, provider
resource names, topology bindings, identities, permissions, runtime policy,
observability, retries, limits, and infrastructure references.

Identical canonical inputs must produce byte-identical logical artifact
manifests and deterministic provider-package hashes. Invalid or unsafe
artifacts must fail before Terraform.

### Scope Boundary

| Included | Excluded |
|---|---|
| Python 3.11 domain source, deterministic locked dependencies, typed non-secret configuration, platform wrappers, immutable artifacts, provider packaging, approved slot binding, and compact Flutter workflow | Additional runtimes, arbitrary topology, user-authored infrastructure/handlers/permissions, user-managed secret values or references, unrestricted dependencies/network, and live provider deployment |

## 2. Current State And Evidence

The implementation must start with a source audit of:

- `3-cloud-deployer/src/api/function_artifacts.py`
- `3-cloud-deployer/src/api/function_build.py`
- `3-cloud-deployer/src/api/function_discovery.py`
- `3-cloud-deployer/src/api/function_upload.py`
- `3-cloud-deployer/src/function_metadata.py`
- `3-cloud-deployer/src/function_registry.py`
- `3-cloud-deployer/src/providers/terraform/package_builder.py`
- `3-cloud-deployer/src/providers/terraform/package_builders/user.py`
- provider wrappers under `3-cloud-deployer/src/providers/{aws,azure,gcp}/`
- user-upload and project-package generation in `twin2multicloud_backend/src/services/`
- wizard request construction and user-logic UI under
  `twin2multicloud_flutter/lib/bloc/wizard/` and
  `twin2multicloud_flutter/lib/features/configuration_workspace/`

The audit must identify every current user-controlled field, implicit handler,
source rewrite, dependency file, filesystem path, environment variable,
provider-specific wrapper, Terraform variable, permission, and log/error path.
The audit artifact must be stored at
`docs/research/user_function_extension_current_state.md`. It may describe
limitations and reasoning; current user instructions belong in `docs-site/`.

## 3. Fixed Decisions

1. The canonical contract supports Python 3.11 only for the thesis
   implementation. Its stable runtime ID is `python311`. Provider adapters map
   it to the existing Terraform values `python3.11` (AWS), `3.11` (Azure), and
   `python311` (GCP). Adding another runtime requires a new reviewed runtime
   registry version.
2. Each extension point has a stable `slot_id`. The slot defines its canonical
   input/output envelope, configuration schema, limits, permissions, and
   provider adapter compatibility.
3. User source must implement one domain entrypoint named `process`. Provider
   handlers remain platform-owned wrappers and call this entrypoint in-process.
4. User source must not import provider SDK clients to discover downstream
   resources, construct resource identifiers, or perform topology wiring.
5. Version 1 accepts typed non-secret configuration only. User-managed secret
   values and secret references are unsupported and fail closed.
   [#153 Design provider-managed secrets for user-function extensions](https://github.com/TVJunkie724/master-thesis/issues/153)
   owns any later provider-managed secret-store, runtime-identity, rotation,
   pricing, audit, and write-only UI contract; it must not reinterpret v1
   fields.
6. Dependencies must be declared through `requirements.lock` using normalized
   PEP 508 package names, exact `==` versions, and at least one
   `--hash=sha256:<digest>` per wheel. The complete transitive dependency set
   must be locked. Unpinned requirements, editable installs, local paths, URLs,
   VCS references, build hooks, sdists, and unsupported package sources fail
   closed. The builder uses `pip --require-hashes --only-binary=:all:` against
   the allowlisted PyPI simple index only.
7. Packaging must copy normalized source and dependencies; it must not rewrite
   user source, function names, handlers, endpoints, or resource references.
8. Artifact identity is the SHA-256 digest of canonical manifest JSON plus the
   normalized source/dependency payload. Timestamps and local absolute paths
   are excluded.
9. Extension artifacts are immutable once bound to a selected deployment run.
10. Flutter edits only the fields explicitly marked `user_editable` by the
    Management API. It never sends provider handler, resource, IAM, Terraform,
    output, or binding data.
11. Artifact source is immutable after creation. The Management API stores the
    normalized UTF-8 source files and lock manifest as owner-scoped artifact
    rows; it never stores a mutable working copy in deployment configuration.
    Editing creates a new artifact.
12. `CloudConnection` remains exclusively for provider pricing/deployment
    credentials and must not be reused as a user-code secret bag. Platform
    wrappers may use platform-owned deployment bindings internally, but these
    values are never exposed to user source.

## 4. Canonical Contracts

Create repository-owned contracts under:

```text
contracts/user-function-extension/v1/
  extension-slot.schema.json
  artifact-manifest.schema.json
  runtime-envelope.schema.json
  examples/
    processor-slot.json
    valid-artifact.json
    invalid/
```

### 4.1 ExtensionSlot v1

Required fields:

| Field | Type | Rule |
|---|---|---|
| `schema_version` | string | Constant `user-function-extension-slot.v1` |
| `slot_id` | string | Stable lower-case dotted ID; immutable across compatible versions |
| `slot_version` | string | Positive integer encoded as a string |
| `display_name` | string | User-facing label; not an infrastructure name |
| `responsibility_id` | string | Architecture responsibility reference |
| `component_id` | string | Platform component that owns the wrapper |
| `entrypoint` | string | Constant `process` for v1 |
| `runtime_contract` | object | Allowed Python versions and provider adapters |
| `input_schema` | object | Embedded or referenced JSON Schema |
| `output_schema` | object | Embedded or referenced JSON Schema |
| `configuration_schema` | object | JSON Schema with `user_editable` annotations |
| `secret_policy` | string | Constant `forbidden` for v1 |
| `dependency_policy_id` | string | Versioned allow/deny policy reference |
| `resource_limits` | object | Timeout, memory, artifact, source, and response limits |
| `network_policy` | object | Closed-world egress capability identifiers |
| `permission_capabilities` | array | Capability IDs, never IAM actions from clients |
| `error_contract_id` | string | Canonical typed error contract |
| `observability_contract_id` | string | Correlation/log/metric contract |
| `compatibility` | object | Compatible artifact and provider-adapter versions |

The schema must use `additionalProperties: false`, unique arrays, bounded string
lengths, and closed enums or versioned registry references.

### 4.2 UserFunctionArtifactManifest v1

Required fields:

| Field | Type | Rule |
|---|---|---|
| `schema_version` | string | Constant `user-function-artifact.v1` |
| `artifact_id` | UUID | Server generated |
| `artifact_digest` | string | `sha256:<64 lowercase hex>` |
| `slot_id` / `slot_version` | string | Must resolve to one registered slot |
| `runtime_id` | string | Must be allowed by the slot |
| `source` | object | Relative module path, normalized files, content digests |
| `dependencies` | array | Normalized package name, exact version, hashes, policy result |
| `configuration` | object | Schema-valid non-secret values only |
| `declared_capabilities` | array | Subset of slot capability allowlist |
| `created_by` | UUID | Authenticated user ID |
| `created_at` | RFC 3339 | Audit metadata excluded from reproducibility digest |
| `validation` | object | Validator version and successful checks |

For v1, `source.module_path` is exactly `process.py` and
`source.entrypoint` is exactly `process`. Additional `.py` modules may be
included under the artifact root, but packages, imports outside the artifact
root, and native binaries are rejected.

The manifest must not contain source text, credentials, provider endpoints,
Terraform values, deployment names, or resolved secret values.

### 4.3 RuntimeEnvelope v1

Input:

```json
{
  "schema_version": "user-function-runtime-envelope.v1",
  "invocation_id": "uuid",
  "correlation_id": "bounded-string",
  "occurred_at": "RFC3339",
  "slot_id": "processor.telemetry",
  "payload": {},
  "context": {
    "twin_id": "opaque-id",
    "device_id": "opaque-id"
  }
}
```

Output is one of:

- `success`: typed `payload` conforming to the slot output schema;
- `rejected`: stable domain rejection code and bounded safe message;
- `failed`: stable platform error code, retryability, and correlation ID.

Tracebacks, source text, environment variables, credentials, filesystem paths,
provider responses, and deployment identifiers must not cross the runtime
boundary.

The v1 schema rejects `secret_references`, secret-slot definitions, password or
token configuration annotations, and values detected as credential material.
Provider credentials and platform-owned bindings remain outside the extension
contract and user execution context.

## 5. Persistence And API Ownership

The Management API must own artifact metadata and bindings. Add normalized
models and an idempotent migration:

- `UserFunctionArtifact`
- `UserFunctionArtifactFile`
- `UserFunctionArtifactDependency`
- `TwinExtensionBinding`

`TwinExtensionBinding` must reference `twin_id`, `slot_id`, `slot_version`,
`artifact_id`, and an immutable binding digest. A twin may have at most one
active artifact per required slot/version. Historical artifacts remain
immutable and readable.

`UserFunctionArtifactFile` stores `relative_path`, normalized UTF-8
`content_text`, `content_digest`, and `size_bytes`. Only `.py` files plus
`requirements.lock` are accepted in v1. File content is excluded from list and
detail responses.

Required Management API routes:

```text
GET    /architecture/extension-slots
POST   /user-function-artifacts/validate
POST   /user-function-artifacts
GET    /user-function-artifacts
GET    /user-function-artifacts/{artifact_id}
GET    /user-function-artifacts/{artifact_id}/source
PUT    /twins/{twin_id}/extension-bindings/{slot_id}
DELETE /twins/{twin_id}/extension-bindings/{slot_id}
```

All routes require ownership checks. API responses expose validation evidence
and digests but never source text by default. The required owner-only source
endpoint returns a deterministically ordered ZIP with
`Content-Disposition: attachment`; it is rate-limited and audit-logged without
file content.

`POST /user-function-artifacts/validate` and
`POST /user-function-artifacts` use multipart form data with:

- `metadata`: UTF-8 JSON matching the client-authored subset of the artifact
  schema;
- `source_archive`: one ZIP containing `process.py`, optional additional
  `.py` modules, and `requirements.lock`.

The create route always repeats server-side validation. It never trusts a
previous validation response or a client-supplied digest.

## 6. Deterministic Packaging

Implement one provider-neutral package pipeline:

```text
validated artifact manifest
        |
        v
normalized source tree + pinned dependencies
        |
        v
platform-owned canonical wrapper interface
        |
        +--> AWS adapter/package layout
        +--> Azure adapter/package layout
        +--> GCP adapter/package layout
        |
        v
package digest + package evidence
```

Provider-specific file layouts and wrapper modules are versioned,
repository-owned adapter definitions. Each builder must select exactly one
registered adapter version from the artifact manifest; it must not invent or
alter layout at build time. Every adapter consumes the same manifest and
envelope and must not mutate the source tree. Build inputs must have
deterministic order, normalized modes, normalized line endings where the upload
contract permits, fixed ZIP timestamps, and no local metadata.

Package evidence must include:

- artifact, slot, wrapper, adapter, and package versions;
- source/dependency/manifest/package digests;
- included relative paths;
- validation policy versions;
- no file content and no secrets.

## 7. Validation And Failure Contract

Validation is staged and accumulates bounded findings:

1. archive/path safety;
2. manifest/schema/version validation;
3. source/module/entrypoint validation;
4. dependency normalization, pinning, hash, and policy validation;
5. forbidden-file and secret scanning;
6. non-secret configuration validation and secret-material rejection;
7. runtime/provider adapter compatibility;
8. resource/capability/permission policy validation;
9. deterministic build and package inspection;
10. extension-slot binding validation.

Stable error codes must include:

- `EXTENSION_ARCHIVE_UNSAFE`
- `EXTENSION_SCHEMA_INVALID`
- `EXTENSION_VERSION_UNSUPPORTED`
- `EXTENSION_ENTRYPOINT_INVALID`
- `EXTENSION_DEPENDENCY_UNPINNED`
- `EXTENSION_DEPENDENCY_FORBIDDEN`
- `EXTENSION_SECRET_MATERIAL_DETECTED`
- `EXTENSION_CONFIG_INVALID`
- `EXTENSION_RUNTIME_UNSUPPORTED`
- `EXTENSION_CAPABILITY_UNAUTHORIZED`
- `EXTENSION_BINDING_UNRESOLVED`
- `EXTENSION_PACKAGE_NONDETERMINISTIC`

Errors must identify only the safe logical field/file and correlation ID.
User source snippets, dependency credentials, absolute paths, and environment
values must be redacted.

## 8. Implementation Slices

### Slice A: Inventory And Contract Fixtures

Must:

- create the current-state audit;
- define the three JSON Schemas and positive/negative fixtures;
- add shared schema loading, canonicalization, digest, drift, and secret-scan
  tests;
- update #36 to point to this contract or close it only when its acceptance
  criteria are fully covered.

### Slice B: Management Artifact Persistence

Must:

- add the normalized models, repositories, service boundary, API schemas,
  ownership checks, migration, and audit events;
- keep routes thin and transactions atomic;
- reject client-authored validation state, digests, and platform fields.

### Slice C: Deployer Validator And Deterministic Builder

Must:

- replace ad hoc user-package mutation with a canonical artifact reader,
  validator, wrapper adapter, and deterministic package builder;
- preserve ephemeral workspaces;
- create packages only after all validation stages pass;
- return package evidence through existing typed operation evidence.

### Slice D: Provider Runtime Adapters

Must:

- implement equivalent input/output/error/correlation behavior for AWS, Azure,
  and GCP wrappers;
- preserve provider-specific trigger adapters outside user code;
- enforce timeout, response-size, retryability, and safe logging policy.

### Slice E: Flutter Approved Surface

Must:

- add typed Management API models/repository methods for slots, artifacts,
  validation, and bindings;
- adapt the existing User Logic task instead of adding a parallel wizard;
- show source/dependency/config validation with field-level errors;
- hide handlers, resource names, Terraform, IAM, provider endpoints, and
  secret values;
- keep demo/live repository parity.

### Slice F: Cross-Stack Offline Gate

Must prove one valid and all required invalid artifacts across:

```text
Flutter request
  -> Management validation/persistence
  -> DeploymentManifest extension reference
  -> Deployer package
  -> provider wrapper contract
  -> Terraform package reference
```

No live provider credentials or resources are permitted.

## 9. Security And Operational Requirements

- Limit archive size, expanded size, file count, path depth, per-file size,
  source size, dependency count, package size, and validation/build duration.
- Reject symlinks, hard links, absolute paths, `..`, device files, nested
  archives, executable binaries, private keys, credential formats, and hidden
  dependency-manager configuration containing tokens.
- Run dependency/build inspection in the existing isolated Deployer execution
  boundary without host credential mounts. The only permitted build egress is
  HTTPS to the configured PyPI simple index, with redirects restricted to
  approved package-file hosts. Tests use a local wheelhouse and no network.
- Never execute user source during validation or packaging.
- Reject user-managed secret values and references in source metadata,
  configuration, manifests, archives, dependency configuration, and bindings.
- Emit structured audit events for upload, validation, bind, unbind, package,
  and rejection without source or secret material.
- Preserve operation correlation across Management and Deployer.

## 10. Flutter UX Contract

The existing configuration workspace remains the shell. The wide Web and
desktop layout is:

```text
User Logic
+------------------------------------------------------------------+
| Processor logic                                   Valid / Draft  |
| Slot: Telemetry processor                                        |
| [Choose source archive]  [Validate]                              |
|                                                                  |
| Runtime: Python 3.11 (platform selected)                          |
| Dependencies: 8 pinned / 8 verified                              |
| Configuration: 3 required values                                |
|                                                                  |
| Validation details (collapsed)                           [v]      |
| [Bind validated artifact]                                        |
+------------------------------------------------------------------+
```

The compact Web and desktop layout is:

```text
User Logic
+----------------------------------+
| Telemetry processor      Valid   |
| Slot: processor.telemetry        |
| [Choose source archive]           |
| [Validate]                        |
|                                  |
| Python 3.11                       |
| 8 pinned dependencies            |
| 3 configuration values           |
|                                  |
| Validation details          [v]   |
| [Bind validated artifact]         |
+----------------------------------+
```

Required widget tree:

```text
ConfigurationWorkspaceShell [REUSE]
`-- DeploymentTaskContent [MODIFY]
    `-- DeploymentUserLogicSection [MODIFY]
        |-- ExtensionSlotList [NEW]
        |   `-- ExtensionSlotPanel [NEW]
        |       |-- StatusHeader [REUSE shared status primitives]
        |       |-- ArtifactSourcePicker [NEW typed adapter over existing file-input primitive]
        |       |-- RuntimeSummary [NEW]
        |       |-- DependencySummary [NEW]
        |       |-- DynamicConfigurationForm [NEW]
        |       |-- ValidationDetails [REUSE collapsed evidence pattern]
        |       `-- AsyncActionButton [REUSE for bind command]
        `-- LegacyArtifactNotice [NEW, migration state only]
```

New widgets are required because the current User Logic section edits raw maps
of source and `requirements.txt`; no existing shared widget owns a typed,
immutable artifact/slot binding. Existing status, form, disclosure, button,
dialog, alert, and file-input primitives must be reused. `ArtifactSourcePicker`
is only a typed slot/artifact adapter around the existing platform file
selection control; it must not duplicate native file-picker behavior.

Compact layout stacks the status, source action, configuration, and collapsed
validation sections. It must not expose provider handlers or resource wiring.
It must not render a secret input or secret-reference selector in v1.
All sizes, colors, text styles, focus treatment, and spacing must use existing
theme tokens and shared controls. Material icons only.

State remains in the existing Wizard BLoC for this complex workflow. Riverpod
continues to provide runtime composition and the `ManagementApi` adapter.
Widgets must not call HTTP clients directly.

## 11. Test Plan

### Contract

- valid slot/artifact/envelope fixtures;
- every required field absent;
- additional properties;
- duplicate IDs and references;
- unsupported versions/runtimes;
- digest canonicalization and mutation;
- secret-like key/value/path fixtures.

### Management API

- migration from empty and populated databases;
- owner isolation and forbidden cross-user access;
- immutable artifact and binding history;
- transactional bind/unbind;
- client-authored digest/validation rejection;
- bounded upload and validation errors;
- safe OpenAPI schema assertions.

### Deployer

- zip-slip, symlink, nested archive, oversized archive, file-count, and timeout
  rejection;
- invalid entrypoint and import shape;
- dependency pin/hash/policy rejection including #36 cases;
- deterministic package byte/hash equality;
- no source rewriting;
- equivalent AWS/Azure/GCP wrapper envelope tests;
- unresolved extension binding rejected before Terraform;
- package evidence redaction.

### Flutter

- JSON model parsing and unknown-version failure;
- BLoC state transitions for draft, validating, invalid, valid, binding,
  bound, stale, and API error;
- widget tests for wide and compact layouts, keyboard traversal, screen-reader
  labels, field errors, collapsed evidence, absence of secret controls, and
  secret non-disclosure;
- demo adapter parity;
- integration test through a real Docker Management API using fixture
  artifacts and no cloud calls.

Extend `run_frontend_integration_tests()` in `thesis.sh` so the resolved host
device runs
`integration_test/user_function_extension_contract_test.dart` after the
existing Management readiness test. The integration entrypoint remains
credential-free and uses real Management/Deployer HTTP boundaries.

### Safe Commands

```bash
docker compose up -d management-api 3cloud-deployer
docker exec -e PYTHONPATH=/app master-thesis-management-api-1 \
  python -m pytest tests/ -v
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 \
  python -m pytest tests/ --ignore=tests/e2e -v
./thesis.sh test frontend
./thesis.sh test frontend-integration
```

The implementation must resolve actual Compose service/container names before
running commands and must clean up only resources it created. Windows build
runs in the existing GitHub Actions Windows job. Web, macOS, Windows, and Linux
are mandatory; host-local target availability does not waive the matching CI
gate.

Before `docker compose up`, record which named services are already running.
After verification, run `docker compose stop` only for services that this test
invocation started. Never use `docker compose down` against a shared developer
stack as test cleanup.

## 12. Documentation

Update:

- `docs-site/docs/developer-guide/` with the extension model, package pipeline,
  adapter contract, limits, testing, and extension procedure;
- `docs-site/docs/user-guide/` with source, configuration, validation, binding,
  and troubleshooting instructions;
- `docs-site/docs/contracts-and-data-flow/` with artifact/binding ownership and
  sequence diagrams;
- `docs/research/user_function_extension_current_state.md` with predecessor
  analysis, decisions, limitations, and threats to validity;
- this mini-roadmap and GitHub #113/#36 status.

Do not put thesis conclusions into product documentation. Do not edit LaTeX.

## 13. Rollout And Compatibility

- Existing stored source remains readable during migration but is marked
  `legacy_unvalidated` and cannot be selected for a new deployment.
- Provide an explicit owner-triggered import/validation operation. Never mark
  legacy artifacts valid automatically.
- The migration copies current processor, event-action, and event-feedback
  source plus requirements text into immutable legacy artifact rows without
  converting `requirements.txt` into a trusted lock. Successful explicit
  validation creates a new v1 artifact and never mutates the legacy row.
- Existing selected deployments remain readable and destroyable through their
  frozen operation package.
- A new deployment or redeployment requires a valid v1 artifact binding for
  each required slot.
- Rollback may stop new v1 selection while retaining v1 rows and artifacts;
  migrations must not destructively remove legacy data in this phase.

## 14. Definition Of Done

- [ ] The source audit identifies every current user/platform ownership leak.
- [ ] All three v1 schemas and positive/negative fixtures are committed.
- [ ] Contract canonicalization, digest, drift, and secret-scan tests pass.
- [ ] Normalized immutable persistence and idempotent migration pass clean and
      populated-database tests.
- [ ] Management routes enforce ownership and reject platform-field authoring.
- [ ] V1 schemas, APIs, Flutter forms, and package builders reject
      user-managed secret values and secret references.
- [ ] Dependency and artifact validation fully covers #36.
- [ ] Packaging is deterministic and does not execute or rewrite user source.
- [ ] AWS, Azure, and GCP wrappers pass the same envelope/error contract.
- [ ] Unresolved or unauthorized extension bindings fail before Terraform.
- [ ] Structured logs and audit evidence contain no source or secrets.
- [ ] Flutter exposes only the approved compact User Logic workflow through the
      Management API and preserves demo parity.
- [ ] Analyzer, Flutter tests, Web, macOS, Windows, and Linux gates pass.
- [ ] Unit, contract, migration, API, package, security, provider-adapter,
      Terraform-reference, Flutter, and strict documentation gates pass.
- [ ] No live cloud resource or paid API is used.
- [ ] Product docs, research notes, roadmap, and issues are updated.
- [ ] Two implementation reviews find no unresolved issue.
- [ ] The final commit references #113; #36 closes only if its full scope is
      demonstrably covered.
