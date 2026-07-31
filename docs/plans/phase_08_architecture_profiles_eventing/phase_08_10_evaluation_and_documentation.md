---
title: "Phase 8.10: Deferred Comparative Evaluation And Final Documentation"
description: "Suspended comparative plan to be revised after Five-layer v2 and the later Six-layer profile are implemented."
tags: [architecture, evaluation, reproducibility, documentation, thesis, issue-148]
lastUpdated: "2026-07-30"
version: "1.8"
---

<!-- SOURCES:
- GitHub issue #148
- docs/research/research_questions_and_evaluation_design.md
- docs/research/digital_twin_architecture_and_eventing_layer.md
- docs/research/related_work_multicloud_cost_comparability_eventing.md
- Completed Phase 8.0-8.9 contracts, evidence, and verification outputs
- docs-site current user, operator, developer, setup, architecture, and contract documentation
- User-approved separation between product documentation, research evidence, and LaTeX
- User decision to freeze Five-layer v2 evidence before separately planning
  the Six-layer comparison
EXTRACTED: 2026-07-30 | VERSION: 1.8
-->

# Phase 8.10: Deferred Comparative Evaluation And Final Documentation

## Suspension Notice

**Do not execute this comparative plan yet.**

Its pre-2026-07-29 references to co-located L3-hot/L4/L5 bundles, dual
visualization reads, ADX, scenes, and already-approved Six-layer behavior are
superseded planning provenance. Five-layer v2 first produces immutable
standalone evidence under
[`phase_08_service_bundle_closure.md`](phase_08_service_bundle_closure.md):
three single-cloud placements, six `L3-hot == L5 != L4` placements, other
admissible mixed paths, raw visualization, Twin projection, Cosmos capacity,
provider-hosted GCP, costs, and explicit rejections.

After Six-layer is separately planned and implemented from that committed
L1-L5 baseline, this file must be rewritten for the fair comparison. Until
then #148 remains blocked and the instructions below are non-authoritative.

## 0. Metadata

| Field | Value |
|---|---|
| Issue | [#148 Produce Phase 8 evaluation evidence and final documentation](https://github.com/TVJunkie724/master-thesis/issues/148) |
| Milestone | Phase 8 - Twin Architecture Profiles & Eventing |
| Recommended branch | `codex/phase-8-evaluation-package` |
| Branch base | Reviewed Phase 8.9B commit; the branch ultimately targets `master` |
| Blocked by | Phase 8.9A implementation issue and Phase 8.9B / #140 |
| Produces | Reproducible Phase 8 evaluation package and complete current docs |
| Live cloud E2E | Prepared but not executed |
| LaTeX | Must not be edited without separate approval |

Every evidence artifact, research-question mapping, source/digest reference,
regeneration gate, limitation, documentation update, and Definition of Done
item in this plan is mandatory.

## Corrective Complete-Service Addendum

The evaluation composes the immutable Eventing decision with
`phase-08-complete-service-bundles@1`. It must include the complete AWS,
Azure, and provider-hosted GCP L1-L5 bundles, all six directed Eventing bridge
routes, all six directed routes at each of the two storage transitions, and
the three single-cloud plus six `L3-hot == L5 != L4` placements with the
provider-local raw-history read and typed Twin-projection edge. It must
not reuse Event-domain capacity evidence as proof of
complete-Twin capacity. Historical `@1` keeps its all-GCP negative result; both
new profiles require an all-GCP positive result after implementation.

## 1. Outcome

Produce one immutable, reproducible evaluation package that allows another
researcher or developer to answer:

- whether the platform operationalizes the cost-aware architecture model
  reproducibly;
- whether provider implementations are functionally comparable without
  assuming one-to-one service equivalence;
- how admissible single-cloud and multi-cloud cost estimates compare;
- how the explicit Eventing responsibility changes functionality, topology,
  and estimated cost.

The phase also updates all current user/developer/operator documentation to the
implemented state. Research interpretation stays in `docs/research/`; current
system instructions stay in `docs-site/`.

### Scope Boundary

| Included | Excluded |
|---|---|
| Immutable evaluation package, frozen scenarios, functional-total and cost matrices, digest chain, RQ mapping, threats to validity, complete current-system docs, research evidence, and an unexecuted supervised E2E protocol | New runtime behavior, provider/profile redesign, live E2E execution, paid operations, rewriting historical evidence, unsupported-cost fabrication, and LaTeX edits |

## 2. Research Question Mapping

Use the accepted working questions from
`docs/research/research_questions_and_evaluation_design.md`.

| Question | Required Phase 8 evidence |
|---|---|
| RQ1 | Contract/data-flow trace, profile-to-deployment digest chain, migration and offline release evidence, prepared supervised E2E protocol |
| RQ2 | Functional-total matrix, provider bundle matrix, rejected candidates, capability gate results, architecture diagrams |
| RQ3 | Frozen single-provider and multi-cloud totals within each profile |
| RQ3.1 | Same-workload single-cloud versus federated comparison and deltas |
| RQ3.2 | Separate `five-layer-baseline@2`/Event-Layer functional, topology, component, transfer, and cost comparison, with `@1` retained as historical reproduction |

Refactoring activity is engineering method and supporting contribution. It is
not promoted to a new research question in this phase.

## 3. Evaluation Package Layout

Create:

```text
docs/research/evidence/phase_08_evaluation/
  evaluation-manifest.json
  research-question-map.json
  scenario-index.json
  architecture/
    predecessor-implemented-graph.json
    five-layer-baseline.1.json
    five-layer-baseline.2.json
    six-layer-eventing.1.json
    architecture-deltas.json
  functional/
    historical-baseline-functional-total-matrix.json
    event-enabled-five-layer-functional-total-matrix.json
    eventing-functional-total-matrix.json
    provider-bundle-differences.json
    rejected-candidates.json
  costs/
    five-layer-v1-reproduction-results.json
    five-layer-v2-single-provider-results.json
    five-layer-v2-multicloud-results.json
    eventing-single-provider-results.json
    eventing-multicloud-results.json
    profile-delta-results.json
  deployment/
    reproducibility-chain.json
    offline-release-gate.json
    final-e2e-protocol.json
  limitations/
    residual-risks.json
    threats-to-validity.json
  schemas/
  README.md
```

Add:

```text
scripts/phase_08_evaluation/
  build_evaluation_package.py
  validate_evaluation_package.py
  verify_reproducibility.py
  render_tables.py
```

Generated Markdown tables may be created under
`docs/research/generated/phase_08/`, but JSON plus source contracts remain the
machine-readable evaluation SSOT. Generated files must contain a header with
the generator version and input digest and must not be manually edited.

## 4. Evaluation Manifest

`evaluation-manifest.v1` must pin:

- evaluation ID/version/status;
- generated-at timestamp and generator version;
- Git commit SHA;
- ArchitectureProfile, ProviderImplementationProfile, component catalog,
  formula, pricing registry, workload, permission, RTA, RDS, Manifest, graph,
  and Eventing decision versions/digests;
- the Phase 8.8 profile-parity and shared domain-event flow decision digests;
- the approved Eventing implementation-component-manifest version and digest;
- the complete-service decision, provider-bundle, workload-v2, capacity,
  storage-route, and implementation-component-manifest versions/digests;
- the `deployment-access.v1` contract, deterministic L4 seed revision,
  Grafana dashboard revision, interactive-role binding evidence, and safe
  per-surface readiness codes for every evaluated placement;
- scenario and source-ledger digests;
- currency and price observation/effective dates;
- region policy;
- test/release evidence refs;
- every result artifact digest;
- known unsupported paths;
- final package digest.

The package is `publishable` only when all required refs resolve and all
verification gates pass. A timestamp is audit metadata; it must not make
otherwise identical result content nondeterministic.

## 5. Frozen Scenario Set

The scenario index must include:

1. the bounded baseline workloads already approved for five-layer
   cost/deployment verification;
2. the Phase 8.8 channel-aware small/medium/large sensitivity workloads,
   applied identically to `five-layer-baseline@2` and
   `six-layer-eventing@1`;
3. `core-small-v2`, `core-medium-v2`, and `core-large-v2`, including separate
   Twin entity, selected state materialization, graph/model update, and
   aggregate dashboard
   dimensions, fixed cumulative storage boundaries `H=1`, `C=3`, `A=12`
   months, five-minute batches, 24-hour transition retry, and 48-hour source
   grace;
4. the explicit Small/Medium/Large pairing rule between Core Twin and
   Eventing scenario families;
5. one explicitly selected representative thesis comparison workload;
6. the fixed regions AWS `eu-central-1`, Azure `westeurope`, and GCP
   `europe-west1`, plus currency assumptions;
7. availability and evidence status for every candidate.

For each scenario, freeze:

- raw user workload intent;
- derived workload quantities;
- architecture profile ID/version/digest;
- optimization/calculation/formula/scoring strategy bundle;
- provider region policy;
- pricing catalog/evidence snapshots;
- transfer routes;
- extension artifacts by digest, when required;
- selected and rejected resolutions;
- deployment specification and graph digest.

The representative workload must be selected in the research note before
result interpretation. It cannot be chosen after observing which provider wins
without recording that as an exploratory/post-hoc selection.

## 6. Architecture Evidence

Produce four separate data-backed diagrams:

1. predecessor implemented graph reconstructed in Phase 8.0;
2. hardened historical `five-layer-baseline@1`;
3. event-enabled `five-layer-baseline@2`; and
4. `six-layer-eventing@1`.

Each diagram must show:

- logical responsibilities;
- logical/deployment components;
- synchronous, event, workflow, and cross-cloud edges;
- provider assignment only for a named resolved scenario;
- trust and transfer boundaries;
- extension slots;
- no credentials, endpoint values, or Terraform names.

ASCII versions belong in research Markdown for diffability. Mermaid versions
may be used in MkDocs research pages only when generated from the same
machine-readable graph and visually verified. Do not remove existing useful
ASCII diagrams.

`architecture-deltas.json` classifies each predecessor component/edge as:

- retained;
- internalized;
- replaced;
- removed;
- added by Eventing.

Every classification must reference the Phase 8.1 baseline decision and, for
Eventing additions, the Phase 8.8 decision.

## 7. Functional-Total Matrices

### 7.1 Five-Layer Matrices

Cover every five-layer responsibility across AWS, Azure, and GCP. Keep two
separate views:

- `five-layer-baseline@1` as the immutable historical/paper-compatible
  functional total; and
- `five-layer-baseline@2` with mandatory embedded rule evaluation, extension
  action, notification workflow, and device-command feedback.

For each view include:

- mandatory capabilities;
- selected provider service bundle;
- local-edge resources and topology-conditional cross-cloud outboxes;
- complete bidirectional device-boundary and integration-adapter status;
- extra functionality;
- missing/unsupported functionality;
- supporting resources;
- executable support;
- evidence refs.

This is a total matrix for the complete evaluated architecture, not seven
isolated product-name rows.

### 7.2 Eventing Matrix

Reuse the reviewed Phase 8.8 matrix and add:

- implemented component/package/Terraform/permission status;
- verified envelope and edge behavior;
- bridge behavior;
- known implementation limitations;
- exact mapping to the resolved architecture.

### 7.3 Comparability Rule

Cost tables may include a candidate only when its functional-total matrix
status is `complete`. `unsupported`, `unverified`, and `incomplete` remain
visible with reasons and no fabricated total.

The matrices must explicitly demonstrate that:

- equal product counts are not required;
- one provider service may implement multiple capabilities;
- one responsibility may require a service bundle;
- extra provider functionality does not make missing mandatory behavior valid;
- a cheaper incomplete candidate cannot win.

## 8. Cost Evaluation

### 8.1 Per-Profile Isolation And Fair Comparison

Reproduce `five-layer-baseline@1` independently as historical evidence. Do not
use it as the primary Event-Layer counterfactual because it intentionally omits
the domain-event paths.

Evaluate `five-layer-baseline@2` and `six-layer-eventing@1` independently.
Within each profile, use:

```text
same profile + same workload + same functional contract
  -> admissible single-provider baselines
  -> admissible federated paths
  -> selected minimum and deltas
```

Never rank candidates from different profiles in one optimizer run. Compare
the reported profile totals only through this separate cross-profile control:

```text
same eventingScenarioId + same canonical workload digest
  + same rule/action/workflow/command outcomes
  -> five-layer-baseline@2 reported result
  -> six-layer-eventing@1 reported result
  -> functional-quality + topology + estimated-cost delta
```

Attribute the remaining functional delta specifically to the Eventing
responsibility's transport, failure, replay, ordering, observability, and
decoupling semantics.

The Phase 8.8 scenario totals are event-domain evidence only. Phase 8.10 may
label a result as a single-cloud or federated whole-Twin total only after
combining it with the remaining L1-L5 responsibilities and proving the complete
resolved path admissible. In both profiles, same-provider responsibility edges
create no bridge. Remote five-layer v2 edges include their embedded outbox,
bridge compute, transfer, and destination landing costs even though those
resources are owned by L1/L2 rather than by an Eventing responsibility.

### 8.2 Required Results

For every scenario/profile:

- each admissible all-AWS, all-Azure, and all-GCP total for the new profiles;
- the historical all-GCP unsupported state for `@1`;
- federated selected total;
- provider allocation per responsibility/component;
- service, edge, transfer, source-owned transition-adapter/cross-cloud-bridge,
  L3-hot/L5 supporting bundle, raw-history read, Twin-projection edge, fixed,
  variable, and minimum-capacity
  contributions;
- non-overlapping workload-v2 storage residence (`H`, `C-H`, `A-C`), source
  grace, provider minimum-duration charges, lifecycle requests, and one
  transfer per storage stage; historical `@1` formulas remain reproduced
  unchanged;
- free quota and tier/rounding effect;
- extra capability notes;
- selected and rejected evidence/formula refs;
- absolute and percentage delta against each admissible single-provider
  baseline.

When a full single-provider path is unsupported, report that state; do not fill
it with an equivalent-looking partial total.

### 8.3 Eventing Deep Dive

For RQ3.2, show:

- `five-layer-baseline@2` embedded/direct-edge cost and behavior;
- Eventing component/adapter/bridge cost;
- changed transfer routes;
- changed function/workflow invocations;
- retry/DLQ/replay/retention quantities;
- fixed-capacity effects;
- functional gains and provider-specific extras;
- total profile delta.

Report the `five-layer-baseline@1` reproduction separately so the thesis can
show historical continuity without presenting "events disabled" as a fair
control.

The result must not claim that the Eventing profile is "better" solely because
it is cheaper or more expensive. It reports the functionality/cost tradeoff.

### 8.4 Precision And Presentation

- calculations use canonical decimal values;
- currency conversion is excluded unless a versioned conversion source is
  explicitly added;
- monthly estimates state the billing-period convention;
- display rounding never changes comparison inputs;
- raw provider units and normalized units remain traceable;
- estimated cost is never described as an invoice or observed bill.

## 9. Reproducibility Chain

For every selected evaluation result, prove:

```text
scenario input digest
  -> workload digest
  -> profile/provider/catalog digests
  -> Eventing implementation-component-manifest digest, when applicable
  -> pricing/formula evidence digests
  -> calculation run ID
  -> ResolvedTwinArchitecture digest
  -> ResolvedDeploymentSpecification digest
  -> DeploymentManifest digest
  -> ResolvedDeploymentGraph digest
  -> package/Terraform offline evidence digest
  -> rendered evaluation row digest
```

`verify_reproducibility.py` must regenerate the calculation and documentation
tables from frozen input without network access and compare all content
digests. It must fail on:

- missing or unexpected artifact;
- stale generated table;
- profile/evidence/formula drift;
- result mutation;
- unsupported candidate shown with a numeric total;
- secret-like field or physical cloud identifier in public evidence.

## 10. RQ1 Engineering Evidence

Capture named, machine-readable gate results for:

- cross-project contract synchronization;
- capability agreement;
- pricing/formula source completeness;
- migration from populated legacy data;
- complete-path optimization;
- Manifest/graph/package preflight;
- Terraform validate/native/mock-plan;
- API ownership and redaction;
- all nine Five-layer v2 L3/L4/L5 access fixtures with exact L4/L5 service,
  auth mode, HTTPS URL classification, and secret-free readiness;
- Flutter Web/macOS/Windows/Linux;
- demo/live interface parity;
- strict docs.

Do not copy entire logs into the package. Store:

- command ID and exact command;
- commit SHA;
- start/end UTC;
- exit status;
- summary counts;
- output artifact/log reference;
- digest;
- environment/tool versions;
- explicit `live_cloud_resources_created: false`.

## 11. Final Supervised E2E Protocol

Prepare `final-e2e-protocol.json` and a matching human checklist. Do not execute
it in this phase.

The protocol must define:

- prerequisites and approved credential purpose/scope;
- exact profiles/scenarios/providers to deploy;
- cost and resource limit;
- explicit confirmation points;
- preflight and expected resource inventory;
- deployment, runtime verification, log/evidence collection;
- for every approved Five-layer v2 placement, opening both the provider-owned
  L4 semantic Twin surface and L5 raw/rollup Grafana surface, verifying the
  deterministic content, and recording only redacted result codes/screenshots;
- Eventing publish/delivery/retry/DLQ/replay checks where applicable;
- destroy and independent cleanup verification;
- abort/rollback criteria;
- credential revocation/retention steps;
- evidence redaction and storage.

Execution remains blocked by the user-led manual visual audit and separate
explicit approval.

The full Five-layer v2 live protocol contains all three single-cloud and all
six `L3-hot == L5 != L4` placements. An approved execution may run a smaller
subset for cost/time reasons, but the evidence must name the omitted rows and
must not generalize live accessibility to them. Offline contract evidence
still covers all nine.

### 11.1 Security And Privacy Boundary

- Evaluation inputs, manifests, diagrams, generated tables, logs, and public
  documentation must contain only synthetic or explicitly approved bounded
  identifiers.
- Secret-like fields, credentials, secret references, physical resource names,
  account/subscription/project identifiers, provider endpoints, user source,
  event payloads, tfvars, and raw provider errors are forbidden.
- Evidence collection stores stable error/result codes, correlation IDs,
  content digests, counts, durations, and repository-relative references only.
- Publication uses a separate secret and physical-identifier scanner in
  addition to schema validation; findings block `publishable` status.
- The unexecuted E2E protocol must define redaction and retention before any
  future live evidence is collected.

## 12. Threats To Validity And Residual Risk

At minimum classify:

- construct validity of layer/profile and functional equivalence;
- pricing evidence freshness, regional variation, free tier, account plans,
  and non-fetchable official prices;
- workload representativeness;
- estimated versus observed cost;
- unexecuted live-provider paths;
- provider service evolution;
- unsupported provider/profile paths;
- cross-cloud latency, delivery, identity, and consistency assumptions;
- Terraform mock-plan versus real apply;
- effects of curated closed-world bundle selection;
- Eventing scenario/post-hoc selection risk;
- generalizability beyond the two approved profiles.

Each risk has severity, affected RQ/artifact, mitigation, residual status, and
whether final E2E can reduce it.

## 13. Current Product Documentation

Update `docs-site/` to describe the implemented system only:

- setup and `thesis.sh` commands;
- supported Web/macOS/Windows/Linux modes;
- profile selection, workload, User Logic, optimization, deployment review;
- five-layer and Eventing architecture behavior;
- credential and pricing-account setup;
- contract/data-flow diagrams;
- Management, Optimizer, Deployer, Flutter, docs-site structure;
- profile/component/formula/provider extension procedure;
- operation logs/errors/troubleshooting;
- demo scenarios;
- current support and known limitations.

Do not include:

- thesis conclusions or research-question answers;
- unimplemented alternative architectures;
- claims that unsupported providers are complete;
- raw evidence tables intended only for evaluation;
- hidden credentials or environment-specific paths.

All external links open in a new tab through the existing MkDocs external-link
behavior. Diagrams remain in their relevant context rather than on a detached
gallery page.

## 14. Research Documentation

Update:

- `docs/research/digital_twin_architecture_and_eventing_layer.md`;
- `docs/research/research_questions_and_evaluation_design.md`;
- `docs/research/related_work_multicloud_cost_comparability_eventing.md`;
- `docs/research/resolved_deployment_reproducibility.md`;
- one Phase 8 evaluation narrative generated from the package.

Research docs record:

- predecessor-to-target reasoning;
- functional-completeness-first method;
- closed-world scope;
- matrices and cost comparison method;
- results and limitations;
- differentiation from cited work;
- trace from evidence to RQs.

Do not modify `twin2multicloud-latex`. The package must be ready for a later,
separately approved thesis-writing slice.

## 15. Implementation Slices

### Slice A: Evaluation Schemas And Generator

Must implement package schemas, manifest, scenario index, deterministic
generator, validation, and negative fixtures.

### Slice B: Architecture And Functional Evidence

Must generate all four architecture views, deltas, baseline total matrix,
Eventing matrix, rejected candidates, and comparability checks.

### Slice C: Cost Results

Must regenerate all per-profile single-provider/federated results, deltas, and
Eventing deep-dive traces from frozen evidence.

### Slice D: Reproducibility And RQ Mapping

Must generate the full digest chain, gate evidence, research-question map,
threats, residual risks, and deterministic rerun proof.

### Slice E: Current Documentation

Must update complete user/developer/operator/contracts/demo docs to actual
behavior and verify navigation, links, diagrams, and external-tab behavior.

### Slice F: Research And Finalization Preparation

Must update research notes, prepare but not run final E2E, independently review
claims/evidence, and update roadmap/issues.

## 16. Test Plan

### Package And Schema

- every required field absent/additional;
- invalid/duplicate/unresolved artifact refs;
- unknown version;
- digest mutation;
- non-canonical decimal/timestamp;
- unsupported candidate with total;
- result missing evidence/formula/profile refs;
- secret/physical identifier detection.

### Evaluation Logic

- every admissible historical-baseline, five-layer-v2, and Event-Layer
  scenario;
- all supported and unsupported provider paths;
- single-provider versus federated deltas;
- exact zero, positive, and negative delta;
- provider tier/rounding boundary;
- profile isolation;
- historical `five-layer-baseline@1` is not used as the fair Event-Layer
  counterfactual;
- `five-layer-baseline@2` and `six-layer-eventing@1` use identical
  rule/action/workflow/command workload assumptions;
- Eventing incremental and total contributions;
- no double-counted transfer, adapter, or fixed cost.

### Reproducibility

- clean offline regeneration is byte-identical;
- randomized input ordering does not change content;
- one source/formula/profile mutation changes every dependent digest;
- stale generated table fails;
- missing historical artifact fails;
- network access is unnecessary during regeneration.

### Documentation

- strict MkDocs build;
- internal link and asset validation;
- external links use new-tab behavior;
- referenced PDFs/images/diagrams exist in context;
- current docs contain no draft research conclusion;
- research docs do not become user setup instructions;
- all project pages match actual commands/contracts.

### Regression

- complete safe Optimizer, Management, Deployer, Flutter, contract, deployment,
  demo, and docs gates from previous phases;
- no live provider call, apply, deploy, destroy, or paid operation.

Safe verification:

```bash
python scripts/phase_08_evaluation/build_evaluation_package.py --offline
python scripts/phase_08_evaluation/validate_evaluation_package.py --strict
python scripts/phase_08_evaluation/verify_reproducibility.py --clean
python scripts/phase_08_evaluation/render_tables.py --check
./thesis.sh test deployment-contract
./thesis.sh test backend
./thesis.sh test frontend
./thesis.sh test frontend-integration
docker compose --profile docs run --rm docs \
  mkdocs build --strict --config-file /docs/mkdocs.yml
```

The implementation must use the actual existing `thesis.sh` test command set.
If a command changes before implementation, update the handbook/script and
record each named safe project suite explicitly.

## 17. Review Gates

Review 1, architecture/evidence:

- profile and provider comparability;
- complete cost ownership;
- source/formula/unit correctness;
- digest/reproducibility;
- unsupported candidate honesty.

Review 2, thesis validity:

- each claim supported by artifact;
- RQ mapping complete;
- no overclaim;
- threats and residual risks explicit;
- predecessor contribution represented fairly.

Review 3, product documentation:

- setup/use/configuration/troubleshooting complete;
- content matches implementation;
- research and product docs separated;
- navigation and diagrams usable.

Every finding must be fixed and all affected artifacts regenerated before
commit.

## 18. Rollout And Maintenance

- Publish current docs only after strict validation.
- Mark evaluation package `publishable` only after all gates.
- Preserve prior package versions; corrections create a new version/digest.
- Provider price refresh creates new source/evaluation evidence and never
  rewrites the historical package.
- A later supervised E2E result appends a new evidence version and may reduce
  residual risk; it does not mutate this offline record.

## 19. Definition Of Done

- [ ] RQ1, RQ2, RQ3, RQ3.1, and RQ3.2 map to explicit verified artifacts.
- [ ] Evaluation manifest pins every scenario, profile, provider, catalog,
      workload, pricing, formula, permission, resolution, specification,
      implementation-component manifest, deployment manifest, graph, package,
      and result digest.
- [ ] Predecessor, historical baseline, event-enabled five-layer, and
      six-layer Eventing architecture diagrams and deltas are data-backed and
      complete.
- [ ] Historical baseline, event-enabled five-layer, and Eventing
      functional-total matrices precede cost interpretation.
- [ ] Incomplete, unsupported, and unverified candidates remain visible and
      never receive fabricated totals.
- [ ] Single-provider and federated results are profile-isolated,
      field-traceable, and reproducible.
- [ ] The fair cross-profile comparison is
      `five-layer-baseline@2` versus `six-layer-eventing@1`; `@1` is reported
      only as immutable historical reproduction.
- [ ] Eventing functionality/topology/cost effects are reported separately and
      as a total profile delta.
- [ ] The full offline digest chain regenerates byte-identically.
- [ ] Estimated cost is not represented as an invoice or universal optimum.
- [ ] Threats to validity and residual risk are explicit and linked to RQs.
- [ ] Final supervised E2E is fully specified but not executed.
- [ ] Current user/developer/operator/demo/contract docs are complete and
      describe only implemented behavior.
- [ ] Research reasoning/results remain under `docs/research/`; LaTeX remains
      untouched.
- [ ] Schema, evaluation, scenario, reproducibility, regression, MkDocs, link,
      asset, and separation gates pass.
- [ ] No live credential, provider resource, paid API, deploy, destroy, or E2E
      operation occurs.
- [ ] Roadmap, #148, and parent #112 contain named evidence and residual risks.
- [ ] Three reviews find no unresolved issue.
- [ ] The structured commit references #148 and #112.
