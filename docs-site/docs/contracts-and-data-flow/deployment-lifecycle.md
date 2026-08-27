# Deployment lifecycle

```text
editable draft
    |
    v
cost calculation + immutable resolved graph
    |
    v
CloudConnection selection
    |
    v
readiness -> confirmed bounded preparation -> readiness
    |
    v
deployment review + confirmation
    |
    v
durable Deploy operation
    |
    v
infrastructure probes + telemetry roundtrip + access handoff
    |
    v
explicit confirmed Destroy + residual inventory
```

Management creates a one-use operation package from the selected calculation,
canonical architecture digest, typed Twin configuration and transient provider
credentials. The Deployer validates that package against the same graph before
building Terraform inputs. It does not accept a user-authored Terraform project
as the application workflow.

Deploy and Destroy have idempotency, correlation, persisted progress and one
authoritative terminal result. SSE carries live updates; reconnect resumes the
recorded operation rather than repeating it.

A deployed Twin is immutable. Editing infrastructure, changing provider
allocation or replacing user source requires a new draft created by Duplicate
or typed Export/Import. Re-deploying the same Twin is allowed only after its
successful Destroy.

Shared account prerequisites are recorded separately from Twin-owned
resources. Destroy removes the latter and reports retained prerequisites or
residual failures explicitly.
