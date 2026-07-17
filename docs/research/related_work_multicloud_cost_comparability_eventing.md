# Related Work: Multi-Cloud Cost, Functional Comparability, And Event-Driven Digital Twins

## Purpose And Status

This note records literature and source material for the later Related Work,
Research Method, Evaluation, and Discussion chapters of the thesis. It focuses
on the intersection of:

- cost-aware Digital Twin engineering;
- functional comparability of provider-specific cloud services;
- multi-cloud application modelling and orchestration;
- cost-aware service composition and selection; and
- event-driven Digital Twin architectures.

It is a research working document, not final thesis prose and not product
documentation. Claims and citations must be reviewed and rewritten before they
are transferred to `twin2multicloud-latex/`.

The sources below were identified through a targeted literature search and
verified against publisher, proceedings, DOI, or local primary-source records.
This is not yet a systematic literature review. It must therefore not be used to
claim that no other relevant work exists.

**Search and metadata verification date:** 2026-07-17

## Research Landscape

The relevant literature separates into four overlapping streams:

```text
                   +-----------------------------+
                   | Cost-aware Digital Twins   |
                   | Twin2Clouds                 |
                   +-------------+---------------+
                                 |
         +-----------------------+-----------------------+
         |                       |                       |
         v                       v                       v
+------------------+   +----------------------+   +----------------------+
| Cloud comparison |   | Multi-cloud          |   | Event-driven        |
| and service      |   | modelling and        |   | Digital Twin       |
| selection        |   | orchestration        |   | architectures      |
+---------+--------+   +----------+-----------+   +----------+-----------+
          |                       |                          |
          +-----------------------+--------------------------+
                                  |
                                  v
              +------------------------------------------+
              | Twin2MultiCloud thesis intersection     |
              | functionally gated, cost-comparable,    |
              | traceable, deployable architecture      |
              | profiles with a bounded Eventing study  |
              +------------------------------------------+
```

No reviewed source in this targeted set covers the complete intersection. That
does not by itself prove novelty. It identifies the area in which the thesis
must state and evaluate its contribution precisely.

## Direct Foundations

### Twin2Clouds: Cost-Aware Digital Twin Engineering and Deployment Across Federated Clouds

**Authors:** Philipp Gritsch, Deniz Pierer, Luca Berardinelli, Michael Felderer,
and Sashko Ristov

**Year:** 2025

**Venue:** 2025 ACM/IEEE 28th International Conference on Model Driven
Engineering Languages and Systems Companion (MODELS-C), EDTconf technical
track

**DOI:** [10.1109/MODELS-C68889.2025.00045](https://doi.org/10.1109/MODELS-C68889.2025.00045)

**Local source:** [EDT_25__CloudDT_engineering.pdf](../../docs-site/docs/references/EDT_25__CloudDT_engineering.pdf)

**Core contribution**

Twin2Clouds organizes Digital Twin functionality into five cloud-oriented
layers, defines cloud-agnostic cost and pricing primitives, estimates the cost
of provider services for a workload, and selects the least expensive provider
for each layer. Its reported evaluation compares three scenarios and
single-provider baselines with federated provider allocations.

**Relevance to this thesis**

This is the theoretical and algorithmic baseline. The present thesis inherits
the layer decomposition, workload model, pricing primitives, and layer-wise
provider allocation problem.

**Difference from this thesis**

The present thesis does not need to claim invention of the five-layer cost
model. Its contribution is the engineering and critical extension of that
model:

- an evidence-backed and traceable pricing pipeline;
- explicit provider capability and deployment contracts;
- integration with a production-shaped Management API and Flutter client;
- reproducible deployment across provider boundaries;
- functional-completeness gates before a candidate may participate in cost
  ranking; and
- a bounded investigation of an Eventing and Messaging Layer.

The thesis must also test an assumption that is not established merely by
layer-wise cost minimization: whether compared provider implementations provide
equivalent required functionality.

### Developing A Cloud-Based Multi-Provider Digital Twin: Addressing Layered Architecture, Deployment And Cross-Cloud Integration Challenges

**Type:** Bachelor thesis and implementation predecessor

**Local source:** [bachelor_digital_twins.pdf](../../docs-site/docs/references/bachelor_digital_twins.pdf)

**Core contribution**

The bachelor project turns an earlier layered architecture into an executable,
primarily AWS-oriented proof of concept. It contains the source deployment
topology, provider functions, configuration artefacts, and deployment tooling
from which the current Deployer evolved.

**Relevance to this thesis**

It is the direct implementation baseline and an important provenance source for
the current function-to-function flows, layer numbering, deployment artefacts,
and operational assumptions.

**Difference from this thesis**

The bachelor implementation does not establish that every inherited topology is
an appropriate multi-provider target architecture. It also does not prove
functional one-to-one equivalence among provider services or complete
cross-provider deployment behavior. The master thesis may retain the
implementation as a reproducible baseline while identifying and replacing
bounded architectural debt, provided that the change is explicitly justified
and evaluated.

## Cloud Comparison And Service Selection

### CloudCmp: Comparing Public Cloud Providers

**Authors:** Ang Li, Xiaowei Yang, Srikanth Kandula, and Ming Zhang

**Year:** 2010

**Venue:** Proceedings of the 10th ACM SIGCOMM Conference on Internet
Measurement

**DOI:** [10.1145/1879141.1879143](https://doi.org/10.1145/1879141.1879143)

**Core contribution**

CloudCmp proposes a systematic comparison of public cloud providers using
application-relevant performance and cost metrics for common compute, storage,
and network services. It emphasizes fairness, representativeness, and
application impact instead of comparing product names or advertised features
alone.

**Relevance to this thesis**

The work supports the requirement that a provider comparison needs a shared
measurement basis and a defined application workload. It also supports
including transfer and runtime behavior where those affect the application.

**Difference from this thesis**

CloudCmp is a benchmark and provider-selection framework for common cloud
infrastructure capabilities. It does not model a Digital Twin as layered
managed-service components, generate a deployable multi-cloud Digital Twin, or
evaluate an Eventing layer. Twin2MultiCloud uses explicit workload and pricing
contracts rather than CloudCmp's benchmark suite.

### Identification Of Comparison Key Elements And Their Relationships For Cloud Service Selection

**Authors:** Anis Ahmed Nacer, Olivier Perrin, and François Charoy

**Year:** 2020

**Venue:** Service-Oriented and Cloud Computing, Lecture Notes in Computer
Science

**DOI:** [10.1007/978-3-030-44769-4_6](https://doi.org/10.1007/978-3-030-44769-4_6)

**Core contribution**

The authors show that providers describe similar cloud offerings through
heterogeneous, incomplete, and differently named non-functional attributes.
They propose a method for identifying comparison criteria and their
relationships from architect requirements, provider plans, benchmarks, and
empirical validation. Their case studies include cloud relational databases and
cloud queuing services.

**Relevance to this thesis**

This source directly supports the planned capability and pricing-model
matrices. A comparison must first define functional requirements and the
attributes that influence them. A cheaper candidate cannot be treated as
equivalent merely because the provider places it in a similar product category.
The queuing-service case study is particularly relevant to the proposed
Eventing and Messaging Layer.

**Difference from this thesis**

The work develops a general method for selecting comparison criteria. It does
not implement a Digital Twin cost model, a cross-provider deployment engine, or
the concrete AWS, Azure, and GCP service profiles evaluated by this thesis.

### SLA-Constrained Service Selection For Minimizing Costs Of Providing Composite Cloud Services Under Stochastic Runtime Performance

**Authors:** Kuo-Chan Huang, Mu-Jung Tsai, Sin-Ji Lu, and Chun-Hao Hung

**Year:** 2016

**Venue:** SpringerPlus 5, Article 294

**DOI:** [10.1186/s40064-016-1938-6](https://doi.org/10.1186/s40064-016-1938-6)

**Core contribution**

The paper treats composite-cloud service selection as a cost-minimization
problem subject to service-level constraints and stochastic response time.
Candidate assignments must remain feasible under the required quality
constraints before total cost is minimized.

**Relevance to this thesis**

It supports the central ordering rule:

```text
required functionality and constraints
                |
                v
       feasible candidate set
                |
                v
          cost comparison
                |
                v
        optimized assignment
```

This is conceptually aligned with the proposed functional-completeness gate.

**Difference from this thesis**

The paper optimizes generic composite services under response-time SLAs and
does not address Digital Twin layers, provider-managed service pricing,
infrastructure generation, or deployment evidence. Twin2MultiCloud currently
optimizes monetary cost under deterministic workload inputs, while the wider
QoS model remains future work.

## Multi-Cloud Modelling And Cost-Aware Orchestration

### Cost-Aware Orchestration Of Applications Over Heterogeneous Clouds

**Authors:** Kena Alexander, Muhammad Hanif, Choonhwa Lee, Eunsam Kim, and Sumi
Helal

**Year:** 2020

**Venue:** PLOS ONE 15(2), e0228086

**DOI:** [10.1371/journal.pone.0228086](https://doi.org/10.1371/journal.pone.0228086)

**Core contribution**

The work combines a cloud application topology model, TOSCA, CAMP, a cost
model, and policy processing to orchestrate components across heterogeneous
cloud providers. It argues that component costs alone are insufficient when the
application topology and orchestration affect operating cost.

**Relevance to this thesis**

This is strong prior work for linking cost analysis to a deployable application
topology. It supports modelling both service nodes and cross-cloud edges, and it
supports the planned separation between a fixed architecture profile and the
provider-specific implementations that realize it.

**Difference from this thesis**

The work targets generic cloud application components and VM/platform
orchestration. It does not define the Twin2Clouds Digital Twin workload and
layer model, provider-specific Digital Twin managed services, or the pricing
evidence and review workflow implemented by Twin2MultiCloud.

### Model-Driven Development And Operation Of Multi-Cloud Applications: The MODAClouds Approach

**Editors:** Elisabetta Di Nitto, Peter Matthews, Dana Petcu, and Arnor Solberg

**Year:** 2017

**Publisher:** Springer International Publishing

**DOI:** [10.1007/978-3-319-46031-4](https://doi.org/10.1007/978-3-319-46031-4)

**Core contribution**

MODAClouds presents model-driven design and operation of applications spanning
multiple cloud providers. It addresses provider independence, deployment,
monitoring, QoS, portability, data migration, and runtime management across
IaaS and PaaS environments.

**Relevance to this thesis**

The work provides established context for separating provider-independent
application intent from provider-specific realization and for keeping the
deployment description explicit and model-driven.

**Difference from this thesis**

MODAClouds is a general multi-cloud development and operations framework.
Twin2MultiCloud has a narrower domain and contribution: cost-aware Digital Twin
architecture profiles, provider pricing evidence, and concrete managed-service
deployment across AWS, Azure, and GCP. The thesis does not attempt to reproduce
the breadth of MODAClouds runtime adaptation.

### Adaptive Management Of Applications Across Multiple Clouds: The SeaClouds Approach

**Authors:** Antonio Brogi et al.

**Year:** 2015 according to the journal issue; final bibliography metadata must
be checked because current DOI metadata reports a later publication date

**Venue:** CLEI Electronic Journal 18(1)

**DOI:** [10.19153/cleiej.18.1.1](https://doi.org/10.19153/cleiej.18.1.1)

**Core contribution**

SeaClouds addresses the distribution, monitoring, migration, and adaptive
management of multi-component applications over heterogeneous cloud platforms.
It uses application topology and orchestration models to preserve functional
and non-functional properties across the complete application.

**Relevance to this thesis**

The project reinforces that multi-cloud selection is an application-level
composition problem rather than a collection of independent provider choices.
It is useful context for topology, provider abstraction, and cross-component
constraints.

**Difference from this thesis**

SeaClouds focuses on adaptive lifecycle management and migration of generic
service-based applications. Twin2MultiCloud uses a bounded Digital Twin
architecture and currently performs design-time cost optimization followed by
deployment. Runtime migration and general adaptive re-orchestration remain out
of scope.

## Event-Driven Digital Twin Architectures

### Real-Time Event-Based Platform For The Development Of Digital Twin Applications

**Author:** Carlos Eduardo Belman López

**Year:** 2021

**Venue:** The International Journal of Advanced Manufacturing Technology,
116, 835-845

**DOI:** [10.1007/s00170-021-07490-9](https://doi.org/10.1007/s00170-021-07490-9)

**Core contribution**

The paper presents an event-based platform for building and operating Digital
Twin applications with real-time data processing. It treats event exchange and
stream processing as a first-class architectural mechanism rather than relying
only on direct synchronous component invocation.

**Relevance to this thesis**

It provides prior evidence that eventing is a legitimate Digital Twin
architectural responsibility. It supports evaluating Eventing and Messaging as
an explicit layer or capability rather than assuming that chained cloud
functions are the only implementation.

**Difference from this thesis**

The work does not compare equivalent AWS, Azure, and GCP event services, derive
their provider-specific cost formulas, or integrate them into a layer-wise
multi-cloud optimizer and deployer.

### Digital Twin Concepts For Linking Live Sensor Data With Real-Time Models

**Authors:** Reiner Jedermann, Kunal Singh, Walter Lang, and Pramod Mahajan

**Year:** 2023

**Venue:** Journal of Sensors and Sensor Systems 12, 111-121

**DOI:** [10.5194/jsss-12-111-2023](https://doi.org/10.5194/jsss-12-111-2023)

**Core contribution**

The authors link live sensor data and updateable models through a streaming
platform and event-driven architecture. The work demonstrates model chaining
and evaluates processing overhead in a concrete logistics Digital Twin.

**Relevance to this thesis**

It supports the claim that asynchronous streaming and event-driven model
updates are established Digital Twin mechanisms. It is also relevant to the
functional contract of an Eventing layer: ingestion, routing, decoupling, model
triggering, and continuous synchronization.

**Difference from this thesis**

The paper evaluates a domain-specific streaming platform, not a cloud-provider
service comparison. It does not optimize provider allocation or compare event
service pricing and deployment profiles.

### A Distributed Event-Orchestrated Digital Twin Architecture For Optimizing Energy-Intensive Industries

**Authors:** Nicolò Bertozzi, Anna Geraci, Letizia Bergamasco, Enrico Ferrera,
Edoardo Pristeri, and Claudio Pastrone

**Year:** 2025

**Venue:** Proceedings of the 10th International Conference on Internet of
Things, Big Data and Security, pages 337-344

**DOI:** [10.5220/0013364400003944](https://doi.org/10.5220/0013364400003944)

**Core contribution**

The paper presents a distributed Digital Twin architecture with stateless
microservices, a Kafka-based event backbone, asynchronous workflow execution,
and API-driven scheduling. Its objective is scalable and fault-tolerant
orchestration of monitoring, forecasting, and simulation workflows.

**Relevance to this thesis**

It provides a recent concrete example in which the event backbone is an
architectural component with routing and orchestration responsibilities. It
strengthens the rationale for comparing event buses, brokers, queues, and
routing services as a distinct responsibility.

**Difference from this thesis**

The paper selects Kafka as part of one platform architecture. It does not
compare cloud-managed eventing alternatives, calculate provider-specific costs,
or evaluate whether an eventing extension changes the least-cost single- or
multi-cloud Digital Twin configuration.

## Cross-Source Comparison

| Source | Digital Twin domain | Functional suitability before ranking | Multi-cloud topology or orchestration | Cost comparison or optimization | Event-driven architecture | Direct deployment output |
|---|---:|---:|---:|---:|---:|---:|
| Twin2Clouds | Yes | Partial/implicit | Layer allocation | Yes | No explicit Eventing layer | Reproducible deployment prescription |
| Bachelor predecessor | Yes | Fixed implementation | Limited proof of concept | No independent research contribution | Direct function chains and provider events | Yes, primarily AWS-oriented |
| CloudCmp | No | Common benchmark scope | Provider selection | Cost and performance comparison | No | No |
| Nacer et al. | No | Yes, comparison criteria and requirements | No | Supports later selection | Queuing-service case study | No |
| Huang et al. | No | Yes, SLA-feasible candidates | Composite services | Yes | Workflow composition | No infrastructure deployment |
| Alexander et al. | No | Policy and topology constraints | Yes | Yes | Not Digital Twin-specific | Orchestration proof of concept |
| MODAClouds | No | Functional and QoS models | Yes | Cost is one concern | Not central | Yes, general applications |
| SeaClouds | No | Functional and non-functional properties | Yes | One adaptation criterion | Not central | Yes, general applications |
| López | Yes | One platform architecture | No provider comparison | No | Yes | Domain platform |
| Jedermann et al. | Yes | Domain-specific model requirements | No provider comparison | No | Yes | Demonstrated platform |
| Bertozzi et al. | Yes | Workflow-oriented | Distributed architecture | No provider comparison | Yes | Demonstrated architecture |
| Twin2MultiCloud thesis target | Yes | Explicit functional-completeness gate | Versioned, deployable provider profiles | Yes | Bounded Eventing profile | Yes |

`Partial/implicit` for Twin2Clouds must be verified against the full paper
wording before final thesis prose is written. The table is a research aid, not a
published result.

## Defensible Thesis Differentiation

The thesis must not claim that it invents:

- multi-cloud computing;
- cloud service selection;
- provider cost comparison;
- model-driven multi-cloud deployment;
- event-driven Digital Twins;
- event brokers, queues, or streaming platforms; or
- the original Twin2Clouds five-layer cost model.

The defensible contribution is the integrated and evaluated realization of the
following bounded chain:

```text
Digital Twin workload intent
        |
        v
versioned architecture profile
        |
        v
functional-completeness gate
        |
        v
provider-specific service and pricing contracts
        |
        v
evidence-backed cost calculation
        |
        v
single- and multi-cloud provider allocation
        |
        v
versioned deployment manifest
        |
        v
reproducible infrastructure deployment
        |
        v
verification and inspectable result evidence
```

The proposed Eventing and Messaging Layer is a bounded extension and evaluation
case within this chain. It is not a claim to provide a general dynamic
architecture-composition engine.

## Research Gap Statement For Later Refinement

A provisional research-gap statement is:

> Existing work separately addresses cost-aware Digital Twin layer selection,
> cloud-provider comparison, constrained cloud-service composition,
> model-driven multi-cloud orchestration, and event-driven Digital Twin
> architectures. The reviewed sources do not provide an integrated method that
> first establishes functional completeness of provider-specific Digital Twin
> architecture profiles, then compares their evidence-backed operating costs,
> and finally produces and verifies a reproducible cross-provider deployment.

This wording must remain provisional until a documented systematic search has
tested it against a broader literature set.

## Relationship To Working Research Questions

The current LaTeX scaffold contains earlier research questions about platform
design, prototype integration, and deployment failures. The revised questions
below are the accepted working direction, but not yet supervisor-approved final
thesis text.

The authoritative working question set, evaluation method, verification gates,
scope boundaries, and chapter mapping are maintained in
[Research Questions And Evaluation Design](research_questions_and_evaluation_design.md).
The summaries below provide only the related-work mapping.

### Working RQ1: Operationalization

> How can a configuration-driven platform operationalize a layered, cost-aware
> Digital Twin model into reproducible deployments across AWS, Azure, and Google
> Cloud?

Relevant sources:

- Twin2Clouds;
- the bachelor implementation predecessor;
- MODAClouds;
- SeaClouds; and
- Alexander et al.

### Working RQ2: Functional Comparability

> How can provider-specific cloud services be mapped to functionally complete
> and cost-comparable Digital Twin architecture profiles without assuming
> one-to-one service equivalence?

Relevant sources:

- CloudCmp;
- Nacer et al.;
- Huang et al.; and
- Twin2Clouds.

### Working RQ3: Cost Effect

> To what extent can layer-wise multi-cloud service selection reduce estimated
> operational cost compared with functionally equivalent single-cloud
> baselines?

Relevant sources:

- Twin2Clouds;
- CloudCmp;
- Huang et al.; and
- Alexander et al.

### Working RQ3.1: Baseline Comparison

> How do single-cloud and multi-cloud configurations compare under identical
> workload and functional requirements?

This is evaluated through the functional capability matrix, single-provider
scenario cost matrix, and federated optimization result.

### Working RQ3.2: Eventing Extension

> How does introducing an explicit Eventing and Messaging Layer affect
> functional coverage, architecture topology, and total estimated cost?

Relevant sources:

- López;
- Jedermann et al.;
- Bertozzi et al.;
- Nacer et al.; and
- the Twin2Clouds baseline.

## Planned Use In The Thesis

| Thesis section | Material from this note |
|---|---|
| Related Work | Four research streams, source summaries, and cross-source differentiation |
| Research Objective | Refined problem statement and accepted working research questions |
| Method | Functional-completeness gate, architecture profiles, and comparison order |
| Architecture | Relationship between workload, profile, pricing contract, optimizer, and Deployer |
| Evaluation | Functional matrix, single-provider baseline, multi-cloud optimum, and Eventing experiment |
| Discussion | Limits of one-to-one service equivalence, topology effects, construct validity, and scope |
| Threats to Validity | Targeted rather than systematic search, pricing drift, curated profiles, and bounded scenarios |

## Literature Review Follow-Up

Before the final Related Work chapter is written:

1. Define search databases, search strings, date range, and inclusion/exclusion
   criteria.
2. Search at least IEEE Xplore, ACM Digital Library, Scopus or Web of Science,
   SpringerLink, and Google Scholar for citation chaining.
3. Perform backward and forward citation chaining from Twin2Clouds, CloudCmp,
   Alexander et al., López, and the most recent event-driven Digital Twin work.
4. Record excluded near-matches and exclusion reasons.
5. Verify the final novelty statement against the resulting corpus.
6. Export approved references into the thesis bibliography with stable citation
   keys.

## Citation-Ready Source List

- Gritsch, P., Pierer, D., Berardinelli, L., Felderer, M., and Ristov, S.
  (2025). *Twin2Clouds: Cost-Aware Digital Twin Engineering and Deployment
  Across Federated Clouds*. MODELS-C 2025, 264-275.
  <https://doi.org/10.1109/MODELS-C68889.2025.00045>
- Li, A., Yang, X., Kandula, S., and Zhang, M. (2010). *CloudCmp: Comparing
  Public Cloud Providers*. IMC 2010, 1-14.
  <https://doi.org/10.1145/1879141.1879143>
- Nacer, A. A., Perrin, O., and Charoy, F. (2020). *Identification of Comparison
  Key Elements and Their Relationships for Cloud Service Selection*. Service-
  Oriented and Cloud Computing, LNCS.
  <https://doi.org/10.1007/978-3-030-44769-4_6>
- Huang, K.-C., Tsai, M.-J., Lu, S.-J., and Hung, C.-H. (2016).
  *SLA-Constrained Service Selection for Minimizing Costs of Providing
  Composite Cloud Services under Stochastic Runtime Performance*.
  SpringerPlus, 5, 294. <https://doi.org/10.1186/s40064-016-1938-6>
- Alexander, K., Hanif, M., Lee, C., Kim, E., and Helal, S. (2020).
  *Cost-Aware Orchestration of Applications over Heterogeneous Clouds*. PLOS
  ONE, 15(2), e0228086. <https://doi.org/10.1371/journal.pone.0228086>
- Di Nitto, E., Matthews, P., Petcu, D., and Solberg, A. (Eds.). (2017).
  *Model-Driven Development and Operation of Multi-Cloud Applications: The
  MODAClouds Approach*. Springer.
  <https://doi.org/10.1007/978-3-319-46031-4>
- Brogi, A., et al. (2015). *Adaptive Management of Applications Across
  Multiple Clouds: The SeaClouds Approach*. CLEI Electronic Journal, 18(1).
  <https://doi.org/10.19153/cleiej.18.1.1>
- López, C. E. B. (2021). *Real-Time Event-Based Platform for the Development
  of Digital Twin Applications*. The International Journal of Advanced
  Manufacturing Technology, 116, 835-845.
  <https://doi.org/10.1007/s00170-021-07490-9>
- Jedermann, R., Singh, K., Lang, W., and Mahajan, P. (2023). *Digital Twin
  Concepts for Linking Live Sensor Data with Real-Time Models*. Journal of
  Sensors and Sensor Systems, 12, 111-121.
  <https://doi.org/10.5194/jsss-12-111-2023>
- Bertozzi, N., Geraci, A., Bergamasco, L., Ferrera, E., Pristeri, E., and
  Pastrone, C. (2025). *A Distributed Event-Orchestrated Digital Twin
  Architecture for Optimizing Energy-Intensive Industries*. IoTBDS 2025,
  337-344. <https://doi.org/10.5220/0013364400003944>
