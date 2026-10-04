# Core telemetry results

Status: consolidated offline on 2026-10-04; **9/9 functional passes**.
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
Next: prepare the [bounded AWS/Azure L4 check](../../plans/2026-10-04_poc_l4_evaluation.md).
Research questions remain unchanged; GCP L4/L5 stay excluded without replacement.
