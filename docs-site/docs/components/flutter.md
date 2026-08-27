# Flutter UI

Flutter presents the research workflow and calls only the Management API. It
does not calculate costs, infer provider topology, validate credentials itself,
or contact Optimizer/Deployer ports.

## User responsibilities

The current UI groups four information responsibilities, which may span more
than four routes:

1. Twin scenario and typed bounded configuration;
2. cost result, exclusions, assumptions, trace, and immutable review;
3. deployment CloudConnection selection, readiness, confirmed preparation,
   and repair;
4. Deploy/Destroy operation progress, access handoff, verification, and
   cleanup evidence.

The architecture screen reads one canonical contract. It has no profile or
objective selector. Pricing snapshots are calculation evidence, not an
administration workspace.

## State ownership

Riverpod composes application dependencies and simple global state. Route- or
feature-scoped BLoCs own multi-step commands, retry behavior, concurrent
response protection, operation replay, and one-time secret consumption. A
mutable concern has one state owner.

## Credential behavior

CloudConnection entry/import is write-only. Flutter retains only the returned
label, provider, scope, auth kind, and validation/readiness state. Users may
select among multiple named deployment connections. Repair presents typed
manual guidance or replacement-connection actions when automation is not safe.

## Deployment behavior

The client catches up persisted operation events before reconnecting SSE. A
refresh cannot trigger a second provider command. Access cards open real
provider-managed L4/L5 URLs and show the required identity/authentication
method. Only a service-local one-time Viewer value may enter transient state.

## Safe verification

`flutter analyze`, the full widget/unit suite, the architecture checker, and
Web/native release builds are ordinary offline gates. The deterministic demo
uses the same interfaces but is not live-cloud evidence.
