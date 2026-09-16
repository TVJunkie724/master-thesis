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

## First AWS Core run: concrete pre-approval review

Reviewed offline on 2026-09-16 against implementation commit `08893423`.
The credential-free native mock plan for `core-small-local-aws` passed again.
Its current resource inventory contains **94 Terraform create entries**:
84 AWS resource/configuration entries, two local random values and eight
Terraform guards. This is not 94 running services or an account-bound Apply
plan. The fixture uses synthetic names, package bindings and image references;
real artifacts, device inputs and account bindings remain admission gates.

| Responsibility | Current concrete AWS resources |
|---|---|
| L1 | One IoT Thing, one IoT topic rule, one IoT command definition |
| Event Layer | Two provisioned Kinesis streams with one shard each; three consumers; one SNS FIFO topic; two SQS queues including the control DLQ; S3 telemetry failure storage |
| L2 and adapters | Ten Lambda functions in total: ingress, processing, processor extension, action extension, domain consumer, L3 reader and four Event Layer delivery functions; one Step Functions state machine |
| L3 | Two on-demand DynamoDB tables for raw/history rollup; one history S3 bucket with archive/expiry lifecycle; authenticated Lambda readback |
| L3 transfer | One ECS/Fargate task definition (1 vCPU, 2 GiB), one cluster, one scheduler, one VPC/subnet with public task IP and no NAT gateway |
| Image publication | One deployment ECR repository, one CodeBuild project and one build-context S3 bucket |
| Supporting configuration | Eight log groups, IAM roles/policies, Lambda permissions/event mappings, S3 encryption/public-access/lifecycle settings and networking bindings |

The ten Lambdas use ZIP packages. **Only the storage mover needs a custom
container image in this AWS-only Core case.** There is no processor container,
federation bridge image, TwinMaker, graphical L5 or Grafana deployment. The
legacy `L5-raw-history-reader` log-map key still denotes the L3 reader.

### Smallest useful first verification

Use one synthetic device/source and ten valid telemetry messages. Follow their
trace IDs through IoT ingress, the received stream, processing, the processed
stream, persistence and authenticated readback. Verify transformed values and
record provisioning, verification, delivery and destroy durations. This is a
resource-integration smoke test, not a throughput experiment. Merely invoking
the processing function directly does not satisfy it.

The first smoke test does not claim the later simulator/command roundtrip,
graphical access or elapsed-time archive transitions. Storage-transfer runtime
verification needs a deliberately aged, tiny fixture and one bounded task;
checking an S3 lifecycle rule is not proof that an archive transition ran.

Proposed supervision window: stop functional work and initiate cleanup by
minute 20 after the first mutation; aim to complete inventory reconciliation by
minute 30. These are proposed operator limits, not an implemented cloud spending
cap or a guarantee that asynchronous cleanup finishes on time. Failure to clean
up stops all subsequent scenarios and must be reported as residual exposure.

### Cost and execution blockers before approval

Do **not** deploy the current inputs as an unattended run. The existing schedule
is enabled every five minutes, permits six delivery retries and has a one-day
event-age window. The finite mover bounds input bytes, but has no explicit
wall-clock deadline in its entrypoint. The live plan must first bind a bounded
start/stop procedure for tasks and scheduling, plus the actual image publication
procedure. Creating a CodeBuild project does not imply that a build has run.

No verified total cost ceiling is claimed yet. The pinned Frankfurt rate card
gives only a partial illustration: two shards at USD 0.018/shard-hour yield
USD 0.036 per hour **before** consumers, requests, compute, storage, logs,
publication and network charges. It is not a run quote. The actual three
enhanced-fan-out consumers require their own billing review: AWS charges
consumer-shard hours and retrieval in provisioned mode ([Kinesis pricing](https://aws.amazon.com/kinesis/data-streams/pricing/)).
Fargate charges from image download until task termination and may also incur
public IPv4 and logging charges ([Fargate pricing](https://aws.amazon.com/fargate/pricing/)).
Build duration is separately metered ([CodeBuild pricing](https://aws.amazon.com/codebuild/pricing/)).
Immediate deletion does not waive the 30-day Standard-IA or 180-day Deep Archive
minimum storage charges on affected objects ([S3 pricing](https://aws.amazon.com/s3/pricing/)).
Do not infer credits, a free tier or a total cap from the monthly optimizer
estimate. Keep both Core budget and execution approval unset until these
quantities are bounded and the final regional billable inventory is priced.

Cleanup order: stop the test sender and scheduler; stop/wait for run-owned ECS
tasks and builds; destroy the isolated Terraform state; then inspect run-owned
IoT bindings, streams/consumers, queues/topics, functions, tables, buckets,
registry images, logs, IAM and networking including task ENIs. Preserve existing
account resources and credentials. Retain only sanitized measurement evidence.
