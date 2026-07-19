---
title: "User-Function Extension Development"
description: "Versioned contracts, deterministic packaging, provider adapters, limits, and safe tests for user-function extensions."
tags: [developer-guide, user-functions, contracts, packaging, security]
lastUpdated: "2026-07-19"
---

# User-Function Extension Development

The current extension boundary lets a user supply provider-neutral Python
domain logic without owning cloud handlers, Terraform wiring, IAM, runtime
resource names, endpoints, or credentials. Version 1 has one reviewed slot:
`processor.telemetry` on the platform-owned Python 3.11 runtime.

This contract is an execution extension inside the five-layer Twin. It does not
add an Event Layer or make the separate Eventing architecture profile active.

## Canonical Contract

Edit the canonical source only:

```text
contracts/user-function-extension/v1/
  extension-slot.schema.json
  artifact-manifest.schema.json
  runtime-envelope.schema.json
  registry.json
  runtime.py
  examples/
```

Generated copies in the Management API, Deployer, and Flutter assets carry the
same source digest. The sync check rejects missing, changed, stale, or extra
generated files.

The records have separate owners:

| Record | Owner | Purpose |
|---|---|---|
| extension slot | repository | entrypoint, schemas, limits, capabilities, provider adapters |
| artifact manifest | Management API | immutable source/configuration/dependency identity |
| runtime envelope | platform wrapper | equivalent invocation and result behavior on all providers |
| binding | Management API | append-preserving Twin-to-artifact selection |
| package evidence | Deployer | source, manifest, dependency, adapter, wrapper, and package digests |

## Source Contract

The upload is a ZIP containing:

```text
process.py
requirements.lock
[additional top-level or nested .py modules]
```

`process.py` defines exactly one top-level function:

```python
def process(payload, configuration, context):
    value = payload["value"] * configuration["scale_factor"]
    return {"value": value, "quality": "accepted"}
```

The v1 validator parses but never executes source. It rejects unsafe imports
and calls, provider SDK access, source-controlled handlers, async functions,
classes, bare or `BaseException` handlers, nested archives, links, special
files, native binaries, credential material, and secret references.

## Dependencies

An empty `requirements.lock` is valid. Every non-empty line must contain a
normalized package name, exact version, and at least one wheel digest:

```text
example-package==1.2.3 --hash=sha256:<64-lowercase-hex-characters>
```

The complete transitive closure must be present. URLs, local paths, VCS
references, editable installs, build hooks, sdists, native wheels, and
unapproved packages fail closed. The isolated builder:

1. reads the configured PyPI Simple index over HTTPS;
2. restricts redirects and wheel downloads to registered hosts;
3. verifies a compatible pure-Python wheel against the lock digest;
4. reruns `pip download` offline with `--require-hashes`,
   `--only-binary=:all:`, and `--no-deps`;
5. verifies wheel metadata and the complete locked transitive closure;
6. vendors dependency files into the provider package.

User dependency declarations are not left in provider `requirements.txt`, so a
provider cannot redownload or reinterpret them. Provider-owned runtime
dependencies remain exact platform package inputs.

## Deterministic Package Pipeline

```text
owner-scoped v1 binding
  -> immutable manifest and normalized source
  -> contract and digest validation
  -> locked pure-Python dependency files
  -> platform runtime boundary
  -> registered AWS, Azure, or GCP adapter
  -> fixed-time, fixed-mode deterministic ZIP
  -> package digest and redacted evidence
  -> Terraform digest-checked package reference
```

The user source bytes are copied without rewriting. AWS owns
`lambda_function.py`, Azure owns `function_app.py`, and GCP owns `main.py`.
Each wrapper calls the same `process(payload, configuration, context)`
entrypoint in-process and applies the same input, output, response-size,
timeout, safe-error, retryability, invocation-ID, and correlation-ID contract.

Package evidence contains relative paths and digests, never source text,
secrets, environment values, or local absolute paths. Terraform receives a
validated operational package path only after evidence has been read back
inside the project boundary.

The deployment boundary deliberately stops before Terraform unless a bound
package has a reviewed deployment-component catalog mapping. Phase 8.3 now
provides that mapping for `processor.telemetry@1` on AWS, Azure, and GCP. The
runtime path remains inactive until the later profile resolver phases, so a
validated but unresolved package still cannot be treated as active user logic.

## Limits

The current `processor.telemetry` slot applies:

| Limit | Value |
|---|---:|
| source archive / provider package | 10 MiB |
| expanded source | 2 MiB |
| individual source file | 2 MiB |
| source entries | 64 |
| path depth | 8 |
| dependencies | 64 |
| runtime response | 1 MiB |
| invocation duration | 30 seconds |
| runtime memory declaration | 256 MiB |
| validation duration | 5 seconds |
| package-build duration | 120 seconds |
| owner source downloads | 5 per minute |

Limits are enforced by repository validation and package construction. Source
downloads use the shared production Redis-compatible limiter, fail closed when
that security control is unavailable, and emit source-free audit events.
Provider resource declarations must remain compatible with the registered
slot.

## Adding Or Changing A Slot

1. Add a reviewed schema and registry version; do not mutate a deployed
   semantic contract in place.
2. Keep user-editable configuration scalar, typed, bounded, and explicitly
   `secret: false`.
3. Define closed input/output schemas, capabilities, resource limits, and all
   three provider adapter mappings.
4. Add positive fixtures plus missing-field, additional-field, duplicate,
   unsupported-version, digest-mutation, secret, limit, dependency, binding,
   and provider-equivalence failures.
5. Update canonicalization and generated-copy digests.
6. Extend Management, Deployer, Flutter live/demo adapters, product docs, and
   offline integration coverage together.
7. Map the slot to a reviewed deployment component in the architecture-profile
   catalog before a new architecture profile can require it.

## Safe Verification

Run in repository-provided environments with no cloud credentials:

```bash
python scripts/sync_user_function_extension_contracts.py --check
python -m pytest tests/unit/test_user_function_extensions.py -q
python -m pytest tests/test_user_function_extension_contract.py -q
flutter analyze
flutter test
terraform -chdir=3-cloud-deployer/src/terraform fmt -check
./thesis.sh test deployment-contract
./thesis.sh test frontend-integration
docker compose --profile docs run --rm docs mkdocs build --strict
```

The dependency tests use a local wheelhouse or mocked approved fetch boundary.
Provider-wrapper tests are offline. Do not add live provider credentials,
Terraform apply, or paid API calls to this gate.
