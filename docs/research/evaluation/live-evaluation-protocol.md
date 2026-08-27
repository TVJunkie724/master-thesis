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
