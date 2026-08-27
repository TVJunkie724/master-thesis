# Supervised Six-layer live evaluation

Status: planned and offline-validated; no live execution is claimed.

## Purpose

The live evaluation answers the research questions with the smallest useful
deployment set. It is a cross-stack thesis protocol, not a Deployer component
test suite. The canonical scenario input is
`small-scenario-matrix.json`.

The matrix contains three provider-local baselines and six directed
multi-cloud focus cases. Every AWS/Azure/GCP direction is the primary focus of
one case. The focus edges cover the three contracts that permit cross-cloud
placement: canonical domain events, storage transitions, and Twin projection.
The provider-local baselines verify raw-history queries on AWS, Azure, and GCP;
the optimizer's mandatory hot-storage/visualization co-location is checked
offline as a negative cross-cloud case. Incidental reverse or additional
cross-cloud edges remain part of the recorded graph but do not create extra
scenarios.

## Execution boundary

Live execution remains disabled until all of the following are present for one
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

The normal application continues to deploy only the cost-selected candidate.
Explicit candidate selection is evaluation-only and must not become a public
profile or provider-override feature.

Before any live authorization, one planned candidate can be reproduced from
the pinned catalogs without provider access:

```bash
python scripts/materialize_live_evaluation_candidate.py \
  small-focus-aws-to-azure --output /tmp/candidate.json
```

The output contains the exact candidate, cost ledger, RTA and RDS and is marked
`offline_planned_candidate`. It is an input to budget review, not deployment or
live evidence. The strict public workload model rejects an
`evaluationCandidateId`; only the repository evaluation utility can bind it.

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
normal application outputs and does not execute an operation itself.

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
8. reconcile provider inventory and observed cost before starting the next
   scenario.

No scenario may be left active merely to speed up the next one. Shared account
capabilities are recorded separately from Twin-owned resources.

## Evidence record

Each executed scenario must produce a secret-free evidence directory with:

- input, pricing, candidate, graph, RDS, and manifest digests;
- account scopes and region labels without credential values;
- readiness, preparation, confirmations, and operation correlation IDs;
- Terraform plan/apply timestamps and terminal status;
- reconnect/replay observation;
- access-surface readiness and telemetry trace result;
- Destroy result, provider inventory, and residual classification; and
- budget cap, observed cost, deviations, and limitations.

An unresolved provider blocker is a valid result. Offline or mocked success is
never substituted for missing live evidence.

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
| L4/L5 access | secret-free `deployment-access` response; any one-time credential value is excluded |
| Telemetry roundtrip | persisted data-flow verification record |
| Cleanup and residuals | terminal Destroy operation and its typed `cleanup-evidence.v1` output |
| Observed cost | separately exported provider billing evidence after Destroy |

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
