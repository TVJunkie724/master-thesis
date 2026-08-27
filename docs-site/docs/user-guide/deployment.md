# Deployment and Verification

Deployment actions appear after a calculation is selected and current
graph-derived readiness succeeds.

## Before Deploy

Confirm the immutable calculation/graph, selected connection labels and
scopes, preparation evidence, estimated cost guardrail, region, maximum
duration, and cleanup plan. Every provider mutation requires an explicit
confirmation.

## During Deploy or Destroy

Management creates one durable operation. The UI catches up persisted progress
and then follows SSE. Leaving or refreshing the page does not cancel the
operation or authorize a duplicate.

## After Deploy

Review:

- terminal operation and resource-probe status;
- the defined telemetry roundtrip result;
- typed L4 semantic-Twin and L5 raw/rollup access information;
- provider URL, authentication kind, assigned identity and readiness;
- bounded redacted technical outputs and correlated errors.

Provider browser sign-in is an external live step. A service-local one-time
Viewer credential is shown only when that deployed access surface actually
uses one; Flutter discards it after use.

## Destroy and cleanup

Destroy is explicit and uses retained state. Its terminal evidence separates
removed Twin resources, retained shared account prerequisites, and residual
failures. A failed Deploy may still require Destroy. Never infer an empty
provider account from a local `error` state.

Mock operations and offline access fixtures test UI/contract behavior but are
not live-cloud evidence.
