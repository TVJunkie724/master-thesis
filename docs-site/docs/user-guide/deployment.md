# Deployment And Verification

Deployment actions live on the twin overview after configuration. The UI uses the
Management API; it never uploads files directly to or starts operations on the Deployer.

## Before Deploy

Confirm:

- twin is `configured`, `destroyed`, or recoverable `error`;
- selected architecture is current;
- required deployment CloudConnections are present and validated;
- configuration/artifacts pass validation;
- deployment preflight is successful and not stale;
- a previous operation is not already active.

## During An Operation

The UI receives a session and SSE URL from the Management API. Progress is correlated
to persisted deployment history. Leaving the page does not make the operation disappear;
return to status/history instead of starting a duplicate.

## After Deploy

Inspect:

- final twin and operation status;
- the typed Layer Access section with one independent L4 semantic-Twin surface
  and one L5 raw/rollup Grafana surface;
- structured Terraform outputs (with sensitive values redacted);
- provider/resource verification results;
- operation log history;
- data-flow verification phases where supported;
- simulator controls only after required provider material exists.

Layer Access is available from persisted `five-layer-baseline@2` or
`six-layer-eventing@1` deployment evidence. Historical Five-layer v1 returns an
explicit unsupported state, and destroyed Twins expose no active links. Open
requires the provider resource and interactive binding to be ready; content
and data-probe status are shown independently so one degraded layer never
disables the other or Destroy.

AWS access uses Identity Center, Azure uses Entra ID, and GCP L4 uses IAP. GCP
Grafana alone offers an explicit Viewer-password rotation. Its one-time value
is not part of Terraform outputs, is not persisted by Flutter, and is discarded
when the reveal dialog closes. Provider-console sign-in is not proven by the
credential-free local gate and remains a supervised live check.

## Failure And Retry

An error preserves operation records and last error. Read the correlated log and
readiness/preflight state before retry. A failed deploy may still have created resources;
do not assume `error` means nothing exists. Destroy uses retained Terraform/runtime state
and explicit confirmation.

Mock deployment endpoints are development-only and require the test-route capability.
They exercise UI state/log handling without contacting providers, but they are not
live-cloud evidence.

The Layer Access integration uses the same quarantine: a temporary local
Management API and SQLite database exercise all nine L4/L5 provider pairs for
both active profiles, owner isolation, redaction, destroy, and rotation
concurrency without starting Optimizer, Deployer, Terraform, or a provider API.
