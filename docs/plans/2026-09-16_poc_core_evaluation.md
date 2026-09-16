# Bounded Core evaluation: L1–L3 + Event Layer

## Decision and boundary

Implement the approved separation as one fixed research-only Terraform scope,
`core`, beside the unchanged `full` default. Core has no L4/L5 provider placement,
resources, Twin projection consumer or Twin-directed federation route. It retains
L3 storage readback. No Terraform `-target`, generic partial-deployment framework,
new architecture profile, UI or relaxation of full-profile admission is needed.

The standalone offline preparer materializes three local and six directed Small
Core scenarios using existing sizing and transport definitions. Directed scenarios
place ingestion at the source and Event Layer, processing and storage at the
destination; this definition is separate from the full-profile matrix and must
not inherit its cost/evidence approvals. Generated inputs are incomplete until
runtime artifacts and an exact supervised plan have been reviewed. They are not
a deployment-ready manifest or a replacement for the Management admission path.

## Implementation and checks

1. Add a fixed Terraform scope guard; reject nonempty L4/L5 placements and
   non-Core routes in Core. Keep the full default unchanged.
2. Remove Twin projection fan-out and publication in Core, including remote
   delivery and its IAM. Retain ingestion, processing, persistence, readback,
   lifecycle storage and core event/control transport.
3. Materialize the nine Small Core input sets offline; no credentials, image
   publishing, live API calls or invented deployment-ready evidence.
4. Run credential-free Terraform mock plans for all nine scenarios, negative
   scope checks, affected runtime tests and existing full-path regressions.
5. Record results and limitations. Before any live mutation, review resource
   inventory, real pinned images, account prerequisites, cost ceiling, time
   limit, destroy and residual inventory for one exact scenario.

## Evidence interpretation

RQ1: reproduce provisioning/configuration and cleanup for the explicitly scoped
Core. RQ2: compare the same Core responsibilities across all three providers;
AWS/Azure L4 and L5 remain separate later evaluations, GCP L4/L5 excluded.
RQ3: measure scoped eventing and actual run costs; do not reuse full-profile
estimates or interpret omitted L4/L5 as zero-cost implementations.

There have been no complete workload E2E runs to repeat. Existing live federation
probes remain historical identity evidence; changed routes/bindings require
current preflight and runtime checks. Affected offline tests/mock plans are
rerun now. The first scoped workload run still needs explicit approval.

## Reproduction and handoff

Run the following from the repository root in the existing Deployer development
environment (Python with the repository's dependencies):

```sh
python scripts/prepare_core_evaluation.py --output-dir /tmp/thesis-core-inputs
```

The directory must not exist. Omitting `--scenario` prepares all nine cases;
`--scenario core-small-local-aws` prepares only that baseline. Each case contains
a digest-bound research description and a separate non-secret Terraform input
file. No generated image digest is invented. The preparer does not read account
credentials, create a full deployment manifest, call Terraform or publish images.

The current scope is a standalone research preparation/infrastructure path, not
a new Management deployment option. Before live execution: build the changed
runtime packages/images, bind reviewed immutable images and account inputs,
derive the exact plan and cost/time/cleanup limits, then obtain explicit approval.
Use a separate state/project for each scoped run; do not switch an existing full
deployment to Core (that could plan deletion of its access-layer resources).
Destroy and residual inventory remain mandatory immediately after every run.
Local/mock validation does not prove cloud capacity, actual data transfer or
successful cleanup. GCP Core still includes its existing L1 GKE broker; omitting
L4/L5 does not make Core free.

## Status

Implemented and offline verified:

- 1,725 Deployer unit tests passed, including suppression of Twin publication
  in the AWS, Azure and GCP runtimes.
- Native Terraform mock plans passed for all nine Core scenarios, the eight
  existing full-configuration regressions and four negative cases (21 plans).
  They verify retained ingestion, processing and L3 readback, absent access
  resources/consumers/outputs, and rejection of wrong scope, larger capacity
  or incomplete return routes. The enclosing five-test suite passed.
- 33 Optimizer/contract tests and 45 research-script/contract/gate tests passed
  (the latter include 24 additional subtests). Full-profile readiness remains
  blocked; no Core description is promoted to an RTA/RDS deployment manifest.
- 20 Management contract/persistence tests passed against the refreshed fixtures.
- Updated runtime source digests and generated contract copies are synchronized.
  Changed-Python lint, Terraform formatting and strict documentation build pass.

Mock plans use synthetic image references only inside tests. Pinned Terraform
providers were downloaded, but no cloud credentials or workload APIs were used.
The complete 14-stage release gate, Flutter suite and live E2E were not run.
No live deployment or paid evaluation is authorized by this document.
