---
title: "Twin2MultiCloud Thesis PoC Execution Plan"
description: "Dependency-ordered implementation and evaluation plan for the final research proof of concept."
tags: [implementation-plan, thesis-scope, six-layer, evaluation]
lastUpdated: "2026-08-28"
version: "1.3"
---

# Twin2MultiCloud thesis PoC execution plan

Status: active execution source; offline closure complete, supervised live
evaluation pending

## 1. Purpose

This plan turns the target concept into a dependency-ordered implementation
and evaluation sequence. It is not a product roadmap and contains no promised
post-thesis capabilities.

The canonical scope is defined by:

1. `docs/plans/2026-08-26_thesis_poc_target_concept.md`;
2. `docs/research/research_questions_and_evaluation_design.md`;
3. `docs/plans/2026-08-26_poc_credentials.md`; and
4. the approved Six-layer evidence under
   `docs/research/evidence/phase_08_eventing/`.

The canonical supervised evaluation inputs are the
[`small-scenario-matrix.json`](../research/evaluation/small-scenario-matrix.json)
and the
[`live-evaluation-protocol.md`](../research/evaluation/live-evaluation-protocol.md).

## Current phase status

| Phase | Status on 2026-08-28 | Evidence boundary |
|---|---|---|
| 0–2 | Implemented offline | standalone contracts, cost-only path, graph-derived deployment evidence |
| 3 | Implemented offline | connection selection, graph-bound preflight, confirmed preparation, manual acknowledgement, and retry-safe repair |
| 4–5 | Implemented offline | bounded Twin interchange, durable operations, access and verification contracts |
| 6 | Implemented offline | product surfaces removed; bounded readiness and repair presentation connected to the existing overview |
| 7 | Implemented and container-verified | the 14-stage credential-free deployment-contract gate, repository hygiene, strict documentation build, and LaTeX build pass from a clean commit |
| 8 | Pending supervision | real principals, provider readiness, identity and image probes |
| 9 | Pending supervision | nine cost-controlled Small deployments |
| 10 | Offline preparation complete; results pending live evidence | chapter structure, RQ framing, limitations, and repository cleanup aligned; empirical answers remain pending |

No row in this table upgrades offline fixtures or mocks to live-cloud evidence.

## 2. Dependency order

```text
target and RQ freeze
        |
        v
standalone architecture cleanup
        |
        v
resolved deployment graph SSOT
        |
        +----------------------+
        v                      v
credentials/readiness       immutable Twin workflow
and bounded repair            and interchange
        |                      |
        +-----------+----------+
                    v
       durable deployment operations
          and runtime access handoff
                    |
                    v
           UI consolidation
                    |
                    v
       offline gates and documentation
                    |
                    v
        low-cost live prerequisites
                    |
                    v
      nine supervised Small scenarios
                    |
                    v
          RQ analysis and thesis evidence
```

The credential concept is fixed before implementation, but credential
readiness and repair are deliberately scheduled after the graph source of
truth. UI reduction follows capability cleanup so the frontend does not get
redesigned around behavior that will be removed.

## 3. Global implementation rules

- One deployable contract: `six-layer-eventing@1`.
- One normal optimization objective: estimated monetary cost.
- One immutable trace from Twin intent through calculation, graph, operation,
  verification, and Destroy evidence.
- One active operation per Twin and no duplicated provider mutation after UI
  reconnect.
- Every provider mutation requires a current plan and an explicit
  confirmation.
- No live provider command is run as part of ordinary implementation or CI.
- Capability removal precedes cleanup of now-orphaned models and projections.
- Active documents describe the target; Git history preserves superseded
  implementation details.

## 4. Phase 0 — scope and evidence freeze

### Work

- Make the target concept, research-question design, credential concept, and
  this execution plan the explicit active planning set.
- Create a traceability table mapping every retained capability to at least one
  research question, safety requirement, or reproducibility need.
- Inventory contradictory active docs, product language, obsolete handoffs,
  generated evidence, and historical sources before deleting anything.
- Freeze the live-evaluation inputs, pricing snapshot date, regional set, and
  Small scenario budget envelope before provider work.

### Exit criteria

- every retained capability has a named justification;
- every planned deletion has an active replacement or is recoverable from Git;
- no generated/digest-bound research evidence has been edited casually; and
- implementation issues can point to one phase and one exit criterion.

### Initial cleanup inventory

| Area | Current conflict to resolve | Owning phase |
|---|---|---|
| Optimizer | public objective/profile registries and inactive scoring declarations may outlive the cost-only path | Phase 1 |
| Shared contracts and services | residual architecture selection or compatibility aliases may expose historical paths | Phase 1 |
| Deployer readiness | provider discovery and fixed permission packs are not derived from the complete Six-layer graph | Phase 2 |
| Cloud setup and credentials | stale bootstrap instructions and manual prerequisite lists do not match final repair behavior | Phase 3, then Phase 7 docs cleanup |
| Twin/project handling | arbitrary project/archive/artifact behavior exceeds typed interchange | Phase 4 |
| Operations and dashboards | product-style monitoring surfaces exceed access handoff plus verification | Phase 5 and Phase 6 |
| Documentation | historical handoffs, product roadmaps, duplicated TODOs, and removed behavior remain distributed | Phase 7 and final Phase 10 cleanup |

## 5. Phase 1 — architecture and optimizer scope cleanup

### Retain

- standalone `six-layer-eventing@1` ownership across all services;
- Five-layer v1 as an immutable Optimizer-only historical reproduction;
- one small internal cost-scoring strategy and full cost trace;
- provider capability and exclusion reasoning required by RQ2; and
- frozen pricing snapshots with provenance and digests.

### Remove or finish removing

- any deployable or selectable intermediate Five-layer profile;
- inheritance or registration of architecture profiles;
- public objective/strategy/profile selection;
- dormant latency, sustainability, resilience, and weighted-scoring branches;
- generic price administration, review, refresh, and approval platform
  behavior beyond the frozen thesis snapshots; and
- active documentation that presents removed capabilities as planned work.

Future optimization objectives remain only in one theoretical extension
concept and short code comments at the retained strategy boundary.

### Exit criteria

- contracts, Management, Deployer, Terraform, Flutter, and active docs expose
  only the standalone Six-layer workflow;
- the normal optimizer path has exactly one scoring strategy;
- the historical baseline cannot be selected for deployment; and
- all affected offline contract and cost tests pass.

## 6. Phase 2 — resolved deployment graph source of truth

### Work

- Resolve the exact provider for all six responsibilities, including Eventing.
- Derive resource packages, directed edges, APIs, Azure resource providers,
  permissions, regions, quotas, runtime identities, access prerequisites, and
  verification probes from that graph.
- Replace fixed legacy provider permission packs with graph requirement types.
- Generate Deployer package selection and Terraform variables only from the
  immutable graph and calculation evidence.
- Remove GCP auto-project creation from the supervised path; use an existing
  billing-enabled project consistently with AWS and Azure account inputs.
- Add contract tests for provider-local graphs, every directed provider pair,
  invalid co-location, missing Eventing placement, and drift between graph,
  package, and Terraform projection.

### Exit criteria

- no provider requirement is selected merely because that provider occurs in
  a legacy `layer_*_provider` list;
- Eventing participates in provider selection, readiness, cost, and evidence;
- graph digests invalidate stale plans and confirmations; and
- the graph is deterministic under identical typed inputs.

## 7. Phase 3 — CloudConnections, readiness, preparation, and repair

### Work

- Support multiple named encrypted CloudConnections per provider and explicit
  per-Twin selection.
- Implement allowlisted AWS CSV, Azure service-principal JSON, and GCP
  service-account JSON import alongside typed entry.
- Separate identity probes from graph-derived deployment readiness.
- Produce exact, non-mutating readiness results and a digest-bound preparation
  plan.
- Implement only bounded confirmed preparation: Azure provider registration
  and GCP API enablement. Keep AWS outbound-identity account enablement manual
  until a reviewed, idempotent provider operation is proven live.
- Add typed manual instructions and connection replacement for billing,
  quotas, policy, consent, capacity, and unsupported authority.
- Re-run readiness after preparation and expose partial failure honestly.
- Validate AWS IAM Identity Center primary Region, regional STS, and Azure
  Microsoft Graph authority as separate prerequisites.

### Explicit exclusions

- creating or revoking the deployment administrator;
- least-privilege generation and credential rotation;
- automatic account/billing creation, quota approval, policy override, or
  tenant-wide consent; and
- generic provider command execution.

### Exit criteria

- readiness requirements are traceable to graph nodes or edges;
- every mutation has a review, explicit confirmation, idempotency behavior,
  audit record, and manual fallback;
- secrets remain absent from responses, logs, events, archives, and errors;
- failed preparation can be repaired without editing hidden state; and
- deployment cannot start with a stale or incomplete readiness result.

## 8. Phase 4 — immutable Twin workflow and bounded interchange

### Work

- Keep draft Create/Edit for typed workload, devices, events, state machines,
  simulator configuration, and bounded user functions.
- Prefer typed forms while allowing the corresponding versioned individual
  configuration files to be imported and validated.
- Define one versioned Twin archive for Duplicate/Export/Import that contains
  allowlisted configuration and extension sources but no secrets, Terraform
  state, deployment outputs, or arbitrary executable project layout.
- Require a unique Twin name for Duplicate and Import.
- Make deployed infrastructure immutable. Changes create a new draft and a new
  calculation; no in-place update is offered.
- Retain explicit Destroy and allow same-Twin Re-deploy only after confirmed
  successful Destroy.

### Remove

- arbitrary deployment-project directory discovery;
- generic ZIP execution, provider-package assembly, and artifact catalogs;
- artifact history, ownership, migration, extension marketplaces, and
  free-form project snapshots; and
- infrastructure update, migration, rollback, or automatic source-Twin
  deletion.

### Exit criteria

- imported data is versioned, bounded, validated, and secret-free;
- a user can share a Twin without sharing cloud authority;
- deployed evidence cannot change under the same identity; and
- duplicate Twins have independent lifecycle and cost ownership.

## 9. Phase 5 — durable operations, access handoff, and verification

### Work

- Persist Deploy and Destroy operations with idempotency key, correlation,
  progress history, authoritative terminal result, and bounded retention.
- Keep SSE for live progress and implement reconnect, resume, and replay from
  persisted operation evidence.
- Reject a second active mutation for the same Twin.
- Replace embedded Grafana administration and the general operations dashboard
  with typed L4/L5 AccessBundles.
- Return URL, authentication kind, assigned login identity, and a one-time
  service-local Viewer credential only where the real runtime supports it.
- Implement one defined telemetry roundtrip and record that the event is
  observable or queryable at the expected destination.
- Make explicit Destroy, post-Destroy inventory, and residual-resource evidence
  first-class operation results.

### Exit criteria

- refreshing or reconnecting the UI cannot duplicate a cost-incurring action;
- all access surfaces have usable provider-accurate handoff information;
- deployment-admin credentials never enter an AccessBundle;
- telemetry evidence proves function, not merely Terraform success; and
- cleanup evidence distinguishes removed, retained shared prerequisite, and
  residual failure.

## 10. Phase 6 — UI consolidation

This phase begins only after Phases 1 through 5 have stabilized their API and
capability boundaries.

### Responsibilities to present

1. Twin scenario and bounded configuration;
2. calculation result, assumptions, exclusions, and immutable review;
3. CloudConnection selection, readiness, preparation, and repair;
4. deployment operation, access handoff, verification, and Destroy.

These are information responsibilities, not necessarily exactly four routes.
The UI audit decides whether existing screens should be combined or removed.

### Remove

- architecture-profile and objective selection;
- product-style admin, price-management, and generic project views;
- embedded provider-dashboard management; and
- UI for capabilities removed in earlier phases.

### Exit criteria

- the complete supported journey is possible without hidden backend calls;
- destructive or persistent provider actions have distinct confirmations;
- errors lead to readiness repair rather than raw provider diagnostics; and
- the UI makes PoC limitations and external provider steps visible.

## 11. Phase 7 — offline quality and documentation gate

### Work

- Run service-level tests, cross-service contract tests, Terraform validation,
  static security checks, secret scans, deterministic cost fixtures, and
  archive roundtrips.
- Exercise operation disconnect/reconnect, duplicate commands, partial
  preparation, redaction, cleanup failure, and unsupported graph cases.
- Update research method, threat model, user/developer docs, and traceability.
- Delete superseded phase plans, implementation handoffs, product roadmaps,
  stale TODOs, and docs for removed behavior after their retained rationale has
  moved to active sources.
- Preserve only focused future-work concepts, not distributed promises.

### Exit criteria

- all offline gates pass from a clean checkout;
- active docs agree on one architecture, one optimizer objective, one
  credential boundary, and one lifecycle;
- no live result is claimed from mocks or contract tests; and
- no secret or provider state is required for ordinary CI.

## 12. Phase 8 — low-cost live prerequisite gates

These checks are supervised and separately authorized. They are run before a
full Twin and stop on the first unresolved provider blocker.

### Checks

- identify all three real principals and target account scopes;
- verify exact regional services, APIs, Azure resource providers, permissions,
  quota reads, and capacity availability;
- verify IAM Identity Center primary Region and the selected managed-access
  path;
- verify Azure Microsoft Graph operations needed by the graph;
- enable only the reviewed confirmed provider prerequisites;
- build or pull the pinned runtime images independently;
- execute minimal identity exchanges for AWS→Azure, AWS→GCP, Azure→AWS,
  Azure→GCP, GCP→AWS, and GCP→Azure; and
- immediately remove probe resources and record residual state.

### Exit criteria

- every live prerequisite is ready or has an explicit, thesis-reportable
  blocker;
- all six directed federation paths have provider evidence independent of a
  full deployment; and
- no full Small environment has been left running while a prerequisite is
  unresolved.

## 13. Phase 9 — nine supervised Small deployments

### Scenario set

- three provider-local scenarios: AWS, Azure, and GCP;
- six multi-cloud scenarios covering each directed provider pair exactly once
  on a required cross-cloud Eventing or Twin-projection boundary.

The concrete assignments and their primary edge focus are frozen in
`docs/research/evaluation/small-scenario-matrix.json`. The checked matrix shows
which architecture edge, edge-contract class, and provider direction each
scenario covers. Redundant permutations are not added without a specific RQ
or risk justification. The matrix remains non-executable until every numerical
budget cap and candidate trace has been reviewed.

### Cost guardrails

- Small inputs only;
- one scenario active at a time by default;
- reviewed plan and maximum expected cost before Apply;
- maximum runtime and automatic alert/timer outside the deployment;
- immediate telemetry verification followed by Destroy;
- post-Destroy provider inventory and residual-cost check; and
- a stop condition after any unexplained residual resource, quota surprise, or
  cost deviation.

### Evidence per scenario

- input and calculation digest;
- provider allocation and cost trace;
- readiness and preparation record;
- Terraform plan/apply identifiers and timestamps;
- operation reconnect/replay evidence;
- L4/L5 access and telemetry roundtrip result;
- Destroy and residual-resource result; and
- observed cost, functional deviation, and classified limitation.

### Exit criteria

- all nine scenarios have complete comparable evidence, or an honest provider
  blocker is documented without substituting mocked success;
- each provider-local baseline and each directed pair is covered; and
- cleanup and actual cost are reconciled before the next scenario.

## 14. Phase 10 — thesis analysis and final repository cleanup

### Work

- Answer RQ1 from the intent-to-deployment trace and operationalization gaps.
- Answer RQ2 from capability gates, common roundtrip behavior, and deviations.
- Answer RQ3/RQ3.1 from paired provider-local and selected multi-cloud costs.
- Answer RQ3.2 from Eventing topology, directed route behavior, and explicit
  Eventing cost attribution.
- Add sensitivity analysis for workload, transfer, region, price snapshot, and
  the hosted GCP device boundary.
- Separate implementation defects, provider blockers, model limitations,
  threats to validity, and future product work.
- Reconcile final docs and remove completed implementation-only plans and
  handoffs while retaining the target concept, method, decisions, and evidence.

### Exit criteria

- every research answer cites reproducible repository evidence;
- conclusions do not generalize beyond the supervised Small PoC evidence;
- limitations state what remains manual and what was not live-validated; and
- the repository reads as a coherent research artifact rather than an
  unfinished product backlog.

## 15. Scope-change gate

A new capability enters implementation only if it:

1. is necessary to answer a research question, remove a validity threat, or
   prevent unsafe/cost-duplicating behavior;
2. cannot be represented by an existing closed-world contract;
3. has an identified phase, test, evidence output, and deletion impact; and
4. does not silently expand the live-evaluation matrix.

Otherwise it belongs in a bounded future-work concept, not the active plan.
