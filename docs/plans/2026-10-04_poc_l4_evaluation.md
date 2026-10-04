# Bounded L4 evaluation: AWS and Azure

Status: infrastructure plans checked offline and account-bound read-only on
2026-10-04; **projection blocked, not approved for Apply**.
Predecessor: [nine Core telemetry passes](../research/evaluation/core-telemetry-results.md).
Research questions and full-profile admission remain unchanged. GCP L4/L5
remain excluded; no replacement VM, dashboard or custom Twin service is added.

## Smallest useful check

Run AWS, then Azure, sequentially. Each case provisions the real managed L4
service with Terraform, seeds one Twin and the existing telemetry model, invokes
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

The lean proposed correction is native current-state entity properties, matching
the bounded Azure projection; L3 remains the history owner. That would require
a small AWS model/adapter/readback correction and an explicit comparison note,
not a substitute connector/storage service. It is **not implemented or approved
by these plan-only checks**. Do not seed a differently defined test model and
claim that the unchanged application passed.

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
| AWS | `aws_s3_bucket.aws_six_layer_twinmaker`, `aws_s3_bucket_public_access_block.aws_six_layer_twinmaker`, `aws_iam_role.aws_six_layer_twinmaker`, `aws_iam_role_policy.aws_six_layer_twinmaker`, `awscc_iottwinmaker_workspace.aws_aws_iot_twinmaker_standard` | One telemetry component type and one entity, seeded using the existing model contract |
| Azure | `azurerm_resource_group.main`, `azurerm_digital_twins_instance.azure_azure_digital_twins` | One ADT-scoped Data Owner binding for the existing administrator, one existing DTDL model and one Twin |

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
instance before the data-plane check. No additional administrator credential
or subscription-wide grant is required by this proposal.

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

Conservative **service-only arithmetic**, not approved total spending ceilings:
the existing two-entity AWS seed charged for a full month would be USD 0.105;
120 data-access calls and 60 queries add USD 0.003348. A USD 0.12 TwinMaker-only
allowance covers that arithmetic, but not connector compute, S3 or a correction
to the actual model. Azure's proposed direct GET/update check has no routed
messages or graph queries; 1,000 billed operation units cost USD 0.00325, below
a USD 0.01 ADT-only allowance. Operations are metered by response size, not just
request count, so a future runner must enforce both limits and bounded SDK retries.

These are list-price calculations without credits, tax or currency conversion,
not invoices or hard billing caps. A complete cost ceiling and exact approved
live assertion remain open until the AWS model decision and final runner/call
envelope are resolved. Do not Apply infrastructure merely to make a partial
checkpoint appear green.

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
