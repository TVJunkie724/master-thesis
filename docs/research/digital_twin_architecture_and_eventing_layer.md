# Digital Twin Architecture And Eventing Layer Research Note

## Purpose

This research note records a source-based assessment of the Digital Twin
decomposition used by Twin2MultiCloud. It is input for the later thesis
synthesis and the architecture audit in GitHub issue
[#112](https://github.com/TVJunkie724/master-thesis/issues/112), not a decision
to replace the implemented architecture. It is deliberately not part of the
published user and developer documentation.

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

The fair approach is to preserve the source topology as a reproducible baseline,
identify its assumptions and limits, and evaluate a bounded alternative against
the same workload and functional contract. Replacing a source-project
anti-pattern is justified only when the new architecture has explicit evidence,
complete cost ownership, and equivalent required behavior.

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

## Recommended Research And Implementation Sequence

The direction is deliberately incremental.

### Stage 0: Stabilize And Freeze The Current Platform

- Complete the remaining current-system refactoring and hardening.
- Complete pricing, tier, formula, evidence, and provider capability contracts.
- Complete current UI and simulator behavior without redesigning it around
  `LE`.
- Preserve broad deterministic unit, integration, contract, security, and build
  gates.
- Fix security-critical defects in the existing direct-call path, but do not
  spend a separate phase making a topology that `LE` is expected to replace
  appear permanently production-final.
- Record the resulting five-layer implementation as the reproducible baseline.
- Defer supervised cost-incurring live-cloud E2E until all planned architecture
  work and the manual UI audit are complete.

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
- Extend calculation, capability, deployment, and result contracts explicitly.
- Compare the five-layer baseline with the `LE`-extended model as separate
  experiments.
- Keep theory-only event services outside executable optimizer and Deployer
  selection.

### Future Profile: General Architecture-Topology Optimization

- Compare complete validated topology bundles.
- Map each topology back to required capabilities.
- Calculate node and edge metrics rather than assuming one scalar per layer.
- Permit provider-native service bundles and omitted technical stages where
  functionality is still covered.
- Treat this as a separate experiment with separate assumptions, result schema,
  and validity discussion.

The general topology profile must not be presented as a transparent extension
of the two bounded layer models. It answers a broader research question and
remains future work. No general dynamic architecture engine is planned.

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
stabilized first. The capability matrix, scenario cost matrix, and architecture
audit will determine the functional contract and one curated implementation
profile per provider. General topology optimization remains a separate future
research direction.
