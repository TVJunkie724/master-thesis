# Digital Twin Architecture And Eventing Layer Research Note

## Purpose

This research note records a source-based assessment of the Digital Twin
decomposition used by Twin2MultiCloud. It is input for the later thesis
synthesis and the architecture audit in GitHub issue
[#112](https://github.com/TVJunkie724/master-thesis/issues/112), not a decision
to replace the implemented architecture. It is deliberately not part of the
published user and developer documentation.

The related implementation hardening for user-provided function logic,
provider packaging, and infrastructure-owned bindings is tracked in GitHub
issue
[#113](https://github.com/TVJunkie724/master-thesis/issues/113). That issue is
part of the active thesis hardening backlog, not post-thesis future work.

The broader literature landscape, citation-ready source metadata, and explicit
differentiation from the planned thesis contribution are maintained in
[Related Work: Multi-Cloud Cost, Functional Comparability, And Event-Driven
Digital Twins](related_work_multicloud_cost_comparability_eventing.md).
The working research questions and their evaluation design are maintained in
[Research Questions And Evaluation Design](research_questions_and_evaluation_design.md).

The assessment addresses three questions:

1. Are the five layers required for the published cost comparison?
2. Can the same decomposition support optimization objectives other than cost?
3. How can provider-native architectures be compared without losing functional
   equivalence or the scientific baseline?

## Primary Sources Reviewed

### Twin2Clouds paper

[Twin2Clouds: Cost-Aware Digital Twin Engineering and Deployment Across
Federated Clouds](../../docs-site/docs/references/EDT_25__CloudDT_engineering.pdf)
defines:

- five cloud-oriented Digital Twin layers;
- provider-neutral cost and pricing primitives;
- workload parameters;
- service cost per layer;
- transfer cost between layers; and
- a provider-allocation optimization over the layer set.

The relevant source sections are IV-VII, especially the architecture in Figure
1, the primitive mappings in Tables III-VI, and the total-cost formulation in
Section V-G.

### AWS bachelor implementation

[Developing a Cloud-Based Multi-Provider Digital Twin: Addressing Layered
Architecture, Deployment and Cross-Cloud Integration
Challenges](../../docs-site/docs/references/bachelor_digital_twins.pdf)
implements an AWS proof of concept derived from the earlier layer model. The
relevant source sections are 3-4, the system-level evaluation in Section 6, and
the architectural discussion and future work in Sections 8-10.

The bachelor implementation demonstrates an executable AWS topology and
deployment tool. It does not validate a functioning cross-provider deployment
or prove that all provider services are one-to-one substitutes.

## Rationale For Re-Evaluating The Source Architecture

The current project may reuse the source implementation without treating every
prototype decision as a binding target architecture.

Direct Function invocation was a comprehensible way to keep an AWS-focused
proof of concept small and executable. The master-level implementation has a
different responsibility: it must justify whether that topology remains
functionally complete, cost-comparable, secure, and operationally defensible
when it is generalized across providers.

The research should therefore avoid two equally weak claims:

- the bachelor implementation was wrong because it used a simplified
  architecture; or
- the current implementation is justified merely because it inherited the
  architecture from the bachelor project.

The fair approach is to preserve the source topology as an auditable historical
reference, identify its assumptions and limits, and derive a hardened
five-layer implementation as the executable comparison baseline. A bounded
alternative can then be evaluated against the same workload and functional
contract. Replacing a source-project anti-pattern is justified only when the new
baseline or alternative has explicit evidence, complete cost ownership, and
equivalent required behavior.

## Important Provenance Finding

The two sources do not use identical layer numbering.

| Layer | Twin2Clouds paper | AWS bachelor implementation and current platform |
|---|---|---|
| L1 | Data Acquisition | Data Acquisition |
| L2 | Data Storage | Data Processing |
| L3 | Data Processing | Data Storage |
| L4 | DT Management | Digital Twin Management |
| L5 | Visualization | Data Visualization |

The bachelor work also makes hot, cold, and archive storage explicit as L3
sub-layers. The current Twin2MultiCloud implementation follows that executable
AWS-derived numbering rather than the paper's numbering.

This difference must remain explicit in thesis documentation. A layer identifier
without its semantic capability is not an unambiguous scientific reference.

The paper itself contains a related notation inconsistency in Table V: a
storage-to-DT-management transfer is labeled L3 to L4 although Section IV
defines storage as L2. Comparisons must therefore use semantic layer names in
addition to numbers.

## Why The Layers Matter For The Published Cost Model

The paper models a fixed set of layers `L` and assigns one provider to every
layer. For workload `w` and provider-allocation vector `p`, total cost is the
sum of service and inter-layer transfer costs:

```text
C(p, w)
  = sum(service_cost(layer, provider, workload))
  + sum(transfer_cost(source_layer, target_layer, providers, workload))
```

The optimizer then selects:

```text
p* = argmin C(p, w)
```

The layers provide the decision boundaries that make this search finite,
reproducible, and functionally comparable. They ensure that an AWS-only,
Azure-only, and federated candidate all claim to provide the same broad Digital
Twin responsibilities.

Consequently:

- the five-layer decomposition is required to reproduce and evaluate the
  published Twin2Clouds optimization model;
- changing the decomposition changes the search space and therefore the
  experiment;
- a cheaper candidate is meaningful only if it still covers the required
  functionality; and
- provider and transfer costs cannot be compared honestly without stable
  functional boundaries.

The layers are therefore part of the scientific baseline, not an incidental UI
or deployment convention.

## Functional Completeness Before Cost Ranking

Cost comparison is valid only after functional completeness has been
established. A candidate that is cheaper because it omits required behavior is
not a cost optimization result; it is a different system.

The comparison must therefore distinguish:

- **structural equivalence:** candidates use the same number and shape of
  services; and
- **functional equivalence:** candidates provide the same required externally
  observable responsibilities and data semantics.

Twin2MultiCloud needs functional equivalence, not forced structural equivalence.
An Azure implementation may use a managed routing or messaging service where an
AWS implementation uses a rule plus one or more functions. Conversely, a
provider may need several resources to realize a responsibility exposed by one
managed service elsewhere.

Let `R` be the required functional contract and `X` the set of architecture
candidates. Cost ranking must operate only on the feasible subset:

```text
feasible(R) = {x in X | x completely and correctly satisfies R}

x* = argmin cost(x, w) for x in feasible(R)
```

The completeness gate must cover more than the presence of a named service. It
must verify relevant behavior such as:

- ingestion and routing semantics;
- required processing and transformation;
- authoritative operational and historical state;
- retention and retrieval behavior;
- Digital Twin model and query capabilities;
- visualization requirements;
- delivery, ordering, retry, and duplication assumptions;
- security and data-residency constraints; and
- all additional resources required to make the candidate operational.

This is a central validity condition for the thesis. Without it, a provider can
appear cheaper because functionality or supporting resources were omitted.

## What The Sources Do Not Prove

The papers do not establish that:

- every provider exposes one equivalent service per layer;
- every service belongs to exactly one layer;
- every valid Digital Twin topology is a linear L1-L5 pipeline;
- selecting each layer independently always produces an operational topology;
- the layer-wise cost minimum also minimizes latency, risk, emissions, or
  operational complexity; or
- cross-cloud integration preserves the same consistency, security, latency,
  and failure behavior as provider-native integration.

The Twin2Clouds paper explicitly identifies decomposition sensitivity as a
construct-validity concern. It also limits the implemented objective to
monetary cost and leaves latency, availability, energy, compliance, migration
cost, and repeated optimization to future work.

The bachelor thesis describes provider interchangeability primarily as an
architectural intention. Its evaluation is AWS-only and records sequential
Lambda overhead, cross-cloud consistency and identity as future concerns, and
hybrid/containerized architectures as possible alternatives.

These are not minor implementation details. They bound the claims that can be
made from a layer-wise cost result. A result demonstrates the cheapest modeled
candidate under the chosen decomposition, workload, prices, constraints, and
equivalence assumptions. It does not prove that the selected topology is the
globally best cloud architecture.

## Capabilities As Validation Vocabulary

Capabilities are useful for defining and checking the functional contract of a
layer implementation. They are not independently selectable architecture
building blocks in the planned thesis implementation.

For example, a validation vocabulary may include:

```text
Ingestion
Event Routing
Transformation
Operational Twin State
Semantic Twin Graph
Historical Storage
Analytics
Visualization
Cross-Cloud Transport
```

A flat list alone does not define:

- which capabilities are mandatory for a particular use case;
- which service supplies one or several capabilities;
- which services must be deployed together;
- where state is authoritative;
- how data moves between capabilities;
- whether one capability is upstream, downstream, or parallel to another;
- which costs would be double-counted for bundled services; or
- whether a composed selection is deployable.

Twin2MultiCloud will therefore not expose a free capability composition engine.
Capabilities may later help prove that provider-specific layer implementations
are functionally complete.

## Architecture Model Alternatives

### Alternative A: Strict Service Parity Per Layer

```text
L1 -> L2 -> L3 hot/cold/archive -> L4 -> L5
```

Advantages:

- reproduces the paper;
- keeps formulas and comparison tables understandable;
- produces a bounded provider-allocation search; and
- supports clear per-layer and transfer-cost attribution.

Limitations:

- can confuse functional equivalence with one-to-one service equivalence;
- cannot naturally represent branching or provider-managed integrations;
- may introduce glue services only to preserve the layer boundary; and
- makes non-cost quality attributes difficult to calculate accurately.

The fixed layer vector remains the correct scientific baseline. Requiring the
same internal service shape inside every provider implementation does not.

### Alternative B: Provider-Specific Layer Implementation Profiles

Keep the five functional comparison boundaries, but allow a provider to realize
one layer with a validated bundle of one or more services:

```text
Functional layer contract
        |
        +--> AWS implementation profile
        |       +--> required AWS resources and internal edges
        |
        +--> Azure implementation profile
        |       +--> required Azure resources and internal edges
        |
        +--> GCP implementation profile
                +--> required GCP resources and internal edges
```

Each profile must declare:

- which functional contract it satisfies;
- all billable and non-billable supporting resources;
- internal dataflow and delivery semantics;
- workload-to-usage transformations;
- pricing and formula contracts;
- constraints and unsupported behavior; and
- Deployer capability and verification evidence.

The optimizer still chooses one provider implementation per paper-compatible
functional boundary. It does not construct arbitrary architectures.

Advantages:

- preserves the thesis comparison model;
- avoids forcing identical service structure across providers;
- includes hidden helper services in the cost;
- permits targeted provider-native improvements; and
- remains a bounded, testable extension of the current implementation.

Limitations:

- integrations spanning several layers may require an explicit coupled profile;
- functional equivalence must be reviewed carefully; and
- the profile catalog remains curated rather than fully dynamic.

This is the recommended thesis-appropriate extension seam.

### Research Candidate C: Add A Nonlinear Eventing And Messaging Layer

A layer does not need to be one position in a linear pipeline. It can define a
stable logical responsibility, own a group of services and costs, and connect
to several other layers.

The proposed `LE` Eventing and Messaging Layer would own:

- event routing and filtering;
- durable queues, topics, and streams;
- buffering and backpressure;
- publish/subscribe fan-out;
- ordering, retention, and replay;
- retry and dead-letter behavior;
- event envelopes and delivery contracts; and
- event transport between cloud or trust boundaries.

It would not own device protocols and onboarding from L1, domain processing
from L2, long-term domain storage from L3, semantic Twin state from L4, or
visualization behavior from L5. Depending on the provider implementation, `LE`
may connect any of these layers:

```text
Devices
   |
   v
  L1 -----> LE -----> L2
              |         |
              |         +-----> LE -----> L3
              |                     |
              +--------------------> L4
              |
              +--------------------> L5 / realtime UI / alerts

  L4 -----> LE -----> commands / feedback -----> L1 / device
```

`LE` is preferred over `L6` as a research identifier because `L6` suggests a
stage after visualization even though the responsibility is nonlinear.

Advantages:

- exposes eventing resources and invocation costs hidden inside broad layers;
- allows delivery functionality to be compared explicitly;
- avoids treating direct Function chains as cost-free architecture glue;
- permits provider-native service groups behind one functional contract; and
- makes non-linear transfer paths and feedback loops visible.

Limitations:

- adding `LE` changes the published five-layer experiment and therefore requires
  a separately reported extended model;
- provider services still do not align one-to-one;
- one logical Eventing Layer may require several channels or services;
- integrated routing capabilities can be double-counted unless every billable
  resource has exactly one cost owner; and
- the functional contract must distinguish event routing, streaming, durable
  work, command delivery, and replay requirements.

The candidate is scientifically defensible if it is independently selectable,
has explicit workload semantics, changes the cost or constraint model
materially, and is evaluated beside rather than silently substituted for the
five-layer baseline.

It must not be implemented before the current platform contracts, pricing
formulas, provider capability matrix, and safe deterministic test suite have
been stabilized and frozen as the comparison baseline.

### Alternative D: Compare Validated Topology Bundles As Future Work

A topology bundle is a deployable architecture candidate with explicit
capabilities, resources, dependencies, dataflow edges, constraints, and
calculation contracts.

```text
Use-case requirements
        |
        v
Feasible topology templates
        |
        +--> paper-compatible five-layer topology
        +--> provider-native AWS topology
        +--> provider-native Azure topology
        +--> selective multi-cloud topology
        +--> future portable/self-hosted topology
        |
        v
Metric calculation per topology
        |
        v
Constraint filtering and ranking
```

For topology `T = (V, E)`, cost can be generalized without losing the paper's
principles:

```text
cost(T, w)
  = sum(resource_cost(node, workload) for node in V)
  + sum(transfer_cost(edge, workload) for edge in E)
  + fixed_platform_cost(T)
  + optional_migration_cost(T)
```

A topology is considered only if it:

- covers the required Digital Twin capabilities;
- satisfies feature and policy constraints;
- has valid dependency and dataflow contracts;
- has a complete price/evidence contract; and
- is supported by the Deployer.

The paper's model is a constrained special case in which the topology nodes are
the fixed layers and every layer receives one provider assignment.

This alternative is intentionally future work. Building a general architecture
search engine is outside the scope of the current master thesis.

## Azure Messaging Example

The current Azure deployment path is structurally close to the AWS-derived
pipeline:

```text
IoT Hub
  -> Event Grid
  -> L1 Dispatcher Function
  -> L2 Processor/Wrapper Functions over HTTP
  -> Persister Function
  -> Cosmos DB
```

Azure IoT Hub also supports native message routes to Service Bus queues and
topics, Event Hubs, Storage, and Cosmos DB. A provider-specific profile could
therefore investigate whether Azure-managed routing or messaging can replace
part of the custom dispatch path while preserving the required behavior.

Service Bus is a plausible example when durable work queues, independent
consumers, dead-letter handling, or message settlement are required. It is not
automatically the correct or cheapest telemetry path:

- Event Grid, Event Hubs, and Service Bus target different event and messaging
  semantics;
- an additional Service Bus namespace and message operations create their own
  cost;
- direct IoT Hub Service Bus endpoints have feature restrictions, including
  restrictions on sessions and duplicate detection; and
- the current per-device processing, persistence, feedback, and cross-cloud
  requirements may still require compute or adapters.

The correct thesis claim is therefore not that Service Bus is already a better
solution. It is that forcing the AWS-derived service shape onto Azure may exclude
a cheaper or operationally stronger Azure-native implementation. The later
architecture audit should compare complete functionally equivalent profiles
before drawing a conclusion.

## Cross-Provider Event And Messaging Example

Event handling is an especially relevant cross-provider example because the
providers divide similar-looking responsibilities across different products.
There is no reliable one-to-one mapping based on product names:

| Functional need | Azure examples | AWS examples | GCP examples |
|---|---|---|---|
| telemetry ingestion and replay | Event Hubs | Kinesis Data Streams | Pub/Sub |
| discrete event routing | Event Grid | EventBridge | Eventarc |
| durable asynchronous work | Service Bus queues | SQS | Cloud Tasks or Pub/Sub, depending on invocation semantics |
| publish/subscribe fan-out | Event Grid or Service Bus topics | SNS or EventBridge | Pub/Sub |
| IoT-native routing | IoT Hub message routing | IoT Core rules | Pub/Sub-based ingestion path |

These rows are not declarations of exact equivalence. Retention, replay,
ordering, fan-out, filtering, transactions, dead-letter behavior, throughput,
delivery guarantees, invocation control, and pricing differ substantially.
Some services cover several rows, while some requirements need a service
combination.

This matters to the current layer model in three ways:

1. An event or messaging backbone may be a billable implementation resource
   currently hidden inside a layer or an inter-layer edge.
2. Requiring every provider to reproduce the same dispatcher/function chain can
   overstate one provider's cost or omit a cheaper native route.
3. A nonlinear Eventing and Messaging Layer may provide a clearer comparison
   boundary than assigning routing, delivery, replay, and failure handling to
   unrelated functional layers.

The research must compare both representations rather than assume one:

- eventing resources embedded in existing provider-layer profiles; and
- eventing resources grouped into a separate nonlinear `LE` contract.

An eventing profile is eligible for ranking only after its delivery and
processing semantics satisfy the same scenario requirements. For example,
removing a processor function is valid only when no required transformation,
validation, enrichment, feedback, or persistence behavior is lost.

## Two Required Research Matrices

The service landscape and the executable implementation must not be collapsed
into one table.

### Matrix 1: Capability And Pricing-Model Matrix

The first matrix records the relevant event services considered at a defined
research cut-off date, including services that will not be implemented:

| Field | Purpose |
|---|---|
| provider and service | stable candidate identity |
| service family | routing, stream, queue, pub/sub, command/task delivery |
| capabilities | filtering, replay, ordering, fan-out, DLQ, retention, transactions |
| limits and exclusions | unsupported requirements and regional/tier constraints |
| pricing dimensions | operations, messages, bytes, capacity units, retention, transfer |
| source and evidence date | reproducible official price/function evidence |
| scenario eligibility | whether the service can satisfy each comparison contract |
| implementation status | theory-only or implemented reference profile |

This matrix explains why similarly named products are not automatically
equivalent.

### Matrix 2: Scenario Cost Comparison

The second matrix applies one fixed example workload and explicit formulas to
every relevant candidate:

| Field | Purpose |
|---|---|
| scenario and functional contract | identical requirement boundary |
| normalized workload | messages, bytes, peak throughput, retention, consumers |
| provider usage transformation | conversion into provider billing dimensions |
| formula and tier selection | reproducible calculation path |
| service and supporting-resource cost | complete modeled monthly cost |
| functional gaps | missing behavior that invalidates direct ranking |
| feasibility result | eligible or rejected before optimization |
| modeled total and ranking | ranking among feasible candidates only |

The result must distinguish visibility from eligibility:

```text
all investigated services
        |
        v
capability and cost calculation
        |
        +--> visible but infeasible, with missing functionality and modeled cost
        |
        +--> functionally complete
                    |
                    v
              comparable ranking
```

This exposes cases where a provider service appears cheaper because it offers
less functionality, and cases where a provider-native bundle is cheaper even
though its internal structure differs from another cloud.

### Eventing Cost Contract

For eventing profile `e` and normalized workload `w`, the modeled layer cost
must expose its contributing dimensions:

```text
C_LE(e, w)
  = fixed_capacity_cost
  + event_or_operation_cost
  + throughput_or_data_volume_cost
  + retention_and_replay_cost
  + delivery_and_fanout_cost
  + retry_and_dead_letter_cost
  + supporting_compute_cost
```

The extended architecture cost is:

```text
C_extended(p, e, w)
  = sum(existing_layer_costs)
  + C_LE(e, w)
  + sum(cost_of_each_physical_transfer_edge)
```

Every billable resource must have exactly one cost owner. A routing capability
bundled into an L1 product may be referenced by the `LE` capability profile, but
its fixed price cannot be charged again. Transfer is calculated from physical
source, destination, provider, region, and volume rather than from the visual
number of arrows in a diagram.

## Bounded Implementation Strategy

The Deployer and Optimizer do not need to support every service in the research
matrices. The implementation should use a small, curated and versioned reference
profile per provider, selected only after the matrix and functional contract are
reviewed:

```text
aws-eventing-v1
azure-eventing-v1
gcp-eventing-v1
```

Each implemented profile must bind:

- the `LE` functional contract;
- provider resources and non-linear layer connections;
- workload-to-usage transformations;
- pricing classifications and formulas;
- constraints and unsupported behavior;
- Deployer provisioning and lifecycle behavior; and
- deterministic verification evidence.

Theory-only candidates remain visible in the research matrices but cannot enter
the executable optimizer ranking or deployment selection. This keeps the thesis
scope bounded without pretending that unimplemented alternatives are deployable.

## Direct Function Chaining As Architecture Debt

Using a serverless function to trigger another function is not inherently
invalid. The reliability assessment depends on the invocation semantics and on
where durable state, retries, backpressure, failure isolation, and workflow
state are owned.

The problematic form is a direct synchronous chain in the operational data
path:

```text
event
  -> Function A
       -- synchronous HTTP/RPC --> Function B
                                    -- synchronous HTTP/RPC --> Function C
                                                                 -> storage
```

This structure couples the availability and latency of every stage. A slow or
failed downstream stage holds upstream compute open and can cause cascading
timeouts. Retries can repeat already completed side effects unless every stage
is idempotent. There is no natural buffer for traffic spikes, and workflow
state, correlation, partial failure, and recovery logic become distributed
across the functions.

Two different patterns are more defensible:

```text
Brokered event processing

producer
  -> durable queue/topic/stream
       -> idempotent consumer
            -> durable state
            -> next durable event when required
```

```text
Explicit workflow orchestration

trigger
  -> durable workflow/orchestrator
       -> activity A
       -> activity B
       -> activity C
       -> recorded completion or compensating path
```

The brokered pattern is appropriate when telemetry stages can be decoupled and
processed asynchronously. The orchestration pattern is appropriate when steps
must run in a defined order, exchange results, preserve workflow state, or use
central retry and compensation rules. A shallow authenticated synchronous call
can still be valid when an immediate result is part of the functional contract,
but it must not be treated as the default pipeline mechanism.

Provider guidance supports this distinction:

- [AWS describes direct Lambda-to-Lambda invocation as generally an
  anti-pattern](https://docs.aws.amazon.com/lambda/latest/dg/concepts-event-driven-architectures.html)
  because of cost and complexity, while recommending event sources, durable
  functions, or Step Functions according to workflow complexity.
- [Azure Durable Functions](https://learn.microsoft.com/en-us/azure/azure-functions/durable/programming-model-overview)
  provides persistent orchestration and recovery for ordered function
  activities. For asynchronous work, Azure's
  [queue-based load-leveling pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/queue-based-load-leveling)
  uses a durable queue to isolate producers from consumer latency and failure.
- [Google Cloud Workflows](https://docs.cloud.google.com/workflows/docs/overview)
  makes ordered service dependencies and workflow state explicit. Google
  distinguishes decoupled event distribution with Pub/Sub from controlled
  endpoint invocation with
  [Cloud Tasks](https://docs.cloud.google.com/pubsub/docs/choosing-pubsub-or-cloud-tasks).

### Finding In The Current Implementation

The current deployment templates contain direct function chains in every
provider implementation:

| Provider | Current path characteristics | Initial assessment |
|---|---|---|
| AWS | Dispatcher invokes the processor wrapper asynchronously; the wrapper invokes the user processor synchronously and the persister asynchronously; the persister can invoke the event checker asynchronously. | Better isolated than a fully synchronous chain, but explicit queueing, delivery, retry, destination/DLQ, idempotency, and correlation contracts are not consistently represented as part of the architecture profile. |
| Azure | Event Grid triggers the dispatcher; dispatcher, processor wrapper, user processor, persister, and event checker communicate through HTTP calls. Several internal endpoints use anonymous HTTP authorization as a Terraform dependency-cycle workaround. | Not production-grade as a target profile. It combines synchronous failure coupling with an unacceptable authentication workaround. |
| GCP | Dispatcher, processor wrapper, user processor, persister, and event checker use authenticated HTTP calls; Pub/Sub exists in parts of the surrounding deployment. | Authentication is stronger than in the Azure path, but the central HTTP chain still lacks a durable boundary between several operational stages. |

This topology was inherited from the AWS-oriented bachelor implementation and
then adapted across providers. Preserving the same function shape made the
proof of concept easier to compare structurally, but it does not prove that the
result is equally reliable or provider-native.

The finding also affects cost validity. A direct chain can:

- add invocation duration and cold-start cost at every synchronous edge;
- omit the cost of queues, topics, workflow executions, dead-letter storage,
  monitoring, and replay required by a production-ready alternative; or
- make a provider appear more expensive by forcing it to reproduce the
  AWS-derived function topology instead of using a native managed route.

Issue
[#112](https://github.com/TVJunkie724/master-thesis/issues/112) must therefore
reconstruct these call paths as explicit resource and dataflow graphs. For every
provider profile it must record:

- whether each edge is synchronous, asynchronous, buffered, or orchestrated;
- delivery, ordering, retry, timeout, and dead-letter semantics;
- idempotency key and duplicate-processing behavior;
- authentication and trust boundaries;
- correlation and end-to-end observability;
- partial-failure and replay behavior; and
- the complete resource, invocation, transfer, and operational cost.

This review does not yet select Service Bus, SQS, Pub/Sub, Cloud Tasks, Step
Functions, Durable Functions, or Workflows as mandatory replacements. The
correct choice depends on the functional contract of the edge. It does establish
that the current direct chains cannot be accepted as production-ready merely
because they execute successfully in the proof of concept.

### Does An Eventing Layer Remove The Current Hardcoding?

Not by itself. Adding an `eventing_provider` field and provisioning one more
managed service would preserve most of the current rigidity. The audit found
hardcoding at several independent boundaries:

| Boundary | Current coupling |
|---|---|
| Runtime calls | Dispatchers construct processor or connector names; processor wrappers call user processors and persisters; persisters know storage, event-checking, and selected L4 destinations. |
| Event actions | `config_events.json` contains concrete function names and provider-specific action types; event checkers construct ARNs or call function URLs and workflow endpoints. |
| Function catalog | `src/function_registry.py` contains a fixed `Layer` enum, a fixed static function set, and fixed layer-boundary rules. |
| Infrastructure | Terraform exposes seven fixed provider variables and wires concrete function URLs, names, ARNs, resources, and conditional dependencies directly. |
| Optimizer | The cost engine and provider capability contracts require the canonical fixed set `L1`, `L2`, `L3_hot`, `L3_cool`, `L3_archive`, `L4`, and `L5`. |
| Management API | Provider selections are persisted and projected through dedicated `cheapest_l1` to `cheapest_l5` fields, then materialized into seven fixed Deployer keys. |
| Deployment package | The manifest records providers but does not yet describe a versioned architecture profile, logical responsibilities, event contracts, or dataflow edges. |

The existing system already uses provider eventing at the device-ingress edge:

- AWS IoT Core rules invoke the L1 dispatcher;
- Azure IoT Hub events reach the dispatcher through Event Grid; and
- GCP Pub/Sub and Eventarc trigger the dispatcher.

After that first edge, the implementations return largely to direct
function-to-function or function-to-HTTP routing. The existence of a topic or
event source at L1 therefore does not make the remaining layers independent.

#### Independence Has Several Meanings

| Independence dimension | Can `LE` provide it? | Required condition |
|---|---|---|
| Producer does not know consumer location or function name | Yes | Producers publish a logical, versioned event instead of invoking a concrete endpoint. |
| Consumer failure does not immediately fail or block the producer | Mostly | Durable buffering, retry, dead-letter, acknowledgement, and backpressure semantics are explicit. |
| A new consumer can be added without changing the producer | Yes | Fan-out subscriptions are owned by the architecture profile and Deployer. |
| A layer can move to another provider without changing upstream domain code | Mostly | Cross-cloud bridges preserve the same event contract and are infrastructure adapters rather than domain logic. |
| Event schemas can evolve independently | Partly | Compatibility policy, schema versions, consumer contract tests, and migration rules are enforced. |
| All layers can be deployed in any order | No | Brokers, identities, subscriptions, schemas, and data stores still have provisioning dependencies. |
| All runtime interactions can become asynchronous | No | Queries, commands requiring immediate acknowledgement, administration, and some workflow steps remain synchronous by contract. |
| A completely new layer requires no cross-project work | No | A new responsibility still needs profile, pricing, capability, deployment, state, API, and UI support. |

The realistic target is therefore **strong runtime decoupling and bounded
architectural extensibility**, not literal independence.

#### Bounded Target Architecture

The Eventing-extended thesis profile should introduce the following contracts:

1. A versioned `ArchitectureProfile` declares the approved responsibilities and
   edges for `six-layer-eventing@1`.
2. Every asynchronous edge references a logical channel and a versioned event
   contract, not a function name or URL.
3. Each provider has an Eventing adapter that maps logical channels,
   subscriptions, delivery policies, and cross-cloud bridges to the curated
   provider implementation.
4. Producers publish through a small event-publisher port. They do not import a
   downstream function SDK or construct downstream resource names.
5. Consumers declare accepted event types and emit their own output event or
   durable state change. Adding a consumer must not require changing the
   producer.
6. The Deployer resolves physical topics, queues, routes, identities, and
   subscriptions from the architecture profile and records them in deployment
   evidence.
7. Every edge declares delivery semantics, ordering scope, retention, retry,
   dead-letter handling, idempotency key, correlation metadata, trust boundary,
   and cost owner.
8. Synchronous read and control paths remain explicit typed ports. They are not
   forced through Eventing merely to make the diagram look uniform.

`LE` must not be inserted mechanically between every helper function. The
decoupling unit is an architectural responsibility or a required fan-out
boundary, not every implementation method:

- the L2 wrapper and user processor can become one packaged processing
  component when separate runtime isolation is not a functional requirement;
- if user-code isolation is required, that internal L2 interaction needs an
  explicit activity or work-queue contract, but it remains an implementation
  detail of L2;
- L3 hot-to-cold and cold-to-archive transitions may use provider-native
  lifecycle policies where these satisfy the shared contract; and
- cross-cloud storage movement, L4 state updates, alerts, and feedback are
  explicit edges because they cross responsibility, provider, trust, or
  delivery boundaries.

This prevents the Eventing profile from replacing one over-segmented function
chain with an equally rigid and more expensive chain of topics.

Illustrative logical flow:

```text
L1 acquisition
  |
  | publishes telemetry.received.v1
  v
LE logical channel
  |
  +--> L2 processor subscription
  |       |
  |       | publishes telemetry.processed.v1
  |       v
  |     LE logical channel
  |       |
  |       +--> L3 persistence subscription
  |       +--> L4 Twin-state subscription
  |       +--> event-rule subscription
  |
  +--> audit or future analytics subscription

L5 query/read path -- typed synchronous API --> L4 or L3 read capability
```

`LE` is a logical layer and may be implemented by more than one physical
broker, topic, queue, or cross-cloud bridge. A single global broker would create
a new central dependency and could distort transfer cost, latency, and
availability. The provider profile must therefore own the physical topology
while preserving the same logical contracts.

#### Refactoring Outcome Required For The Thesis Profile

The Eventing work has solved the relevant rigidity only when all of the
following are true:

- changing the provider of a downstream asynchronous responsibility does not
  require editing the upstream function;
- adding a second consumer does not require changing or redeploying the
  producer;
- no domain function constructs another domain function's name, ARN, or URL;
- event and command contracts are versioned and tested across all provider
  adapters;
- the architecture profile, rather than scattered conditionals, is the source
  of truth for active nodes and edges;
- the Optimizer, Management API, Deployer, and Flutter client identify the
  architecture profile version explicitly; and
- unsupported profile or provider combinations fail before calculation or
  deployment.

Even after this refactoring, adding a completely new architectural
responsibility is not a zero-code operation. It should become a modular
cross-project extension instead of a rewrite: add the profile responsibility,
provider implementations, pricing and capability contracts, deployment
adapter, state projection, and UI representation without modifying unrelated
existing responsibilities.

### Closed-World Architecture Profile Boundary

The agreed target is a closed-world model: runtime users select one of a small
set of reviewed architecture profiles, while developers can extend the catalog
through versioned code and data contracts.

The thesis implementation should initially expose exactly two profiles:

```text
five-layer-baseline@1
  original paper-compatible functional boundaries

six-layer-eventing@1
  baseline responsibilities plus explicit Eventing and Messaging
```

The second name is intentionally `six-layer-eventing@1`. Eventing is modeled as
an additional logical responsibility even though its edges are not a linear
sixth step after L5.

The user does not:

- create arbitrary layers;
- enable and disable individual layers;
- draw or edit a deployment graph;
- supply Terraform;
- choose physical function names or endpoints; or
- create provider-service combinations that are absent from the reviewed
  catalog.

This keeps the architecture reproducible and the optimization search bounded.
A developer may add a new profile version, provider implementation, or
component adapter, but the complete profile must pass contract, capability,
cost, and deployment validation before it becomes selectable.

#### Four Distinct Models

| Model | Responsibility | Expected owner |
|---|---|---|
| `ArchitectureProfile` | Logical Digital Twin responsibilities, required capabilities, approved edges, edge semantics, extension slots, and profile version | Shared architecture contract |
| `ProviderImplementationProfile` | Curated AWS, Azure, or GCP service bundle that realizes one or more logical responsibilities, including constraints, pricing formulas, and internal resources | Optimizer and Deployer contract |
| `DeploymentComponentCatalog` | Concrete Terraform modules, provider adapters, function templates, runtime wrappers, permissions, artifacts, and output bindings | Deployer-internal implementation catalog |
| `ResolvedTwinArchitecture` | Immutable deployment decision for one Twin: profile version, provider assignments, selected implementation bundles, component instances, and logical-to-physical bindings | Management API and deployment manifest |

Function templates and other currently hard-coded runtime artifacts therefore
remain explicit. They move behind registered deployment components rather than
being distributed as implicit knowledge across Flutter fields, API columns,
Terraform string conventions, and function source code.

A Terraform module is not a logical layer. It is one reusable infrastructure
implementation unit that may provision all or part of a provider-specific
implementation profile. Conversely, one logical layer may require several
Terraform modules and runtime artifacts.

#### Resolution Before Infrastructure Execution

The target deployment dataflow is:

```text
user selects approved architecture profile
                  |
                  v
workload and functional requirements
                  |
                  v
Optimizer selects admissible provider implementations
                  |
                  v
Management API creates ResolvedTwinArchitecture
                  |
                  v
Deployer resolves component graph and runtime bindings
                  |
                  v
contract + graph + permission + artifact preflight
        |                         |
        | invalid                 | valid
        v                         v
typed failure before       Terraform plan/apply
Terraform execution              |
                                 v
                    runtime outputs and evidence
```

The resolved graph must be complete before infrastructure execution. Every
required input declares its source; every provided output has one stable
logical identifier; duplicate, missing, incompatible, or unauthorized bindings
fail before `terraform plan`.

Terraform should consume provider-resource references, module outputs, and
validated binding objects. It must not depend on several independently repeated
string conventions for function names, URLs, ARNs, topics, or storage
resources. A centralized naming policy may still produce physical resource
names, but domain code and user code must not reconstruct those names.

Some runtime values only exist after infrastructure provisioning. Those values
must use an explicit staged deployment contract:

1. provision identities, infrastructure resources, and stable endpoints;
2. collect typed provider outputs;
3. build or configure runtime artifacts from validated bindings; and
4. record the final binding evidence and artifact hashes.

This does not make Terraform or cloud providers infallible. Quotas, eventual
consistency, IAM propagation, regional incompatibility, provider drift, and
cloud outages remain possible. The architectural gain is that missing or
misnamed internal references become deterministic preflight or plan failures
instead of scattered runtime surprises.

#### Persistence And API Target

The current dedicated provider-selection fields such as `cheapest_l1` through
`cheapest_l5` encode the present topology in the database and API. The target
stores:

```text
TwinArchitecture
  twin_id
  profile_id
  profile_version
  resolution_status
  resolved_at

ArchitectureAssignment
  twin_architecture_id
  responsibility_id
  provider
  implementation_profile_id
  implementation_profile_version
```

The assignment rows are optimizer output and deployment input. They are not a
free-form user topology. This representation allows another reviewed profile
to add a responsibility without adding another `cheapest_*` column throughout
the Management API and Flutter client.

#### Flutter Target

The configuration workflow should expose architecture intent without becoming
an infrastructure editor:

1. **Architecture:** select one approved profile and inspect a read-only
   flowchart, responsibilities, and functional differences.
2. **Workload:** enter the scenario quantities required by the selected
   profile.
3. **User Logic:** bind supported processing or event actions to declared
   extension slots.
4. **Optimize And Review:** inspect admissibility, provider assignments, cost
   evidence, and profile-specific warnings.
5. **Deployment Review:** inspect the resolved architecture and deployment
   consequences before execution.

The flowchart is derived from the selected `ArchitectureProfile`; it is not
editable. Provider implementation details may be inspected during review but
cannot be assembled into unsupported combinations by the user.

#### User Logic Is A Separate Hardening Boundary

The platform still needs an explicit decision about how much function logic a
user may control. The supported surface must be narrower than a provider
function editor:

- the platform owns resource names, runtime handlers, provider entrypoints,
  topology bindings, credentials, permissions, lifecycle, and observability;
- the user supplies domain logic through a versioned extension slot with typed
  input and output contracts;
- non-secret configuration is typed and validated;
- secrets are injected through references and are never embedded in source,
  manifests, logs, or Terraform variables;
- runtime, dependency, artifact, timeout, network, retry, and resource policies
  are explicit; and
- packaging is deterministic and must not rewrite user source to insert
  physical service names.

Whether the user processor runs in the same deployable component as its
platform wrapper or in an isolated worker is a trust and failure-isolation
decision. Merely placing several functions in one Azure Function App does not
remove their runtime coupling. If wrapper and user logic form one trusted L2
component, the cleaner implementation is an in-process module behind a stable
interface. If isolation is required, the boundary needs a durable work contract
and remains an internal implementation detail of L2.

The complete audit and implementation contract is tracked in
[#113](https://github.com/TVJunkie724/master-thesis/issues/113). It includes the
narrower dependency-validation work already tracked in
[#36](https://github.com/TVJunkie724/master-thesis/issues/36).

## Recommended Research And Implementation Sequence

The direction is deliberately incremental.

### Stage 0: Stabilize And Freeze The Current Platform

- Complete the remaining current-system refactoring and hardening.
- Complete pricing, tier, formula, evidence, and provider capability contracts.
- Complete current UI and simulator behavior without redesigning it around
  `LE`.
- Preserve broad deterministic unit, integration, contract, security, and build
  gates.
- Preserve the five functional and cost-accounting boundaries, not every
  inherited function-to-function invocation as an architectural invariant.
- Build a complete Function-and-Edge Matrix before changing the baseline
  topology. Classify every edge as an in-component call, synchronous command or
  query, asynchronous responsibility boundary, durable workflow, storage
  transition, or cross-cloud boundary.
- Decide and document the hardened implementation of each baseline edge from
  its functional contract. Do not assume in advance that every direct call must
  remain or that every edge must move to a broker.
- Fix security-critical defects in retained direct-call paths and include every
  required support resource in deployment and cost evidence.
- Record the resulting five-layer implementation as the reproducible baseline.
- Defer supervised cost-incurring live-cloud E2E until all planned architecture
  work and the manual UI audit are complete.

The historical bachelor topology and the hardened five-layer baseline are
different evidence objects. The former explains provenance. The latter is the
executable comparison baseline. Hardening may merge implementation helpers that
belong to one responsibility or replace an unsafe internal edge, provided that
the five functional contracts, observable behavior, workload assumptions, and
all resulting resource costs remain explicit.

Any eventing infrastructure used only as a fixed internal support resource of
the five-layer baseline is part of that provider implementation and is not an
independently optimized layer. `six-layer-eventing@1` is a separate experiment
because it makes Eventing and Messaging an explicit functional, deployable, and
costed responsibility.

### Stage 1: Paper-Compatible Layer Cost Optimization

- Preserve the current functional layer contract.
- Permit curated provider-specific implementation profiles within that contract.
- Preserve workload and cost/pricing primitives.
- Compare AWS, Azure, GCP, and federated layer assignments where capability and
  deployment contracts are complete.
- Keep transfer costs explicit.
- Use this profile for replication, evaluation, and direct comparison with the
  published results.

### Stage 2: Eventing-Extended Cost Optimization

- Define the nonlinear `LE` functional contract and workload schema.
- Build both research matrices.
- Select one functionally comparable reference profile per provider.
- Design the multi-cloud event bridge explicitly, including trust boundary,
  authentication, delivery guarantees, retry and dead-letter behavior,
  idempotency, ordering, observability, data transfer, and cost ownership.
- Extend calculation, capability, deployment, and result contracts explicitly.
- Compare the five-layer baseline with the `LE`-extended model as separate
  experiments.
- Keep theory-only event services outside executable optimizer and Deployer
  selection.

### Out-Of-Scope Profile: General Architecture-Topology Optimization

- Compare complete validated topology bundles.
- Map each topology back to required capabilities.
- Calculate node and edge metrics rather than assuming one scalar per layer.
- Permit provider-native service bundles and omitted technical stages where
  functionality is still covered.
- Treat this as a separate experiment with separate assumptions, result schema,
  and validity discussion.

The general topology profile must not be presented as a transparent extension
of the two bounded layer models. It answers a broader research question and is
outside the implementation scope of this thesis. No general dynamic
architecture engine is planned.

## Implications For Other Optimization Objectives

The five layers can remain reporting categories, but they are usually
insufficient as the only calculation structure for other objectives.

| Objective | Additional model required |
|---|---|
| Monetary cost | resource prices, workload quantities, tiers, node costs, transfer edges |
| Latency | regions, routing path, processing stages, queueing, invocation behavior, network edges |
| Availability | dependencies, redundancy, failure domains, retry/DLQ behavior, provider outages |
| Sustainability | resource consumption, region-specific energy/carbon evidence, utilization |
| Compliance | data location, service eligibility, identity/trust boundaries, retention |
| Operability | resource count, deployment complexity, observability, manual prerequisites |
| Vendor lock-in | migration paths, proprietary models/APIs, exportability, switching cost |

Some objectives can be constraints around the existing cost optimizer. Others,
especially latency and resilience, depend on topology and cannot be represented
honestly by changing only the per-layer scoring formula.

Therefore, a new optimization objective does not automatically require a
different deployed architecture. It does require a metric model rich enough to
evaluate the architecture. When the metric depends on paths, dependencies, or
failure domains, the architecture representation must also become richer.

## Thesis-Scope Recommendation

1. Stabilize and freeze the paper-compatible five-layer implementation as the
   cost-optimization baseline.
2. Finish current-system refactoring, UI behavior, pricing, tier, formula,
   evidence, capability, and transfer correctness before changing the
   architecture search space.
3. Document the paper/current L2-L3 numbering difference everywhere layer IDs
   cross a public contract.
4. Define functional completeness criteria before comparing provider
   implementations.
5. Use the later architecture audit to reconstruct the actual deployed resource
   graph rather than inferring it from layer labels.
6. Build a capability/pricing-model matrix and a separate scenario cost matrix
   for event services.
7. Investigate `LE` as a nonlinear Eventing and Messaging Layer.
8. Implement only one curated reference eventing profile per provider after the
   comparison contract is fixed.
9. Treat general topology optimization as rigorously specified future work.
10. Never compare candidates that provide materially different Digital Twin
   capabilities without exposing the difference as a requirement or constraint.

## Questions For The Later Architecture Audit

- Which Digital Twin capabilities are mandatory in every evaluated scenario?
- Which current layers are scientific comparison boundaries, deployment
  boundaries, or merely historical module boundaries?
- What is the minimum functional completeness contract for every compared
  provider implementation?
- Which deployed services span several layers or exist only as cross-cloud glue?
- Does each provider-layer result describe a genuinely deployable equivalent?
- Which provider-native integrations remove resources or transfer edges?
- Which existing and proposed connections from `LE` to L1-L5 are mandatory for
  each scenario?
- Does an independent `LE` provider assignment produce a valid and secure
  topology?
- Which event services belong in the broad research matrices, and which three
  curated profiles are deployable reference implementations?
- Which costs are currently omitted when a provider-native bundle is decomposed
  into layers?
- Which non-cost metrics can be measured deterministically with available
  evidence?
- Which metrics require live benchmarks or remain explicit assumptions?
- Can a small topology catalog remain understandable and testable within the
  thesis scope?

## Current Research State

No current implementation contract is changed by this review.

The five-layer model remains necessary as the current paper-compatible baseline.
A nonlinear `LE` Eventing and Messaging Layer is now a serious bounded research
candidate, not an approved implementation contract. The existing system must be
stabilized first. Stabilization preserves the five functional and cost
boundaries but does not pre-approve the inherited direct-call topology; that
decision requires the Function-and-Edge Matrix and explicit baseline edge
contracts. The capability matrix, scenario cost matrix, architecture audit, and
multi-cloud bridge design will then determine the Eventing contract and one
curated implementation profile per provider. General topology optimization
remains a separate future research direction.
