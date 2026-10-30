# Core telemetry results

Historical checkpoint: consolidated offline on 2026-10-04;
**9/9 functional passes**. Renewed observations are recorded separately below.
Scope: L1–L3 plus Event Layer, ten real ingress messages per successful run and
ten expected values at authenticated destination hot-storage readback.
This is not nine complete-profile E2E passes.

Source: the [Core execution record](../../plans/2026-09-16_poc_core_evaluation.md),
including its dated successful runs, failed attempts and retained private
evidence. This summary does not overwrite any original report.

## Successful observations

Durations are seconds, rounded to one decimal. Apply excludes preceding image
foundation/publication and the separately listed Kubernetes stage. Destroy
excludes preceding Kubernetes removal and subsequent independent inventory.
Verification includes sending and polling, not only application processing.
Do not sum these columns and label the sum total deployment/lifecycle time.

| Source → destination | Messages | Main Apply | Kubernetes Apply | Verification | Terraform Destroy | Message-to-persistence sample (s) |
|---|---:|---:|---:|---:|---:|---|
| AWS → AWS | 10/10 | 98.8 | n/a | 56.0 | 71.8 | Not recorded individually |
| Azure → Azure | 10/10 | 668.8 | n/a | 209.2 | 782.6 | Ten samples retained; range not consolidated here |
| GCP → GCP | 10/10 | 791.5 | 139.0 | 19.0 | 542.9 | Ten samples retained; range not consolidated here |
| Azure → AWS | 10/10 | 541.5 | n/a | 32.9 | 228.8 | 25.508–26.602 |
| AWS → Azure | 10/10 | 668.2 | n/a | 148.6 | 889.3 | 58.4–146.7 |
| AWS → GCP | 10/10 | 604.9 | n/a | 26.6 | 443.3 | 21.3–23.8 |
| Azure → GCP | 10/10 | 941.7 | n/a | 48.3 | 479.3 | 35.9–37.8 |
| GCP → AWS | 10/10 | 471.4 | 136.9 | 19.5 | 561.7 | 14.5–15.6 |
| GCP → Azure | 10/10 | 654.1 | 116.6 | 220.3 | 948.4 | 46.8–218.8 |

Each row represents one successful integration observation, not repeated
benchmark trials. Azure's local run uses the documented warm HTTP condition;
other freshly deployed paths have different readiness/cold-start conditions.
Cross-provider timestamps depend on clock alignment. Neither verification
duration nor persistence latency is an isolated Event Layer latency.
Do not infer provider performance rankings or a causal multi-cloud penalty.

Resource creation/destruction observations are retained separately from phase
times: the older AWS local logs yielded 186 records, Azure local retained 194,
Azure→AWS 308, GCP→AWS 356 and GCP→Azure 364. These are lifecycle observations,
not counts of unique deployed services. Other runs retain their measurements in
their original records; no missing count or timestamp is fabricated here.

## Cleanup and cost interpretation

The successful runs were destroyed and independently inventoried with zero
active run-owned residuals at their recorded checks. Provider-managed inactive
Logging/identity/IoT deletion markers are separate from active resources and
can keep strict tombstone-free all-clear false. These observations are dated,
not a fresh global account inventory.

For GCP→AWS, the original inventory omitted the reverse-route GCP identity
pool. Its original `green=true` report is retained, but the corrected independent
inventory is authoritative: zero active residuals and one `DELETED` pool.
GCP→Azure likewise retains one deleted pool. Functional reruns are not needed
solely to wait for physical deletion.

Provider-billed costs remain pending run attribution. Planning allowances,
technical reserves and monthly account totals are not actual per-run costs.
Failed attempts, image publication and cleanup must be included when later
reporting the cost of obtaining a result, separately from a successful attempt.

## Research interpretation and remaining evidence

- **RQ1:** real provisioning, packages/images, configuration, verification,
  failures and cleanup establish the bounded operational evidence chain.
  Failure corrections remain visible in the execution record.
- **RQ2:** all nine paths meet the same ten-message telemetry/readback assertion.
  This does not establish command return, storage-tier transitions, Twin
  projection, graphical visualization or the complete simulator workflow.
- **RQ3:** topology and persistence observations are available; billed cost
  attribution and comparable isolated Eventing effects are not established.
  The Five-layer reference remains an offline baseline, not a paired live trial.

The older AWS local run lacks individual persistence samples and later structured
phase timestamps. Its functional result stands, but a matched nine-case latency
distribution cannot be claimed. No automatic rerun of all nine cases is planned.
Follow-up: the [bounded AWS/Azure L4 check](../../plans/2026-10-04_poc_l4_evaluation.md)
has passed separately for both providers, including cleanup and zero active
inventory. Its synthetic local-adapter projection is not Event-to-L4 delivery.
Subsequent separately scoped observations are summarized below.
Research questions remain unchanged; GCP L4/L5 stay excluded without replacement.

## Consolidated claim coverage — 2026-10-09

This checkpoint combines observations, not deployments. Passing adjacent cuts
does not prove their composition through the ordinary application workflow.

| Responsibility / claim | Actual evidence | Permitted conclusion / limitation |
|---|---|---|
| L1–L3 + Event telemetry | Nine successful cases above; ten inputs each | Three local and six directed telemetry paths; not full-profile E2E |
| Local command return + exact L3 | AWS attempt 05 (`f505bb69`), Azure 08 (`c806f134`), GCP 02 (`13fbdb99`) | One correlated receipt per provider; 13.646645 / 38.264408 / 28.965664 s, not a distribution |
| Event→L4 | AWS 03 (`86d46701`), Azure 04 (`974e96b5`) | Actual deployed consumers and authenticated state readback; local edges only |
| Graphical L3→L5 | AWS/Azure 03 (`1d82debe`; Azure runner `f6b426bb`) | Three exact seeded raw and hourly points, two panels, unauthorized access rejected; not simulator→L5 |
| Normal L5 application implementation | `49fa9fc0`; offline contracts, API, UI, native mock plans and builds; later AWS run below | AWS/Azure implemented; complete normal Azure run not claimed |
| Normal application deploy/reconnect/composed roundtrip | [AWS application observation](application-closeout-results.md), runtime `cd4e7b39` | Actual UI start, one operation across reconnect, downloaded simulator/command/L3/Event→L4/L5 pass; supplementary identity cleanup and Destroy retry; popup rendered from unchanged returned HTML, not captured as an independent popup |
| Directed command return / cross-cloud L4 / tier transitions | No scoped successful observation | Explicitly unverified, no inferred equivalence |
| GCP L4/L5 | Deliberately excluded | Scope finding, not a negative service-capability proof |
| Costs | Dated account/subscription billing and [reproduced frozen model](poc-cost-model-results.md): eight placements, three workload sizes | Conditional modeled ranking/scale sensitivity; no per-run attribution, paired live FiveLayer comparison or causal Event-Layer savings claim |

Detailed revisions, failed attempts and timings remain in the
[integration record](../../plans/2026-10-04_poc_integration_closeout.md) and
[L5 record](../../plans/2026-10-05_minimal_l5_evidence.md).
AWS command tombstones were absent at the October 5 afternoon reconciliation.
Azure successful cuts had strict zero inventory. GCP's recorded inactive Logging
deletion markers are not active resources; their later expiry has not been
rechecked here. None of these historical checks is a current global inventory.

RQ1 is supported by actual supervised provisioning and lifecycle observations,
including one normal AWS composed functional path with its stated UI/cleanup
conditions. RQ2 supports the named
contracts under their conditions, not product-level service equivalence.
RQ3 requires separating modeled monthly allocations, account billing and the
cost of failed attempts. Successful cuts alone cannot isolate the Event Layer's
causal cost effect. Missing data stay missing rather than triggering broad reruns.

## Renewed Core observations — 2026-10-20

The following observations use the existing bounded research runner, not the
complete Management/UI lifecycle. All successful rows assert ten distinct real
ingress messages and exact authenticated hot-storage values. L4/L5 and command
return are disabled for this cut. The historical nine-case matrix above remains
unchanged; these observations are not nine newly completed full-profile tests.
Seconds below have the same phase boundaries as the historical table.

| Source → destination | Runtime/source revision | Main Apply | Kubernetes Apply | Verification | Delivery/readback | Terraform Destroy | Total supervised | Resource timing records |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| GCP → GCP | `f5173e7b` | 726.180 | 125.860 | 17.429 | 17.237 | 541.682 | 1796.543 | 236 |
| AWS → Azure | `f5173e7b` | 422.390 | n/a | 148.443 | 148.176 | 956.601 | 1767.472 | 322 |
| Azure → AWS | `af17dcf7` | 412.080 | n/a | 32.236 | 28.269 | 232.055 | 881.984 | 310 |
| AWS → GCP | `19a54ae2` | 559.767 | n/a | 61.303 | 61.000 | 447.716 | 1502.229 | 302 |
| Azure → GCP | `38730a79` | 836.227 | n/a | 41.691 | 37.039 | 468.661 | 1649.577 | 298 |
| GCP → AWS (retry) | `674a05ad` | 470.102 | 85.690 | 29.650 | 18.460 | 537.452 | 1510.136 | 358 |
| GCP → Azure | `f4b24b43` | 550.196 | 95.824 | 185.447 | 176.252 | 967.514 | 2126.159 | 366 |

Total supervised time additionally includes initialization, foundation/image
publication, readiness, Kubernetes removal where applicable and final inventory.
Resource timing records count creation and deletion completions, not distinct
services. Revision differences include documentation-only commits and the
explicit inventory/reader corrections described in the
[execution record](../../plans/2026-08-26_thesis_poc_execution_plan.md).

The first GCP→AWS attempt is retained as failed: its stream reader stopped on
an empty Kinesis page although the ten exact hot-storage values had arrived.
The corrected reader follows bounded shard cursors; the fresh retry additionally
verified ten received and ten processed records with unchanged value/quality
assertions. No application architecture change was required. This retry does
not erase the first attempt's 1,568.380 s lifecycle or its resource/cost history.
Two GCP-local supervisor failures occurred before reservation or cloud mutation
and remain separate from the successful local observation.

Every completed row has successful Destroy and zero active run-owned residuals.
Only Azure→AWS was strict-zero at its original check. Other rows retain inactive
provider Logging, IoT Command and/or deleted federation-pool markers. A shared
independent inventory correction added the previously omitted AWS→GCP pool;
its original report is preserved and a supplementary scoped check found that
pool already deleted. Inactive-marker follow-ups must not rewrite observations
or require new functional deployments. All seven renewed Core cases passed
functionally and were destroyed. GCP→Azure used 22 readback polls without
transport timeouts; its final inventory found only a deleted federation-pool
marker, not an active resource or Entra object.

A terminal read-only follow-up rechecked all eight deployed attempt namespaces,
including the failed first GCP→AWS attempt, using current credentials and
original-plan account/project/region scope. All eight checks completed without
inventory errors and found zero active residuals. The same inactive markers
remain; Azure→AWS alone is strict-zero. The follow-ups are separate records,
not replacements for the original observations or a global account inventory.

These measurements support RQ1 lifecycle/recovery and RQ2 scoped functional
comparability. Delivery/readback includes readiness, network and polling effects;
it is not isolated Event Layer latency. RQ3 still requires separating estimates,
account billing and actual run attribution. No performance ranking, causal cost
saving or complete cross-provider UI qualification follows from these rows.
