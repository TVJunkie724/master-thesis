---
title: "Twin2MultiCloud Development and Decision Log"
description: "Durable rationale for the research PoC architecture and implementation boundaries."
tags: [thesis, decisions, methodology, architecture]
lastUpdated: "2026-08-28"
version: "1.2"
---

# Twin2MultiCloud development and decision log

Status: active durable rationale

This log records decisions that affect interpretation of the thesis PoC. It is
not a product backlog and does not promise future functionality. Git preserves
the detailed implementation history; the active execution state is maintained
in `docs/plans/2026-08-26_thesis_poc_execution_plan.md`.
The predecessor-to-target rationale, alternatives, and evidence maturity are
maintained in `docs/research/architecture_evolution.md`.

## Decision principles

1. A retained capability must answer a research question, make a cloud
   mutation safer, or make an experiment reproducible.
2. Offline contract or fixture evidence is never described as live-cloud
   validation.
3. One owner is assigned to every durable datum and every public workflow.
4. Extensibility is demonstrated by a small clean boundary, not by inactive
   runtime choices.
5. Git history is the archive for superseded implementation plans.

## D-01 — Six-layer Eventing architecture

**Decision:** `six-layer-eventing@1` is the only deployable architecture.

**Rationale:** The original five scientific responsibilities remain useful,
but Eventing has its own placement, delivery semantics, trust boundary,
cross-cloud routes, verification requirements, and cost. Treating it as an
independent sixth responsibility makes those effects observable for RQ1,
RQ2, and RQ3.2 instead of hiding them inside Processing or provider glue.

**Consequence:** Every new Twin is pinned automatically to one hashed contract.
The public API provides read-only contract metadata, not a profile registry,
version selector, inheritance mechanism, or plugin system. Five-layer v1 is
retained only as an immutable Optimizer-side offline baseline for comparison.

## D-02 — Cost-only optimization with an extension boundary

**Decision:** Estimated monetary cost is the only scoring objective.

**Rationale:** RQ3 and RQ3.1 require a deterministic monetary comparison, not a
generic multi-objective framework. A small internal cost-scoring strategy keeps
the Strategy pattern and its tests visible without exposing unused choices.

**Consequence:** Latency, sustainability, resilience, weighted scoring, and
objective selection are absent from runtime contracts, APIs, persistence, and
UI. Their possible implementation belongs to the focused future-work concept.

## D-03 — Frozen pricing evidence

**Decision:** Calculations use dated, cited, hashed repository snapshots.

**Rationale:** A thesis result must be reproducible. Live catalogs can change
between scenarios and would turn price acquisition, review, approval, and
account-plan administration into a second product.

**Consequence:** The Optimizer exposes only read-only baseline/reference reads
and calculation. There is no pricing refresh, review center, approval state,
pricing credential, or public pricing administration workflow. Staleness and
provider-plan limitations are reported as evaluation limitations.

## D-04 — One resolved deployment graph

**Decision:** The immutable Six-layer resolution is the source of truth for
packages, directed edges, provider prerequisites, permissions, identities,
Terraform inputs, probes, and cleanup expectations.

**Rationale:** Fixed provider permission packs or UI-derived layer lists can
drift from what is actually costed and deployed. A graph-bound digest makes
that drift testable and invalidates stale readiness evidence.

**Consequence:** Provider readiness and bounded preparation must cite graph
requirement IDs. The Deployer rejects packages that do not match the selected
calculation and architecture digest.

## D-05 — Pre-existing deployment administrator credentials

**Decision:** Users can store several named encrypted deployment
CloudConnections per provider and select the required ones for a Twin.

**Rationale:** Creating, rotating, revoking, and minimizing cloud authority is
a large security product in its own right. The PoC instead accepts a
pre-existing non-root administrator credential for isolated thesis scopes and
concentrates on safe use of that authority.

**Consequence:** Credential values are write-only and transient outside the
encrypted Management store. Identity probes and graph-derived readiness are
separate. Supported account preparation is shown before mutation, requires
confirmation, is idempotent, and offers typed manual repair or connection
replacement. Account creation, billing repair, quota approval, organization
policy, tenant consent, and provider-side revocation remain external.

## D-06 — Immutable deployed Twins and bounded interchange

**Decision:** Drafts are editable; deployed Twin definitions are immutable.
Duplicate and typed Export/Import create independent drafts with unique names.

**Rationale:** In-place infrastructure updates would require migration,
rollback, optimizer invalidation, and Terraform replacement semantics that are
not needed to answer the research questions.

**Consequence:** A portable archive contains only versioned allowlisted Twin
configuration and bounded extension sources. It excludes credentials,
Terraform state, secret outputs, arbitrary directory layouts, and executable
provider packages. A source Twin is never destroyed implicitly.

## D-07 — Durable cost-incurring operations

**Decision:** Deploy and Destroy use persisted operations plus SSE replay and
resume.

**Rationale:** A browser reconnect must not duplicate a provider mutation or
lose the evidence needed to decide whether cleanup is required.

**Consequence:** One mutation may be active per Twin. Commands are idempotent,
progress history is bounded, and terminal deployment, verification, and
cleanup evidence is authoritative in Management.

## D-08 — Access handoff instead of dashboard administration

**Decision:** The PoC returns typed L4/L5 access information and one defined
telemetry roundtrip. It does not manage provider dashboards.

**Rationale:** RQ1 and RQ2 need proof that the deployed function is usable, not
a Grafana administration platform.

**Consequence:** Access bundles contain the provider URL, authentication kind,
assigned identity, readiness, and only a service-local one-time Viewer secret
where the deployed runtime actually has one. Administrator credentials are
never returned.

## D-09 — Bounded live evaluation

**Decision:** The final target is three provider-local and six directed
multi-cloud Small deployments, preceded by cheaper prerequisite probes.

**Rationale:** The matrix covers every AWS/Azure/GCP direction while avoiding
redundant enumeration of every layer permutation. It is broad enough to answer
the multi-cloud research questions but still cost-controlled.

**Consequence:** Each run has an approved budget/duration, immediate functional
verification, guaranteed Destroy attempt, inventory check, and residual-state
record. Live mutations require separate supervision and authorization.

## D-10 — AI-assisted engineering method

**Decision:** AI assistance is used openly for repository investigation,
implementation, test generation, documentation, and audit support; research
decisions and live-cloud authorization remain human responsibilities.

**Rationale:** The contribution is the documented method, contracts,
validation, evidence, interpretation, and critical review—not code volume or a
claim that generated code is correct by construction.

**Controls:** AI-assisted commits use a traceable commit prefix, changes are
reviewed against the research scope, deterministic tests and static gates run
before handoff, and live or empirical claims require recorded provider
evidence. AI output is never treated as a source for scientific facts.

## D-11 — Profile-bound startup without external application login

**Decision:** The PoC retains one owner profile for Twin and CloudConnection
ownership but uses a configured static local bearer instead of an interactive
identity provider.

**Rationale:** Google OAuth, Microsoft login, university SAML, JWT issuance,
roles, and multi-tenant session lifecycle do not contribute evidence for the
research questions. Ownership of encrypted provider credentials still requires
an explicit profile boundary.

**Consequence:** External application-login implementations and dependencies
are removed. The login page remains compiled but dormant and unrouted so a
future authentication adapter can reuse the presentation boundary. Cloud
workload identity and provider-owned access login remain separate Six-layer
deployment concerns.

## D-12 — Explicit architecture-evolution trace

**Decision:** Every material departure from the predecessor architecture is
recorded with its baseline, trigger, alternatives, rationale, RQ link,
consequence, evidence level, and status before the new behavior is treated as
the thesis target.

**Rationale:** The final code alone cannot show whether a design was inherited,
reasoned offline, changed after a blocker, or empirically validated. The thesis
must explain the evolution without presenting implementation history as
scientific evidence.

**Consequence:** `docs/research/architecture_evolution.md` is the durable delta
record. Open choices remain marked open, particularly the Small GCP-L1 broker
sizing. Git retains superseded implementation detail, while active documents
describe only the accepted target and explicit future-work concepts.

## Current implementation checkpoint

As of 2026-08-28, the standalone contract, graph boundary, credential services,
immutable interchange, durable operations, access handoff, cost-only Optimizer,
frozen pricing snapshots, and narrowed Flutter/Management contracts are
implemented and pass the complete credential-free container gate. The bounded
Flutter confirmation and repair surface is implemented and covered by the
frontend suite. Live prerequisite probes and the nine supervised Small
scenarios remain open and are not claimed complete.
