# Management API Development Guide

The Management API is the application boundary. Flutter calls only this
service; Optimizer and Deployer are internal dependencies.

## Ownership rules

- route modules perform transport/authentication and delegate;
- repositories own database queries;
- application services own lifecycle and transaction boundaries;
- typed clients own internal HTTP adaptation;
- public errors are bounded, stable and redacted;
- encrypted CloudConnections contain deployment credentials only;
- the Optimizer never receives deployment credential material;
- a successful calculation atomically persists result, trace, resolved graph
  and deployment specification;
- deployment readiness and packages bind to exact graph/connection digests;
- deployed Twin definitions are immutable.

## Canonical architecture

New Twins receive one automatic `six-layer-eventing@1` digest pin. Public API
reads expose the canonical contract and a Twin's pin; there is no profile
catalog, selector, preview, mutation, inheritance, or registration boundary.

## Local workflow

From the repository root:

```bash
./thesis.sh up --setup
./thesis.sh test backend
```

Or run the isolated service suite:

```bash
cd twin2multicloud_backend
APP_ENV=test PYTHONPATH=. python -m pytest -q
```

Use an isolated SQLite database and test-only application secrets. Ordinary
tests must not read provider credentials or run provider commands.

## Contract rules

1. Public request models reject unknown fields.
2. Flutter-authored configuration never becomes calculation/deployment
   evidence without server validation.
3. Pricing values remain in the Optimizer; Management persists exact immutable
   references.
4. Credential values are absent from responses, events, logs, archives and
   durable retry payloads.
5. Operation commands are idempotent and one mutation is active per Twin.
6. Verification and cleanup results remain distinguishable from operation
   transport success.
7. OpenAPI snapshots are regenerated after public contract changes.

## Upload and interchange safety

Typed Twin archives and individual configuration/user-function uploads use
bounded size, path, type and schema checks. They cannot contain credentials,
Terraform state, arbitrary executable project structures, or secret outputs.

Live deployment tests can create billable resources. They are never part of
the default Management test gate and require separate supervision.
