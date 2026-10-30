# Bounded L4 evaluation: AWS and Azure

Status: infrastructure plans checked offline and account-bound read-only on
2026-10-04; native AWS projection correction implemented and verified offline;
**AWS and Azure isolated L4 acceptance passed, including cleanup and zero active inventory**.
Predecessor: [nine Core telemetry passes](../research/evaluation/core-telemetry-results.md).
Research questions and full-profile admission remain unchanged. GCP L4/L5
remain excluded; no replacement VM, dashboard or custom Twin service is added.

## Smallest useful check

Run AWS, then Azure, sequentially. Each case provisions the real managed L4
service with Terraform, seeds the root/device graph and existing telemetry model, invokes
the existing provider projection adapter locally with a canonical
`twin.state.upserted` fixture, and authenticates readback of the expected metric,
numeric value and exact `source_sequence`. Send one update and replay that same
event once; verify the final state still matches. This is a bounded acceptance
check, not a general claim of exactly-once delivery or time-series deduplication.

**Preparation finding:** this was the proposed assertion, not an executable
AWS test. The existing AWS seed marks metric/value/sourceSequence as external
time-series properties and requires a Lambda data connector. The active
Six-layer Terraform workspace does not provision that connector, and the older
seeder resolves legacy output names/resources disabled in this profile.
`BatchPutPropertyValues` cannot be assumed to store those values in the
workspace: AWS describes it as invoking a
[DataWriter connector](https://docs.aws.amazon.com/iot-twinmaker/latest/guide/data-connector-interfaces.html).
The AWS infrastructure plan therefore does not clear the projection gate.

The approved lean correction now uses native current-state entity properties,
matching the bounded Azure projection; L3 remains the history owner. The actual
AWS seeder resolves the active workspace output, creates the telemetry component
without external/time-series properties or Lambda connectors, and rejects an
incompatible pre-existing component. Legacy external components remain unchanged.
The runtime uses `UpdateEntity` for metric/value/sourceSequence/observedAt/lastEventId;
the probe uses `GetEntity` and requires one active, correlated current-state snapshot.
Content/probe revisions are now `aws-l4-seed.v3` / `aws-twinmaker-readback.v2`.
This does **not** claim TwinMaker historical data-connector equivalence to the
original five-layer architecture, exactly-once delivery, or stale-event ordering.
RQ2 compares the bounded current-state responsibility; history is assessed at L3.
The nine Core observations remain valid because their scope excludes L4.

Use the actual adapter source, not a replacement implementation or direct SDK
write masquerading as adapter verification. SDK clients use the existing local
administrator credentials without printing them. No function deployment,
container build/publication, IoT device, Event broker, L3, L5 or federation is
needed for this isolated check. The fixture is explicitly synthetic; it does
not claim that a real Core event reached L4.

This proves managed L4 provisioning/model/projection/readback/cleanup only.
Event-Layer-to-L4 delivery, deployed runtime identity and the simulator/command
roundtrip remain later integration checks, not inferred from an isolated pass.
Do not repeat the nine Core cases to obtain this evidence.

## Implementation cut and expected resources

Current Terraform accepts only `core` (no L4/L5) or `full` (both placed). Do not
change that public contract, relax its guard, or deploy the full graph just to
test L4. Prepare a fixed research-only targeted plan against the existing L4
resource definitions in a fresh, disposable state per provider. This is an
explicitly partial Terraform experiment, not an admitted Management deployment.
No generic layer-selection framework or third architecture profile is needed.

| Provider | Existing Terraform resource roots | SDK-owned children |
|---|---|---|
| AWS | `aws_s3_bucket.aws_six_layer_twinmaker`, `aws_s3_bucket_public_access_block.aws_six_layer_twinmaker`, `aws_iam_role.aws_six_layer_twinmaker`, `aws_iam_role_policy.aws_six_layer_twinmaker`, `awscc_iottwinmaker_workspace.aws_aws_iot_twinmaker_standard` | One telemetry component type and two entities (root/device), using the corrected application seed |
| Azure | `azurerm_resource_group.main`, `azurerm_digital_twins_instance.azure_azure_digital_twins` | One ADT-scoped Data Owner binding for the existing administrator, one existing DTDL model, two Twins and their contains relationship |

Saved account-bound create-only plans now contain **six AWS entries** (the five
roots plus `random_id.deployment_suffix`) and **two Azure entries** (group/ADT).
The fixed [plan-only preparer](../../scripts/prepare_l4_evaluation.py) rejects any
missing, extra, duplicate or non-create managed entry. These counts exclude
SDK-owned children and do not claim a successful deployment.
Reject unrelated infrastructure or any mutation to pre-existing resources.
Do not target the whole Azure role-assignment collection, create human access
roles, or grant extra account-level roles for a local-adapter experiment.
If safe isolation cannot be achieved, stop and revise this small plan rather
than adding the complete Core or bypassing production admission.

The initially proposed Azure `twin_seed_deployer` target unexpectedly pulled
eleven managed entries into the dependency graph, including IoT Hub, ACR,
Service Bus, storage and a user-assigned identity. That plan was rejected, not
applied. The two-root alternative excludes that shared role map. A future runner
must explicitly track/create/delete its single SDK role binding on the new ADT
instance before the data-plane check. The supervised runner now implements that
binding and cleanup. No additional administrator credential or subscription-wide
grant is required.

One output-only correction handles a missing human-reader binding in a targeted
Azure plan by returning empty binding evidence rather than indexing an absent
resource. Full-profile planning still returns its real binding; production
scope/admission guards remain unchanged. Three credential-free native L4 mock
plans and nine plan-scope unit tests cover the preparation.
Three existing provider-local full-profile mock plans also pass, including the
Azure human-reader binding regression. Terraform validation has zero errors
and warnings. L4 mocks/validation used Terraform 1.15.8; the full-profile
regression and account-bound plan-only checks used the existing 1.7.5 CLI.
Saved plans are private, fresh-state and uniquely prefixed; no Apply ran.

The fixed [L4 runner](../../scripts/run_l4_evaluation.py) and
[projection check](../../scripts/l4_projection_check.py) now implement the isolated
experiment. They use real seeding/model assets and runtime source, fresh allowlisted
plans, active-state readiness, exact projection/replay snapshots, private phase
and resource timings, and unconditional cleanup followed by independent inventory.
SDK response/call limits and a 20-minute functional deadline stop the experiment;
cleanup has its own time window. Cleanup cannot delete a pre-existing prefix when
preflight rejects the run. Permission errors are not treated as absent resources.
Implementation/offline tests did not Apply resources; the separately approved
live observations below now provide real provisioning/projection evidence.
Verification: 176 focused offline tests pass across runner/scope guards,
AWS/Azure adapters, seed lifecycle, probes and access contracts. Another 136
simulator/Eventing/metrics tests pass; these groups do not duplicate a live run.
Changed Python files pass Ruff; the three native L4 mock plans pass again after
the correction. Account-bound plan-only checks on the corrected revision still
admit exactly six AWS/two Azure entries, without Apply.

Reuse the existing seeding/model assets, projection adapters, authenticated
verification probes and pre-destroy helpers where compatible. Azure's current
`check_adt_twin` verifies source sequence but not metric/value; the bounded
runner must additionally assert both from authenticated readback. AWS's
projection probe already checks all three. No broader probe redesign is needed.

## Time, cost and execution gate

Proposed functional window: 20 minutes per provider, including Apply, model
seeding, projection and readback. This is an abort limit, not an expected
deployment duration. Retry only transient readiness/permission propagation
inside that same window. After success, failure or timeout, cleanup begins
immediately; its own elapsed time is measured and it is not cancelled when
the functional deadline expires.

Public pricing reviewed read-only on 2026-10-04:
[AWS TwinMaker](https://aws.amazon.com/iot-twinmaker/pricing/) charges depend on
pricing mode, entities, data-access calls and queries, with S3 costs separate.
[Azure Digital Twins](https://azure.microsoft.com/en-us/pricing/details/digital-twins/)
uses operations, messages and query units. Short lifetime alone is not a
complete cost bound. Do not assume credits/free tiers or activate an AWS
account-wide pricing-plan change.

Before any mutation, finish these narrow offline/read-only gates:

1. Native mock plans for each fixed target set; allowlist all dependency
   addresses and offline tests of adapter/reader assertions and failure cleanup.
2. Read-only identity, Region, model compatibility, permissions and AWS pricing
   mode checks; account-bound create-only saved plans with exact resource counts.
3. Count bounded seeding, update/replay and readback API calls (at most 60
   readback rounds, at most 20 results per request, no unbounded pagination).
   Include provisioning/cleanup calls, entity billing and AWS S3 requests.
   Resolve regional prices and disclose any monthly minimum/non-prorated charge.
4. Present the exact plans, technical cost ceilings, time limit and cleanup to
   the user. Execution remains disabled until those ceilings and this separate
   live L4 scope are explicitly approved. Historical Core allowances do not
   authorize L4 or establish its cost bound.

Read-only price retrieval also completed on 2026-10-04. AWS `GetPricingPlan`
reports `STANDARD`, zero billable entities and no tier; no pricing mode was
changed. Price List `GetProducts` uses service code `IoTTwinMaker` (not the
internal catalog label `AWSIoTTwinMaker`) and location `EU (Frankfurt)`.
The Azure Retail Prices API uses product-name `Digital Twins`, Region
`westeurope`, USD Consumption rates. Neither query has remaining pages for the
selected regional meters. Sources:
[AWS Price List API](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/price-changes.html),
[Azure Retail Prices API](https://learn.microsoft.com/en-us/rest/api/cost-management/retail-prices/azure-retail-prices).

| Regional meter | Retrieved USD list price |
|---|---:|
| AWS entity-month | 0.0525 per entity/month |
| AWS unified data access | 0.00000165 per call |
| AWS queries | 0.0000525 per query |
| Azure operations | 0.00325 per 1,000 billed units |
| Azure routed messages | 0.0013 per 1,000 billed units |
| Azure query units | 0.00065 per 1,000 units |

Historical preparation arithmetic (superseded by the runner envelope below):
the existing two-entity AWS seed charged for a full month would be USD 0.105;
120 data-access calls and 60 queries add USD 0.003348. A USD 0.12 TwinMaker-only
allowance covers that arithmetic, but not connector compute, S3 or a correction
to the actual model. Azure's proposed direct GET/update check has no routed
messages or graph queries; 1,000 billed operation units cost USD 0.00325, below
a USD 0.01 ADT-only allowance. Operations are metered by response size, not just
request count, so a future runner must enforce both limits and bounded SDK retries.

These were list-price calculations without credits, tax or currency conversion,
not invoices or hard billing caps. At that checkpoint the model decision and
runner/call envelope were unresolved. The implemented envelope below supersedes
the connector and call-count assumptions; it does not itself authorize Apply.

### Implemented runner envelope

The native AWS correction removes connector compute/storage entirely. One
attempt per provider uses two entities/Twins, one numeric update and its replay,
at most 60 readback rounds per assertion, and at most two HTTP attempts per SDK
operation. The projection client stops after 300 calls or a response exceeding
16 KiB. AWS child cleanup has a separate 300-call budget; Azure has only the
fixed relationship, two Twins, model and role to remove. Permission-readiness
polling is capped at 60 rounds. Functional execution stops after 20 minutes;
Terraform is interrupted gracefully and cleanup is attempted regardless.
No cross-month run or change of AWS pricing mode is allowed by this proposal.

For conservative planning, 1,200 AWS data calls cost USD 0.00198; two full
entity-months cost USD 0.105. The current Frankfurt S3 Price List API gives
USD 0.0000054 per Tier-1 request and USD 0.00000043 per Tier-2 request: an extra
1,000 of each costs USD 0.00583. No object payload is uploaded by the runner;
TwinMaker creates its own workspace lifecycle marker in S3. A technical
allowance of USD 0.25 leaves margin for the tiny response transfer and provider
control-plane requests; it is not a measured bill or enforced billing cap.
[S3 pricing](https://aws.amazon.com/s3/pricing/).
For Azure, budgeting 1,200 responses of 16 KiB gives 19,200 operation units,
USD 0.0624 at the retrieved meter. USD 0.10 is the ADT planning allowance;
there are no routed messages or query workloads. Limits stop further functional
calls after an oversized response, not retroactively undo already billed traffic.
Cleanup is never abandoned to conserve a call allowance.

The two specific managed-service checks were approved on 2026-10-04.
The CLI interlock is not itself authorization. The operator must stop after a
failed attempt, review its private report and inventory, and recheck the remaining
allowance before a retry or moving to the second provider. Historic Core spending
approval is not used as an L4 budget.

## Measurements and cleanup

Retain revision/fixture/model digests; plan, Apply, per-resource creation,
model/Twin seeding, projection acknowledgement, readback, Destroy and inventory
durations. Timestamp projection and successful correlated readback separately
from service creation; this is a local-adapter sample, not cloud-message latency.
Record failed attempts, retry counts and billed attribution separately.

Always remove only run-owned SDK children before Terraform Destroy: AWS entity
then custom component type; Azure Twin then model. Reuse prefix ownership checks
and retain the state if deletion fails. Independently inventory the workspace,
bucket (including versions), IAM role/policy or the Azure group, ADT and scoped
role assignment. Count active residuals and provider tombstones separately.
Stop before the second provider if active resources remain or cost deviates
without explanation; never conceal cleanup failure with a functional pass.

RQ1 gains real service/model provisioning and teardown evidence; RQ2 compares
the same bounded numeric Twin projection responsibility on AWS/Azure. RQ3
records the scoped resource/API costs without treating omitted GCP L4 as free
or attributing these fixture measurements to Eventing. L5 stays last.

## Live observations (2026-10-04)

AWS isolated L4 passed at revision `cdf0d3e6`. The actual native seed created
one telemetry component type and the root/device entities. The actual adapter
updated the current state and replayed the same event; both authenticated
readbacks matched metric, numeric value, sequence, event ID and observation time.
SDK child deletion, Terraform Destroy and independent workspace/S3/IAM inventory
completed with zero active residuals. The run used 16 projection/seed SDK calls
and 21,978 cumulative response bytes; this is not a billed-operation count.

| AWS phase | Seconds |
|---|---:|
| Plan and runner initialization | 6.174 |
| Apply, including one bounded IAM-readiness retry | 48.803 |
| Model/entity seed | 1.066 |
| Projection acknowledgement / correlated readback | 0.093 / 0.060 |
| Replay acknowledgement / correlated readback | 0.123 / 0.059 |
| SDK child cleanup | 6.739 |
| Terraform Destroy | 14.278 |
| Independent inventory | 0.895 |

Six create and six destroy resource-duration observations are retained privately.
These are local-adapter API timings, not Event-Layer message latencies, repeated
benchmarks, or proof of deployed runtime identity. Provider-billed attribution
remains pending; no allowance is reported as actual cost.

Two earlier AWS cloud attempts failed before model/entity seeding and were
cleaned with zero inventory: the first encountered IAM trust propagation
(Apply 11.809 s, Destroy 9.342 s); the second successfully created the workspace
but exposed an output that indexed intentionally omitted human SSO bindings
(Apply 50.636 s, Destroy 15.007 s). The runner now retries only that classified
workspace/IAM failure, at most twice, after reviewing a plan with one missing
workspace create and no changes to the five existing entries. The output now
returns empty binding evidence for the isolated cut, without inventing access.
See [AWS service-role requirements](https://docs.aws.amazon.com/iot-twinmaker/latest/guide/twinmaker-gs-service-role.html).

Two additional starts stopped locally before Apply: the container lacks Git,
so the runner accepts a validated pinned revision; Azure's installed resource
SDK exports its client under `azure.mgmt.resource.resources`. Both are corrected.
The failure records remain separate from the successful observation.

Azure isolated L4 passed at revision `f7770bd3`. Terraform provisioned only the
resource group and ADT instance. One instance-scoped Data Owner assignment
authorized the existing administrator; no extra administrator or tenant role
was created. The existing DTDL model, root/device Twins and contains relationship
were seeded; the actual adapter's update and replay produced matching authenticated
snapshots. SDK cleanup removed the relationship, Twins, model and scoped role,
then Terraform removed both infrastructure resources. Independent group/role
inventory found zero active residuals. Nine seed/projection SDK calls returned
5,065 cumulative bytes; these are observations, not billed units.

| Azure phase | Seconds |
|---|---:|
| Plan and runner initialization | 33.686 |
| Terraform Apply | 115.292 |
| Scoped-role readiness (one observation) | 1.313 |
| DTDL/Twin/relationship seed | 3.185 |
| Projection acknowledgement / correlated readback | 0.769 / 0.059 |
| Replay acknowledgement / correlated readback | 0.064 / 0.056 |
| SDK child and scoped-role cleanup | 4.017 |
| Terraform Destroy | 129.808 |
| Independent inventory | 1.361 |

Two create and two destroy resource-duration observations are retained privately.
These two isolated passes establish managed service/model/current-state behavior,
not Event-to-L4 delivery, command return or graphical L5. Successful AWS evidence
uses revision `cdf0d3e6`; the later Azure change only corrected runner SDK import
and added its offline initialization regression. No AWS rerun is needed for that.
Following the live findings, 179 focused offline tests and all three credential-free
native L4 mock plans pass. Per-provider billing attribution remains pending.

## Remaining close-out sequence

The [integration close-out](2026-10-04_poc_integration_closeout.md) records the
subsequent simulator preparation and read-only Event/L4 dependency experiments.

1. Completed: both isolated L4 cases passed, with failed attempts retained and
   immediate cleanup/independent zero active inventory. Do not rerun them merely
   because the integration stages remain open.
2. Verify actual Event-to-L4 delivery and deployed identity separately. A green
   local-adapter fixture does not clear that edge. Review the exact resource
   delta before a combined cut; do not relax full-profile admission or add L5
   merely to obtain this evidence.
3. Exercise the existing simulator and command receipt on the three provider
   delivery mechanisms, recording actual telemetry and return-path checkpoints.
   Existing simulator, command-listener, Event-runtime and metrics-assembler
   tests passed offline (136 tests); no live command result follows from them.
   Do not automatically repeat every directed telemetry case: add a directed
   command case only for an unverified routing/identity path and label coverage.
   Preparation finding: AWS send/listen currently create separate connections
   with the same MQTT client ID; Azure helpers likewise create separate clients
   for one device. An optional bounded send-after-listener-ready mode is now
   implemented using the same connection and accepting only the matching
   diagnostic trace. Existing manual listener behavior is preserved. No new role, certificate, UI,
   service or general session framework. GCP already separates telemetry/command
   client IDs; its listener now also accepts an expected trace and ignores other
   receipts. These changes are offline-tested preparation, not live roundtrip
   evidence. The current Core preparer deliberately has empty event/device
   configuration; the next live cut must explicitly add one registered simulator
   device and one feedback rule, with exact plan/cleanup review. Merely rerunning
   the unchanged ten-message telemetry smoke cannot establish command return.
4. Resolve and verify the smallest graphical L5 responsibility last. The existing
   feasibility review is not implementation approval. No Grafana platform,
   GCP VM, silent reader-to-visualization relabelling or changed research question
   is introduced by this work. A changed service mapping needs an explicit
   decision before implementation/spending.
5. Consolidate observed metrics, failed-attempt overhead, cleanup and provider
   billing attribution. Leave unavailable values null/pending; do not equate an
   allowance or monthly account total with a measured scenario cost.
