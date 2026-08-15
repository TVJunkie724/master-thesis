---
title: "User-Function Extension Contract"
description: "Artifact, binding, package, runtime, ownership, and correlation flow for version 1 user-function extensions."
tags: [contracts, data-flow, user-functions, ownership, security]
lastUpdated: "2026-07-19"
---

# User-Function Extension Contract

Version 1 provides one provider-neutral execution boundary for reviewed
user-function slots. It is part of the five-layer processing responsibility,
not a separate Event Layer.

## Ownership

| State or record | System of record | Disclosure |
|---|---|---|
| selected ZIP and form draft | Flutter Wizard BLoC | local draft only |
| slot registry and schemas | repository canonical contract | public, read-only |
| normalized source/dependency rows | Management API | owner-only; omitted from list/detail |
| artifact manifest and digest | Management API | metadata and evidence only |
| active and historical bindings | Management API | owner-scoped |
| deployment binding index | frozen operation package | IDs, versions, relative paths, digests |
| provider package | Deployer ephemeral workspace | never persisted as editable application state |
| package evidence | Deployer operation workspace | redacted versions, paths, and digests |
| runtime invocation/result | provider-owned wrapper | bounded contract envelope |

Flutter never calls the Deployer directly for this workflow. The Management API
never trusts a client-authored digest, validation state, handler, provider
field, or binding. The Deployer never discovers an unvalidated source tree
without a valid binding index.

## Validation And Persistence Sequence

```text
Flutter
  |  metadata + source ZIP
  v
Management API
  |  bounded multipart read
  |  schema/version/archive/source/dependency/secret/config validation
  |  canonical manifest + source/dependency digests
  |  repeat validation on create
  v
owner-scoped immutable artifact
  |  artifact ID + digest
  v
append-preserving Twin binding
```

The validation endpoint is advisory evidence. The create endpoint repeats the
same server-side validation and deduplicates by owner plus artifact digest.
Files and dependencies are normalized rows. Source is immutable after create;
editing produces another artifact.

The source-download route is owner-only, limited to five requests per owner per
minute through shared production storage, fail-closed when that control is
unavailable, audit-logged for success and rejection, marked `no-store`, and
returns a deterministic ZIP attachment. List/detail responses contain
filenames and counts but no source text.

## Deployment And Package Sequence

```text
Management deployment materializer
  |  validate active owner/Twin/artifact/digest relationship
  |  write relative manifest/source paths and binding digest
  v
frozen operation package
  |  .twin2multicloud/extensions/bindings.json
  v
Deployer isolated workspace
  |  validate binding index and immutable artifact again
  |  resolve locked pure-Python wheels under approved HTTPS host policy
  |  copy source unchanged
  |  add platform runtime + registered provider adapter
  |  build deterministic ZIP twice and compare bytes
  v
redacted package evidence
  |  verify project-relative path and package digest
  v
Terraform package reference
```

An invalid owner relationship, artifact digest, binding digest, path, adapter,
dependency, package digest, or missing reviewed deployment-component mapping
stops before Terraform. The prerequisite records the digest-checked Terraform
reference but deliberately does not make that reference executable. Package
evidence excludes source text, configuration values, credentials, environment
values, and local absolute paths.

## Runtime Envelope

Every provider adapter accepts the same input fields:

```text
schema_version
invocation_id
correlation_id
occurred_at
slot_id
payload
context { twin_id, device_id }
```

The wrapper validates the registered input schema, rejects secret-like
material, calls `process(payload, configuration, context)` in-process, validates
the output schema, enforces the response-size and 30-second duration limits,
and returns one of:

- `success` with a validated payload;
- `rejected` with a stable `DOMAIN_*` code;
- `failed` with a stable `PLATFORM_*` code and explicit retryability.

AWS returns the envelope from its Lambda adapter. Azure and GCP serialize the
same envelope through their HTTP adapters; rejected domain results use a
successful HTTP transport response, while platform failures use a server-error
transport response.

## Correlation And Audit

```text
Management request ID
  -> validation/create/bind/unbind/source-download audit event

Deployer operation ID
  -> package build structured log
  -> package evidence index
  -> deployment operation evidence

runtime correlation ID
  -> provider-neutral invocation result
```

Audit records contain operation/action, outcome, safe IDs, slot, correlation,
and stable error code. They never include source content or secret material.
Management and Deployer IDs refer to their respective operation boundaries;
the frozen binding/artifact digests provide the immutable cross-boundary join.

## Legacy Compatibility

Migration copies predecessor processor, event-action, and feedback source into
immutable `legacy_unvalidated` rows. It does not convert `requirements.txt`
into a trusted lock and creates no active binding.

An owner can explicitly upload and validate a corrected v1 replacement. The
legacy row is not mutated. A new deployment with legacy source and no valid v1
binding fails closed; once v1 is selected, raw legacy files are omitted from
the new operation package. Previously frozen deployments remain readable and
destroyable.

## Current Scope

The registry currently contains `processor.telemetry@1` with Python 3.11 and
AWS, Azure, and GCP adapters. Architecture-profile component/catalog mapping is
a separate reviewed contract. A future Eventing profile must pass its own
functional, cost, and compatibility decision gate; this extension boundary
does not activate it.
