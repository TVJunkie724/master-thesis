---
title: "User-Function Extensions"
description: "Prepare, validate, and bind provider-neutral Python user logic in the Configuration Workspace."
tags: [user-guide, user-functions, configuration, validation]
lastUpdated: "2026-07-19"
---

# User-Function Extensions

The **Prepare deployment > User logic** task accepts a provider-neutral Python
source archive. You provide domain logic and non-secret configuration. The
platform owns the AWS, Azure, or Google Cloud handler, deployment resource,
permissions, endpoints, and Terraform wiring.

The current reviewed slot is **Telemetry processor**
(`processor.telemetry`). It runs on the platform-selected Python 3.11 runtime.

## Prepare The Archive

Create a ZIP with these files:

```text
process.py
requirements.lock
```

Additional `.py` modules are allowed. `requirements.lock` is required but may
be empty.

`process.py` must define:

```python
def process(payload, configuration, context):
    value = payload["value"] * configuration["scale_factor"]
    return {"value": value, "quality": "accepted"}
```

The telemetry payload requires numeric `value` and may contain a short `unit`.
The result requires numeric `value` and `quality` equal to `accepted` or
`suspect`. The current form requires a non-secret **Scale factor** from 0
through 1000.

Do not include:

- AWS, Azure, or Google Cloud SDK calls;
- cloud handlers, resource names, URLs, IAM, or Terraform values;
- passwords, tokens, private keys, secret references, or credential files;
- nested ZIP/wheel files, native binaries, symlinks, or executable files;
- unpinned `requirements.txt` content.

## Lock Dependencies

If the function has no external packages, leave `requirements.lock` empty. For
each package, use an exact version and the SHA-256 digest of its pure-Python
wheel:

```text
example-package==1.2.3 --hash=sha256:<wheel-digest>
```

Include every transitive package as a separate locked line. Validation rejects
version ranges, missing hashes, source distributions, native wheels, URLs,
local paths, editable installs, and unsupported package sources.

## Validate And Bind

1. Open the Twin and go to **Prepare deployment > User logic**.
2. Select **Choose source archive** and choose one ZIP.
3. Enter all configuration values shown for the slot.
4. Select **Validate**.
5. Expand **Validation details** to inspect the passed checks.
6. Save the Twin first if it does not yet have an ID.
7. Select **Bind validated artifact**.

Validation creates a digest-bound result but does not persist a mutable source
draft. Binding first creates or reuses an immutable artifact, then records an
append-preserving binding revision for this Twin. Changing the source or
configuration returns the panel to **Draft** and requires validation again.

The extension workflow is complete only when every reviewed slot has an active
binding. A stale binding revision or API failure is shown as an attention
state; retry only after reviewing the message and current binding.

The current prerequisite validates and packages the bound artifact, but a real
deployment fails closed until the reviewed architecture component catalog maps
that slot to an executable provider resource. This avoids silently deploying a
package that is not connected to the Twin data path.

## Legacy User Logic

Existing provider-specific source remains readable and downloadable as
`legacy_unvalidated`. It is never trusted automatically and cannot be selected
for a new deployment.

To migrate:

1. download the legacy source as its owner;
2. rewrite it to the provider-neutral `process` contract;
3. replace `requirements.txt` with a complete hashed `requirements.lock`;
4. upload and validate the replacement archive;
5. bind the new v1 artifact.

The old row remains unchanged for history. Existing frozen deployment packages
remain available for inspection or destroy operations. New deployment packages
never include legacy source.

## Troubleshooting

| Status or message | What to check |
|---|---|
| invalid archive | ZIP is non-empty, within 10 MiB, and contains only approved files |
| invalid entrypoint | `process.py` has exactly one top-level three-argument `process` function |
| dependency unpinned/forbidden | every package and transitive package has exact version and approved wheel hash |
| secret material detected | remove credentials, secret-like keys, values, references, and filenames |
| configuration invalid | complete required fields and respect their numeric, length, enum, or format limits |
| runtime unsupported | use the platform-selected Python 3.11 contract |
| binding unresolved/stale | reload the Twin, revalidate the current draft, and bind against the latest revision |
| extension timeout | reduce work so `process` completes within 30 seconds |
| response limit/invalid result | return only the registered output fields and stay below 1 MiB |

Errors expose a safe logical field and correlation ID. They do not return
source snippets, credentials, environment values, or local paths.
