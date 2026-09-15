---
title: "Twin2MultiCloud Development and Decision Log"
description: "Durable rationale for the research PoC architecture and implementation boundaries."
tags: [thesis, decisions, methodology, architecture]
lastUpdated: "2026-09-10"
version: "2.7"
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

## D-27 — Storage read access is not visualization

**Decision (2026-09-16):** Assign the existing authenticated raw-history readers,
their runtime lifecycle and their exact-once costs to L3 hot storage. L5 is a
consumer; a JSON response does not establish graphical equivalence. Preserve
resource identities, packages, authentication and bounds. Retain old L5 output
names only as explicit compatibility aliases. No new service or dashboard is
introduced. Full-profile publication stays blocked while graphical L5 is
unimplemented; remote L5-to-L3 integration is a separate explicit blocker.

**Scope finding:** Exclude GCP L4/L5 rather than maintaining a custom Twin or
visualization platform. Preserve GCP L1–L3/Eventing. The matrix contains two
complete local planning cases plus six directions; GCP core/storage evaluation
and a genuine core-only deployment path remain pending. Research questions
and the original Five-layer baseline remain unchanged. Earlier IAP/Grafana
bootstrap proposals do not authorize work outside this reduced scope.

**Bounded audit:** L2 domain behavior versus Event Layer transport remains
separate despite shared packages. Source-owned storage movers, co-located L3
tiers, logging and registry sharing are intentional PoC restrictions, not
reasons to introduce further abstractions. One missing GCP Event-Layer-only
registry binding was corrected in the existing catalog.

**Evidence boundary:** New offline candidates and revised digests supersede
prior graph approvals. They do not prove deployment, graphical comparison or
cost-free L5. Verification and remaining prerequisites are tracked in the
[separation plan](plans/2026-09-16_poc_l3_read_access_separation.md).

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

### 2026-09-08 — Record the attempted automation and retained modeling effort

Automatic pricing acquisition was implemented and iteratively investigated,
not merely proposed. The repository history retains the three provider
fetchers, candidate extraction, matching evidence, normalization, and regression
tests. Representative checkpoints are `8f980bde` (fetcher matching evidence),
`4bf4a10d` (Azure Digital Twins billing corrections), `48458db1` (exact transfer
route evidence), and `b10df896` (removal of the live catalog/refresh boundary).

The decision to freeze pricing was also a scope decision: reliable, general
automatic acquisition and semantic integration of heterogeneous cloud tariffs
would have exceeded the bounded thesis PoC. API access alone did not establish
the correct service edition, region, meter, unit, tier, allowance, billing
scope, or minimum charge. This is an engineering finding for the investigated
implementation, not proof that automated cloud pricing is impossible.

Removing fetching does not remove the substantial effort already invested in
making provider prices comparable and calculable. Curated inputs still require
explicit workload-to-meter mappings, unit conversions, tier handling,
functional service-bundle comparison, and prevention of omitted or duplicated
costs. These belong to RQ1 operationalization, RQ2 comparability, and RQ3 cost
validity. Effort is reported qualitatively through implementation history; no
person-hour measurement or development-cost total is inferred.

The Infracost alternative was investigated through documentation on 2026-09-08,
but was not integrated or experimentally validated against the full Optimizer
JSON. No migration or new fetching subsystem is planned. The account of this
decision is carried into the research design and the thesis Discussion chapter.

### 2026-09-09 — Remove unused fetching remnants without changing prices

Removed the unreferenced raw-catalog candidate extractor, pricing-refresh SSE
helper, and unused fetcher URL/credential/path constants. Corrected the baseline
README and runtime messages to describe pinned evidence rather than a refresh
workflow. Historical snapshots, source manifests, offline reconstruction tools,
and the five-layer currency input remain for scientific traceability. No price,
snapshot identity, formula, or deployment behavior was changed.

Offline verification covers the three pinned provider snapshots and digests,
deterministic Six-layer rate-card reconstruction, registered meter coverage,
frozen-price calculations, all 243 Eventing topology/scenario allocations, and
read-only API resolution. Management selection remains fail-closed when pinned
evidence cannot be verified. This establishes input compatibility and internal
consistency, not current market-price accuracy or an account billing guarantee.

Verification used isolated Python 3.12 environments with each service's locked
dependencies because Docker was unavailable: 428 Optimizer pricing,
architecture, calculation, and catalog API tests passed; five existing tests
for the removed five-layer adapter remained skipped. Eleven Management run and
pricing-context tests passed, as did supplemental API/import/currency tests,
read-only rate-card reconstruction, and lint checks. No cloud resources were
created and no provider pricing requests were made.

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
CloudConnections per provider and select the required ones for a Twin. Every
connection contains one administrator principal for its isolated thesis scope.
The Azure administrator is used for ordinary resources, Azure RBAC assignments,
Microsoft Graph operations, verification, and cleanup.

**Rationale:** Creating, rotating, revoking, and minimizing cloud authority is
a large security product in its own right. The PoC instead accepts a
pre-existing non-root administrator credential for isolated thesis scopes and
concentrates on safe use of that authority. One Azure administrator deliberately
trades least privilege for a shorter, reproducible supervised setup. That trade
is appropriate only for this isolated single-operator PoC and is not presented
as a production pattern.

**Consequence:** Credential values are write-only and transient outside the
encrypted Management store. Identity probes and graph-derived readiness are
separate. Supported account preparation is shown before mutation, requires
confirmation, is idempotent, and offers typed manual repair or connection
replacement. Account creation, billing repair, quota approval, organization
policy, tenant consent, and provider-side revocation remain external.
The Azure principal must have subscription Owner and the Microsoft Graph
application permissions `Application.ReadWrite.All` and
`AppRoleAssignment.ReadWrite.All` with manual tenant admin consent. This does
not generalize CloudConnection purposes or add an IAM administration product.
The Flutter Cloud-access surface is import-first but retains typed fallback.
Its Azure compatibility parser is deliberately local and closed-schema: it
extracts the Azure administrator member, discards other-provider and retired
preparation fields, and uploads only normalized administrator JSON through the
unchanged Management endpoint. This removes avoidable manual re-entry without
adding a generic credential mapper.

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
assigned identity, readiness, and bounded capabilities. Provider credentials,
Function keys, and administrator credentials are never returned.

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
are removed. The previously dormant login page was removed during the
2026-09-10 cleanup; the local profile bootstrap remains the boundary. Cloud
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
complete simulator protocol. One metrics document per attempt records these
stages and cleanup; no separate component report or partial-deployment API is
required.

**Rationale:** Provider-specific Terraform target lists or a second reduced
architecture would add another executable topology, weaken cleanup guarantees,
and repeat expensive infrastructure. Early checkpoints still permit immediate
Destroy when an upstream layer fails, limiting L4/L5 lifetime without claiming
that they were absent from the atomic Apply.

**Consequence:** An aborted attempt remains incomplete and never replaces a
complete scenario record. GCP's early stage additionally validates the selected Small
1+1 broker/adapter allocation. Every final comparison is accepted only when
the exact matrix, revision, workload, simulator, protocol, candidate placement,
cost export, and terminal cleanup evidence remain bound and comparable.

### 2026-09-07 — Freeze implementation and reduce evaluation overhead

The agreed reduction keeps the nine scenarios and functional checks while
removing duplicate component reports and repeated shared UI-reconnect tests.
One representative replay observation covers the evaluated application
revision; provider paths and cleanup remain per-scenario evidence. The default
summary produces four core CSV tables. Stage analysis and SVG plots are opt-in
derivations from retained measurements.

An early failure uses the same metrics format, records failed/skipped phases,
explains incomplete sampling and preserves cleanup. Validators reject using
that attempt as a completed scenario. Existing Import, Export and Duplicate
features are frozen, with further work limited to evaluation blockers. No
additional normalized Five-layer implementation or visualization client is
introduced. This decision leaves the outstanding L5 comparison question open.

Scope is owned by the target concept, operating rules by the live protocol,
progress by the execution plan and scientific interpretation by the research
design. Other documents link to those rules instead of duplicating checklists.

Verification: 58 focused evaluation/plan tests and 24 subtests passed offline;
the changed Python passed static checks, and all six edited Markdown documents
rendered with valid relative file links. No provider operation was executed.

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

## D-18 — Start-or-resume Twin inventory

**Decision:** The Flutter `/dashboard` route is a **Twin experiments**
start-or-resume surface. `New Twin` is the only primary action. Each existing
Twin exposes one state-specific continuation; Duplicate, typed Export and safe
Delete remain in a secondary overflow.

**Rationale:** The thesis user needs to begin or continue a reproducible
experiment, not administer a product portfolio. Filters, sortable operational
columns and parallel row icons repeated presentation choices without adding
RQ1 operational evidence, RQ2 comparability or RQ3 cost evidence.

**Consequence:** The inventory keeps the existing Management-only routes and
mutation contracts while removing filter state, the five-column table,
last-deploy presentation and the duplicate action cluster. Latest-update
ordering is deterministic, draft continuation opens Configuration Workspace,
and all other lifecycle states open the overview. Cloud access remains a
separate app-bar utility.

## D-19 — Four-phase Configuration Workspace

**Decision:** The Flutter Wizard retains all 15 scientific tasks but exposes
only four persistent top-level phases: **Scenario**, **Optimize**, **Prepare**,
and **Review**. The task selector is scoped to the active phase, task status is
independent from UI selection, and the bottom bar has at most one filled
primary action.

**Rationale:** The thesis workflow requires dependency, completeness and
invalidation evidence, not a product-scale task tree. Showing every task as
global navigation and presenting both Calculate and Continue as primary made
the implementation surface appear broader than the research method.

**Consequence:** Phase selection resolves to a deterministic reachable task;
blocked phases explain their prerequisite. The existing ordered Back/Continue
path, Wizard BLoC, Management-only contracts, save/invalidation dialogs,
calculation, immutable selection, CloudConnection binding, validation and
finish semantics remain unchanged. Cloud access is a direct app-bar utility,
not an account-profile menu.

## D-20 — State-ordered Twin lifecycle overview

**Decision:** The Twin overview uses one identity/state/next-step summary and
shows exactly one lifecycle mutation command at a time. Its sections follow
the safe experimental sequence: prepare/deploy; verify/access before Destroy;
cleanup before retry; cleanup evidence before another approved run; then
configuration evidence.

**Rationale:** The thesis requires a reproducible lifecycle and observable
evidence, not a product operations dashboard. Duplicate headers and competing
Deploy/Destroy controls obscured the safe next action and weakened the
relationship between verification, immediate cleanup and residual inventory.

**Consequence:** Ready preflight becomes secondary to Deploy, blocking
preflight remains the primary remediation, and error states require Cleanup
before another attempt. Existing BLoC events, Management-only transport,
durable operation/SSE replay, access handoff, telemetry, simulator,
verification and cleanup-evidence contracts remain unchanged.

## D-21 — Four-surface PoC presentation boundary

**Decision:** The supported Flutter presentation consists of four focused
surfaces: Cloud access, Twin experiments, Configuration Workspace and Twin
lifecycle. They share app-bar utilities, top-aligned bounded content,
responsive behavior and one dominant next outcome. The local profile bootstrap
gate is not a product screen; no dormant login screen is retained.

**Rationale:** These four surfaces map directly to provider preparation,
experiment selection, immutable configuration and safe execution evidence.
Additional navigation, dashboards or vertically centered short workspaces add
product chrome without strengthening RQ1, RQ2 or RQ3.

**Consequence:** Secondary reproducibility/management actions remain outlined
or in overflow menus, destructive and persistent mutations retain explicit
confirmation, and each surface owns actionable loading/error states. The
shared audit changes presentation only and introduces no provider, Terraform
or Management API capability.

## D-22 — Resource-scoped Azure data-plane bootstrap

**Status:** Superseded by D-23. Retained to preserve the rationale and evidence
state of the earlier two-principal checkpoint.

**Decision:** Azure preflight requires the built-in Contributor role for
ordinary resource management and rejects effective role-assignment mutation.
It does not require Azure Digital Twins data-plane authority at subscription
scope. The atomic Six-layer graph uses the preparation provider to grant Azure
Digital Twins Data Owner to the deployment principal only on the newly created
ADT instance before seed and readback.

**Rationale:** Requiring the later resource-scoped data role before the resource
exists produced a false readiness failure and encouraged a redundant,
subscription-wide custom role. Contributor plus the existing split preparation
authority is the smaller supported PoC setup.

**Consequence:** The obsolete Azure custom deployer-role artifacts are removed.
Preflight reports graph-provisioned data actions without treating them as
ambient prerequisites, while Terraform drift tests retain the L4 binding as a
mandatory part of the atomic deployment graph.

## D-23 — One Azure administrator for the thesis PoC

**Decision:** The active Azure contract uses one service principal with the
built-in Owner role at the isolated subscription scope and the required
consented Microsoft Graph application permissions. The same identity performs
AzureRM, AzAPI, Azure RBAC, Entra, verification and cleanup operations.

**Rationale:** The earlier split-authority design was valid but disproportionate
for a single-operator thesis PoC. It created extra credentials, conditional RBAC
configuration, UI fields and failure modes without contributing evidence for
RQ1, RQ2 or RQ3. One administrator keeps the evaluated cloud workflow lean and
reproducible. The loss of least privilege is explicit and bounded to the
isolated thesis subscription.

**Consequence:** Azure input contains one client ID and secret. Readiness checks
subscription Owner plus `Application.ReadWrite.All` and
`AppRoleAssignment.ReadWrite.All`; it does not reject unrelated additional
Graph grants. Terraform has no preparation provider alias. The operator still
creates the app and secret manually and performs one privileged interactive
login. From that supervised session, the exact Owner assignment and Graph
admin consent may be applied programmatically; the deployment application
never elevates itself. Subsequent graph-required setup remains programmatic and
review-gated. Retired
preparation fields are ignored by the local compatibility parser and dropped
before the Deployer boundary. Existing historical live results remain valid as
records of the authority used at that time, but they do not describe the active
credential contract.

## D-24 — Machine-readable L5 instead of dashboard infrastructure

**Decision:** For the active Six-layer thesis PoC, L5 is one authenticated,
bounded JSON readback of raw history and hourly rollups on each provider. The
logical `component.visualization` identifier remains stable for the frozen v1
contract, but it does not provision or administer Grafana, dashboards, plugins,
viewer accounts, credential rotation, a GKE dashboard workload, or a separate
monitoring plane.

**Rationale:** The research questions require reproducible provisioning and a
functionally comparable way to inspect persisted results. They do not require a
product analytics UI. A common two-query contract provides the relevant RQ1
operational evidence and RQ2 comparison while removing standing workspace,
seat, cluster, disk, and load-balancer cost from RQ3.

**Consequence:** AWS uses IAM-signed Lambda Function URL requests, Azure uses
one function-scoped key created or reused during post-deployment verification,
and GCP uses an identity token against authenticated Cloud Run. Access responses
remain secret-free and expose no credential-rotation workflow. GCP image
publication uses at most four essential images on `e2-standard-2`, with a
20-minute timeout per image; current free-tier usage and the exact Terraform
plan remain mandatory supervised pre-Apply checks.

## D-25 — L5 visualization review stops at the cost gate

**Decision (2026-09-07):** Preserve D-24's current runtime while reviewing the
requested minimal restoration: existing AWS/Azure Managed Grafana integrations
and one GCP Grafana VM instead of a GKE dashboard workload. One dashboard with
two series panels is the full proposed scope, not a monitoring product.

**Correction:** D-24 establishes comparable readback only; its rationale must
not be read as proving graphical equivalence to the original Five-layer L5.
The original offline baseline remains unchanged. No third baseline is added.

**Result:** The [public-price and local-code review](research/evaluation/l5-visualization-feasibility.md)
found an AWS workspace-license floor above the existing scenario and portfolio
ceilings, plus incompatible legacy AWS/GCP reader authentication. Trials are
unverified. The review therefore stops before runtime restoration and requests
a hosting/cost decision. It does not increase caps, weaken reader authentication,
change frozen candidate evidence or claim cloud verification. No cloud mutation
or credential access occurred during this review.

## D-26 — Remove inactive surfaces and repair standalone simulator packaging

**Decision (2026-09-10):** Remove the 21 Flutter libraries unreachable from
the application entrypoint, their five exclusive test files, the inactive
five-layer calculation form, and two uncalled Management test-simulation
helpers. Preserve historical DTO decoding, migrations, cleanup/state recovery,
provider runtime contracts and scientific evidence. No live L5 or pricing
decision is changed. L5 post-deployment wrapper names now describe visualization
instead of implying that the active JSON readback deploys Grafana; referenced
historical helpers remain isolated rather than being blindly deleted.

**Rationale:** Speculative UI and duplicated historical controls add maintenance
without improving RQ1--RQ3. The supported scenario/currency form is retained;
missing or unsupported architecture pins cannot emit calculation input. The
shared skill guardrails now describe the actual Riverpod/BLoC ownership,
Management-only transport, local bearer and feature-branch rules in one place.

**Simulator correction:** Generated packages use explicit configuration paths,
an explicit Python package, read-only mounts for every device, and no automatic
restart. Device credentials are excluded from both image contents and build
context. The corrected GCP quick start and second-device lookup are exercised
against a real generated package with synthetic inputs, without sending data.

**Evidence:** 767 Flutter unit/widget tests passed, including scenario restore,
profile loss, historical input isolation and responsive boundaries. Flutter
analysis, architecture checks, Web and macOS release builds passed. The
network-disabled Deployer checks passed 31 simulator-focused tests and 212
core/post-deployment/package tests (overlapping selections); 27 Management
quarantine/simulator tests passed with synthetic credentials. This is offline
regression evidence, not a provider runtime or paid evaluation result.

## Current implementation checkpoint

The dated paragraphs below preserve the sequence of Phase 8 observations. D-23
and D-24 govern the active implementation; D-25 qualifies its research claims
and records the blocked visualization restoration. Earlier split-authority and
dashboard wording is historical rather than current setup guidance.

On 2026-09-04, the one-administrator contract was bootstrapped under a
supervised, temporary Global Administrator user session using the already
pinned Azure CLI image. The existing PoC service principal received
subscription Owner and the two approved Microsoft Graph application grants;
its redundant Contributor, Reader, Billing Reader and Cost Management Reader
assignments were removed only after the new authority was verified. The user
session and device code were then removed locally. A fresh application-token
probe passed Azure administrator authority, Graph authority, all six required
control planes and the Azure L4/L5 Region prerequisites. No application,
secret, workload or Terraform resource was created and no direct cloud charge
was incurred. Azure quota visibility remains partial by provider API design.

On 2026-09-05, the first supervised Azure-to-AWS probe with that administrator
stopped at AWS OIDC-provider validation before the target role or billable ACI
runner was created. AWS preserved a trailing slash from the issuer URL in the
returned provider ARN. The harness rejected this unallowlisted representation,
but set its cleanup-ownership flag only after the comparison and consequently
reported a false clean residual result. Immediate reconciliation selected the
single object by the exact Phase 8 run tags and normalized issuer, deleted it,
and then confirmed clean AWS, Azure Resource Manager and Microsoft Graph
inventories. Direct cost was USD 0.00. The runner now accepts only the two
semantically equivalent ARN forms and records the returned provider as
cleanup-owned before validation; focused coverage increased from 40 to 42
tests. No live retry followed the fix.

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
references pass the credential-free Deployer suite with 2,085 tests and one
intentional skip. The same offline gate covers an idempotent SQLite migration
that removes the three obsolete production-auth user columns while preserving
active user data.

On 2026-09-01 the completed two-principal bundle passed a read-only live
validation: both identities authenticated, Microsoft Graph and the conditional
preparation role were ready, the deployment principal excluded RBAC mutation,
and all eight deployment layers passed. The check also exposed that ADT
data-plane actions were incorrectly modeled as ambient subscription
prerequisites although Terraform creates the exact resource-scoped assignment.
The checker and setup guide now match the atomic graph, and the redundant
custom deployment-role assignment was removed under supervision. No Terraform
Apply or Twin workload was created.

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
`sha256:30fe0808341565f501dcb90b7574220559b4a4101f06d79125fbde9be0793873`.
The candidate-bound canonical function is also packaged deterministically; its
GCP processor extension builds locally for `linux/amd64` and passes the frozen
runtime-envelope contract. No registry image was published and no provider was
mutated.

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
source prerequisite; RQ2 still claimed four, not six, successful directed
identity paths. Azure-to-GCP remained unexecuted at that checkpoint.

After the Azure split authority passed live, the next Azure-to-AWS attempt
exposed a second operational prerequisite: a new managed identity can exist in
Azure Resource Manager before its service principal is readable through
Microsoft Graph. The attempt therefore stopped before the billable ACI runner
and incurred USD 0.00 direct cost. Cleanup completed; one application required
an exact object-bound delete retry after Graph continued to list it, after which
all active AWS, ARM and Graph residual classes were absent. The harness now
waits for this propagation within the existing deadline and retries only the
known application delete during residual reconciliation. RQ1 records both
identity and deletion propagation, RQ2 remains at four of six successful
directions, and RQ3 records no direct charge for this attempt. The
`first_exchange_failed` stop condition prevented an unsupervised retry.

The explicitly approved retry confirmed that the managed-identity wait works,
then exposed a second Entra propagation boundary: the newly created audience
service principal did not yet expose its app role when the assignment was
requested. The attempt again stopped before ACI creation, incurred USD 0.00,
and completed with immediately clean residual inventory. The harness now waits
for the exact audience service principal and expected app-role ID before
assignment. This adds a second measured RQ1 propagation point without changing
the four-of-six RQ2 result or the zero-charge RQ3 attribution. No additional
cloud retry was started.

The next supervised Azure-to-AWS attempt passed the managed-identity and
audience-application steps but received HTTP 403 while creating the audience
service principal. A free, read-only check of deleted Entra objects proves that
the preparation principal created the application and set its identifier URI;
the active permission token contains exactly the approved three Graph roles.
The service-principal request had included the optional
`appRoleAssignmentRequired=true` property even though the destination policy
already rejects assertions without the assigned `EventBridge.Exchange` claim.
The runner now sends only the required application ID and exposes precise
stages for application creation, identifier update and service-principal
creation. This is a PoC-scoped payload reduction, not an expansion of Graph
authority. Cleanup and residual inventory were clean, ACI was never started,
and direct cost was USD 0.00. RQ1 records the service-principal mutation
boundary, RQ2 remains at four of six successful directions and RQ3 remains
zero-charge for the attempt. The stop condition again prevented another live
retry without approval.

The following supervised attempt stopped before reaching service-principal
creation: the audience application was created, but its immediate identifier
URI PATCH returned HTTP 404 while the new object propagated through Graph.
Cleanup and active residual inventory were clean, ACI was never started and
direct cost was USD 0.00. The runner now retries only that exact idempotent
PATCH on 404 within the existing deadline; any other response still stops the
probe. RQ1 records this additional read-after-write boundary, while RQ2 remains
four of six and RQ3 records another zero-charge attempt. No permission, trust
or resource scope was expanded, and no further live retry was started.

On 2026-09-03 the user approved the D-23 PoC simplification. Management,
Deployer, Terraform, the federation runner and Flutter now use one Azure
administrator credential. The current API rejects retired preparation fields;
the local Flutter compatibility parser may read and discard them so an existing
untracked credential file can still be imported without exposing those values.
The local credential-free gate passes with 684 Management tests, 2,084 Deployer
tests plus one intentional skip, 812 Flutter tests, 40 focused evaluation-runner
tests and eight Management integration checks. Terraform validation, Flutter
architecture, Web/macOS builds and strict documentation build also pass. This
checkpoint changes no provider state and does not claim that the new
one-principal contract has been validated live; the next Azure provider check
still requires explicit approval if it would exceed read-only behavior.

On 2026-09-06, supervised Azure-to-AWS retries continued under the frozen
15-minute, no-ingress, one-container, USD 0.01-per-attempt boundary. The first
reached ACI for 57.237 seconds and demonstrated that AWS IAM evaluates the
complete Azure issuer path in its trust-policy condition. Two pre-ACI retries
then exposed eventual consistency at service-principal creation and app-role
assignment; both were USD 0.00. The assignment failure initially left one
cleanup-owned service principal visible, so the exact delete was reissued and
an independent inventory then passed all six resource classes. The runner now
retries only the observed Graph 400/404 propagation cases within its existing
deadline and reissues only that exact owned delete during reconciliation.

The next retry passed the managed-identity token, AWS web-identity exchange,
and AWS session-identity check in 40.320 seconds. Immediate cleanup and the
independent six-class AWS, Azure Resource Manager, and Microsoft Graph
inventory were clean. No Terraform Apply, Twin workload, message transfer, or
full E2E run occurred. For RQ1, the sequence records concrete identity
propagation and cleanup complexity. For RQ2, five of six directed standalone
identity paths now pass. For RQ3, only two retries reached billable ACI and
each stayed within its unchanged USD 0.01 technical cap; no exact provider
invoice is inferred. At that checkpoint, Azure-to-GCP remained the sole
directed prerequisite.

Azure-to-GCP then required four individually cleaned attempts. The first
reached ACI for 51.225 seconds, but the immediate terminated-container log read
returned HTTP 400, so no exchange success was inferred. The second created its
GCP provider but stopped before ACI because the Principal-URI validator still
accepted only the original pool name. Both cleanups and independent active
inventories were clean; the second attempt incurred USD 0.00. The harness now
retries only temporarily unavailable one-line ACI logs and derives a bounded
two-digit pool/provider suffix for retries because GCP soft-deleted names are
not reusable for approximately 30 days.

The third attempt passed the managed-identity and GCP STS stages but stopped at
service-account impersonation after 33.908 seconds. The exact token-generation
request now retries ten times with five-second spacing inside the unchanged
300-second ACI limit. The fourth attempt passed all three stages in 57.268
seconds, followed by immediate cleanup and a clean independent ten-class
inventory. Four expected pool/provider tombstones remain deleted and unusable.
RQ1 now includes measured Azure-log, GCP namespace, and IAM-propagation
behavior; RQ2 has standalone evidence for all six directed identity contracts.
RQ3 records three billable Azure-to-GCP runner attempts, each under USD 0.01,
and a conservative USD 0.05 cumulative technical ceiling for the five ACI-
reaching attempts across both Azure-source directions. No exact provider
invoice, Terraform Apply, Twin workload, message transfer, or full E2E run is
claimed.

The remaining runtime-image gate then completed entirely offline. The exact
canonical `processor.telemetry@1` artifact already bound into the candidate
pack produced a deterministic GCP package and container context, built for
`linux/amd64`, and returned the expected frozen runtime response. The updated
readiness record binds the artifact, package, context and local image digests
to exactly the four scenarios that place L2 on GCP. No registry publication,
Terraform action or provider mutation occurred. This is a deployment fixture
for the resource-integration evaluation, not a separate image feature or
research claim.

The subsequent offline pre-authorization review repeated all three
provider-local Terraform plans with mock providers: AWS planned 107 resources,
Azure 81, and GCP 143; all three tests passed without provider access. Current
provider terms exposed two cost-model boundaries that the hourly proposal does
not cover. AWS Managed Grafana requires at least one USD 9 Editor license per
workspace and monthly billing cycle, above the checked USD 3 scenario ceiling.
The GCP lifecycle can additionally start up to five metered Cloud Builds to
publish deployment-local images, although image preparation is not part of the
Optimizer ledger. The nine caps therefore remain unapproved and execution
disabled. The next decision is deliberately narrow: remove repeated image
publication from scenario cost and resolve the AWS L5 minimum without turning
the PoC into a generic registry or dashboard product.

On 2026-09-07, D-24 resolved that narrow decision offline. The active L5
implementation now exposes the same authenticated, bounded raw-history and
hourly-rollup JSON contract on AWS, Azure, and GCP; all managed/self-hosted
Grafana resources, GCP dashboard image inputs, viewer credential rotation, and
their active readiness requirements were removed. The nine Small candidates
materialize against the refreshed immutable pricing snapshots, and their
offline cap proposal totals USD 20 while remaining unapproved and disabled.
The runtime-image record now contains one public image, four pinned build
inputs, six static custom images, and the scenario-bound GCP processor image.
GCP publication uses at most four `e2-standard-2` builds with 20-minute
timeouts, bounding the worker list-price exposure to USD 0.48 if no promotional
free minutes remain. No image publication, Terraform Apply, Twin workload, or
paid end-to-end run occurred.
