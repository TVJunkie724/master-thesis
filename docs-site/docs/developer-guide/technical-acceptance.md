# Technical PoC Acceptance

Acceptance date: **2026-11-04**. The bounded technical artifact is accepted
with the evidence limits below. No new paid cloud run was used for this final
acceptance. Research questions and the agreed PoC scope remain unchanged.

## Frozen artifact

- Annotated acceptance tag: `thesis-poc-2026-11-04`. Resolve its exact final
  documentation commit with `git rev-parse thesis-poc-2026-11-04^{commit}`.
- Application source: `a82ca0e4532a917170644db3b493eeec463caa2c`, adding only
  the exact-decimal UI repair to the previously integrated source. The prior
  `master` merge is `dae336438b4e5bed13efbd478c61443df6859c43`; the release
  tag also includes this acceptance documentation. The 2026-11-07 publication
  retains this frozen tag and adds the thesis/editorial reconciliation on
  `master`; application behavior is unchanged.
- Architecture: `six-layer-eventing@1`, resolved architecture v2. GCP L4/L5
  remain excluded; AWS/Azure use native L4 and real Managed Grafana for L5.
- Flutter **3.44.0** (`559ffa3f75e7402d65a8def9c28389a9b2e6fe42`), Dart **3.12.0**,
  Web and macOS ARM64 host builds. Dependency locks are retained in Git.
- Frozen model artifact: `docs/research/evaluation/poc-cost-model-results.json`,
  SHA-256 `bbb22c30acf5d352110d0113dfb4779c36d15edbe27226d7d5eb8df4b5828265`.
  Its embedded provider catalog references pin the exact inputs; no prices
  were refreshed. The final Small comparison is **18.67% modeled savings**
  for AWS with GCP Eventing versus AWS local, not measured billing savings.

## Acceptance evidence

| Boundary | Observed result |
|---|---|
| Local lifecycle UI | Latest destroyed AWS Twin loads, shows COMPLETE recorded cleanup and immutable-definition guidance; no live access or deployment is initiated. |
| Browser portability | Real browser ZIP download → real file chooser upload → imported Configuration Workspace → reload passed against the local Management API. |
| Data fidelity | Manifest hashes pass; re-exported definition equals the source apart from the name, including one user function and nine populated Deployer fields. Result and all three credential bindings are cleared. The source is unchanged. |
| Failure and test cleanup | Invalid ZIP displays `Portable Twin archive contract is invalid` and creates no Twin. Only the new local test draft is removed through Management API; GET returns 404 and refreshed UI no longer lists it. |
| Final Flutter regression | **843 unit/widget tests passed**, analysis and architecture gate passed; Web/macOS release builds passed. Four actual persisted Management response DTOs additionally decode successfully. |
| Unchanged companion services | Full 2026-11-02 baseline: Management 717 passed; Optimizer 470 passed/5 skipped; Deployer 2,305 passed/1 skipped. The final repair changes only Flutter models/tests. |
| Reproducibility baseline | Four contract synchronization checks, 24 byte-identical model results (22 priced, two excluded), strict docs and the 42-page Docker/pdfLaTeX thesis build passed on 2026-11-02. |

The manual check found a real UI defect: equivalent decimal strings ending in
`030` and `03` were rejected as inconsistent. The repair compares normalized
decimal strings exactly, without floating-point tolerance; different values,
malformed representations and mismatching currencies still fail. Ten new
regressions cover these cases. No layout, API, BLoC or cloud behavior changed.

## Cleanup observation

The **2026-11-04 read-only GCP/federation check** found **zero active matches**
and **five inactive workload identity pools in `DELETED` state**. Logging buckets,
providers of active pools and service accounts have no matching residuals.
The query covers retained experiment prefixes, known Logging locations plus
global, and the selected project's IAM collections; it is not a global account
inventory. Inactive tombstones are explicitly retained as such, not called a
strict zero-marker result. No restore, deletion or paid query job was issued.

The latest independent AWS observation remains **2026-11-01: zero in all 24
checked categories**, including deletion markers. Azure's dated scoped cleanup
and resource-group observations retain their original scope. This acceptance
does not relabel those earlier checks as fresh three-provider inventories.

## Research and coverage limits

- **RQ1:** immutable deployment/operation evidence, timing records, portability
  and cleanup support operationalization. The browser archive chain is now
  directly observed; earlier missing interactions remain historical.
- **RQ2:** three provider-local and six directed **Core** paths have live
  evidence. AWS/Azure L4, simulator/command roundtrips and real Grafana charts
  have additional dated observations. These are not nine full-profile UI E2E
  runs at one revision. The final AWS Grafana repair was verified in place.
- **RQ3:** exact frozen model outputs and provisional account-level bills are
  distinct. No precise incremental cost or causal Event-Layer saving is claimed.
- The continuous local UI Open → live provider-login → chart path remains
  separately qualified: controlled Open tests and real provider charts passed,
  but no new continuous live observation was made after resources were removed.
  Cross-cloud command permutations and excluded GCP L4/L5 are not inferred.

Detailed dated results and failures are retained in
[`application-closeout-results.md`](https://github.com/TVJunkie724/master-thesis/blob/master/docs/research/evaluation/application-closeout-results.md).
Screenshots, response checks, read-only inventory and SHA-256 manifests remain
in ignored local evidence, outside the release. Credentials are never included.

For local reproduction use the existing [startup instructions](setup.md) and
[quality gates](testing.md). `./thesis.sh demo --setup` is offline;
`./thesis.sh up --setup` starts the integrated local workflow. Provider Deploy,
Destroy or a new live experiment is not part of this acceptance procedure.

## Publication and preservation — 2026-11-07

The final publication merges the accepted source into `master` and publishes
the original annotated tag without replacing it. Evaluation, Discussion and
Conclusion now include the observed browser portability check; RQ wording,
live-coverage boundaries and model values are unchanged. The updated thesis
build passes with 42 pages; changed pages were visually inspected. The frozen
model reproduction still passes with the existing dependency image and network
disabled. The host Python installations lack the required `jsonschema` package;
that environment failure is not a model-result discrepancy.

A separate encrypted local backup retains **15,315 evidence files** with
source-file hashes. Reproducible `.terraform` and `__pycache__` directories are
excluded and symlinks are not followed. Full decryption and every archived
member hash were verified. The backup also receives the published source bundle
and final thesis PDF. The encryption key stays separately in the ignored local
secret directory; neither raw evidence nor the key enters Git. This is a
separate directory on the same Mac, not an off-device backup service.
