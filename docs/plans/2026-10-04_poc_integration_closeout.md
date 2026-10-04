# Bounded integration close-out

Status: offline implementation and account-bound read-only planning; **no new
live integration pass**. Continue after the nine Core telemetry and two isolated
L4 observations. Those results are not invalidated or silently broadened.

## Simulator and command return

Reuse the Core runner and deployed domain/Event code. The first fixed case is
local AWS, selected explicitly with `--command-roundtrip`; directed/other-provider
combinations currently fail before creating an output directory. The ordinary
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
Azure/GCP live harness wiring, exact account plans and cost review remain pending;
do not enable those CLI cases based on an AWS result.

## Event-to-L4 delivery

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

The private account-bound plans are preparation observations, not an execution
runner or an approved cost quote. Before Apply, freeze the exact address allowlist,
verify seed/readback and failure cleanup for this cut, and review its technical
cost envelope. Review the Azure dependency closure separately. No general layer
selection framework or alternate production architecture is introduced.

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
