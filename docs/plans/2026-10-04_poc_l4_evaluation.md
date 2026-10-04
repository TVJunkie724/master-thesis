# Bounded L4 evaluation: AWS and Azure

Status: offline slice design, **not executable or approved for Apply**.
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
| Azure | `azurerm_resource_group.main`, `azurerm_digital_twins_instance.azure_azure_digital_twins`, the `twin_seed_deployer` instance of `azurerm_role_assignment.azure_azure_entra_layer_access_bindings` | One existing DTDL model and one Twin |

The five AWS roots and three Azure roots are **not verified final resource
counts**. Terraform dependency closure may add naming resources/data reads;
freeze every resulting address and action from the saved plan before approval.
Reject unrelated infrastructure or any mutation to pre-existing resources.
Do not target the whole Azure role-assignment collection, create human access
roles, or grant extra account-level roles for a local-adapter experiment.
If safe isolation cannot be achieved, stop and revise this small plan rather
than adding the complete Core or bypassing production admission.

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

No monetary ceiling is asserted yet; pricing and final dependency closure are
open preparation gates, not evidence of a free test.

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
