# Supervised Six-layer live evaluation

Status: planned and offline-validated; bounded account preparation is verified,
but no Twin workload deployment is claimed.

## Purpose

The live evaluation answers the research questions with the smallest useful
deployment set. It is a cross-stack thesis protocol, not a Deployer component
test suite. The canonical scenario input is
`small-scenario-matrix.json`.

The matrix contains three provider-local baselines and six directed
multi-cloud focus cases. Every AWS/Azure/GCP direction is the primary focus of
one case. The focus edges use the two contracts implemented as cross-cloud PoC
boundaries: canonical domain events and Twin projection. Hot, cool, archive,
and visualization form one provider-local storage/read bundle; the two storage
transitions and raw-history query remain versioned contracts but are not
cross-cloud deployment choices. Incidental reverse or additional cross-cloud
edges remain part of the recorded graph but do not create extra scenarios.

## Current prerequisite checkpoint

On 2026-08-29, the supervised account-level gate completed without Terraform
Apply or workload-resource creation. AWS identity, Region, regional STS, IAM
Identity Center, and 108 required permissions are ready. Azure subscription,
Regions, Microsoft Graph authority, all 16 required resource providers, and all
eight permission groups are ready. The GCP project, billing check, Region, all
18 Six-layer APIs, and all 80 project-testable permissions are ready.

The secret-free local summary is
`.evidence/provider-bootstrap-2026-08-29/provider-free-final-readiness.json`
with SHA-256
`f8dbf103e4b0878ba1d16375d61872594b968576ae034a3a947860eb67c926a4`.
Because `.evidence/` is intentionally ignored, a different checkout must obtain
the supervised evidence separately and verify this digest. These results do
not satisfy the remaining image, quota/capacity, L4/L5, directed federation,
or scenario records.

## Execution boundary

Scenario Apply remains disabled until all of the following are present for one
scenario:

1. an immutable Small workload digest;
2. an Optimizer candidate and cost trace matching the exact assignments;
3. a graph, RDS, manifest, and preparation-plan digest;
4. a reviewed numerical budget cap and maximum runtime;
5. real CloudConnection selections and a passing or honestly blocked
   graph-derived readiness result;
6. explicit Apply and Destroy confirmations; and
7. an external timer plus a named operator responsible for residual cleanup.

The checked matrix is validated in its current non-executable state with:

```bash
python scripts/validate_live_evaluation_plan.py --require-state planned
```

After all nine numerical budget caps have been reviewed, the tracked plan must
record `status: approved_for_supervised_execution` and
`execution_enabled: true`. Before any provider action, the operator then runs
the same validator with `--require-state ready`. This transition validates the
plan only; it never replaces the distinct Apply and Destroy confirmations.

The normal application continues to deploy only the cost-selected Small
candidate. Small uses the published static sizing bounds and becomes
deployable only after the independent graph-derived account preflight;
Medium/Large calculations remain evaluation-only until their explicit live
capacity gates are demonstrated. Runtime capacity observations for Small are
evaluation outputs, not impossible preconditions to the first deployment.
Explicit candidate selection remains an operator-only evaluation hook and
must not become a public profile or provider-override feature.

Before any live authorization, one planned candidate can be reproduced from
the pinned catalogs without provider access:

```bash
python scripts/materialize_live_evaluation_candidate.py \
  small-focus-aws-to-azure --output /tmp/candidate.json
```

The output contains the exact candidate, cost ledger, RTA and RDS and is marked
`offline_planned_candidate`. It is an input to budget review, not deployment or
live evidence. The strict public workload model rejects candidate overrides;
only the disabled-by-default Management evaluation endpoint can pass the
repository-validated internal binding to the Optimizer.

The complete nine-scenario handoff is materialized into a new, non-overwriting
directory with:

```bash
python scripts/materialize_live_evaluation_candidate.py --all \
  --output-dir /tmp/six-layer-live-candidates
```

The directory contains one digest-bound candidate file per checked scenario
and `candidate-pack-manifest.json`, including the calculated monthly totals
used for the separate budget review. The totals are estimates, not approved
Apply caps, and materialization still performs no provider or Deployer call.

After the tracked matrix is approved, all nine budget caps are set, and the
candidate pack has been regenerated against that exact plan digest, build one
non-overwriting Management request offline:

```bash
python scripts/build_supervised_evaluation_request.py \
  --candidate-pack /tmp/six-layer-live-candidates \
  --scenario-id small-focus-aws-to-azure \
  --output /tmp/small-focus-aws-to-azure.request.json
```

The command validates the ready plan and candidate pack and performs no HTTP
or cloud call. During the supervised session, the operator temporarily enables
`SUPERVISED_EVALUATION_ENABLED`, posts that body to the owner-scoped
`/twins/{twin_id}/optimizer-runs/supervised-evaluation` endpoint, then disables
the hook again. The resulting calculation run is selected and processed by the
same preflight, Apply, replay, access, verification, Destroy, and cleanup path
as a normal cost-selected run.

Final metrics are accepted into the evidence index only when their provider
scope equals the exact candidate placement and every checkpoint provider
matches the candidate's component assignment. This prevents measurements from
a different deployment from being attached to a valid candidate digest.

Create the non-overwriting, not-started evidence index beside the future
evidence files:

```bash
python scripts/manage_live_evaluation_evidence.py create \
  --candidate-pack /tmp/six-layer-live-candidates \
  --output /tmp/six-layer-live-evidence/evidence-index.json
```

After recording only redacted artifacts from the supervised workflow, validate
the index and every referenced file digest with:

```bash
python scripts/manage_live_evaluation_evidence.py validate \
  --candidate-pack /tmp/six-layer-live-candidates \
  --record /tmp/six-layer-live-evidence/evidence-index.json
```

The evaluation-only schema is
`schemas/live-evaluation-evidence.schema.json`. It fixes three provider checks,
all six directed identity exchanges, and the nine scenario records. A completed
scenario cannot validate without readiness, Terraform plan, Apply, replay,
access, telemetry, Destroy, cleanup, and provider-cost artifacts. A blocker is
valid only when it is explicit and evidence-backed; an Apply followed by a
blocker still requires Destroy and cleanup evidence. This index references the
normal application outputs and does not execute an operation itself. A
completed scenario has exactly one artifact of every required kind. Its cleanup
artifact must be a clean `cleanup-evidence.v1` record covering the exact
candidate providers, and its observed-cost value must name the one indexed
provider-cost export.

## Cost-efficient order

For each required provider and directed route:

1. run identity and read-only readiness probes;
2. validate pinned runtime images;
3. exercise the minimum short-lived workload-identity exchange and remove its
   probe resources;
4. review the full Small Terraform plan and budget cap;
5. deploy exactly one scenario;
6. verify operation replay, access handoff, and one telemetry roundtrip;
7. destroy immediately; and
8. reconcile provider inventory before starting the next scenario and attach
   observed provider cost when the provider billing export becomes available.

No scenario may be left active merely to speed up the next one. Shared account
capabilities are recorded separately from Twin-owned resources.

### Component probes before complete scenarios

Component probes and final scenarios are different measurement datasets, not
different public deployment modes. A component record uses
`run_kind: component_probe`; it cannot satisfy, replace, or be relabelled as
one of the nine final scenario records. Provider-local and directed multi-cloud
final records use `run_kind: provider_local` and
`run_kind: directed_multicloud` and bind to the exact candidate evidence
digest.

The Deployer intentionally exposes one atomic graph-bound Apply/Destroy path.
Adding a generic layer-targeted Apply or maintaining provider-specific
Terraform target lists would enlarge the PoC and weaken cleanup guarantees.
The first provider-local deployment for each provider therefore supplies both
an early component dataset and, only if it passes, the final scenario dataset;
it does not create the infrastructure twice. The supervised order is:

1. provider, image, account, and regional prerequisites;
2. Apply the approved provider-local Small candidate;
3. immediately verify L1-L3 plus Eventing and record the component dataset;
4. on a missing checkpoint, stop and Destroy without exercising L4/L5;
5. otherwise verify L4 queryability, then L5 access as separate gates;
6. only then run the complete simulator protocol and record the final dataset;
7. Destroy, reconcile inventory, and proceed to the next provider-local or
   directed scenario only when cleanup is clean.

This ordering cannot avoid creating L4/L5 during the atomic Apply, but it
minimizes their billable lifetime when a cheaper upstream gate fails and avoids
three additional deployments. The later six directed scenarios reuse the same
gate order without adding separate component records unless diagnosing a
blocker.

GCP-L1 retains an additional observed-capacity gate. Its previous three-replica
`e2-standard-8` Small broker allocation has been replaced offline by one
non-HA `e2-standard-4` broker node plus one `e2-standard-2` adapter node. The
early L1-L3/Eventing stage of the GCP provider-local run must validate that 1+1
allocation before L4/L5 and the final simulator protocol continue. The
capability decision (bidirectional MQTT through BifroMQ with Pub/Sub
durability) remains separate from the still open observed-capacity evidence.

### Minimal PoC diagnostics

The application reuses provider-native logs; it does not introduce a separate
monitoring platform. A `TRACE-*` or `VERIFY-*` message may emit the payload-free
`diagnostic-checkpoint.v1` record at a bounded set of stages. Ordinary Twin
traffic does not emit these records, and a checkpoint contains identifiers,
stage, provider, component, status, and timestamp only—never telemetry or
credential payloads.

For the inexpensive component trace, the active graph requires this forward
path:

```text
l1_accepted
  -> event_layer_durable
  -> l2_started
  -> l2_completed
  -> l3_hot_persisted
```

CloudWatch log groups, every active Azure Log Analytics workspace, and the GCP
Cloud Functions, Cloud Run, worker-pool, and GKE log resource types are queried
read-only for the correlation identifier. The trace completes early when the
full path is observed. A timeout, unavailable provider query, or missing stage
produces a `partial` result with the exact missing checkpoints; the UI must not
turn this into an unqualified success.

The same record vocabulary includes L4 queryability and the command/receipt
path for later supervised probes. Those stages are not claimed by the cheap
L1-L3 trace. L5 is intentionally a supervised access observation: the operator
opens the returned provider URL, authenticates through the declared access
mode, and confirms that the fixed dashboard can query the test point or show a
typed no-data state. Twin2MultiCloud does not administer that dashboard. L4
data-flow verification, L5 access evidence, command receipt, and provider
inventory remain separate evidence sources in the live protocol.

Infrastructure diagnosis stays similarly bounded: Terraform state classifies
L1, the independent Event Layer, L2, L3, L4, and L5; provider SDK checks cover
the resources that cannot be established honestly from state alone. Existing
stable error codes, operation IDs, persisted deployment logs, SSE replay, and
cleanup evidence provide the failure context. Continuous alerting, dashboards,
log retention beyond the short PoC window, and automatic incident remediation
remain outside scope.

## Evidence record

Each executed scenario must produce a secret-free evidence directory with:

- input, pricing, candidate, graph, RDS, and manifest digests;
- account scopes and region labels without credential values;
- readiness, preparation, confirmations, and operation correlation IDs;
- Terraform plan/apply timestamps and terminal status;
- reconnect/replay observation;
- access-surface readiness and telemetry trace result;
- one validated `live-evaluation-metrics.v1` measurement document;
- Destroy result, provider inventory, and residual classification; and
- budget cap, observed cost, deviations, and limitations.

An unresolved provider blocker is a valid result. Offline or mocked success is
never substituted for missing live evidence.

## Structured measurement protocol

Functional verification and descriptive measurement are separate. One
successful message proves that a path is reachable; it does not establish a
latency distribution. Unless a reviewed run record states otherwise, each
required direction therefore uses five warm-up messages followed by 50
measured messages with the same payload and cadence.

Every successful trace carries one non-null event identifier unchanged across
all primary stops. The simulator, application, and provider observations record
timestamps for the applicable path stops:

```text
telemetry:
simulator_sent
  -> l1_accepted
  -> event_layer_durable
  -> l2_started/l2_completed
  -> l3_hot_persisted
  -> l4_queryable

command/receipt:
command_issued
  -> event_layer_command_durable
  -> l1_command_published
  -> simulator_command_received

provider delivery outcome (separate durable evidence, not device execution):
command_issued
  -> outcome_event_durable
  -> outcome_persisted/outcome_queryable
```

The exact expected path is declared per metrics document so a component probe
does not pretend to cover absent downstream stages. A successful sample must
contain that complete ordered path. Failed and timed-out samples retain their
partial path and a typed failure code.

The `command_receipt` measurement ends at `simulator_command_received`. The
persisted provider-delivery outcome proves accepted/failed handoff separately
and is not presented as a portable arbitrary device-action result. AWS
additionally records its native IoT Command terminal response; Azure and GCP
are compared at the common receipt boundary.

When the same command trace contains provider-delivery outcome checkpoints,
the metrics record retains them as `auxiliary_stages`. They do not alter the
ordered command-receipt path or its latency calculation.

The clock source and maximum observed skew are checked within the recorded run
window. Unsynchronized clocks invalidate the measurement. Every metrics record
is also bounded to the plan's 60-minute maximum runtime and must contain Plan,
Apply, Destroy, and inventory-reconciliation measurements. A component probe
adds at least the readiness phase it actually exercises; a final scenario
records infrastructure, L1-L3/eventing, L4, and L5 readiness, including honest
failed or skipped states. Terminal cleanup evidence is mandatory even when a
functional phase fails.

The result reports:

- end-to-end mean, p50, p95, and maximum latency;
- consecutive-stage mean, p50, p95, and maximum latency;
- success, failure, timeout, retry, duplicate, ordering, and DLQ observations;
- Terraform plan, Apply, readiness, L4/L5 readiness, Destroy, and inventory
  reconciliation durations;
- deployed provider resources and SKUs;
- approved budget, calculated monthly estimate, and later observed incremental
  provider cost; and
- cleanup residuals and explicit limitations.

The evidence validator accepts only bounded UTF-8 JSON, JSONL, CSV, log, or
text artifacts (maximum 8 MiB each). Besides path and digest validation, it
rejects sensitive JSON/CSV fields and recognizable private keys, access keys,
tokens, and connection secrets. Credential files, binary archives, raw
Terraform state, and one-time access values must never be copied into the
evaluation directory.

Latency is an evaluation metric only. It does not re-enter the Optimizer as an
objective or weighted score.

The schema is
`schemas/live-evaluation-metrics.schema.json`. Validate one or more recorded
runs without cloud access:

```bash
python scripts/manage_live_evaluation_metrics.py validate \
  --record /tmp/six-layer-live-evidence/<run>/evaluation-metrics.json
```

Generate deterministic CSV tables and dependency-free SVG charts into a new,
non-overwriting directory:

```bash
python scripts/manage_live_evaluation_metrics.py summarize \
  --record /tmp/six-layer-live-evidence/<run>/evaluation-metrics.json \
  --output-dir /tmp/six-layer-live-evaluation-summary
```

For the final thesis comparison, pass all nine final metrics files as repeated
`--record` arguments and add `--require-complete-matrix`. The batch gate rejects
duplicate runs or scenarios, missing or unexpected matrix entries, and mixed
architecture contracts, source revisions, workload/simulator digests, or
measurement protocols. Component probes may be summarized separately and do
not count as final matrix evidence.

The generated `run-summary.csv`, `stage-latency.csv`, `lifecycle.csv`,
`resources.csv`, `cost-observations.csv`, `end-to-end-latency-p95.svg`, and
`lifecycle-duration.svg` remain derived artifacts. The digest-bound JSON
measurement document is the primary evidence. A delayed provider-cost export
is either recorded atomically with value, interval, and source path, or left
entirely pending; it never delays Destroy or cleanup.

Assemble the primary metrics document from one reviewed metadata template, one
explicit sample plan, and one or more copied provider/simulator checkpoint logs:

```bash
python scripts/manage_live_evaluation_metrics.py collect \
  --template /tmp/six-layer-live-evidence/<run>/metrics-template.json \
  --sample-plan /tmp/six-layer-live-evidence/<run>/sample-plan.json \
  --checkpoint-log /tmp/six-layer-live-evidence/<run>/checkpoints.jsonl \
  --output /tmp/six-layer-live-evidence/<run>/evaluation-metrics.json
```

The collector is offline, refuses to overwrite output, rejects unplanned traces
and duplicate or unexpected stages, accepts plain and provider-wrapped JSON log
records, and validates direction, provider scope, clocks, stage/layer mappings,
and run-time bounds before writing. It does not query a cloud or start a
simulator.

### Existing evidence sources

The supervised operator collects the evidence from the normal owner-scoped
Twin workflow; there is no second product-like evaluation orchestrator:

| Evidence | Canonical source |
|---|---|
| Input, workload, pricing, allocation, cost trace, RTA and RDS | candidate pack plus the selected Optimizer run and its pricing-evidence response |
| Account scopes | secret-free CloudConnection metadata; never the imported credential payload |
| Graph-derived readiness | `deployment-preflight` response and cached `deployment-readiness` response |
| Reviewed account changes | digest-bound `deployment-preparation` request and response |
| Apply/Destroy correlation and replay | deployment history, bounded persisted logs, and the owner-scoped SSE stream with `Last-Event-ID` |
| L4/L5 access | secret-free `deployment-access` response plus supervised L5 open/query observation; any one-time credential value is excluded |
| Telemetry roundtrip | persisted data-flow verification record |
| Timing, reliability, resources and measurement protocol | one schema- and semantics-validated `live-evaluation-metrics.v1` document; component and final runs remain distinct |
| Cleanup and residuals | terminal Destroy operation and its typed `cleanup-evidence.v1` output |
| Observed cost | one indexed provider billing export whose path is bound from the metrics document after Destroy; provider-dependent delay does not postpone cleanup or keep a scenario active |

Apply and Destroy are initiated only from their distinct confirmed UI actions
during the supervised run. The API operation and stream IDs are retained as
the correlation evidence; screenshots are optional supporting evidence, not a
substitute for the persisted operation result.

### Phase 8 boundary

The application already owns read-only provider preflight and reviewed account
preparation. It deliberately does not own a generic cross-provider identity
laboratory. The six minimal federation probes are therefore a supervised
evaluation activity against the exact Terraform/runtime identity contracts,
performed before the full scenarios and immediately cleaned up. Each probe
records provider-native success or an explicit blocker plus residual-resource
evidence. A full Twin deployment must not be used to relabel a missing
standalone prerequisite probe as successful.
