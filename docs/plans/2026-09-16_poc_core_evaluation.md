# Bounded Core evaluation: L1–L3 + Event Layer

## Decision and boundary

Implement the approved separation as one fixed research-only Terraform scope,
`core`, beside the unchanged `full` default. Core has no L4/L5 provider placement,
resources, Twin projection consumer or Twin-directed federation route. It retains
L3 storage readback. No Terraform `-target`, generic partial-deployment framework,
new architecture profile, UI or relaxation of full-profile admission is needed.
The existing provider image-foundation targets remain part of image publication;
they are not used to implement the Core layer cut.

## Supervised live execution

### Follow-up on 2026-09-19

The independent AWS inventory became completely empty on 2026-09-17, including
the two formerly pending IoT Command definitions. The cleanup monitor was
stopped after that observation.

The next Azure attempt completed Core Apply in 610.4 s but still did not finish
authenticated readback. Repeated request timeouts therefore do not establish
that the previous failure was merely a cold start. The operator initiated
cleanup after the functional deadline: the original deadline raised Python's
`TimeoutError`, which an HTTP library can translate into a retryable request
timeout. The runner now raises a dedicated `RuntimeError` subtype, with a
regression check proving that HTTP retry handling does not swallow it.

The two Azure Python host packages also lacked the extension-bundle declaration
required for their Event Hubs and Service Bus bindings. The standard v4 bundle
reference is now included in both actual ZIP packages, and the source/catalog
digests are refreshed. This fixes a concrete prerequisite; it is not yet proof
of successful Azure readback. See the [Microsoft Event Hubs binding reference](https://learn.microsoft.com/en-us/azure/azure-functions/functions-bindings-event-hubs).

The first follow-up cleanup completed in 787.6 s with zero remaining resource
groups. A second Azure attempt completed Apply in 619.8 s but the reader still
timed out. Read-only inspection then identified a deployment collision: five
Flex apps shared one package container, whose root contained OneDeploy's
`released-package.zip` and `kudu-state.json`. The source ZIP paths were unique,
but that does not isolate the platform's active deployment files. Microsoft
requires a [separate deployment container per Flex app](https://learn.microsoft.com/en-us/azure/azure-functions/flex-consumption-how-to#configure-deployment-settings).
Each existing domain/extension app now receives its own private container;
the event runtime already had a separate one. This adds four small containers
to the local Azure Core case, not another storage account or compute service.
Native mock plans assert distinct deployment containers for all Azure apps;
source checks verify matching app and publisher references.
The defective live attempt was interrupted for cleanup before another retry.
These supervised diagnostic runs, including HTTP readiness probes, are not
cold-start benchmarks or replacements for the final evaluation samples.

Read-only retained GCP logs for the last failed run explicitly report
`image has non-numeric user` and `CreateContainerConfigError`. This confirms the
startup defect addressed by the numeric UID/GID correction; at that point the
subsequent workload still required its live test.

The subsequent GCP retry completed Google-resource Apply in 748.6 s and the
Kubernetes stage in 107.7 s. Direct read-only pod inspection confirmed both
broker and MQTT adapter Ready with zero restarts, so the numeric UID fix is
live-verified. Verification then stopped after 5.0 s in the client's initial
TCP connection attempt, before TLS/MQTT authentication or message submission.
This is not a passed Core smoke. The harness now retries only TCP timeout or
connection refusal at most 20 times, separated by three seconds and still
inside the existing whole-run deadline. TLS errors are not retried and
certificate verification remains enabled. Connection attempts/wait time are
retained on success or exhausted retries. This distinguishes transient external
load-balancer readiness from a persistent connectivity fault without changing
the deployed topology or extending the overall limit.

That GCP attempt removed Kubernetes resources in 84.5 s and completed Destroy
in 549.9 s. The original 14 inventory categories were empty. An additional
read-only check found the deployment's Cloud Logging bucket in
`DELETE_REQUESTED`, which the original inventory did not cover. The inventory
now includes active and pending-deletion log buckets separately. Google retains
this [deletion state for seven days](https://docs.cloud.google.com/logging/docs/buckets).
An empty active-workload inventory is therefore not a claim of complete physical
absence. Functional pass, accepted Destroy and provider-side final deletion
remain separate observations; a pending log bucket keeps strict overall `green`
false without requiring the functional test to be repeated after its expiry.
The second Azure cleanup completed in 756.5 s with zero resource groups.

The isolated-container Azure retry completed Apply in 596.6 s. A supervised
diagnostic change kept only the reader's HTTP group at one always-ready 2-GB
instance. Its health route then responded with authenticated HTTP 200 and
unauthenticated HTTP 401. The data query exposed a concrete Cosmos compiler
error (`SC1001`, reserved property `value`), so the attempt still failed and its
unchanged overall deadline initiated cleanup. The query now uses bracket
notation for reserved value/aggregate property names. The next **Core-only**
Terraform reader keeps one HTTP instance ready from provisioning; the full
profile stays unchanged. This is a warm resource-integration condition, not
a cold-start result. Record its additional billed baseline separately from
on-demand execution; the reader is destroyed with the run.

The next GCP retry completed Apply in 715.3 s and Kubernetes in 98.2 s, but
MQTT authorization failed after 6.6 s. Broker/adapter logs showed successful
HTTP calls to both authentication and authorization endpoints with a rejected
connection. The pinned [BifroMQ webhook source](https://github.com/apache/bifromq/blob/v4.0.0-incubating/build/build-plugin-demo/src/main/java/org/apache/bifromq/demo/plugin/WebHookBasedAuthProvider.java)
sends underscore identity headers that Werkzeug discards at the real HTTP
boundary. A local socket-based reproduction confirmed rejection with valid
configured identities; the previous Flask test-client checks bypassed this
boundary. The adapter now preserves only the two upstream webhook identity
headers and rejects ambiguous hyphen aliases. A real localhost HTTP regression
test covers accepted device/bridge identities and rejected missing, unknown
or ambiguous identities. No broker image, credentials or IAM roles change.

The following Azure attempt completed Apply in 656.9 s. The warm reader returned
authenticated HTTP 200 and a valid empty history response, confirming the query
correction, but no telemetry points arrived before the unchanged deadline.
Ingress, event-runtime and processor-extension apps still exposed zero registered
functions. One supervised trigger sync was accepted without changing that
observation. All six remote builds reported success. Offline imports of the
three downloaded deployed packages, with network disabled and the matching
Python/CPU platform, discovered their expected 2/4/1 functions. The remaining
Azure startup/registration cause is unresolved; this is not a Core pass.

Provider documentation exposed two further concrete Azure ingress defects:
the built-in IoT Hub Event Hubs-compatible endpoint does not support
[Entra ID authentication](https://learn.microsoft.com/en-us/azure/iot-hub/authenticate-authorize-azure-ad),
and the Terraform resource does not enable its fallback route when omitted.
The binding now uses a deployment-owned ServiceConnect-only policy and the
built-in `events` fallback route is explicit. The obsolete IoT Hub Data Reader
assignment is removed; other managed-identity connections remain unchanged.
This adds no Event Hub or other billed service and requires no user-entered key.
It fixes unsupported ingress configuration, not yet proven Azure startup.
Retained plans also show S1/one unit in the earlier runs: the runner's requested
F1 override affected legacy variables, not the Six-layer component. That inert
override and the inaccurate F1 claims are removed. Cost interpretation uses
the actual S1 resource and pending provider billing, not the intended override.

The next GCP attempt completed Apply in 790.7 s and Kubernetes in 96.5 s.
MQTT authentication passed, but readback returned Firestore `FailedPrecondition`:
the raw-history composite index sorted `stored_at` descending while the reader
queries ascending. Terraform now matches the reader, with a native-plan check.
The webhook timeline also showed the bridge connection/subscription only 22 s
after the device began publishing. The adapter's HTTP health endpoint previously
returned success before a subscription acknowledgement. It now reports readiness
only after QoS-1 SUBACK and clears readiness on disconnect/reconnect, using the
existing Kubernetes probes. Tests cover delayed/rejected acknowledgements and
reconnection. No additional service or generic retry framework is introduced.

The following GCP attempt exposed a readiness bootstrap dependency: the broker
authenticates through the adapter's private Service, but that Service originally
hid the endpoint until the adapter had obtained SUBACK. The auth Service now
publishes not-yet-ready endpoints, just as the broker's existing headless
bootstrap Service does. The device-facing listener and workload readiness remain
separate. This single setting was applied to the owned Service during the
supervised attempt and is covered by the native plan. Its deployment time includes
that diagnostic intervention and one adapter restart; it is not an unassisted
benchmark sample.

That attempt subsequently delivered all ten device messages to ingress, but the
processor rejected Event-Layer deliveries with
`EVENTING_CONSUMER_PROVIDER_MISMATCH`. Its runtime requires `L2_PROVIDER`, which
the processor's Terraform environment omitted even though the resolved placement
was correct. The service now receives that existing placement variable, and a
native mock-plan assertion checks the actual processor environment. This is a
wiring correction, not a changed runtime contract or additional resource.
The failed attempt entered immediate cleanup; successful end-to-end readback
still requires a fresh bounded run.

The next GCP retry failed earlier in Kubernetes creation: the adapter service
account and private auth Service raced namespace creation and received
`namespaces not found`. All eight namespaced L1 objects now reference the owned
namespace resource directly instead of repeating its local name. Terraform can
therefore enforce creation and reverse destruction ordering. A regression check
covers all eight references, alongside the native mock plans. The failed attempt
entered cleanup without claiming that its processor-provider correction had been
live-verified.

The Azure attempt with supported IoT ingress authentication completed Apply in
597.8 s but still reached the functional deadline without readback. Ingress,
event runtime and processor extension exposed no registered functions; existing
HTTP functions elsewhere remained registered. Destroy and independent inventory
confirmed zero remaining run resource groups.

Two small follow-up diagnoses reused the actual processor-extension package and
the existing OneDeploy module with just one disposable Function App, FC1 plan
and storage account. Both the on-demand and single-always-ready-instance cases
initially exposed zero functions and encountered host/trigger-sync timeouts.
They do not prove that a longer cold-start allowance or warming all Core apps
would fix Azure. Both diagnoses completed Destroy and zero-group inventory.
The remaining Azure startup cause is unresolved; no further full Azure retry
was started on the basis of these observations. The GCP namespace-race attempt
also completed Destroy with zero active residuals and one pending-deletion
Logging bucket; its functional path remains unverified after the latest fixes.

Before another Azure deployment, an offline check against the actual Azure
Python worker's function registry reproduced two registration failures that
plain SDK discovery had missed: the extension declared `request` while its HTTP
binding used the default `req`; Event Hubs batch handlers used `list[T]`, which
the tested worker rejected as a non-type annotation. The adapter now uses `req`
and all seven batch-handler declarations use the supported `typing.List[T]`.
The same offline registry then accepted the processor, all 12 enabled domain
functions and all seven enabled Event-Layer functions. Focused regression tests
cover binding/signature agreement and every batch declaration. This identifies
concrete package defects, not yet a successful live Core test; no resource,
permission, timeout or functional responsibility was changed by these fixes.

The next GCP run passed infrastructure/Kubernetes creation and delivered ten
messages to ingress. Processing then failed with `PROCESSOR_EXTENSION_FAILED`:
the extension had internal-only ingress, while its Cloud Run caller had no VPC
egress path. Read-only inspection confirmed that the processor's invoker grant
existed and public invocation was disabled. Google's
[Cloud Run networking rules](https://docs.cloud.google.com/run/docs/securing/private-networking#receive-requests-from-other-cloud-run-resources-or-app-engine)
require a VPC path for this internal-only service-to-service combination.
Terraform now permits endpoint reachability while explicitly keeping the IAM
check enabled and the existing service-account-only grants. The identical
domain-to-action configuration defect is corrected too; action execution is
not claimed by the ten-message Core smoke. No connector, NAT gateway or public
invoker grant is added. The attempted supervised correction was safely skipped
because cleanup had already begun; this failed run contains no live ingress
change. A native-plan regression covers reachability and retained IAM, and a
new bounded Core run is still required to verify this correction.

The subsequent Azure single-app comparison separated fixture and runtime issues.
Two diagnostic minimal ZIPs had owner-only file permissions, unlike the actual
project packages; retained host diagnostics reported access denied on `host.json`.
Those disposable groups were destroyed and their zero-group inventories recorded.
The corrected minimal fixture uses the existing deterministic ZIP writer (0644).
It registered one function, but bounded on-demand HTTP requests still timed out.
After enabling one always-ready HTTP instance in that same app, its expected
HTTP response passed. Replacing only the package with the corrected real
processor then passed registration and the first checked invocation, including
the expected transformed value and accepted quality. This is supervised warm
integration evidence, not a cold-start benchmark. The third comparison retains
the warm-setting intervention and both package digests/timings separately.

The next Core-only Azure configuration consequently keeps one HTTP instance ready
at processing, processor extension and reader. The latter already used this
condition; this adds two warm HTTP instances, not two new Function Apps. Full
profile configuration and non-HTTP trigger settings are unchanged. Maximum
on-demand scale-out remains one per function group; always-ready instances are
additional to that ceiling. Record the warm baseline separately in cost and
readiness interpretation, and remove all three with the run. Native mock plans
verify these exact Core HTTP settings. The subsequent live result is recorded
below.

The warm single-app comparison completed Destroy and independent zero-group
inventory. Application Insights had created an additional action group inside
the disposable diagnostic group; it was identified and removed before declaring
cleanup complete. No existing group or notification configuration was changed.

The subsequent Azure Core run passed the actual ten-message IoT Hub → Event
Layer → processing → Cosmos readback path. All ten expected values were returned,
and ten persistence-latency samples were retained. Apply took 668.8 s and
verification 209.2 s, with 24 readback polls and no readback request timeout.
All six apps registered their configured functions, including the formerly
missing ingress, Event runtime and processor extension. Immediate Destroy
completed in 782.6 s; independent inventory confirmed zero remaining run
resource groups. An additional group-name check found no separate managed
infrastructure group. Functional verification and cleanup are both green.
The run retains ten structured lifecycle phases and 194 Terraform resource
timing records, and uses the explicitly documented warm HTTP condition.

An offline audit of the earlier successful AWS smoke recovered 186 Terraform
create/destroy timing records from its retained logs, alongside its existing
phase and batch-delivery durations. The original report was not overwritten.
That older run did not retain ten individual source-to-persistence latency
samples or the later structured phase timestamps. Partial diagnostic checkpoint
pairs are not substituted for that missing distribution. AWS functional and
cleanup success stand; any later comparison requiring matched per-message
latency distributions must explicitly account for this evidence gap.

### Original run observations (2026-09-17)

The user authorized the three local Core smoke tests. This does not authorize
directed multi-cloud or L4/L5/full-profile execution. The sections below retain
the earlier pre-approval reviews; they are historical preparation evidence.

`scripts/run_core_evaluation.py` runs one provider with real runtime packages,
an empty-prefix inventory, a create-only account-bound plan, the existing image
publisher, full Core Apply, ten ingress messages, authenticated L3 readback,
Destroy and an independent inventory. Credentials/raw diagnostics/state stay
private. Cumulative allowance inputs are supplied externally; they are not
cloud billing measurements or a provider-enforced spending cap. The functional
deadline includes image publication and provisioning. Provider defaults are
10 minutes for AWS, 20 minutes for Azure and 30 minutes for GCP; an explicit
smaller override remains possible and no functional deadline above 60 minutes
is accepted. Cleanup is attempted on failure/interruption; host failure or
forced process termination still requires operator recovery from the retained
state. No unattended execution is claimed.

Every Core attempt retains UTC start/end timestamps and completed or failed
phase durations for initialization, baseline inventory, Plan, image foundation,
image publication, Apply, verification, Destroy and residual inventory. It also
extracts Terraform's create/update/destroy duration per resource address while
discarding provider resource IDs, and records Azure readback polling attempts,
request timeouts and wait duration. Individual resource timings are diagnostic:
provider reporting granularity differs, so the cross-provider thesis comparison
uses the lifecycle phases defined by the live-evaluation protocol. The external
allowance ledger remains distinct from observed provider billing.

Core keeps recurring movers disabled. Azure Flex and GCP Cloud Run scale-out
is limited to one instance per scaling group/revision for this tiny smoke test.
The supervised Azure smoke uses the resolved IoT Hub S1/one-unit component for
ten messages; it does not establish throughput evidence.

Initial AWS live attempts exposed and reproduced two lifecycle problems:
dynamic IoT Commands require a JSON-substitution preprocessor, and SNS FIFO
archives must be disabled before topic deletion. The first failed Apply was
fully cleaned after the SNS recovery. The next Apply succeeded and both event
streams contained all ten correlation IDs with accepted processor results,
but authenticated readback returned only nine rows: **not a passed E2E**.
The persistence retry path reused an event-only DynamoDB transaction token
across changing rollup writes. After correction, the third workload attempt
passed: ten messages in each event stream, accepted processor quality and ten
correct values through authenticated L3 readback. Foundation provisioning took
62.6 s, image publication 54.8 s, Core Apply 98.8 s, verification 56.0 s and
Destroy 71.8 s. Independent inventory found no active run resources. Two IoT
Command definitions from the final attempts remain inactive and pending
provider-side physical deletion.

Azure completed image publication and the full Core Apply in 627.7 s. All ten
messages were submitted through IoT Hub, but the first authenticated L3 reader
request hit a Flex cold start and timed out after 30 s. No successful readback
was recorded, so the run is not a functional pass. Destroy completed in 773.3 s
and the independent resource-group inventory returned zero. The reader polling
path now treats request timeouts as retryable within the bounded loop and records
the polling attempts, timeout count and wait duration. The provider-specific
functional deadline remains 20 minutes because the earlier failure was the
single-request timeout, not the whole-run limit. These corrections are
offline-tested but were not re-run live.

GCP completed image publication and the full Google-resource Apply in 805.8 s.
The second stage created the namespace, service account, two internal services,
configuration and secret, but the BifroMQ deployment did not become Ready before
the whole-run deadline. No MQTT messages were sent and no L3 readback is claimed.
Kubernetes removal took 39.4 s, Terraform Destroy 557.9 s, and all 14 independent
inventory categories returned zero. No speculative runtime change was made
without pod-level evidence. The GCP functional deadline is raised once from the
previous run's 25 minutes to 30 minutes so a bounded retry can distinguish a
slow rollout from the earlier whole-run cutoff. A second increase is not the
default response; another timeout requires diagnosis. This is not a claim that
the rollout problem is resolved.

The subsequent offline image/configuration check found one concrete startup
precondition: the pinned upstream image declares the named user `bifromq`
(UID/GID 1000), while the Pod previously set only `run_as_non_root`. Kubernetes
cannot verify a named image user numerically at admission/runtime. The broker
Pod now pins that existing UID/GID explicitly; no resource, topology, image or
capacity choice changes. This correction is offline evidence only until the
bounded GCP retry reaches a Ready Pod.

AWS IoT Commands have a provider-enforced deletion delay (normally 12 hours).
Report inactive `pendingDeletion` definitions separately from active resources;
an accepted Delete/empty Terraform state is not proof of physical absence.
Overall `green` remains false until the independent inventory is empty, even
if `functional_passed` is true. For RQ1, the runs establish repeatable AWS
deployment plus cleanup behavior and expose Azure cold-start and GCP rollout
latency as operational boundaries. For RQ2, only AWS currently proves the full
ten-message Core contract; Azure and GCP remain incomplete rather than being
treated as negative functional results. For RQ3, external run allowances are
not billing evidence and omitted retries are not zero-cost implementations.
No research question changes.

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

### Historical supervised Core preparation checkpoint

This subsection preserves the pre-execution checkpoint. The subsequent live
outcomes are recorded at the top of this document. Authorization did not turn
incomplete inputs into executable plans or permit unbounded retries; at this
historical checkpoint no workload Apply had run.

Implemented for `core` only; the complete-profile defaults remain unchanged:

- AWS storage scheduling disabled, delivery retries zero, CodeBuild timeout five minutes.
- Azure storage job manual-only, replica timeout five minutes, no retries;
  ACR publication timeout five minutes per image.
- GCP storage scheduling paused, scheduler/task retries zero, task timeout five
  minutes; Cloud Build timeout five minutes per image; disposable build-source
  bucket soft delete explicitly disabled.

These are provider-side bounds, **not a total spending cap or an implemented
experiment watchdog**. The AWS mover must not be manually started without a
supervised stop procedure. The first ten-message smoke test starts no mover.

`python -m scripts.prepare_core_runtime PROVIDER --output-dir NEW_DIRECTORY`
now prepares real runtime packages and the same validated processor example for
each local baseline. It does not register a device, publish an image, execute
Terraform or produce a full-profile manifest. Short resource prefixes are
separate from scenario IDs: the first account-bound Azure plan exposed that
`core-small-local-azure` exceeds Terraform's 21-character limit. The preparer
now emits `core-SOURCE-TARGET`; regression tests cover all nine names.

Read-only provider identity/permission checks passed for AWS, Azure and GCP.
Checked GCP Small quotas passed; resource-scoped permissions and Azure quotas
that require created resources are still Apply-time observations. Six custom
Linux/amd64 images built locally, and the pinned public BifroMQ image was pulled.
Local Docker image IDs are not registry manifest digests or image-pull evidence
from a deployed cloud resource. Registry publication remains pending.

Account-bound, non-mutating plans with real processor packages passed after the
name correction: AWS 93 create entries, Azure 72, GCP 110 before its Kubernetes
stage. The mock fixtures additionally include one synthetic AWS outbound-identity
guard; the complete GCP mock includes nine Kubernetes objects. These plans still
use explicitly unpublished image placeholders and **must not be applied**. No
workload resource or provider build was created. The external watchdog and
complete residual inventory remain the live-execution blockers, not credential
authority. In particular, the existing AWS fallback inventory does not cover
all retained Core services (including Kinesis, ECR/CodeBuild, ECS and Scheduler);
an empty Terraform state alone would not close that gap.

Verification: 434 Terraform-related unit tests plus the native five-test suite
(21 Terraform mock plans), and 15 Core input/runtime-preparation tests passed.
The publisher tests cover both unchanged full-profile and shortened Core build
timeouts. These are not three successful live E2E runs.

The provider reviews below describe the **pre-bound inventory/behavior**. Their
recurring-job and long-build findings are addressed above; the external
deadline, whole-run cost accounting, guaranteed cleanup attempt and complete
residual check still have to be connected to the live Core procedure. Existing
full-profile admission must not be bypassed to run this research slice.

### Earlier implementation checks

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

## Azure Core run: concrete pre-approval review

Reviewed offline on 2026-09-16 against implementation commit `08893423`.
The native mock plan for `core-small-local-azure` passed again: **73 Terraform
create entries**, comprising 62 Azure resource/configuration entries, two local
random values and nine guards. These are fixture counts, not running-service
counts or an account-bound Apply plan. Region: `westeurope`.

| Responsibility | Current concrete Azure resources |
|---|---|
| L1 | One resolved IoT Hub S1, one unit; ten messages in the supervised Core smoke. |
| Event Layer | One Standard Event Hubs namespace, one throughput unit, three hubs and three consumer groups; one Standard Service Bus namespace, one topic/subscription and filter |
| L2 and adapters | Six Flex Consumption Function Apps in total: processing, event adapter, processor extension, action extension, Event runtime and L3 reader; six FC1 plans because Flex permits one app per plan; one Consumption Logic App with its trigger/actions |
| L3 | One serverless Cosmos DB account/database/container; one storage account with three containers for history and runtime packages; archive/expiry lifecycle; authenticated Function readback |
| L3 transfer and publication | One scheduled Container Apps job (1 vCPU, 2 GiB, one replica), one environment and one Basic ACR |
| Supporting configuration | Two Log Analytics workspaces, nine supported diagnostic settings, two user-assigned identities and scoped role assignments in one deployment resource group |

The Functions use ZIP packages. **Only the storage mover needs a custom Azure
container image.** Its current publisher uses an ACR build task with a
1,200-second timeout; creating the registry does not build or verify an image.
There is no Azure Digital Twins, L5, Grafana or cross-cloud federation in this
local case. Reuse the approved deployment administrator; do not add another
credential/bootstrap model for this test.

Use the same ten-message verification as AWS, via the actual IoT Hub device
ingress, Event Hubs received/processed delivery, processing, Cosmos persistence
and authenticated readback. Record matching trace IDs and transformed values.
The first test does not claim command roundtrip or completed cool/archive
transitions. An aged fixture and one controlled storage execution remain a
separate verification step, not an unattended recurring workload.

### Azure blockers, price boundaries and cleanup

- The current mover is scheduled every five minutes, allows three retries and
  has a **1,800-second timeout per replica**, not per experiment. Repeated or
  overlapping executions can exceed the short smoke-test window. Before live
  approval, arrange no recurring execution during the first test and a bounded
  one-off procedure for the later transfer check. This is planned, not implemented.
- Function scale maxima (mostly 100, reader 20) are not prepaid instances or
  spending caps. Review retry/fan-out and log volume alongside the ten-message
  input limit. Do not silently change the reviewed Small service selection.
- Price one S1 unit using its daily unit billing, not ten-message pricing
  ([IoT Hub pricing](https://azure.microsoft.com/en-us/pricing/details/iot-hub/)).
  Include Event Hubs throughput, the subscription-level Standard Service Bus
  base charge, operations, Functions, Logic Apps, Cosmos, logs and storage;
  do not double-count an existing subscription base charge as incremental cost
  ([Service Bus pricing](https://azure.microsoft.com/en-us/pricing/details/service-bus/)).
- Include ACR tier/storage and actual build CPU time separately from the
  Container Apps execution ([ACR pricing](https://azure.microsoft.com/en-us/pricing/details/container-registry/)).
  Cool/Archive object deletion can still incur minimum-duration charges of
  30/180 days respectively; a quick Destroy does not waive these
  ([Blob access tiers](https://learn.microsoft.com/en-us/azure/storage/blobs/access-tiers-overview)).

Read-only prerequisites before a live proposal: verify subscription/region and
provider registration, S1/FC1/Container Apps availability and relevant quotas,
Cosmos serverless support, resource/IAM permissions and data-plane access for
package upload, device registration and readback. Treat missing prerequisites
as blockers; no automatic SKU upgrade or new principal. No live account checks
were performed for this planning update.

Cleanup: stop the sender and prevent new job/workflow starts; cancel or drain
run-owned job executions, workflow runs and ACR builds; destroy the isolated
state/resource group. Reconcile resource-group contents plus run-owned role
assignments, identities, registry artifacts, storage and retained/soft-deleted
resources. Do not delete shared applications, credentials or existing resources.
Use the same proposed 20-minute stop/30-minute cleanup target as AWS; include
publication and provisioning in the clock. No verified total cost ceiling yet.

## GCP Core run: concrete pre-approval review

Reviewed offline on 2026-09-16 against implementation commit `08893423`.
The native mock plan for `core-small-local-gcp` passed again: **120 Terraform
create entries**, comprising 93 Google resource/configuration entries, nine
Kubernetes objects and 18 local/random/TLS/guard entries. The fixture includes
the final Kubernetes stage; it is not merely the image/cluster foundation.
It does not prove cluster scheduling, image pull, device delivery or cleanup.
Region: `europe-west1`; the cluster is **zonal**, in `europe-west1-b`.

| Responsibility | Current concrete GCP resources |
|---|---|
| L1 | One GKE Standard cluster; one broker node (`e2-standard-4`, 50 GiB disk) and one integration node (`e2-standard-2`, 30 GiB disk); BifroMQ and MQTT adapter deployments; one external LoadBalancer service and reserved address |
| Event Layer | Five Pub/Sub topics and five subscriptions, including failure/control and MQTT command delivery; one Event runtime Cloud Run service |
| L2 and adapters | Eight Cloud Run services in total including Event runtime: processing, processor extension, ingress/domain/persistence adapters, action sink and L3 reader; one Workflows workflow |
| L3 | One deployment Firestore database with three composite indexes and seven field configurations; one Nearline history bucket with native Archive/expiry lifecycle; authenticated Cloud Run readback |
| L3 transfer | One Cloud Run job (Small: one task, 1 vCPU, 2 GiB), one Cloud Scheduler job |
| Image publication and support | One Artifact Registry repository, one build-source bucket, twelve service accounts and IAM bindings, one logging bucket/sink; Kubernetes namespace/config/secret/service account and three services in total |

There are **four custom image roles**: platform (shared by several runtimes and
the MQTT adapter), processor extension, Event runtime and storage mover. There
is also the existing digest-pinned public BifroMQ image. These are executable
payloads inside the Terraform-provisioned resources, not substitutes for testing
their wiring. The mock uses synthetic image references; real build/pull checks
and digest recording remain pending. The current publisher builds sequentially
in Cloud Build, with a 1,200-second timeout per image: four such limits are not a
bounded short experiment. Bound/review publication separately before admission;
no builds were submitted here.

Use the same ten messages through **MQTT/TLS → BifroMQ → MQTT adapter → ingress
and Pub/Sub → processing → processed delivery → Firestore → authenticated
readback**. Do not substitute direct Pub/Sub publication: that would omit the
L1 provisioning/connectivity being evaluated. L4/L5 exclusion does not remove
this L1 cluster, and it is not evidence that GCP Core is serverless-only.

### GCP blockers, price boundaries and cleanup

- Price the cluster, both nodes and their disks, address/load balancer and
  controller-created networking, including transient default-node-pool creation.
  The default pool is removed; the two retained pools are not multiplied over
  three zones. GKE's USD 0.10/cluster-hour management fee is only one component;
  node compute is separate. Assume no available free-tier credit
  ([GKE pricing](https://cloud.google.com/kubernetes-engine/pricing)).
- Include Cloud Run, Pub/Sub, Firestore/index operations, Workflows, Scheduler,
  logging, network traffic, registry storage and build duration. Eight Cloud Run
  service definitions are not eight constantly running instances; their scaling
  settings still do not impose a total spending cap.
- The storage job has a 900-second task timeout and one retry. Its five-minute
  scheduler has a separate retry allowance; that is not a global execution
  bound. Prevent recurring starts and bound one-off execution before approval.
- Nearline/Archive objects have 30/365-day minimum storage durations and can
  incur early-deletion charges ([Cloud Storage pricing](https://cloud.google.com/storage/pricing)).
  History soft delete is explicitly disabled in the template, but the build
  bucket has no explicit setting. Resolve its effective policy before uploading
  artifacts: the service default is seven days, so ordinary deletion alone may
  leave billable retained bytes ([soft delete](https://docs.cloud.google.com/storage/docs/soft-delete)).
  Any change must be limited to the disposable run bucket, not project-wide policy.

Read-only prerequisites: required APIs already enabled, project/billing scope,
regional CPU/disk/address and GKE quotas, node machine availability, default
network/IP capacity, organization-policy compatibility, Artifact Registry/build
and deployment permissions, named Firestore database/index limits and runtime
invoker bindings. Check Kubernetes endpoint reachability after authorized cluster
creation. Quota availability is not a capacity reservation. No live account
checks were performed for this planning update.

The existing deployment lifecycle has image-foundation, runtime/cluster and
post-cluster Kubernetes stages. Their review and cleanup must be explicit in
the eventual Core run procedure; the offline preparer does not execute them.
Do not bypass full-profile admission or emulate Core with ad-hoc `-target`.
All stages, including publication, count toward the approved time/cost envelope.
Keep the proposed 20-minute stop/30-minute cleanup target for the first attempt;
if GKE setup consumes the window, record a provisioning result and clean up,
rather than extending it silently or claiming functional success.

Cleanup: stop the sender/scheduler and cancel run-owned Cloud Run executions,
workflow executions and builds. Remove the run-owned Kubernetes LoadBalancer
service while its cluster/controller still exists and confirm its generated
network resources are released; then destroy the cluster/node pools and remaining
isolated state. Inspect compute instances/disks, forwarding rules/backend and
health-check resources, addresses/firewalls, Cloud Run, Pub/Sub, database, buckets
(including retained objects), registry, logs, service accounts and IAM. Controller
children are not all individual Terraform entries. Preserve the existing project,
shared APIs/network and credentials. Residual cost exposure blocks the next run.

## Shared next step and approval gate

Azure and GCP planning adds no new product feature or test framework. Both local
mock plans passed (two runs, zero failures); application/infrastructure behavior
has not changed. The next small implementation slice is a bounded run procedure
for publication, scheduling, retries, cancellation and residual inventory, followed
by exact account-bound plan/pricing review. Reuse existing provider mechanisms;
do not add generic orchestration. Keep numeric cost ceilings and execution
approval unset until that review is complete.

Run the three local baselines separately, never concurrently; each ends in
Destroy and residual inventory before the next starts. Plan each of the six
directed cases afterwards using its own resources and bidirectional identity
bindings, without inheriting a local cost approval. RQ1 retains provisioning and
cleanup measurements, RQ2 uses the same verified Core path, RQ3 separates
publication/setup baseline from message delivery and final billed costs. Ten
messages establish integration evidence, not performance statistics or full
simulator/command/access-layer coverage. No Apply, image publication or live
workload execution is authorized by this review.
