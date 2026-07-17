# Research Questions And Evaluation Design

## Purpose And Status

This note is the research source of truth for the working research questions,
their rationale, the evidence required to answer them, and the relationship
between the implementation and the thesis evaluation.

The question set was accepted as the working direction during the architecture
discussion on 2026-07-17. It is not yet final thesis prose. The wording must be
reviewed once more when the implementation scope and evaluation scenarios are
frozen, before it replaces the commented scaffold in
`twin2multicloud-latex/chapters/introduction.tex`.

This note is deliberately separate from the published user and developer
documentation. Product documentation explains the implemented system. This
document records scientific intent, evaluation reasoning, and thesis scope.

Related research material:

- [Related Work: Multi-Cloud Cost, Functional Comparability, And Event-Driven Digital Twins](related_work_multicloud_cost_comparability_eventing.md)
- [Digital Twin Architecture And Eventing Layer](digital_twin_architecture_and_eventing_layer.md)
- [Pricing Evidence Dataflow](pricing_evidence_dataflow.md)
- [Cloud Pricing Industry Context](cloud_pricing_industry_context.md)

## Core Thesis Focus

The thesis is not about constructing an arbitrary Digital Twin or a general
multi-cloud architecture generator. It investigates how a theoretical,
layer-based cloud cost optimization can be turned into a functionally complete,
traceable, and reproducibly deployable multi-cloud Digital Twin platform.

The central scientific concern is:

> A cost comparison is only meaningful when every compared architecture
> satisfies the same required Digital Twin functionality. Otherwise, a cheaper
> but functionally incomplete architecture can incorrectly win the
> optimization.

The implementation therefore connects five concerns that must remain
consistent:

```text
workload and functional requirements
                 |
                 v
versioned Digital Twin architecture profile
                 |
                 v
functionally admissible provider implementations
                 |
                 v
evidence-backed cost calculation and optimization
                 |
                 v
reproducible deployment and verification
```

## Why The Earlier Research Questions Need Revision

The current LaTeX introduction contains three commented research questions.
They focus on:

1. building a configuration-driven multi-cloud Digital Twin platform;
2. refactoring and integrating the optimizer and Deployer prototypes; and
3. identifying and resolving deployment failures.

These questions were useful for the initial engineering scope, but they no
longer represent the strongest scientific framing.

| Earlier focus | Assessment | Disposition |
|---|---|---|
| Configuration-driven platform | Central, but too broad | Retain and sharpen as RQ1 |
| Prototype refactoring and integration | Important engineering method and contribution | Describe in method, architecture evolution, and contributions |
| Deployment failures | Relevant evaluation evidence and lessons learned | Treat as supporting evidence for RQ1 and Discussion |
| Functional equivalence | Missing | Add as RQ2 |
| Cost effect under equivalent functionality | Only implicit | Add as RQ3 |
| Eventing architecture effect | Missing | Add as bounded sub-question RQ3.2 |

Refactoring remains a substantial thesis contribution. It does not need to be a
main research question unless the thesis is reframed primarily as a study of
legacy-system modernization, which is not the current objective.

Deployment failures remain important because they reveal where a theoretical
provider allocation is not yet deployable. They are evidence about
operationalization, not the primary research object.

## Working Research Questions

### RQ1: Operationalization

> **How can a configuration-driven platform operationalize a layered,
> cost-aware Digital Twin model into reproducible deployments across AWS,
> Azure, and Google Cloud?**

#### Intent

RQ1 asks how the theoretical Twin2Clouds cost model becomes an executable
system. The answer must cover more than API integration. It includes contracts,
state, pricing evidence, provider capabilities, credentials, deployment
manifests, infrastructure provisioning, traceability, and verification.

#### Method

- Analyze the optimizer and Deployer predecessor projects.
- Define explicit contracts between workload intent, optimization result,
  Management API state, and deployment manifest.
- Refactor provider and strategy boundaries without discarding validated core
  logic.
- Implement a configuration-driven workflow through the Management API and
  Flutter client.
- Establish deterministic validation, preflight, observability, error handling,
  and verification boundaries.
- Verify behavior through unit, contract, integration, Docker, demo, and later
  supervised live-cloud end-to-end tests.

#### Required Evidence

- Versioned API and deployment contracts.
- Trace from input configuration to optimizer result and deployment decision.
- Provider capability agreement between Optimizer and Deployer.
- Deterministic configuration and credential validation.
- Reproducible deployment manifests and ephemeral workspaces.
- Tests covering supported provider and layer combinations.
- Documented deployment failure modes and their resolutions.
- Final live-cloud evidence after the implementation and manual UI audit are
  complete.

#### Expected Answer Shape

The thesis should answer RQ1 with an architecture and an evaluated engineering
method, not with a simple yes/no result. The answer should identify the
contracts and controls required to transform a cost result into a deployable
Digital Twin.

#### Scope Boundary

RQ1 does not claim a generic deployment platform for arbitrary cloud
applications. It is limited to the supported Twin2MultiCloud Digital Twin
profiles, providers, services, and configuration schema.

### RQ2: Functional Comparability

> **How can provider-specific cloud services be mapped to functionally complete
> and cost-comparable Digital Twin architecture profiles without assuming
> one-to-one service equivalence?**

#### Intent

RQ2 addresses construct validity. Product names and broad provider categories
do not prove that two services satisfy the same functional requirement. A
provider may implement one responsibility through one managed service, while
another provider requires a bundle of services or offers a differently scoped
capability.

The comparison unit is therefore not automatically one cloud product. It is a
curated provider implementation profile that satisfies a shared functional
contract.

#### Method

1. Define mandatory Digital Twin capabilities for the evaluated architecture
   profile.
2. Define the workload, behavioral, delivery, retention, and operational
   requirements relevant to each architecture responsibility.
3. Build a provider capability and pricing-model matrix.
4. Map one curated implementation profile per provider to each evaluated
   responsibility.
5. Record missing, additional, or materially different functionality.
6. Reject profiles that fail mandatory requirements before cost ranking.
7. Compare costs only among admissible profiles.

#### Functional-Completeness Gate

```text
provider implementation profile
              |
              v
mandatory capability checks
       |                |
       | fail           | pass
       v                v
excluded with       pricing and formula
explicit reason     validation
                         |
                         v
                  cost comparison
```

The gate must be deterministic and explainable. Cost cannot compensate for a
missing mandatory capability.

#### Required Evidence

- Versioned functional contracts.
- Capability matrix for AWS, Azure, and GCP.
- Service or service-bundle mappings with rationale.
- Provider capability contract exposed by Optimizer and Deployer.
- Pricing model, formula, unit, tier, and workload-input mapping per profile.
- Explicit unsupported and non-comparable states.
- Tests proving that incomplete candidates cannot enter the publishable
  optimization path.

#### Expected Answer Shape

RQ2 should produce:

- a method for defining comparison boundaries;
- an explicit functional matrix;
- curated provider implementation profiles;
- admissibility rules; and
- a discussion of unavoidable differences and threats to equivalence.

It should not claim that AWS, Azure, and GCP services are universally
equivalent.

#### Scope Boundary

The thesis does not need to catalogue every potentially relevant provider
service. It evaluates a bounded, justified profile per provider. Alternative
services can be shown in the theoretical matrix without becoming executable
optimizer or Deployer choices.

### RQ3: Cost Effect

> **To what extent can layer-wise multi-cloud service selection reduce
> estimated operational cost compared with functionally equivalent
> single-cloud baselines?**

#### Intent

RQ3 is the primary quantitative evaluation question. It evaluates whether the
multi-cloud allocation selected by the optimizer provides an estimated cost
advantage after functional-completeness constraints, service-specific pricing
models, transfer costs, and deployment support are taken into account.

#### Method

- Select bounded workload scenarios from the Twin2Clouds baseline and the
  implemented platform capabilities.
- Freeze the workload, architecture profile version, region assumptions,
  pricing snapshot, currency, and calculation strategy for each comparison.
- Calculate each admissible single-provider baseline within the selected
  architecture profile.
- Calculate the federated provider allocation within the same architecture
  profile.
- Include cross-cloud transfer and required glue costs.
- Preserve intent, selected pricing evidence, normalization, formula, tier, and
  result traces.
- Compare estimated monthly totals and the provider allocation per
  architecture responsibility.
- Repeat the procedure independently for another architecture profile when its
  functional contract differs. Do not place candidates from different profiles
  into one optimization result set.

#### Required Evidence

- Reproducible scenario inputs.
- Reviewed and versioned pricing snapshots.
- Complete formula and unit contracts.
- Single-provider cost totals.
- Multi-cloud cost total and selected path.
- Transfer and glue cost attribution.
- Traceable service-level and layer-level cost contributions.
- Sensitivity discussion for price, workload, tier, and profile assumptions.

#### Expected Answer Shape

The result should report:

- absolute estimated monthly cost;
- relative difference from each single-provider baseline;
- selected provider profile per architecture responsibility;
- cost contribution and evidence;
- excluded candidates and reasons; and
- conditions under which the multi-cloud result changes.

The answer must say "estimated operational cost" rather than claiming observed
provider billing unless billing data is collected and reconciled separately.

## RQ3 Sub-Questions

### RQ3.1: Single-Cloud And Multi-Cloud Baselines

> **How do single-cloud and multi-cloud configurations compare under identical
> workload and functional requirements?**

RQ3.1 controls the comparison:

- identical workload;
- identical mandatory functionality;
- identical architecture profile version;
- identical pricing snapshot time or documented snapshot set;
- explicit region and currency assumptions; and
- identical calculation and evidence policy.

It is answered by the functional matrix, the scenario cost matrix, and the
federated optimization result.

### RQ3.2: Eventing And Messaging Extension

> **How does introducing an explicit Eventing and Messaging Layer affect
> functional coverage, architecture topology, and total estimated cost?**

#### Intent

The bachelor implementation and current baseline rely heavily on direct
function invocation and provider-specific event mechanisms embedded in other
layers. RQ3.2 investigates whether Eventing and Messaging should become an
explicit architectural responsibility with owned functionality and cost.

The proposed Eventing and Messaging Layer, `LE`, may connect multiple existing
layers:

```text
                 +-------------------------+
                 | Eventing and Messaging |
                 | route, queue, replay,  |
                 | fan-out, delivery      |
                 +---+----+----+----+-----+
                     |    |    |    |
                    L1   L2   L4   L5
                           |
                          L3
```

It is not required to be a linear stage between two existing layers.

#### Two Required Eventing Matrices

**Matrix A: Functional and pricing-model comparison**

This matrix compares:

- routing and filtering;
- queueing and buffering;
- publish/subscribe and fan-out;
- delivery guarantees;
- retry and dead-letter behavior;
- ordering;
- retention and replay;
- throughput and scaling model;
- integration targets;
- pricing basis and tiers; and
- operational prerequisites.

It may contain more services than the executable implementation.

**Matrix B: Scenario cost comparison**

This matrix applies one fixed workload and required capability set to the
curated provider profiles. It calculates comparable eventing costs and makes
visible where a provider gains or loses cost because its service bundle
provides more or less functionality.

#### Executable Scope

- One curated, functionally admissible eventing profile per provider.
- Explicit Eventing workload and cost contract.
- Explicit eventing nodes and edges in the architecture profile.
- Complete ownership of eventing, transfer, glue, and function costs with no
  double counting.
- Separate evaluation of the five-layer baseline and the Eventing-extended
  profile.

#### Non-Goals

- No arbitrary user-defined topology.
- No optimizer support for every event service offered by every provider.
- No claim that Event Grid, Event Hubs, Service Bus, EventBridge, SQS, SNS,
  Pub/Sub, and Cloud Tasks are interchangeable.
- No dynamic architecture synthesis.
- No replacement of the original Twin2Clouds baseline.

#### Expected Answer Shape

RQ3.2 should identify:

- which functional debt the explicit Eventing responsibility resolves;
- how the deployed resource graph changes;
- which costs move from functions or glue into event services;
- whether provider rankings change;
- which additional functionality is gained; and
- whether the comparison remains valid under the shared functional contract.

## Evaluation Sequence

The four previously discussed analysis steps are evaluation instruments, not
four separate primary research questions.

| Step | Evaluation artefact | Research question answered |
|---|---|---|
| 1. Functional total matrix | Capability coverage and admissible provider profiles, evaluated separately for each architecture profile | RQ2 |
| 2. Single-provider total cost | AWS, Azure, and GCP baselines under identical inputs within one profile | RQ3.1 |
| 3. Eventing deep dive | Functional and scenario cost matrices that define and validate `six-layer-eventing@1` | RQ3.2 |
| 4. Overall optimization | Best admissible allocation within each profile, followed by an explicit functional, topology, and cost delta between profiles | RQ3 |

The evaluation contains two separate experiment paths:

```text
five-layer-baseline@1
  |
  +--> functional-completeness gate
  |          |
  |          v
  |     single-cloud baselines
  |          |
  |          v
  |     multi-cloud optimum
  |
six-layer-eventing@1
  |
  +--> functional-completeness gate and Eventing matrices
             |
             v
        single-cloud baselines
             |
             v
        multi-cloud optimum

the two independently evaluated profiles
             |
             v
functional delta + topology delta + estimated cost delta
             |
             v
interpretation and threats to validity
```

The five-layer result reproduces and extends the original Twin2Clouds result
space. The Eventing-extended result is a second experiment with its own
functional contract and admissible candidates.

The optimizer must not choose one global winner from a candidate pool that
mixes both profiles. Such a ranking would be valid only if both profiles were
shown to satisfy the same mandatory scenario contract despite their structural
differences. The default thesis interpretation instead reports:

- the best single-cloud and multi-cloud result for `five-layer-baseline@1`;
- the best single-cloud and multi-cloud result for
  `six-layer-eventing@1`; and
- the additional functionality, topology change, and estimated cost delta
  introduced by `LE`.

## Evaluation Constructs

| Construct | Operationalization |
|---|---|
| Workload | Versioned scenario input with device, message, execution, storage, query, user, and retention quantities |
| Functional completeness | Mandatory capability checks for the selected architecture profile |
| Provider implementation | Curated service or service-bundle profile for one provider |
| Cost | Estimated monthly monetary cost in a declared currency |
| Transfer | Explicit cross-provider data volume, egress price, and required receiving/glue execution |
| Architecture | Versioned profile with responsibilities, implementation slots, and relevant edges |
| Evidence | Provider pricing row, official static source, reviewed decision, normalization, and formula trace |
| Deployability | Agreement between Optimizer and Deployer capability contracts plus successful manifest validation |
| Reproducibility | Versioned inputs, contracts, pricing snapshot, code revision, and verification commands |

## Verification Gates

A scenario result is thesis-evaluable only when:

1. The workload input passes schema and semantic validation.
2. The architecture profile and calculation strategy versions are recorded.
3. Every selected provider profile passes mandatory capability checks.
4. Every required pricing field has admissible evidence.
5. Units, tiers, free allowances, minimums, and formulas are validated.
6. Emergency fallbacks are absent from publishable calculation results.
7. Transfer and glue costs are attributed exactly once.
8. The Optimizer and Deployer agree on provider-layer availability.
9. The deployment manifest is valid for the selected architecture.
10. The complete intent-to-result trace is inspectable.
11. The result can be recreated from recorded inputs and evidence.
12. Candidates from different architecture profiles are not ranked in one
    result set unless their mandatory functional contract is demonstrably
    identical.
13. Live-cloud claims are made only after the deferred supervised end-to-end
    evaluation has been executed.

Failure of a gate must produce an explicit non-publishable or unsupported result
rather than a misleading numeric optimum.

## Architecture Extensibility Implication

The current refactoring introduced strong extension points for:

- optimization objectives and scoring strategies;
- pricing intents, sources, normalizers, and evidence;
- calculation formulas and provider component calculators;
- cloud provider strategies;
- deployment manifests and provider capability contracts; and
- result traceability.

However, the current layer set remains encoded explicitly across the Optimizer,
Deployer, Management API, database projection, and Flutter models. Adding a new
service inside an existing responsibility is a bounded extension. Adding `LE`
as a new architectural responsibility is still a cross-project contract
change.

Before implementing `LE`, the system should introduce a bounded, versioned
architecture-profile contract:

```text
five-layer-baseline@1
  responsibilities: L1, L2, L3-hot, L3-cool, L3-archive, L4, L5
  edges: baseline data flows

six-layer-eventing@1
  responsibilities: baseline responsibilities plus LE
  edges: explicit eventing and messaging flows
```

This contract should make the two approved profiles data-driven and iterable.
It must not become a general architecture editor or arbitrary topology engine.
Each profile owns its admissibility gate, candidate set, and optimization run.
Cross-profile evaluation compares reported deltas; it does not silently merge
different functional scopes into one ranking.

## Contribution Mapping

| Contribution | Primary RQ | Supporting RQ |
|---|---|---|
| Refactored and integrated platform | RQ1 | RQ2 |
| Versioned workload, pricing, optimization, and deployment contracts | RQ1 | RQ2, RQ3 |
| Evidence-backed pricing and intent-to-result traceability | RQ3 | RQ1 |
| Functional-completeness gate and provider profiles | RQ2 | RQ3 |
| Reproducible multi-cloud deployment and verification | RQ1 | RQ3 |
| Single- versus multi-cloud cost evaluation | RQ3.1 | RQ3 |
| Eventing and Messaging Layer investigation | RQ3.2 | RQ2, RQ3 |
| Documented architecture debt and bounded evolution from predecessors | RQ1 | RQ2 |

## Thesis Chapter Mapping

| Thesis section | Research-question role |
|---|---|
| Introduction | Problem, objective, final RQ wording, contributions |
| Background | Digital Twins, cloud pricing, multi-cloud, service composition, event-driven architecture |
| Related Work | Position the four literature streams and research gap |
| Predecessor Analysis | Explain inherited models, prototypes, assumptions, and debt |
| Method | Functional gate, provider profiles, evidence model, scenarios, and comparison protocol |
| System Architecture | Answer the design part of RQ1 and show extension boundaries |
| Evaluation | RQ3.1 baseline, RQ3 multi-cloud result, and RQ3.2 Eventing experiment |
| Discussion | Answer all RQs, interpret provider differences, and discuss validity |
| Conclusion | Concise answers and future work |

## Threats To Validity

### Construct Validity

- A layer name does not prove equivalent functionality.
- A service bundle may provide more functionality than another provider's
  candidate.
- Estimated cost does not equal observed billing.
- Provider pricing units and tiers may not map cleanly to one canonical metric.
- A curated profile may hide other valid provider-native architectures.

### Internal Validity

- Formula, unit, tier, or free-allowance errors may alter rankings.
- Cross-cloud transfer or glue costs may be omitted or double counted.
- Pricing evidence may drift between providers or collection times.
- Unsupported deployment paths may appear economically attractive unless
  capability gates are enforced.

### External Validity

- The selected workload scenarios may not represent all Digital Twin systems.
- One curated profile per provider does not represent every valid architecture.
- Results are limited to supported regions, services, and price models.
- AWS, Azure, and GCP results do not generalize automatically to other
  providers.

### Conclusion Validity

- A small estimated cost difference may not be meaningful under pricing drift.
- Results must include sensitivity and assumptions.
- Eventing benefits include functionality and operability, not only monetary
  cost.

## Scope Decisions

### In Scope

- AWS, Azure, and GCP.
- The paper-compatible five-layer baseline.
- One bounded Eventing-extended architecture profile.
- Monetary cost as the only enabled optimization objective.
- Functionally gated provider profiles.
- Provider-specific pricing models, formulas, tiers, and evidence.
- Transfer and glue costs.
- Reproducible deployment contracts and later live-cloud validation.

### Out Of Scope

- General dynamic architecture synthesis.
- Arbitrary layer creation through the UI.
- Exhaustive support for every provider service.
- Runtime migration and continuous re-optimization.
- Full FinOps billing reconciliation.
- Automatic equivalence decisions made solely by AI.
- Implemented latency, resilience, sustainability, or multi-objective
  optimization.
- A claim that the Eventing extension replaces or invalidates the original
  Twin2Clouds model.

## Finalization Checklist

Before these questions become final thesis text:

- [ ] Complete the systematic literature search and citation chaining.
- [ ] Freeze the implemented architecture profiles.
- [ ] Finalize mandatory capabilities and provider profile mappings.
- [ ] Finalize formulas, pricing evidence, tiers, transfer ownership, and
      publishability gates.
- [ ] Define the final workload scenarios and sensitivity variables.
- [ ] Align chapter structure and contribution wording with the approved RQs.
- [ ] Review the RQs with the thesis supervisor.
- [ ] Replace the outdated commented RQs in `introduction.tex`.
- [ ] Add stable bibliography keys to the LaTeX bibliography.
- [ ] Execute the deferred manual UI audit.
- [ ] Execute supervised live-cloud end-to-end evaluation only after the
      implementation is frozen.
- [ ] Write explicit answers to every RQ in Discussion and Conclusion.

## Working Decision

The three primary questions and two sub-questions form a coherent thesis arc:

```text
RQ1: Can the theoretical model be operationalized reproducibly?
  |
  v
RQ2: Are the compared provider implementations functionally admissible?
  |
  v
RQ3: What cost effect remains after enforcing that admissibility?
  |
  +--> RQ3.1: single-cloud versus multi-cloud baseline
  |
  +--> RQ3.2: bounded effect of an explicit Eventing and Messaging Layer
```

This structure keeps implementation, scientific validity, and quantitative
evaluation connected without turning the thesis into a general-purpose cloud
architecture optimization project.
