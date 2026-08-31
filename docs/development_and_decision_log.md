---
title: "Twin2MultiCloud Development and Decision Log"
description: "Durable rationale for the research PoC architecture and implementation boundaries."
tags: [thesis, decisions, methodology, architecture]
lastUpdated: "2026-09-01"
version: "1.7"
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
CloudConnections per provider and select the required ones for a Twin. AWS and
Google Cloud use one principal per connection. Azure is a bounded exception:
one deployment-purpose connection contains a resource-only deployment
principal and a distinct preparation principal for exact conditional RBAC and
graph-required Entra operations.

**Rationale:** Creating, rotating, revoking, and minimizing cloud authority is
a large security product in its own right. The PoC instead accepts a
pre-existing non-root administrator credential for isolated thesis scopes and
concentrates on safe use of that authority. Azure cannot safely combine
ordinary resource CRUD, role-assignment delegation, and Microsoft Graph
application administration in one principal without granting broader authority
than the PoC needs, so the two responsibilities are separated inside the same
encrypted lifecycle object.

**Consequence:** Credential values are write-only and transient outside the
encrypted Management store. Identity probes and graph-derived readiness are
separate. Supported account preparation is shown before mutation, requires
confirmation, is idempotent, and offers typed manual repair or connection
replacement. Account creation, billing repair, quota approval, organization
policy, tenant consent, and provider-side revocation remain external.
The Azure deployment principal must not mutate role assignments. The
preparation principal is accepted only with one condition-version-2.0 Role
Based Access Control Administrator assignment limited to the active role
allowlist and `User`/`ServicePrincipal` targets, plus exactly
`Application.ReadWrite.OwnedBy`, `Application.Read.All`, and
`AppRoleAssignment.ReadWrite.All` with manual tenant admin consent. This does
not generalize CloudConnection purposes or add an IAM administration product.
The Flutter Cloud-access surface is import-first but retains typed fallback.
Its Azure compatibility parser is deliberately local and closed-schema: it
extracts the two-principal Azure member, discards other-provider members and
uploads only normalized deployment-principal JSON through the unchanged
Management endpoint. This removes avoidable manual re-entry without adding a
generic credential mapper or changing the two-principal security boundary.

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

## D-13 — Provider service-selection trace

**Decision:** Changes to provider services, tiers, hosting models, access
surfaces, and support components are recorded separately from changes to the
logical layer model.

**Rationale:** Retaining a layer name does not mean the architecture stayed the
same. A service replacement can change protocols, durability, identities,
deployment risk, and cost formulas and therefore affect RQ1-RQ3.

**Consequence:** `docs/research/service_selection_evolution.md` compares the
predecessor mappings with the selected AWS, Azure, and GCP bundles. Any later
service change must update that trace before the provider bundle is refrozen;
offline bundle selection and live validation remain explicitly distinct.

## D-14 — Bounded provider-native diagnostics

**Decision:** Diagnose the Six-layer PoC through existing provider logs,
payload-free trace checkpoints, graph-scoped expected stages, structured
infrastructure checks, durable operation logs, and cleanup evidence. Do not add
a monitoring dashboard, alert manager, or autonomous remediation subsystem.

**Rationale:** The thesis needs enough evidence to locate a failed architecture
hop and to distinguish configuration, provider-query, runtime, and cleanup
problems. A second observability product would add cost and implementation
scope without answering another research question. Provider-native log sources
plus one strict checkpoint contract make the forward L1/Event/L2/L3 path
observable while keeping L4/L5 and command/outcome verification as explicit,
separately measured gates.

**Consequence:** Only `TRACE-*` and `VERIFY-*` flows emit checkpoint records;
they never contain telemetry or credentials. A trace is complete only when all
expected forward checkpoints are observed and is otherwise reported as
partial. The independent Event Layer is included in Terraform-state
verification. Live correctness remains pending until supervised component and
final scenarios produce provider evidence.

## D-15 — Atomic deployment with staged live verification

**Decision:** Keep one graph-bound Apply/Destroy lifecycle and stage functional
verification inside it: L1-L3/Eventing first, then L4, then L5, and finally the
complete simulator protocol. The first provider-local run per provider may
produce a separate component metrics document from the same deployment, but it
does not introduce a partial-deployment API.

**Rationale:** Provider-specific Terraform target lists or a second reduced
architecture would add another executable topology, weaken cleanup guarantees,
and repeat expensive infrastructure. Early checkpoints still permit immediate
Destroy when an upstream layer fails, limiting L4/L5 lifetime without claiming
that they were absent from the atomic Apply.

**Consequence:** Component measurements never replace one of the nine final
scenario records. GCP's early stage additionally validates the selected Small
1+1 broker/adapter allocation. Every final comparison is accepted only when
the exact matrix, revision, workload, simulator, protocol, candidate placement,
cost export, and terminal cleanup evidence remain bound and comparable.

## D-16 — Identity-only directed federation probes

**Decision:** Validate each AWS/Azure/GCP direction once with the smallest
ephemeral identity-only resource set before any full Twin deployment. Do not
create brokers, storage, Twin services, visualization services, or test
messages for these probes. AWS targets terminate at STS GetCallerIdentity,
Azure targets at one Reader-scoped ARM GET in an isolated probe resource group,
and GCP targets at one service-account impersonation.

**Rationale:** The six workload-identity contracts are a prerequisite for the
directed scenarios, but proving them with a full topology would conflate RQ1
operational setup, RQ2 interoperability, and RQ3 Eventing cost. Four source
paths can run locally without a directly charged resource. The exact Azure
managed-identity source semantics require provider-hosted execution, so only
those two paths receive one pinned, no-ingress, five-minute container runner.

**Consequence:** The schema- and digest-bound
`docs/research/evaluation/directed-federation-probe-plan.json` remains disabled
until each direction receives explicit mutation approval. Its aggregate direct
technical cap is USD 0.02, with immediate dependency-ordered cleanup and
residual inventory after every probe. GCP soft-delete tombstones are accepted
only when inactive, non-usable, and recorded with their purge time; any active
residual blocks the next direction. This is an evaluation harness, not a new
deployment mode or generic federation product.

## D-17 — Console-assisted GCP L4 IAP bootstrap

**Decision:** Protect the existing GCP Cloud Run Twin Explorer with its direct
IAP integration and perform one supervised, console-generated custom OAuth
bootstrap for the evaluation project, which has no organization ancestor. Run
the bootstrap only in the first explicitly approved GCP scenario, after
L1--L3/Event Layer verification and before L4 verification. Do not implement
OAuth in the application, create a load balancer or placeholder service, or
automate credential creation.

**Rationale:** Google-managed IAP OAuth is not available for this
no-organization project, while the console can create the minimal project-level
client and redirect configuration for direct Cloud Run IAP. Reusing the
already-modeled read-only service and Terraform-managed IAM bindings is the
smallest path that preserves authenticated L4 evidence. A separate five-minute
manual-step measurement makes the operational difference visible to RQ1;
bounded authenticated reads support RQ2; and a USD 0.00 direct incremental cap
keeps the setup cost distinct for RQ3.

**Consequence:**
`docs/research/evaluation/gcp-l4-iap-bootstrap-runbook.md` is the authoritative
procedure. It forbids exposing or persisting client values, adding roles or
resources, and continuing if the console surfaces a paid feature. The
project-level OAuth configuration may persist only across the required GCP L4
runs as an inventoried evaluation prerequisite and is removed after the final
one. Normal Terraform Destroy and residual inventory still run after every
scenario. The decision is approved; execution remains a separately approved
cloud mutation and no live success is claimed.

## Current implementation checkpoint

As of 2026-08-29, the standalone contract, graph boundary, credential services,
immutable interchange, durable operations, access handoff, cost-only Optimizer,
frozen pricing snapshots, and narrowed Flutter/Management contracts are
implemented and pass the complete credential-free container gate. The bounded
Flutter confirmation and repair surface and the provider-native diagnostic
checkpoint path are implemented and covered by offline tests. GCP Small L1 is
fixed to a non-HA 1+1 broker/adapter allocation, and all three device simulators
expose bounded telemetry-send and actual command-receipt checkpoints.

The 2026-08-31 offline provider-access correction implements the Azure
exception from D-05 across Management, Deployer, Terraform, Flutter, and the
setup guides. Every active Azure role assignment is now authenticated through
the separate preparation provider; ordinary resources remain on the deployment
provider. The Phase 8 readiness and directed-federation harnesses enforce the
same split for compatibility-file runs: Azure Resource Manager calls use the
deployment principal, while Graph and role-assignment calls use the preparation
principal. The same review found that `IoT Hub Data Receiver` is not a public
Azure built-in role. The active Six-layer contract and Terraform were corrected
to `IoT Hub Data Reader`, whose immutable public role definition is covered by
the preparation allowlist. The split authority, exact three-permission Graph
contract, legacy-connection replacement behavior, redaction, and policy
references pass the credential-free Deployer suite with 2,082 tests and one
intentional skip. The same offline gate covers an idempotent SQLite migration
that removes the three obsolete production-auth user columns while preserving
active user data. This is offline implementation evidence, not a live Azure
success claim; the completed two-principal bundle still requires a read-only
live validation before either remaining Azure-source probe.

The first supervised Phase 8 checkpoint has additionally verified the three
configured principals and their account scopes, AWS account/Region/STS/IAM
Identity Center readiness with 108 required permissions, Azure subscription,
Region, Graph, 16 resource-provider, and eight permission-group checks, and the
GCP project, billing, Region, 18 API, and 80 project-testable permission checks.
No Terraform Apply or workload resource was created. The local secret-free
evidence digest is
`f8dbf103e4b0878ba1d16375d61872594b968576ae034a3a947860eb67c926a4`;
the ignored evidence file remains a supervised artifact rather than a tracked
credential or product fixture. The nine candidates have since been
materialized offline and a digest-bound budget proposal records bounded USD
2–3 review caps, USD 21 in total, and an external 45/50/60-minute warning,
Destroy, and cleanup schedule. The calculation scales the complete monthly
estimate to one hour with threefold headroom and a fixed one-dollar uncertainty
buffer; unverified minimum charges block execution rather than raising a cap.
Those caps remain unapproved, the matrix retains `execution_enabled: false`,
and no provider call was made by the budget review.

The static runtime-image checkpoint is also complete without cloud mutation.
Both public runtime images and four pinned build inputs resolve at their
declared immutable digests; seven custom images build locally for
`linux/amd64`. The build exposed and regression-covered a GCP Grafana context
path defect. The checked record is
`docs/research/evaluation/small-runtime-image-readiness.json` with digest
`sha256:895b1bc40ae6e9862422110ccee01652de5dc7f09141fd0976ab118b8222e6e9`.
No registry image was published, and the per-Twin GCP processor extension
remains blocked until the exact canonical user-function artifact is frozen.

The subsequent read-only provider probe completed without a write operation.
AWS has sufficient checked Grafana, TwinMaker, and Kinesis headroom; Azure
resource types are regionally available, with four quota surfaces honestly
deferred until a resource exists; and GCP exposes sufficient Small compute,
disk, address, GKE, Firestore, and Cloud Run capacity. AWS and Azure L4/L5
prerequisites pass. GCP L5 remains an Apply-time check. The no-organization GCP
L4 path now has an approved console-assisted custom OAuth bootstrap with a
five-minute limit and USD 0.00 direct incremental cap, but it remains
unexecuted and therefore is not live readiness evidence.

All six federation probes are planned, schema-checked, and digest-bound. Their
exact resource manifests received supervised approval for run `26083001`. AWS
outbound identity federation is enabled as a zero-direct-charge evaluation
prerequisite and remains inventoried until the final AWS-to-Azure Twin
scenario, after which it must be disabled explicitly.

The four local-runner directed probes are complete. GCP-to-AWS passed one
Google OIDC to AWS STS exchange and `GetCallerIdentity`; GCP-to-Azure passed
the Entra exchange and one Reader-scoped ARM GET after adding a
condition-constrained Azure RBAC assignment for the deployment principal.
AWS-to-Azure passed the account-enabled regional STS assertion, Entra
exchange, and one Reader-scoped ARM GET. AWS-to-GCP passed the exact
role-bound Workload Identity Federation exchange and issued one ephemeral
target-service-account access token. Each direction removed its ephemeral
resources immediately, active residual inventory is clean, and only the
planned non-usable GCP soft-delete tombstones remain. The Azure deployment
assignment cannot delegate Owner, User Access Administrator, or Role Based
Access Control Administrator and remains inventoried only until the final
Azure evaluation cleanup.

RQ1 records Azure role-assignment permission and provider IAM propagation as
real operational prerequisites. RQ2 now has successful standalone identity
interoperability evidence for all four local directions without a Twin
deployment. RQ3 attributes USD 0.00 direct charge to these identity-only
checks. The remaining open work is the two bounded Azure-source federation
probes, the scenario-bound GCP processor image, the approved-but-unexecuted GCP
L4 bootstrap during the first applicable run, and finally the nine supervised
Small scenarios.

Both Azure-source runners are now implemented offline against the frozen
pinned image, no-ingress shape, 300-second runtime limit, and USD 0.01
per-direction technical cap. A first Azure-to-AWS attempt stopped before the
container group was created because the deployment application cannot create
the required ephemeral Entra application through Microsoft Graph. Its Azure
resources were removed immediately, active residual inventory is clean, and
the attempt incurred USD 0.00 direct charge. Subscription RBAC does not grant
this tenant-directory operation. RQ1 therefore records temporary, explicitly
consented Microsoft Graph application permissions as the remaining Azure
source prerequisite; RQ2 still claims four, not six, successful directed
identity paths. Azure-to-GCP remains unexecuted until the same prerequisite is
resolved.
