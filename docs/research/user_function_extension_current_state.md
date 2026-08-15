---
title: "User-Function Extension Current-State Audit"
description: "Cross-stack inventory of the predecessor user-function upload, persistence, packaging, wrapper, and Terraform boundaries."
tags: [research, user-functions, security, packaging, flutter, management-api, deployer]
lastUpdated: "2026-07-19"
version: "1.1"
---

# User-Function Extension Current-State Audit

## Scope and method

This audit records the predecessor implementation that issue #113 replaces. It
is descriptive evidence, not current user guidance. The inspection covered the
Management API persistence and deployment-package path, the Deployer function
APIs, registry and provider package builders, the AWS/Azure/GCP processor and
feedback wrappers, Terraform variables/resources, and the Flutter
Configuration Workspace and Wizard BLoC.

No credential file, runtime upload, Terraform state, provider response, or live
cloud resource was read or used. The audit is based on repository source as of
2026-07-19.

## Existing end-to-end path

```text
Flutter editable code + requirements.txt strings
  -> WizardState dynamic maps and booleans
  -> PUT /twins/{id}/deployer/config
  -> mutable columns on deployer_configurations
  -> deployment_service materializes provider-shaped files
  -> Deployer discovers files from config-derived directories
  -> provider-specific package builders mutate/merge source and requirements
  -> tfvars selects ZIP paths by device/action name
  -> Terraform creates provider functions with fixed handlers
  -> provider wrapper constructs user-function identity or URL at runtime
```

There is no single immutable artifact identity across these steps. Validation
booleans can be persisted independently from the source they describe, and the
same logical function changes shape at multiple boundaries.

## User-controlled fields

| Boundary | Current user-controlled data | Current representation |
|---|---|---|
| Flutter | processor, event-action, and feedback source | mutable strings keyed by device or function name |
| Flutter | dependency declarations | optional mutable `requirements.txt` strings |
| Flutter | legacy validation state | client-side booleans and validation feedback |
| Flutter | uploaded project archive | provider-shaped ZIP whose extracted contents repopulate mutable fields |
| Management API | processor source/requirements/validation | JSON text columns on `deployer_configurations` |
| Management API | event-action source/requirements/validation | JSON text columns on `deployer_configurations` |
| Management API | feedback source/requirements/validation | scalar text/boolean columns |
| Management API | state-machine source | a sibling mutable user-logic field, not an extension artifact |
| Deployer project | directory and function names | derived from device IDs and event `functionName` values |
| Deployer build API | provider, uploaded Python file, requirements file | provider-specific manual build request |

The predecessor API also accepts client-authored validation booleans in the
same update model as source. Source, dependencies, validation, and deployment
selection therefore do not share an immutable revision.

## Platform-controlled fields that leak into user artifacts

| Concern | Current behavior | Ownership leak |
|---|---|---|
| Handler | AWS expects `handler`/`lambda_handler`, GCP expects `main`/`handler`, Azure accepts any decorated function | user source must know provider handler conventions |
| Source filename | AWS `lambda_function.py`, Azure `function_app.py`, GCP `main.py` | provider layout is exposed in Flutter and persisted data |
| Function identity | device IDs and event function names become Terraform/function names | topology naming is coupled to user-controlled identifiers |
| Runtime | Terraform fixes provider runtime strings separately | no stable provider-neutral runtime registry |
| Wrapper | different out-of-process HTTP/Lambda invocation contracts | user functions do not receive one canonical envelope |
| Permissions | broad platform roles/policies are coupled to wrapper/resource naming | no capability-level slot contract |
| Configuration | topology URLs, resource names, function keys, and Twin metadata are environment variables | no typed split between user configuration and platform bindings |
| Validation | client booleans are stored next to mutable source | validation evidence is neither server-owned nor digest-bound |
| Observability | wrappers log through `print`, raw exceptions, and provider logging | error and redaction behavior differs by provider |

## Implicit handlers, wrappers, and source rewrites

### Manual Deployer build API

`src/api/function_build.py` validates provider-specific entrypoints and writes
provider-specific filenames. It can add default unpinned dependencies for
Azure and GCP. It validates Python syntax but does not define the `process`
domain entrypoint, a canonical runtime envelope, deterministic metadata, a
locked transitive dependency graph, or a slot/capability boundary.

### AWS

- User packages are separate Lambda ZIPs.
- Terraform fixes `lambda_function.lambda_handler`.
- The processor wrapper constructs
  `{digital_twin_name}-{device_id}-processor`, invokes it synchronously, and
  forwards the returned JSON to the Persister.
- The feedback wrapper invokes a separately named Lambda and sends the result
  to the device.
- Predecessor wrappers can log raw exception strings and tracebacks.

### Azure

- User functions are combined into one Function App ZIP.
- `function_app.py` files are converted to Blueprints.
- Processor decorator names and routes are rewritten with regular
  expressions.
- `require_env` access is rewritten for lazy loading.
- A generated root `function_app.py` imports and registers every generated
  module.
- Processor and feedback wrappers call user functions over HTTP and append a
  function key to the URL.

This is an explicit source-mutation boundary: identical uploaded source is not
the source packaged for Azure.

### GCP

- User functions are separate Cloud Function ZIPs with Terraform entrypoint
  `main`.
- Shared modules and a generated dependency set are merged into packages.
- Existing helpers retain historical processor wrapping/rewrite hooks even
  where the current decoupled path no longer rewrites names.
- Processor and feedback wrappers call user functions over HTTP with an ID
  token.
- Predecessor failures can include raw exception messages and runtime URLs.

## Dependencies

The existing user surface edits `requirements.txt`. Package builders merge
wrapper defaults and user lines without enforcing a complete transitive lock.
The current boundary does not require:

- normalized PEP 508 package names;
- exact `==` versions;
- hashes for every distribution;
- wheel-only artifacts;
- an allowlisted index/redirect host;
- a complete transitive closure;
- rejection of URLs, VCS, editable installs, local paths, build hooks, or
  dependency-manager credential files.

This is the scope overlap with issue #36.

## Filesystem and archive paths

Provider-specific roots are:

- AWS: `lambda_functions/{processors,event_actions,event-feedback}/...`
- Azure: `azure_functions/{processors,event_actions,event-feedback}/...`
- GCP: `cloud_functions/{processors,event_actions,event-feedback}/...`

The Management API materializes source directly into those shapes when
building a deployment project. Deployer discovery is driven by
`config_iot_devices.json`, `config_events.json`, optimization flags, and the L2
provider. Existing path helpers reject traversal and symlinks in several
locations, and deterministic ZIP helpers normalize entry order/metadata, but
there is no one archive policy that also bounds expanded size, file count,
path depth, nested archives, hard links, device files, native binaries,
hidden credential configuration, and total validation/build duration.

## Platform environment and topology bindings

Current wrappers consume platform-owned values including:

- `DIGITAL_TWIN_INFO`
- `PERSISTER_LAMBDA_NAME`
- `PERSISTER_FUNCTION_URL`
- `FUNCTION_APP_BASE_URL`
- `FUNCTION_BASE_URL`
- `EVENT_FEEDBACK_LAMBDA_NAME`
- `EVENT_FEEDBACK_FUNCTION_URL`
- `USER_FUNCTION_KEY`
- `IOT_HUB_CONNECTION_STRING`
- `GCP_PROJECT_ID`
- `GCP_IOT_REGION`
- `GCP_IOT_REGISTRY_ID`

These are legitimate platform bindings, but their discovery and error behavior
is provider-specific. The new contract must keep all of them outside user
source, artifact manifests, runtime envelopes, Flutter forms, and safe error
messages.

## Terraform and permission bindings

Terraform currently selects user ZIPs through:

- `aws_processors`, `aws_event_actions`, and
  `aws_event_feedback_zip_path`;
- `gcp_processors`, `gcp_event_actions`, and
  `gcp_event_feedback_zip_path`;
- the combined `azure_user_zip_path`.

AWS handlers are fixed to `lambda_function.lambda_handler`; GCP entrypoints are
fixed to `main`; Azure discovers decorators inside the combined Function App.
Function names, package paths, runtime environment, IAM/invoker permissions,
and platform URLs are assembled from provider templates and configuration
conventions rather than resolved from an immutable extension-slot binding.

## Persistence and ownership

The Management API correctly scopes current deployer configuration through the
Twin owner, but user logic is stored in a mutable aggregate row:

- no immutable artifact row;
- no normalized file/dependency rows;
- no artifact digest tied to source and configuration;
- no append-only binding history;
- no one-active-binding uniqueness rule;
- no owner-only source download boundary;
- no explicit legacy validation/import state.

List/detail responses can expose source because source is part of the general
deployer configuration read model. This prevents least-disclosure API shaping.

## Flutter surface

The Configuration Workspace already has the correct shell and `User Logic`
task, but the current section renders provider filenames and one editable
`FunctionPackageBlock` per processor/action/feedback item. Source and
`requirements.txt` are mutable text fields in `WizardState`; validation
commands call the legacy Deployer configuration-validation proxy and update
client state.

The surface therefore exposes handler filenames, does not model immutable
artifacts or slot bindings, and cannot distinguish `draft`, `valid`, `bound`,
`stale`, or `legacy_unvalidated` through a typed Management API contract.

## Error and logging paths

Existing Management routes generally map service errors and enforce owner
checks. Existing Deployer API paths use bounded uploads and safe top-level
errors in several locations. Provider wrappers remain inconsistent:

- some use `print`;
- some log exception text or tracebacks;
- some return `str(exception)` in response bodies;
- some include runtime URLs or constructed resource identifiers in logs;
- success/failure payloads differ by provider;
- no shared correlation/invocation/error-code envelope exists.

## Required replacement boundary

Issue #113 must replace, not merely document, the leaks above:

1. one versioned slot/artifact/envelope contract with Python `process`;
2. immutable, owner-scoped artifacts, normalized files/dependencies, and
   append-only bindings;
3. server-owned validation evidence and deterministic identities;
4. exact hashed `requirements.lock` validation;
5. one non-executing deterministic package pipeline;
6. repository-owned AWS/Azure/GCP adapters with the same envelope and safe
   error behavior;
7. fail-closed binding validation before Terraform;
8. a compact Flutter slot/artifact workflow through the Management API only;
9. explicit `legacy_unvalidated` import with no automatic trust upgrade.

## Implemented replacement decisions

Issue #113 implements that boundary as a prerequisite contract rather than as
an additional Twin layer:

- `contracts/user-function-extension/v1` is the canonical source for the
  slot, artifact, runtime-envelope, registry, validator, and fixtures;
- `processor.telemetry@1` is the only reviewed slot, with provider-neutral
  Python 3.11 source and one platform-owned adapter for AWS, Azure, and GCP;
- Management owns immutable, owner-scoped artifacts, normalized files and
  dependency records, append-preserving bindings, shared fail-closed
  source-download limits, and source-free audit evidence for both accepted and
  rejected source access;
- Deployer revalidates the binding and artifact, restricts dependency fetches
  to registered HTTPS hosts, vendors a complete hashed pure-Python closure,
  preserves source bytes, and emits deterministic packages and redacted
  evidence before Terraform;
- all wrappers use the same bounded envelope, response validation, timeout,
  retryability, safe-error, invocation-ID, and correlation-ID behavior;
- Flutter adapts the existing User Logic task with typed live/demo Management
  API contracts and gates deployment readiness on active reviewed bindings;
- migrated predecessor source remains `legacy_unvalidated`; an explicit owner
  operation creates a new validated v1 artifact without mutating the legacy
  record, and new packages omit legacy source.

Architecture-profile component mapping remains owned by the next Phase 8
contract slice. The extension contract therefore establishes a safe execution
boundary without claiming that a new architecture profile or Event Layer is
active.

## Limitations and threats to validity

- The audit evaluates repository behavior, not live provider consoles.
- No live cloud deployment was run, so provider runtime behavior is inferred
  from wrappers, Terraform, and offline tests.
- Legacy branches or local ignored upload/state directories are outside the
  evidence set.
- Local verification covers Web and macOS builds. The repository's Windows and
  Linux jobs remain the authoritative platform gates after the commit is
  pushed.
- Phase 8.3 will bind reviewed architecture-profile extension slots to the
  provider catalog. This prerequisite must provide the secure execution
  contract without prematurely making an unreviewed profile slot executable.
