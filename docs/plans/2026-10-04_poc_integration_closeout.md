# Bounded integration close-out

Status: supervised integration attempts in progress; **no new integration pass
is inferred from preparation**. Continue after the nine Core telemetry and two isolated
L4 observations. Those results are not invalidated or silently broadened.

## Simulator and command return

Reuse the Core runner and deployed domain/Event code. The first fixed case is
local AWS, selected explicitly with `--command-roundtrip`; local Azure and GCP
now have provider-specific receipt/readback harnesses. Directed command
combinations fail before creating an output directory. The ordinary
ten-message Core smoke remains unchanged.

The read-only fresh-state plan has 94 managed creation entries, including ten
Lambda functions, two Kinesis streams/three consumers, two DynamoDB tables,
three S3 buckets, one SNS topic/two SQS queues, IoT ingress/command definition,
the existing build/registry and scheduled mover infrastructure, and supporting
IAM/network/configuration resources. Counts include bindings and configuration,
not 94 independently billed services. No L4, L5, federation or Grafana is added.
SDK registration adds exactly one simulator Thing, one certificate and one
exact-topic IoT policy. The Terraform gateway Thing is a different resource.

Send one value `42` through the actual MQTT/TLS simulator after subscribing to
the command topic. One typed feedback rule causes the existing action boundary
and Event command-delivery path to return a command. Require the same diagnostic
trace at simulator send/receipt and an authenticated L3 point with the exact
input timestamp and value. The current L3 response intentionally does not expose
`source_sequence`; do not assert a nonexistent field or change its contract for
this experiment. An API-accepted command alone is not receipt evidence.

Retain phase/resource times and simulator checkpoints privately. This is one
integration sample, not a performance estimate. Capture failure evidence as well
as success. The existing runner's overall functional deadline includes the
300-second command wait. Stop sending and clean up immediately afterward.
Cleanup removes the exact registered certificate, policy and Thing before
Terraform Destroy; an identity journal covers failure before certificate attach.
Foreign attachments fail closed. Independent inventory includes the journaled
certificate and policy as well as the existing Core inventory. Missing API
permission is an error, not zero inventory. Cleanup errors preclude overall green.
Inactive command tombstones remain separate from active resources.

AWS and Azure already support bounded send-after-listen on one connection.
GCP now supports the same optional mode, but waits for a successful MQTT SUBACK
before sending. This avoids a listener-start race; the existing manual listener
and send helpers retain their behavior. These changes are tested offline only.
The focused simulator, runtime, policy, package and runner regression contains
117 passing tests; changed Python files pass Ruff.
Account-bound read-only plans admit 98 Azure and 109 GCP managed creates; GCP's
existing staged MQTT deployment additionally checks nine Kubernetes addresses.
These counts include bindings/configuration, not independently billed services.
Azure/GCP receipt checks still require their own live result, not inference from AWS.

AWS attempts exposed a legacy-only Terraform endpoint guard: the Six-layer IoT
command adapter received an empty Data-ATS endpoint. The guard now follows actual
AWS L1 placement. The next attempts delivered the real command and exposed two
simulator SDK callback details: the message callback supplies `None` as its client,
and PUBACK supplies `mid` by keyword. Acknowledgement now uses the owned client's
asynchronous publish and reports success only after PUBACK. Regression tests use
the actual callback shapes, including a missing-ACK negative case. Failed attempts
remain failed; arrival alone does not override teardown or harness errors.

### AWS command observation (2026-10-04)

Attempt 05, with runtime fixes through `f505bb69`, passed the actual simulator/command and
authenticated L3 assertion: one telemetry message, one trace-correlated command,
broker-acknowledged device response and one exact timestamp/value readback. The
single observed send-to-receipt time was **13.646645 s**. This is not a latency
distribution or a directed multi-cloud command result.

| Attempt | Functional result | Deploy s | Verify s | Destroy s | Total s |
|---|---|---:|---:|---:|---:|
| 01 | Receipt timeout | 97.879 | 301.836 | 103.077 | 657.882 |
| 02 | Empty command endpoint diagnosed; stopped | 105.270 | 182.513 | 106.003 | 548.622 |
| 03 | SDK message callback client was `None` | 104.750 | 166.099 | 114.506 | 545.033 |
| 04 | PUBACK keyword callback mismatch | 107.769 | 118.249 | 83.925 | 479.066 |
| 05 | Simulator roundtrip and L3 passed | 109.611 | 38.508 | 137.858 | 439.303 |

Deploy excludes the separately captured image foundation/publication phases;
total includes preparation, image phases, diagnostics where needed, and cleanup.
All five attempts completed Destroy and independent zero **active** inventory,
including simulator identity/certificate/policy. Each initial residual snapshot
still contained one inactive IoT command marked `pendingDeletion`. Accordingly,
the strict runner retained `green=false` even for functional attempt 05. Later
zero-inventory reconciliation must be recorded separately, not overwrite these
original observations. Per-resource lifecycle timings and private raw evidence
remain retained; billing attribution is pending.
One subsequent read-only reconciliation still found zero active resources and
the same five inactive command tombstones. AWS documents a **12-hour deletion
waiting period** for recently deprecated commands; there is no immediate-delete
override in `DeleteCommand`. This provider lifecycle is not a reason to rerun the
functional test or repeatedly issue mutations
([AWS API reference](https://docs.aws.amazon.com/iot/latest/apireference/API_DeleteCommand.html)).

### Azure command adapter correction

The first Azure command attempt was stopped during provisioning after a primary
API review found the existing sender using an unsupported HTTP POST to a device
endpoint. Azure's service-side C2D send uses AMQP, not that REST endpoint
([Microsoft endpoint documentation](https://learn.microsoft.com/en-us/azure/iot-hub/iot-hub-devguide-endpoints)).
No device receipt or live HTTP failure is claimed for the stopped attempt.

The adapter now uses the official token-authenticated `IoTHubRegistryManager`
with the existing runtime Managed Identity and explicitly closes its connection.
The Function package pins `azure-iot-hub==2.7.0`, `uamqp==1.6.11` and `six==1.17.0`.
The last dependency is needed by that SDK despite missing from its direct package
metadata. Import and real token-auth client construction were verified locally in
the Linux amd64 Azure Functions Python 3.12 image, without a network send. 61 focused
runtime/simulator/receipt tests pass. Cloud resources, roles and command semantics
are unchanged; live receipt still requires a new bounded attempt.

The second attempt completed deployment (636.472 s) and recorded one simulator
send, but failed `COMMAND_RECEIPT_TIMEOUT` after 305.703 s of verification.
Available logs showed processing-host initialization, not a traced end-to-end
message flow; they do not establish an AMQP failure or a cold-start root cause.
Its immediate Destroy completed in 958.803 s (total attempt: 2035.337 s),
followed by independent zero resource-group inventory. Before another send, the local Azure
harness now requires the expected functions to be indexed across all six apps.
The bounded registration wait is timed and retained privately. A failed receipt
also triggers one authenticated exact-timestamp L3 check, reported as diagnostic
evidence only. The input fixture is retained so that this check cannot match an
unrelated point. No extra cloud resource or alternate data path is introduced.
The focused registration/receipt/runtime group passes 72 tests; the broader Azure
runtime/package/Terraform group passed 226 tests after the SDK change.

Attempt 03 indexed all required apps, including the rule evaluator, but still
timed out waiting for a device command. An exact authenticated L3 read found the
new point both during verification and after the receipt failure. Retained logs
show ingress, processing and historical persistence, but no rule-evaluator
execution in the observation window. This localizes the missing evidence; it
does not prove an AMQP failure or a platform scaling defect.
Attempt 03 measured 583.996 s deployment, 314.914 s verification and 950.904 s
Destroy (1995.107 s total); its independent resource-group inventory is zero.

The next bounded command experiment adds one always-ready instance for each of
the existing rule-evaluator and control-router functions and the action HTTP
group. This applies only to Core with configured rules; the nine telemetry-only
Core plans and full-profile defaults are unchanged. No new resource, route or
alternate command path is added, and the 300-second receipt window is unchanged.
This tests trigger startup as a hypothesis, not an already established fix.
Microsoft documents separate per-function scale groups and separate always-ready
capacity; the on-demand limit is not a combined cap including warm instances
([Flex scaling](https://learn.microsoft.com/en-us/azure/azure-functions/flex-consumption-plan#per-function-scaling)).
Any successful observation must be labelled as warm functional integration, not
scale-to-zero latency evidence. Cleanup removes the warmed apps with the run.
The native mock-plan suite passes with positive warm-group and unchanged
telemetry-plan assertions; 669 Azure/Terraform/runner regression tests pass
(the separately executed native-plan test is excluded from that count).

Attempt 04 exposed an apply-time AzureRM validation before verification: the
provider requires the sum of always-ready instances not to exceed the configured
maximum. Two warmed trigger groups therefore cannot use the telemetry-only
limit of one. This is the pinned provider's validation, not evidence that Azure
uses a shared on-demand scale group. The command-only Event runtime limit is now
two; telemetry-only Core remains one and full-profile defaults remain unchanged.
Native mock assertions explicitly check both the sum constraint and the bounded
exception. See the [pinned provider implementation](https://github.com/hashicorp/terraform-provider-azurerm/blob/v4.67.0/internal/services/appservice/function_app_flex_consumption_resource.go).
No command receipt was tested in this attempt. Deployment took 443.070 s,
Destroy 844.046 s and total lifecycle 1431.215 s; independent resource-group
inventory is zero. The corrected native mock-plan suite passes.

## Event-to-L4 delivery

AWS attempt 01 reached workspace creation, but TwinMaker rejected its role/S3
permission validation (`InvalidRequest`). No fixture was sent. Apply took
85.704 s and Destroy 46.432 s; independent inventory is zero. The existing
bounded same-state IAM retry now also recognizes this narrow S3-validation
variant, retaining the create/no-op allowlist and overall deadline. It does not
add permissions or treat an arbitrary access-denied error as retryable. The
same workspace bucket policy already passed isolated L4; propagation is a retry
hypothesis, not a reason to grant broader access.
Attempt 02 created the cut's resources, then failed while evaluating the output
map's reference to a deliberately absent Storage-Mover log group. No fixture was
sent. Apply took 110.503 s and Destroy 50.233 s; independent inventory is zero.
The output now omits the unavailable log reference in a targeted cut, without
adding the background mover or changing complete-deployment output behavior.

Attempt 03 passed the deployed AWS Event-to-L4 edge at source revision
`86d46701bc7a4a8e982328bdb00dc14949e0f28a`: one canonical processed fixture
traversed the real Kinesis consumer and deployed domain adapter under its runtime
identity. Authenticated TwinMaker readback matched value, source sequence, event
ID and timestamp. Apply took 138.602 s, seed creation 1.196 s and projection plus
readback 27.208 s (14 polls). The readback duration includes polling and is not a
message-latency distribution. SDK cleanup took 15.255 s, Terraform Destroy
46.452 s and independent inventory 7.839 s. All 33 managed resources and SDK seed
objects were removed; functional, cleanup and inventory assertions passed.
No IAM retry was needed. Earlier failed attempts remain separate observations.

Do not repeat Core or mistake a local SDK projection for Event delivery. An AWS
read-only targeted dependency experiment first produced 51 managed creates.
The smaller Event/L4-only experiment produces **33 creates**, using the existing
resource definitions: four functions, two streams/two consumers, one active
Twin-update event-source mapping, two DynamoDB tables, one TwinMaker workspace,
two buckets, one SNS topic/two queues, and IAM/logging/configuration dependencies.
It requires neither image publication nor an IoT device or graphical L5.

This is a partial research graph, not a full-profile Management deployment.
L1/L2 are not provisioned in this cut; a canonical processed fixture is inserted
into the real Event stream. The deployed Event consumer must invoke the deployed
domain adapter under its runtime role and update the seeded Twin. Readback must
match the fixture. The declared non-AWS L1/L2 placement only excludes unneeded
AWS dependencies from this partial plan; **no Azure resources or cross-cloud
delivery are tested**. Full-profile admission stays closed.

The fixed AWS runner enforces all 33 addresses and a 900-second functional window.
The separately reviewed Azure runner admits exactly 45 addresses: three Function
Apps (two published packages), Event Hubs namespace/three hubs/two consumer groups,
Service Bus, Cosmos DB, Digital Twins, Storage, an empty registry dependency and
supporting identities/bindings/configuration. It publishes no container image and
creates no IoT Hub. The existing package dependency also creates an unused reader
app; this is not L5 evidence. One SDK-owned Event Hubs sender role is journaled and
removed during cleanup. Terraform owns both Twin data roles. Its functional window
is 1500 seconds, including provisioning and at most one processed fixture.

Both runners are plan-only by default, use exact fresh create-only plans, preserve
phase/per-resource timing, attempt cleanup on failure/interrupt and independently
check inventory. Azure permits only the two known package submodules in its frozen
state allowlist. Neither cut claims replay, cross-cloud delivery, graphical L5 or
full-profile admission. The L4 runner group has 56 passing offline tests. A private
execution allowance is not measured provider billing. No general layer-selection
framework or alternate production architecture is introduced.

## L5 and interpretation

Graphical L5 needs a user decision, not automatic restoration of the historical
Grafana proposal. A local view of real authenticated L3 data would be a bounded
evaluation aid, **not** evidence of provider-hosted L5, and cannot be introduced
as an equivalent service mapping without approval. Alternatively leave graphical
L5 explicitly unevaluated. GCP L4/L5 remain excluded; research questions do not
change.

RQ1 records provisioning, configuration, cleanup and integration defects.
RQ2 reports each actually verified edge and excluded responsibility separately.
RQ3 keeps measured timings, technical allowances and later billed attribution
distinct.
