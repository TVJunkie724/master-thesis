---
title: "Twin2MultiCloud Development and Decision Log"
description: "Durable rationale for the research PoC architecture and implementation boundaries."
tags: [thesis, decisions, methodology, architecture]
lastUpdated: "2026-10-25"
version: "2.16"
---

# Twin2MultiCloud development and decision log

Status: active durable rationale

## 2026-10-25 — Restore the original L5 service family

AWS and Azure use managed Grafana again; the normal Six-layer path must not
substitute custom HTML/SVG hosting. Reuse one bounded Raw/Hourly dashboard,
existing provider sign-in and the existing UI access card. L3 still owns the
reader; L4 remains AWS TwinMaker/Azure Digital Twins. GCP L4/L5 remain excluded.
No additional product UI, monitoring platform or cross-cloud reader protocol.

RQ1 requires reproducible workspace/datasource/dashboard provisioning and
cleanup. RQ2 requires exact simulator values in actual Grafana panels, not
merely a JSON/HTML response. RQ3 includes workspace and active-user/license
charges: Azure Standard X1 is two node units; an AWS automation service account
is a billable identity and must be reused across retries. Historical SVG
evidence and the Five-layer baseline remain immutable and separately qualified;
the restored implementation is not live-proven until its affected tests pass.

The first live restoration attempt exposed Azure Managed Grafana's 23-character
workspace-name limit after the image-foundation stage materialized the random
suffix. Bound the existing name prefix while retaining that suffix; a native
mock plan now tests the maximum accepted Twin name with a concrete suffix.
Ordinary cleanup with the correction and an independent resource-group,
resource and scoped-role inventory confirmed zero residual cloud resources.
This failed attempt is not functional Grafana evidence. Its initial deployment
log stream was not retained, so missing creation timings remain missing rather
than being reconstructed as measurements.

The following live attempt created Managed Grafana but failed its optional
plugin-catalog preflight. Read-only inspection established that JSON API was
already installed at version 1.4.1 and absent from the optional catalog.
Microsoft documents JSON API as a built-in Standard datasource. Remove the
unnecessary catalog/install path and pin the observed built-in version; retain
the authenticated exact-version and actual datasource-data checks. This is a
provider integration correction, not a replacement visualization architecture.
See [Microsoft's built-in datasource list](https://learn.microsoft.com/en-us/azure/managed-grafana/how-to-data-source-plugins-managed-identity).

The next attempt passed that plugin check and reached the redundant Grafana
function-key creation, which returned HTTP 400. Rather than adding another
credential lifecycle, Grafana now reuses the existing L3 function-scoped key
through the same reader-key helper already exercised successfully by L3's live
post-deployment probe. Flat and ARM-envelope key responses are covered; missing
keys fail closed, without creating credentials or falling back to host/master
keys. The provider's detailed 400 response was not retained, so its internal
validation cause is not inferred from the HTTP status alone.

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

## D-28 — Fixed Core evaluation before access-layer evaluation

**Normal L5 receive-budget correction (2026-10-23):** three authenticated,
cloud-generated snapshots in the instrumented France Central cut matched all
six stored fixture values/timestamps after 69.434, 117.495 and 117.501 s.
The ordinary access path still cut off at 30 s in Deployer and 60 s in both
Management and Flutter. Align this existing one-shot path to the already
bounded Azure readiness read: 180 s at Deployer, 240 s at Management and
300 s at Flutter. Retain AWS's 30 s cloud read, no automatic UI retry, existing
owner/endpoint/size/data checks and stale-response handling. This is a transport
bug correction, not a screen redesign or an explanation of the earlier
unclassified West Europe HTTP 503 responses. A composed application pass must
still be observed separately.

**Instrumented L5 diagnosis (2026-10-23):** distinguish pre-handler admission,
handler failure and L3 dependency failure with a bounded, disposable L3/L5 cut
before another complete Azure application attempt. Temporary execution
telemetry is research instrumentation, not a new product observability feature.
The first instrumented attempt failed in ARM provisioning before any Function
App existed and required supplemental exact-scope group cleanup. Final state
and independent inventory are empty. Do not attribute that transport failure
to historical L5 responses or label it a successful L5 diagnosis.

**Frontend alignment (2026-10-10):** reuse the existing resolved graph and
currency evidence in optimizer and lifecycle views, including independent
Eventing. Remove the native path's misleading legacy allocation/cost comparison.
Model completeness, configuration completeness, cloud preflight and actual
telemetry/command/L4/L5 proof remain distinct. L5 workload labels describe
modeled reads, not a polling dashboard; cleanup copy states the current read
model's limits rather than inventing tombstone or global-inventory fields.
Deploy confirmation exposes available named bindings and the monthly estimate
with its billing limitation. No redesign, new feature, API or cloud run.
The bounded client gate passed 801 tests, analysis, architecture checks and
Web/macOS builds; the execution plan records the offline browser/popup limit.

**Normal L5 integration (2026-10-08):** reuse the proven AWS/Azure HTML/SVG
renderer as an independent provider-local consumer in the normal graph. L3
retains reader/storage ownership; L5 owns its invocation, hosting and read
permission. Fixed owner-scoped Management access signs server-side and returns
one bounded snapshot to the existing Flutter Open action. No Grafana, custom
dashboard client, auto-refresh or new login is introduced. Empty panels prove
reachability only; data evidence remains a separate assertion. GCP L4/L5 and
remote L5 readers stay excluded. The cost model now includes L5 execution and
two L3 reads per snapshot; assumed durations are not live measurements.

The first normal application preflight exposed a representation mismatch:
canonical architecture serialization sorts atomic component IDs whereas RDS
retains bundle order. Compare their complete sorted lists, retaining duplicate
and missing-component rejection. Directory validation also now includes the
canonical hidden extension source root, which ZIP validation already covered;
other build/cache directories remain ignored. Both fixes have regression tests.
The existing isolated observations are preserved; these changes alone do not
establish a successful normal application deployment.

The initial read-only normal AWS plan also failed at initialization of the unselected
AzureRM/AzAPI providers. The existing Core harness explicitly supplied Azure
credentials even for AWS-local runs; their successful runtime observations
remain valid but did not establish provider-independent application credentials.
The normal package does not silently acquire credentials outside its graph.

**Approved PoC simplification (2026-10-08):** retain the shared Terraform root;
do not refactor provider modules. The isolated single-user Deployer may explicitly
opt into `TF_AZURE_PROVIDER_AUTH_FILE`, an ignored, read-only local credential
file. Only subscription, tenant, client ID and client secret are projected into
private Terraform inputs when Azure is not selected and the operation does not
already supply Azure credentials. Selected Azure deployments still require
their normal CloudConnection; this is not a fallback for missing deployment
authority. No Azure resource, region choice, optimizer assignment, UI feature or
portable credential artifact is added. Missing/invalid opt-in files fail with a
value-free error. Apply and Destroy require the same runtime configuration.

This accepts an authentication dependency, not a claim of provider-independent
deployment or production multi-tenancy. Keep it explicit under RQ1 limitations;
RQ wording and runtime evidence boundaries stay unchanged. Verify the native
AWS plan contains no Azure creations before Apply. No cloud mutation occurred
in the initial checkpoint.

Verification of the approved accommodation: 72 focused tests, the full safe
Deployer suite (2187 passed, 1 skipped), seven native Terraform mock-plan tests
and the strict documentation build pass. The real, non-targeted AWS resource
plan passes with 110 managed creates and no Azure/GCP resource creations.
Its placeholder image digest makes this a plan-shape check only; no Apply or
complete application success is inferred.

**Local command observations complete (2026-10-05):** AWS, Azure and GCP now
have real simulator-to-rule/action/Event-to-device receipt and exact authenticated
L3 evidence. GCP's remaining blocker was the local simulator client's use of a
Paho 2-only constructor in the shared Paho 1.6 environment required by the Azure
SDK. Accept the two existing callback APIs and construct the actual client offline
before cloud work; do not change the cloud graph or provider dependency pins.
All successful attempts have Destroy and independent zero active inventory.
Keep AWS/GCP provider-managed inactive deletion markers distinct from strict
zero inventory and retain the original failed attempts. These single local
observations do not establish directed command or complete-profile coverage.
See the [integration close-out](plans/2026-10-04_poc_integration_closeout.md).

**Azure command closure (2026-10-05):** Execution logs and the live subscription
rules API isolated a missing Service Bus filter after successful telemetry,
history and rule evaluation. Native named Terraform rules replace the reserved
child-rule ARM templates without widening event filters. A pre-send live-rule
check and the actual simulator receipt then passed, as did exact L3 readback,
Destroy and independent zero inventory. Retain the explicit warm test condition;
do not recast previous timeouts as cold-start evidence or extend this local
result to directed command paths. See the
[integration close-out](plans/2026-10-04_poc_integration_closeout.md).

**Azure deployed Event-to-L4 observation (2026-10-05):** The fixed 45-resource
cut passed with real Event Hubs delivery, deployed runtime identities and exact
Digital Twins readback. Destroy and independent zero inventory passed. Local
publisher dependency failures remain separate failed attempts. This verifies
the Event/L4 edge, not command return, cross-cloud L4 or graphical L5; timings
and source revision are retained in the
[integration close-out](plans/2026-10-04_poc_integration_closeout.md).

**AWS deployed Event-to-L4 observation (2026-10-04):** The bounded 33-resource
cut passed with a real stream consumer, runtime identity and exact TwinMaker
readback. Destroy and independent zero inventory passed. This closes that edge,
not a full-profile deployment, replay test or cross-cloud L4 claim. Failed
attempts and phase measurements remain in the
[integration close-out](plans/2026-10-04_poc_integration_closeout.md).

**Azure command observation (2026-10-04):** A receipt timeout after successful
function indexing and exact L3 readback is not an ingress failure. Keep that
failed observation, then test bounded warm Rule/Control and action groups without
changing routing or the receipt deadline. The warm condition is explicit and
does not alter telemetry-only Core defaults or support a cold-start claim.
See the [integration close-out](plans/2026-10-04_poc_integration_closeout.md).

**Integration close-out preparation (2026-10-04):** Keep real simulator command
receipt separate from the nine telemetry passes and two isolated L4 checks.
A fixed AWS Core runner option adds one feedback rule and the existing device
registration/simulator, with exact timestamp/value readback and trace-correlated
receipt. Certificate journaling and independent inventory close the SDK-owned
cleanup gap; cleanup errors cannot yield green. GCP's optional combined listener
waits for MQTT subscription acknowledgement before sending. Account-bound
read-only planning admits 94 AWS Core creation entries; a separate targeted
Event/L4 dependency experiment reduces 51 entries to 33 without adding a new
deployment profile. None of these preparation results is live command or
Event-to-L4 evidence. Graphical L5 remains a distinct decision, not a JSON-reader
rename. See the [close-out plan](plans/2026-10-04_poc_integration_closeout.md).

**First directed slice (2026-09-19):** Reuse the existing Azure IoT sender,
AWS authenticated reader, image publisher and supervised lifecycle for one
Azure-to-AWS Core telemetry smoke. Keep reverse-route bindings, but make no
command-roundtrip claim. Live provisioning exposed incompatible Service Bus
source settings (sessions plus autoforwarding); sessions remain on destination
queues only. Subsequent delivery stopped before remote readback, and inspection
found the source bridge lacked hub-scoped Data Receiver permission. That exact
permission is corrected offline, without broader authority or new compute.
RQ1 retains provisioning/cleanup timings and defects; RQ2 remains pending for
directed delivery; RQ3 keeps failed-run costs separate from successful samples.
The initial three attempts have zero independent AWS/Azure/active-Entra residuals.
The fourth attempt then passed all ten expected telemetry values and both AWS
event-stream checks, followed by successful Destroy and zero independent
residuals. This live-validates the narrow receiver-permission correction and
closes RQ2's functional gate for this directed Core telemetry slice only.
Phase/resource timings and ten message-latency samples are retained; billed cost
attribution, the other five directed cases and command roundtrip remain separate.

**Azure integration condition (2026-09-19):** Actual worker indexing exposed
HTTP argument and Event Hubs batch-annotation defects, now corrected without
changing responsibilities. A disposable same-app comparison then verified the
minimal HTTP function and real processor under one always-ready HTTP instance.
The Azure Core telemetry path therefore uses one warm instance at processing,
processor extension and reader; full-profile defaults remain unchanged. This
bounded condition must be reported with its additional baseline cost, not
presented as on-demand/cold-start performance. The subsequent Azure Core run
passed ten-message readback and completed Destroy with zero run resource groups.

**Live execution note (2026-09-17):** The three local Core smoke tests are now
explicitly authorized and supervised. Preserve the distinction between
functional verification, successful Destroy and independent physical absence.
AWS IoT Command deletion can leave an inactive provider-managed tombstone for
12 hours; this is recorded, not silently counted as an empty inventory.
Execution status and bounded-run limitations are maintained in the Core plan.
The runner now retains successful and failed phase timings, Terraform-reported
per-resource lifecycle durations without provider IDs, and Azure readback
poll/timeout observations. These service timings are diagnostic because cloud
resource boundaries differ. The comparable thesis measures remain the shared
Plan, Apply, readiness, verification, Destroy and inventory phases. Based on
the observed runs, the functional fail-safe limits are 10 minutes for AWS,
20 for Azure and 30 for GCP; a second GCP increase requires diagnosis rather
than another automatic extension.

**Decision (2026-09-16):** Implement one research-only `core` Terraform scope
for L1–L3 and Event Layer. L4/L5 placement, Twin projection delivery and access
resources are absent. Keep L3 readback and the existing full-profile admission
gates. No new architecture profile, UI, arbitrary partial-deployment framework
or Terraform targeting is introduced.

**Coverage:** Three local Core cases and six directed cases use the same Small
workload. In directed Core cases ingestion is at the source; Event Layer,
processing and storage are at the destination, with a reverse command path.
These are not renamed full-profile candidates or inherited cost approvals.
GCP Core is retained while its L4/L5 exclusion remains unchanged.

**Evidence boundary:** Offline preparation and mock resource plans are not live
E2E evidence. Prior federation probes remain historical identity evidence. The
All three provider-local Core telemetry smokes have passed ten-message readback.
AWS and Azure cleanup is complete. GCP Destroy succeeded with zero active
residuals; a pending-deletion Logging bucket still blocks strict overall green.
The Core plan retains this distinction. This is not command-roundtrip, tier-transition, directed-case or
L4/L5 evidence. The older AWS run's missing per-message latency distribution is
explicitly retained as a limitation, not reconstructed from incomplete logs.
RQ1 records scoped provisioning/cleanup,
RQ2 comparable Core functions, RQ3 actual scoped eventing and costs. Research
questions and Five-layer reference remain unchanged. Implementation results and
the live approval boundary are in the [Core plan](plans/2026-09-16_poc_core_evaluation.md).

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
remain pending live; D-28 adds offline Core preparation and infrastructure
separation. Research questions
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

**Frontend enforcement (2026-10-10):** derive permissions from lifecycle state
and successful-deployment history, including direct Wizard entry. A Destroy
does not unlock Edit or Deploy on a previously deployed definition. Use the
existing Duplicate action for a new experiment; Delete keeps Management's
separate state/history rule. This corrects client presentation, not the policy.

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

On 2026-09-17 the bounded provider-local Core evaluation concluded without
expanding into L4/L5, directed federation or the full profile. AWS passed the
ten-message Event/L2/L3 contract and authenticated readback; only two inactive
IoT Command deletion tombstones remain. Azure completed deployment and sent ten
messages, but the first Flex reader request timed out before readback; all
resources were destroyed and the cold-start polling path was corrected offline.
GCP completed image publication and Google-resource provisioning, then reached
the Kubernetes stage, where BifroMQ did not become Ready before the whole-run
deadline; no messages were sent. Kubernetes removal, Terraform Destroy and all
14 independent GCP inventory categories completed cleanly. These outcomes add
RQ1 lifecycle evidence, establish RQ2 only for AWS, and do not substitute run
allowances for RQ3 billing data. The research questions remain unchanged.

An offline check of the exact pinned BifroMQ image then resolved its declared
user `bifromq` to UID/GID 1000. The Pod security context had required non-root
execution without supplying that numeric identity, which prevents Kubernetes
from verifying a named image user. The existing UID/GID is now explicit. This
is a narrow startup correction, not a topology or capacity change, and remains
unverified live until a bounded GCP retry reaches Ready.

During local diagnostics, secret-bearing output was exposed inside the private
tool transcript. The affected Azure and AWS administrator credentials were
rotated, the replacement credentials were verified, and every prior credential
was revoked. The ignored credential file remains mode `0600`; no credential or
private evidence file entered Git.

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

### 2026-10-04 — Remaining GCP-source Core cases

The fixed GCP→AWS and GCP→Azure research runners reuse the existing MQTT/TLS
sender, authenticated destination readers, package/image publishers and
Terraform lifecycle. GCP's existing L1 broker remains on GKE; L4/L5 remain
excluded. GCP→AWS passed in its first attempt (10/10, 19.5 s verification).
The first GCP→Azure attempt stopped before message sends when a full follow-up
plan included Azure changes outside the MQTT stage. The narrow correction
targets the nine existing Kubernetes objects and leaves Entra app role/URI
ownership with their dedicated child resources. The retry passed (10/10,
220.3 s verification). Native Terraform validation and 29 targeted tests pass.

Both successful runs and the failed attempt were immediately destroyed and
independently inventoried with zero active resources. A follow-up expanded the
first AWS-case inventory to include its reverse-route GCP pool; the original
report is preserved alongside that correction. Additional Graph prefix queries
confirm no active Entra apps or service principals for either Azure attempt.
Each attempt leaves only one unusable, provider-deleted GCP identity-pool
tombstone. Core telemetry is therefore functionally verified for all nine
cases; strict tombstone-free all-clear remains separate.

The [Core evaluation record](plans/2026-09-16_poc_core_evaluation.md) retains
all attempts and deployment/image/service-creation/verification/message/
destruction measurements. RQ1 gains operational evidence and the scoped
Terraform ownership correction; RQ2 gains all six directed telemetry paths;
RQ3 gains recorded Eventing topologies and persistence samples, with billed
run-cost attribution pending. No research question, full-profile admission,
command-roundtrip claim or product scope was changed.

### 2026-10-04 — Core synthesis and bounded next step

The [compact Core results](research/evaluation/core-telemetry-results.md)
consolidate all nine successful telemetry paths offline using the existing
execution record. Phase boundaries, provider readiness differences, failed
attempts, inactive deletion markers and the older AWS per-message evidence gap
remain explicit. No raw private evidence, personal budget, fabricated latency
or billed-cost claim is published. This is integration evidence, not a provider
performance ranking or proof of complete-profile equivalence.

The [next L4 slice](plans/2026-10-04_poc_l4_evaluation.md) is restricted to AWS
and Azure managed Twin services, one Twin/model and the existing projection
adapter invoked locally. It is a partial research experiment, not a deployed
Eventing-to-L4 integration claim. Fixed Terraform targets reuse existing L4
definitions; final dependency closure, model compatibility, pricing and exact
execution approval remain gates. No production guard is relaxed, new layer
framework added, or cloud mutation performed. Research questions stay unchanged;
GCP L4/L5 remain excluded and L5 stays last.

### 2026-10-04 — L4 plan-only findings

Native mock and account-bound read-only L4 plans now isolate six AWS entries
and two Azure entries, all create-only. A fixed plan-only preparer denies
additional resources or existing-state updates; no Apply/seed occurred.
Azure's original shared role-map target would pull eleven entries including
IoT/ACR/Service Bus into the graph and was rejected. The smaller alternative
requires one separately tracked ADT-scoped SDK role assignment at execution.
The targeted Azure output now returns empty human-binding evidence when that
role was not selected; full-profile access evidence remains covered separately.

The AWS code/model review found that existing time-series projection relies on
a connector absent from the active Six-layer workspace plan, with legacy seed
output names also unresolved. The proposed no-connector current-state mapping
is not silently implemented or counted as a pass. The
[L4 preparation record](plans/2026-10-04_poc_l4_evaluation.md) retains this gate,
regional public meter prices and read-only Standard pricing-mode confirmation.
Service-only cost arithmetic is not a total deployment ceiling. No research
question, private budget, full-profile success or new cloud spending is implied.

### 2026-10-04 — Native AWS L4 current-state correction

Following approval of the lean correction, the active AWS seed now uses its
Six-layer workspace output and a native current-state component. No connector
Lambda or additional datastore is introduced. The runtime updates the entity;
authenticated readback matches metric, value, sequence and observation time in
one active snapshot. An incompatible existing external component fails closed;
the legacy external component contract is preserved. Content/probe revisions
advance to v3/v2. 145 focused offline tests pass across AWS/Azure runtimes,
post-deployment operations, verification and deployment-access projection.

This is not yet live L4 evidence. Historical TwinMaker connector functionality
is not claimed equivalent to the original architecture: L3 owns history, while
this RQ2 comparison covers current Twin state. RQs and the nine Core results
remain unchanged. SDK child counts were corrected to the real root/device graph
on both providers; cloud execution remains a separate bounded step.

### 2026-10-04 — Supervised L4 check and remaining evaluation gates

Implemented one fixed research runner for the two isolated managed L4 checks,
not a new deployment profile. It reuses actual AWS/Azure seed models and adapter
source, validates exact update/replay snapshots, captures phase/resource times
and source/model/fixture hashes, and attempts cleanup plus independent inventory
after failure, timeout or interruption. New AWS entities/components have bounded
active-state readiness; incompatible existing models remain rejected. The runner
does not create images, Core services, Grafana or GCP replacements.

Updated account-bound read-only plans still contain six AWS and two Azure
create-only entries. Three native mocked Terraform plans pass. Focused L4,
runtime, verification and access tests pass; a separate 136-test offline group
covers simulator lifecycle/configuration, provider command receipts, Event
runtimes and metrics assembly. No new cloud workload or live L4/command/L5 pass
is claimed. The detailed plan records the test counts and bounded cost envelope.

The protocol now explicitly distinguishes today's split execution from the
conditional complete-graph protocol. Actual Event-to-L4 delivery, live simulator
command return, graphical L5 and billed-cost attribution remain open. L5 must
not become an unapproved platform build or change of the research questions.

### 2026-10-04 — AWS and Azure isolated L4 passed live

The approved managed-service checks passed on both providers: real Terraform
provisioning, real application seed/model, native numeric projection, exact
authenticated state readback and same-event replay. AWS uses revision `cdf0d3e6`,
Azure `f7770bd3`. Both immediately removed SDK children and infrastructure;
independent scoped inventories found zero active residuals. Phase, per-resource,
projection/replay, Destroy and inventory timings are retained in the
[L4 execution record](plans/2026-10-04_poc_l4_evaluation.md). Billed attribution
is pending, not replaced by an allowance.

AWS exposed IAM propagation during workspace creation and an output indexing
deliberately omitted human bindings. Only the missing workspace is now retried
under an exact re-plan guard; absent human access produces empty evidence.
Both earlier cloud failures were destroyed and inventoried before retry.
Local pre-Apply failures also corrected the git-free runner revision input and
installed Azure SDK import. No extra service, broad role or research question
change was introduced. 179 focused offline tests and three native mock plans
pass after these changes. The full graph, Event-to-L4 deployed delivery,
simulator command return and graphical L5 remain separate, unclaimed evidence.

### 2026-10-04 — Bounded simulator roundtrip preparation

Inspection of the next check found separate send/listen connections in the AWS
and Azure simulator helpers (AWS reused the same MQTT client ID). Their optional
combined mode now subscribes/listens before sending on the same client; it
requires a valid diagnostic trace and the configured device. Only the correlated
command can satisfy the receipt check. Existing manual mode remains unchanged.
GCP already uses distinct client IDs and now offers the same explicit expected
trace check for its listener. No cloud resource, role, certificate, UI or session
framework was added. Positive/wrong-trace and invalid-payload tests cover the
small change; no live command result is inferred. The next resource plan must
include a real simulator device and feedback rule, which today's telemetry-only
Core fixture intentionally omits.
The expanded simulator/Eventing/metrics group passes 146 tests; together with
the 179 focused L4/runtime/verification tests this is 325 offline passes, plus
the three native Terraform mock checks. Changed Python files pass Ruff.

### 2026-10-04 — AWS simulator command return observed live

The bounded local AWS cut now proves actual MQTT simulator telemetry, rule/action,
Event command delivery, trace-matched device receipt with broker ACK, and exact
authenticated L3 readback. The one observed roundtrip was 13.646645 seconds.
Four failed attempts remain in the [integration close-out record](plans/2026-10-04_poc_integration_closeout.md):
a legacy-only Terraform endpoint guard omitted the Six-layer command endpoint;
the actual SDK exposed a `None` message-callback client and keyword PUBACK argument.
The fixes are limited to that endpoint and simulator callback; failure diagnostics
are payload-free and raw simulator errors stay private. No platform redesign.

Every attempt destroyed infrastructure and left zero active scoped resources.
Inactive IoT deletion tombstones are explicitly not reported as complete null
inventory. The successful functional attempt therefore is not yet strict cleanup
green. RQ1 records deployment/configuration defects and retry overhead; RQ2 records
this local command mechanism only; RQ3 retains actual phase/resource timings and
pending billed attribution. No earlier telemetry-only result is relabelled.

Local Azure/GCP receipt harnesses and fixed AWS/Azure Event-to-L4 cuts are prepared
and offline-tested. The latter use exact 33/45-address allowlists and existing
runtime packages; neither adds a general layer-selection framework or graphical
L5. The combined focused runner/simulator/L4 group passes 108 tests. Live results
must be recorded separately for each provider and responsibility.

### 2026-10-05 — Minimal graphical L5 observed on AWS/Azure

The user approved a small provider-hosted L5 consumer instead of the historical
Managed Grafana experiment. A shared server-rendered SVG view reads the existing
authenticated L3 contract through a separate Lambda/Function App. L5 has no
storage permissions or account credentials; readers retain L3 ownership. The
fixed research Terraform cuts add no Core, Event, L4, VM, GCP visualization,
Flutter feature or general partial-deployment platform.

Both live cuts passed: three actual stored raw values and three hourly records
rendered with exact timestamps in two charts; unauthenticated access rejected
(AWS 403, Azure 401); immediate Destroy and independent null inventory passed.
AWS deployment/verification/Destroy took 40.512/2.104/15.376 seconds; Azure
561.910/7.190/711.249 seconds. All 15/20 resource lifecycle timings and immutable
responses/plans are preserved privately. Browser inspection used byte-identical
cloud responses after/during cleanup, not a new local-only datasource.

[The evidence record](plans/2026-10-05_minimal_l5_evidence.md) states the limits:
L3→L5 with a seeded fixture, not simulator→L5, end-user SSO, Managed Grafana
feature equivalence or full-profile integration/admission. Existing RQs and the
historical FiveLayer model are unchanged. RQ1 gains bounded deployment/read/
cleanup observations; RQ2 gains the shared minimal graphical contract; RQ3
does not attribute this service-mapping change to Eventing. Lagged month billing
is separately scoped, not claimed as incremental experiment cost.

107 focused offline tests, Ruff and native Terraform validation pass. Preparation
corrections were limited to the container's missing Git, the installed Azure
Resource SDK namespace and negative-authentication checks before live execution.
The previous five AWS command deletion markers also disappeared: a new read-only
reconciliation found zero active resources and zero markers without repeating
functional runs. Original results were not overwritten.

### 2026-10-09 — Remove optimizer-config redirect from application read path

The representative application check reached the dashboard but the embedded
browser stopped loading the Twin after the authenticated optimizer-config GET
returned HTTP 307. Management now serves the existing slashless client URL
directly, with the same owner-scoped handler and response model as the canonical
trailing-slash route. OpenAPI and Flutter layout remain unchanged. Fourteen
focused route/contract tests pass; the release web application now reaches
the ready-to-deploy lifecycle screen. This is a local integration correction,
not cloud deployment or functional runtime evidence.

The first normal Deploy request then failed at package validation before any
Terraform execution: operation metadata and restored runtime files were counted
as uploaded source. Directory inventory now excludes only the operation marker,
lock, Terraform state and generated simulator/auth outputs; unexpected source
files remain visible to the strict manifest comparison. Twenty-one focused
operation/accessor tests and an offline acquisition/validation of the actual
Management-built package pass. ZIP validation is unchanged. The failed request
remains in the application history and is not a successful cloud observation.

Cleanup additionally exposed an invalid `terraform show -state=...` invocation.
The runner now passes the isolated state file positionally, as required by
`show`, while keeping other commands' state flags unchanged. Twenty focused
runner/destruction tests pass (with the application's normal `src.core` import
order); direct isolated collection exposes a pre-existing circular import.

The next credential check exposed an initialization-order defect: the resolved
graph was attached only after credential validation, although that validation
requires it. Both synchronous and streaming lifecycles now attach the existing
context graph first. Twenty lifecycle/preflight tests pass, including both entry
points. Credential validation is not bypassed. After cleanup of a never-deployed
Twin, the existing configure/preflight transition is required before another
Deploy; the current destroyed-screen redeploy wording does not express this.

The first real image-foundation Apply then exposed premature indexing of the
new L5 output before its resources exist. AWS/Azure L5 outputs now return null
during that intermediate stage; the later complete Apply remains responsible
for creating and publishing the consumer. The credential-free Terraform suite
passes all 26 native checks, including a provider-mocked foundation Apply and
teardown regression (seven Python tests). The live failed foundation was
destroyed, and an independent 23-category namespace inventory found zero
active resources and zero deletion markers. AWS TwinMaker pricing mode was
also read-only verified as STANDARD before the next attempt.

The following normal Apply completed image publication but TwinMaker rejected
its freshly created role with the same propagation signature seen in the
isolated L4 record. The Six-layer workspace now waits 30 seconds after its
role policy, matching the predecessor's bounded approach. This adds one local
Terraform timing resource, not a cloud service (111 rather than 110 managed
entries). Eight native-test wrappers and 19 scoped L4 runner tests pass; prior
live observations and their original resource counts are not rewritten.

Cleanup also identified an archived SNS topic that Terraform could not delete.
The normal pre-destroy hook now disables ArchivePolicy only on archived SNS
topics listed in the exact project state and matching its owned namespace.
Dry-run performs no mutation. Nineteen focused cleanup/lifecycle tests pass.
The independent inventory correctly detected this active residual despite the
older SDK fallback's empty inventory, so SDK-only emptiness is not sufficient
evidence. The separately observed inactive IoT deletion marker is not counted
as an active resource.

### 2026-10-09 — Frozen cost comparison, without widening live scope

The existing candidate materializer now accepts an explicit offline workload
override, still validated against the immutable Small/Medium/Large contract.
Seven materializer tests pass, including unchanged default cost, different
workload digest and rejection of unsupported inputs. A small research summary
reuses it for eight fixed placements at three sizes: 22 costed results and two
Large exclusions, never zero-cost substitutes. `--check` reproduces all 24
records byte-identically. The historical Eventing calculator also reproduces
its original result digest. No pricing refresh or provider call was performed.

The current model's cheapest Small placement in this bounded set uses GCP
Eventing with the remaining responsibilities on AWS (20.73% below AWS local);
AWS local leads at Medium/Large. Full ledgers and assumptions distinguish
modeled monthly projections from bills, causal Eventing claims and live capacity.
The thesis evaluation/discussion now includes the actual nine Core observations,
separate higher-layer cuts and this model comparison. RQs are unchanged.

### 2026-10-09 — Normal AWS application observation and bounded closeout

The ordinary release UI → Management → Deployer path completed one AWS Small
deployment at runtime revision `cd4e7b39` in 270.536770 seconds. Reconnection kept
the same operation and exactly one Deploy. The actual downloaded simulator and
its generated identity delivered a correlated command and exact persisted L3
raw/hourly values, an ACTIVE TwinMaker projection and matching graphical L5
content. The first assertion lacked the existing projection marker and remains
failed; the marked second sample passed within the same deployment. No seeded
storage, direct L4 write or substitute command injection supplied this result.
The shared-root auxiliary Azure authentication remains the approved PoC
simplification, not a root redesign or an Azure resource deployment.

The UI fetched real L5 HTML with HTTP 200. Because the embedded browser did not
expose the separate blob popup, visual evidence renders an unchanged saved copy
of that response. Popup behavior is therefore not independently qualified.
Normal logs preserve 110 creation-completion observations and phase boundaries;
these are not per-service API benchmarks. Five earlier failed Deploy attempts
remain part of the evidence and acquisition-cost boundary.

The journaled simulator certificate/policy/Thing required supplementary bounded
research cleanup. Normal Destroy first failed its state gate (157.246469 s),
then reconciled absent resources and succeeded (30.976129 s). Final independent
inventories found zero active resources in both namespaces (24 and 23 categories),
with one inactive IoT pending-deletion marker each. The original failed namespace
retains a marker-related Terraform entry: neither marker-free cleanup nor a
complete ordinary SDK identity-cleanup catalog is claimed.

The [application result](research/evaluation/application-closeout-results.md)
records metrics, limitations and delayed AWS/Azure month-to-date billing totals.
Current GCP billing remained unavailable; an older amount is not substituted.
No further cloud run was started for documentation or browser polishing.

Final verification passed: the frozen live-plan validator, 24 byte-identical
offline model records, strict MkDocs build, and the 41-page multi-file thesis
build with visual inspection of changed results/conclusion pages. No unresolved
references or overfull boxes were reported. Existing template warnings, including
the draft's empty bibliography, remain: a successful build is not submission
readiness. The changed-file secret check found no local credential values or
private evidence paths among files being committed.

### 2026-10-18 — Populated UI portability observation, bounded finding

The real local Web/Management workflow accepted the frozen Small scenario,
EUR reporting and an uploaded Python processor with `scale_factor = 1`.
Validation reported ten passed checks. Reimport through the browser file chooser
preserved the workload, region metadata and complete function source/configuration;
the exported definitions differ only in the requested Twin name. Optimization
through the UI produced the native immutable model result. Manual synthetic
Azure entry also passed required-field rejection and reload persistence; the
exact disposable connection was removed and absence verified. These are local
integration observations, not cloud E2E or provider authorization evidence.

The embedded browser still did not expose a confirmed ZIP download; the import
fixture came from Management's export endpoint. A newly observed User logic
restoration defect leaves saved configuration blank in the form, while the
backend and exported archive retain it correctly. The active execution plan
contains a narrowly scoped repair awaiting approval under the UI planning gate.
No source editor, API change, redesign, dependency or new cloud run is needed
to repair that display/state boundary. Baseline Flutter analyze and Web release
build passed. Existing historical cloud observations are not relabeled as
passes for the renewed UI campaign.

### 2026-10-19 — Correct credential source and configure transport

The previous authentication rejection used an outdated root credential bundle,
not the current locally recovered authority. Restoring the current ignored
bundle and binding a freshly validated connection resolved AWS authentication;
read-only Azure authentication and authority checks also succeeded. This is
a credential-source selection error, not evidence that the user's current
credentials had expired. No credential values enter tracked evidence.

The actual Web workflow then exposed a separate transport mismatch: Finish
still sent `state: configured` to the metadata update endpoint. The client now
invokes the existing Management `/configure` operation, preserving distributed
validation and rejecting other client-owned lifecycle transitions. No backend
safety gate or screen layout was relaxed. The old service-worker build was
isolated by serving the fresh build on a separate local origin.

Verification: 814 Flutter tests pass, analysis and architecture gate pass,
Web/macOS release builds succeed. Actual Web Finish reached CONFIGURED and
the ready-to-deploy lifecycle. A reviewed AWS-only plan has 111 managed entries;
pre-deploy independent inventory has zero matching resources across 21
categories. These are admission results, not a completed live deployment.

The next actual UI Deploy exposed a package-boundary mismatch: empty legacy
code dictionaries persisted by the normal Wizard as JSON text (`{}`) were
treated as embedded code. The package gate now recognizes only empty objects
in the four map-shaped legacy fields as absence. Populated, malformed, null
JSON, arrays and scene content remain rejected. The normal package build and
715 Management tests pass; the failed preparation created no cloud resources.

### 2026-10-19 — Renewed AWS application path and narrow contract repairs

**Cleanup closure, 2026-10-20:** read-only AWS checks confirmed that the inactive
IoT Command marker had disappeared. The first normal Destroy retry failed on
unused Azure-provider authentication in the shared Terraform root (29.518 s).
The existing opt-in auxiliary-auth mount was restored for the next normal
Destroy, which succeeded in 32.293 s and reconciled the absent command without
manual state removal. Management reports destroyed/complete, empty Terraform
state and zero provider residuals. A subsequent independent inventory is zero
across all 24 checked categories, including simulator identity. The temporary
mount was removed afterward. Failed attempts remain retained. This is RQ1
cleanup/recovery evidence, not a new functional run or a change to the accepted
shared-root PoC simplification.

UI follow-up: lifecycle summary and error banner now distinguish Destroy failure
(`Cleanup incomplete`) from Deploy failure using the existing typed Management
operation, including after reload. Unknown operation context remains generic;
neither error-message guessing nor private research inventory determines the
label. Existing telemetry history stays visible read-only after cleanup, with
live controls removed and its BLoC recreated when leaving deployed state. Cleanup
status, residual evidence and destructive confirmations are unchanged. This
bounded RQ1 evidence-presentation correction adds no provider calls or schema,
and does not resolve the outstanding AWS deletion marker or detached SSE issue.
Regression validation: all 827 Flutter tests pass, including typed failure labels,
reload/refresh, read-only pass/fail/empty/unavailable history, compact layouts and
200% text scaling. Static analysis and the architecture gate are clean.
Web and macOS release builds pass. A read-only browser check against the existing
local Management record confirms `Cleanup incomplete` alongside the separate
persisted telemetry PASS (3/0/0, 3.40 s), without runnable verification controls.
Only the local static Web server was restarted; no new cloud run or cleanup was
triggered by this UI correction.

The real UI-led AWS deployment and downloaded simulator now provide correlated
live L1-L3/Event, L4 projection, L5 raw/hourly readback and command-return evidence.
Deployment: 292.6154 s; simulator command receipt: 9.63888 s; complete functional
verification: 15.297624 s. The separate ordinary UI verification persists 3/3
passed phases in 3.4 s; infrastructure status is 12/12. Per-resource Terraform
creation times and failed attempts remain in private local evidence.

Four narrow integration corrections were required: browser-visible download
metadata headers; state-backed recognition of AWS's shared cold/archive lifecycle;
canonical device/event-time fields on the UI test message; and the existing
TwinMaker terminal evidence-kind value. These are contract repairs, not new
features, a redesign or weakened verification. The actual browser simulator
download differs from the executed API archive only in README text. The returned
L5 HTML was rendered unchanged locally; the embedded popup remains unqualified.

Cleanup exposed an unsupported boto3 paginator in TwinMaker pre-destroy handling.
The helper now follows nextToken when no SDK paginator exists, preserving the
owned-workspace boundary. A local Management auto-reload during Destroy also
interrupted streaming. The operator stopped the Deployer, backed up the local
database, retained that exact operation as failed with LOCAL_STREAM_INTERRUPTED,
and retried the normal Destroy operation. This is an execution deviation and
manual recovery, not proof of automatic restart recovery. Avoid editing mounted
backend source during live lifecycle operations.

Final independent inventory: 24 categories, zero active resources, one inactive
IoT Command pending-deletion marker. The regular Destroy retries took 104.554918 s
and 42.942686 s; Cloud Control reports AlreadyExists for the pending command, so
one Terraform state entry and incomplete cleanup remain truthfully visible.
No manual state removal or terminal success override was used. The browser's
detached-stream missing-ID error is also retained as an unqualified restart
recovery boundary. Strict-zero cleanup awaits provider deletion followed by
normal Destroy/state reconciliation. Simulator identities are removed. Temporary
test admission/provider-auth mounting and the local timeout guard were removed.
Verification gates: 814 Flutter, 717 Management and 2,214 Deployer passes, with
one intentional Deployer skip; analysis, architecture checks and both UI builds
passed. Raw credentials, logs and evidence remain outside version control.

RQ1 receives lifecycle timing and explicit operational failure/recovery evidence;
RQ2 receives exact correlated functional assertions only for this renewed AWS
application run; RQ3 receives observed event/command timing, not a statistical
performance claim or current billed cost. Other renewed provider/directed runs
remain separate.

### 2026-10-18 — Approved restoration and fail-closed cloud admission

The approved User logic repair (`cc3427b4`) preserves saved configuration while
current edits remain authoritative. All 808 Flutter tests, analyze, architecture
checks, Web/macOS builds and 18 native local-API integration checks passed.
Browser reopen/replacement worked; native Export saved the actual ZIP consumed
by native Import. Definitions match except Twin name. No redesign, API change
or feature was added; embedded-browser downloads remain unqualified.

Fresh AWS preflight exposed a retired required SQLite column. Migration 038
(`331db469`) removes only the two obsolete preflight version columns. Unlike
the earlier migration-037 deviation, the API was stopped and a verified private
backup taken before editing. All retained application-table values matched;
integrity/foreign keys and all 704 backend tests passed.

Independent AWS authentication contradicted the initial UI success. STS had been
marked ready before identity verification; partial success then hid overall
failure. `c84be449` fixes both boundaries, with 65 focused tests. The final safe
Deployer suite passed 2,207 tests with one intentional skip and one existing TLS
deprecation warning. The first run's missing-mount environment failure remains
retained; eight Terraform mock-plan tests and then the complete suite passed
with the required read-only repository mount.

AWS currently rejects authentication (`InvalidClientTokenId`); Azure reports
`AADSTS7000215` (invalid secret). The corrected API persists the AWS failure and
the real browser displays it. No new cloud workload or simulator identity was
created. Live execution needs local credential refresh, not another approval.
RQ1 records these migration/admission failures; RQ2 gains no new live equivalence
claim; RQ3 gains no new live latency or cost observation. The execution plan
contains the precise continuation and the distinction from historical passes.

### 2026-10-20 — Preserve scale-to-zero and distinguish diagnostic success

The composed Azure profile retains zero always-ready workers. Intermittent L5
responses do not justify silently replacing the serverless baseline with paid
warm capacity, extending ordinary read timeouts, or rewriting application layers.
Secret-free transport-phase logging and routing L5 logs to the existing workspace
are the only adopted production changes from this diagnostic slice. A temporary
on-demand ceiling of two did not reliably help and was removed with the failed
deployment, not adopted in Terraform.

Minimal HTTP functions reproduced failures without thesis application logic,
including with a native host client. These observations narrow investigation but
do not prove the underlying platform/network cause. A successful request pair
is explicitly distinct from the failed cross-client comparison and the still
open composed Azure simulator/command/L4/L5 chain. All four deployments in this
slice have completed Destroy and independent scoped absence checks. RQ1 retains
the failed lifecycle and cleanup timings; RQ2 receives no new composed-equivalence
claim; RQ3 receives no unsupported cold-start or billed-cost attribution. The
execution plan and application closeout results retain the detailed outcomes.

### 2026-10-21 — Regional HTTP diagnostic does not justify a baseline change

The approved North Europe minimal-host comparison retained identical package
contents and zero always-ready capacity. Four of six authenticated requests
timed out across Docker and host-native clients; two returned the exact expected
body, and anonymous access was correctly rejected. The aggregate failed. Neither
a regional migration nor warm capacity is adopted on this evidence. The shared
network path and hosting behavior remain unresolved diagnostic alternatives;
the failure does not justify rewriting the thesis application.

Ordinary Destroy, empty Terraform state and independent resource-group absence
all passed. Per-resource and request timings remain retained with the failed
result. The composed Azure E2E remains explicitly open. This preserves RQ1's
operational evidence without inflating RQ2 functional coverage or interpreting
request timeouts as measured cold-start performance for RQ3.

### 2026-10-22 — Permit observed initial Azure latency without weakening correctness

One ten-minute minimal-host observation, with zero always-ready instances,
passed all six correlated HTTP requests. A valid host-native response took
approximately 36 s although DNS/connect/TLS took under 0.224 s and its server
request lasted only 9.406 ms. All six AppTraces handler records use the same role
instance. The former 30 s client cutoff is therefore demonstrably too short for
some valid responses; the observed delay precedes application handler execution.
This does not identify the internal Azure component or prove cold-start behavior.
Historical HTTP 503 failures were not reproduced and remain unexplained.

Only initial Azure L5 readiness now allows 180 s per HTTP request, retaining
three bounded attempts and strict authentication/content checks (`f84a043c`).
Ordinary UI/AWS behavior and zero always-ready capacity are retained. Twenty-nine
focused access/API tests pass. RQ1 gains a correlated operational diagnosis and
bounded correction; RQ2 still lacks the composed Azure functional pass; RQ3 gains
individual latency observations rather than a statistical/cold-start or billed
cost attribution. The application closeout results retain the method and limits.

Cleanup completed with empty Terraform state and independently absent resource
group. Destroy's 521.916 s includes a supplementary exact deletion of the sole
provider-created Insights action group left outside the Terraform graph.
That diagnostic-only residual and its successful removal are retained alongside
the eleven managed resource creation/deletion timings; the result is not labeled
an unassisted Terraform cleanup pass. No diagnostic resources or temporary
function-key copies remain.

### 2026-10-22 — Keep deployment readiness separate from a valid functional observation

The seventh composed Azure attempt passed ordinary UI deployment and SDK
L3/Twin-seed/IoT/L5 readiness with scale-to-zero unchanged. A preceding failed
attempt motivated bounded, secret-free phase diagnostics (`a8e242f6`,
`6c7ca0ca`); these diagnostics do not themselves alter runtime behavior.

The external verifier's missing Python import path caused its safety handler
to start Destroy before a manual test retry. The retry's command deadline
therefore coincided with resource removal and is excluded from functional
evaluation. A quiet persisted log view was not proof of an idle cleanup.
Future research launches precheck dependencies before deployment and require
the actual `deployed` lifecycle state throughout verification. No database
state reset, success backfill, warmer baseline or speculative application
rewrite is used to recover an invalid measurement.

Both attempts finished ordinary Destroy, empty state and independent zero
run-owned resource-group/resource/role inventories. RQ1 retains deployment,
test-steering failure and cleanup timing; RQ2 still requires a fresh composed
Azure data-path observation. RQ3 receives no command latency, cold-start or
billed-cost attribution from a test concurrent with teardown. The execution
record and application closeout results retain the successful and excluded
boundaries separately; research questions and PoC scope remain unchanged.

### 2026-10-22 — Do not attribute an unclassified L5 5xx to client timeout

The fresh composed Azure attempt correctly stopped before simulator verification
when authenticated L5 readiness failed. Its final `_L5NotReady` denotes HTTP
502/503/504, whereas a client read timeout is a different exception. Exact HTTP
status/body were not retained. Since the existing L5 handler itself converts
L3/data-read failures to HTTP 503, an Azure hosting explanation is not established.
The handler's separate ten-second L3 read bound is an unexcluded alternative,
not a proven cause. No broader timeout, retry or warm-capacity change follows
from this ambiguous observation.

The lean correction preserves exact HTTP status/phase, classifies only the fixed
public L5 data-error body and logs only the upstream exception class/status.
It does not expose credential values, arbitrary error bodies or exception text.
The required canonical source-digest refresh preserves package admission rather
than bypassing a stale-pin failure. The final safe gate passes 2,254 tests with
one intentional skip; contracts and affected demo fixtures are synchronized.

Ordinary Destroy and independent scoped inventory are clean. RQ1 retains this
failed lifecycle and its cleanup; RQ2's composed Azure gap stays explicit.
RQ3 gains no fabricated latency, cold-start or billed-cost attribution. A
separately reviewed L3/L5 diagnostic cut is preferable to repeatedly rebuilding
the whole Twin without distinguishing the failing boundary. No further paid
run was initiated in this slice.

### 2026-10-23 — Isolate L3/L5 without changing the application baseline

The next Azure diagnostic reuses the existing two-Function/serverless-Cosmos
research fixture, removing its historical always-ready capacity rather than
reintroducing warm workers into the normal profile. A strict plan capacity
gate, private per-request observations and post-L5 direct raw/hourly comparisons
separate transport failure, the fixed L5 data-error response and independent
reader behavior. Neither successful direct queries nor seeded fixtures qualify
the outstanding composed simulator/command/L4/L5 path. The application runtime,
upstream timeout and architecture remain unchanged until a cause is observed.
Cleanup checks nested package-module state as well as independent ARM absence.
This is bounded diagnostic preparation, not a new live result or spending
authorization. RQ1 gains test steering and cleanup safeguards; RQ2/RQ3 receive
no new functional, cold-start or billed-cost claim from offline preparation.

### 2026-10-23 — Correct L5's own reader policy, not cloud capacity

The isolated diagnostic identified fixed L5 data-error responses with matching
live URL/key configuration. Actual reader data was valid, but a direct raw read
took 25.659 s. The unchanged L5 code separately reproduced an hourly reader
`TimeoutError` after its ten-second bound. A controlled host-client comparison
needed both a longer request and one transient retry to obtain both exact
panels. This is a demonstrated failure mechanism, not an assertion that every
historical 503 had the same underlying Azure cause.

The offline correction stays inside the existing Azure consumer: 60 s per
reader attempt, one retry for timeouts/502/503/504 and shared remaining-budget
checks. Authentication, content and size failures remain closed. No warm worker,
new service, dependency, generic retry framework or research-question change is
introduced. The original cloud baseline remains failed; paused-driver follow-up
and local-client comparisons are explicitly qualified, not promoted to E2E.
The evaluation driver also replaces 31 Azure polls with three so its direct
reader diagnosis can execute within the existing functional deadline. The
application closeout record retains measurements and limits; a fresh normal
cloud observation remains necessary for RQ2.
The correction and canonical source-pin cascade are committed in `9c9cc74e`;
2,267 safe Deployer tests pass with one intentional skip. Ordinary Destroy,
empty managed state and independently zero exact-scope ARM inventories close
the diagnostic. Inherited subscription/ancestor roles are explicitly excluded
from run-owned residual counts, never deleted to manufacture a zero result.

### 2026-10-23 — Preserve the failed normal Azure retry and complete cleanup

The ordinary UI-led application run includes the bounded L5 reader fix, current
canonical pins and no always-ready workers. Initial L3/Twin/IoT readiness passed,
but all three authenticated L5 requests returned unclassified HTTP 503 at about
sixty seconds. The fixed application data-error response was not observed; the
existing host logs do not establish the exact exception or a platform root
cause. The simulator/command/L3/L4/L5 verifier was correctly not admitted.
Do not weaken its gates or infer a cold-start cause from timing alone.

The failed deployment (896.535648 s), ACR build (30.990457 s execution), ordinary
successful Destroy (978.274303 s) and 110 creation/110 deletion timings are
retained separately. Empty Terraform/provider inventories and independent zero
ARM group/resource/exact-scope role counts close cleanup. The actual UI shows
DESTROYED/COMPLETE without inventing telemetry evidence. One Deploy and one
Destroy remain in this Twin's history. Temporary local authority/configuration
overrides are removed; original credentials and unrelated user files remain
unchanged. RQ1 gains the failed readiness/cleanup observation; RQ2's composed
Azure gap stays open, with no fabricated RQ3 message latency or billed cost.

### 2026-10-23 — Trace the remaining composed L3/L5 boundary

The instrumented two-app cut returned exact L5 data three times in France
Central (69.434, 117.495 and 117.501 s). A separate West Europe L5 host reading
the same France Central L3 returned exact data twice (68.9 and 123.027 s).
Neither result proves the seven-app, provider-local composed flow. The bounded
capacity comparison expired before producing a capacity-two observation, so
no capacity increase is adopted. Operator steering and that incomplete
comparison remain qualified in the private diagnostic record.

Full Azure L5 deployments now reuse one capped Application Insights component
and the existing shared Log Analytics workspace for L3/L5 request/handler
traces. The existing Core command diagnostic remains unchanged. Connection
strings use the provider-owned site configuration, not duplicate app settings.
The added trace resource has a 0.1-GB daily ingestion cap, no dashboard, and
does not introduce always-ready workers. This is focused diagnosis of the
unclassified HTTP 503 boundary, not a functional pass or a root-cause claim.
Safe Deployer verification: 2,269 passed, one intentional skip; the reviewed
full plan contains 112 creates, no updates/deletes, seven zero-always-ready
Function Apps, and no AWS/GCP resources.

### 2026-10-23 — Bound initial Azure L5 readiness by time, not three responses

The instrumented full topology reproduced initial L5 HTTP 503 responses after
about sixty seconds despite a 180-second client allowance. Two authenticated
requests and one anonymous retry failed; two anonymous requests correctly
returned 401. The three-attempt readiness sequence stopped after 191.226 s.
Available L5 traces show registration/host initialization across three role
instances, but no matching invocation record at collection time. This does not
prove a crash, quota exhaustion or a specific platform cause; ingestion delay
also limits negative conclusions. The coarse built-in detector responses
covered an earlier window and are not evidence of a healthy workload.

Only initial deployment readiness now shares a 600-second monotonic budget
across transient retries, with 30-second spacing and at most 21 attempts.
Each HTTP request is capped by both its existing allowance and the remaining
budget. The budget is rechecked between authentication and data access and
before accepting the result. Immediate transient responses therefore cannot
consume the whole retry policy in a few seconds. Authentication failures,
invalid HTML and unsupported endpoints still fail closed; ordinary UI reads
and AWS behavior are unchanged. This is a controlled test of delayed initial
availability, not a claim that extending a timeout fixes the unclassified 503.
No warm worker, capacity increase or new resource is introduced.

### 2026-10-24 — Test bounded L5 on-demand headroom, not broader credentials

The next normal Azure deployment exhausted the 600-second initial-readiness
window: six authenticated calls returned unclassified HTTP 503 after roughly
60 seconds, followed by a final request bounded by the remaining deadline.
The same deployed L5 subsequently returned valid HTML with its existing
function-scoped key (37.504 s), returned 503 with the host default key (60.312 s),
then returned valid HTML with the original function key (0.805 s). These are
diagnostic reads, not a successful application deployment or full E2E result.
They do not support broadening credentials or attributing every failure to the
L5-to-L3 handler. Missing invocation records alone do not prove non-entry.

The next controlled change raises only Azure L5's on-demand maximum from one
to two instances. Memory remains 2048 MB, always-ready remains absent, and
runtime packages, access checks and functional assertions are unchanged.
Microsoft warns that an overly low HTTP scale limit can cause latency and
rejected requests ([scaling guidance](https://learn.microsoft.com/en-us/azure/azure-functions/event-driven-scaling)).
This is an explicitly unconfirmed capacity hypothesis, not a platform-root-cause
claim. Retain the failed baseline; require a fresh ordinary deployment, exact
simulator/command/L3/L4/L5 assertions, UI verification and independent cleanup.

### 2026-10-24 — Repair the ordinary Azure UI verification adapters

The capacity-two full deployment passed initial L5 readiness and the downloaded
simulator/command/exact-L3/L4/L5 assertions. Additional ordinary UI testing then
exposed two separate adapter defects. The Cosmos verification probe used an
account key although the Six-layer account disables local authentication;
a read-only live reproduction confirmed that rejection. The infrastructure
status adapter still called legacy Azure naming and Grafana probes rather than
the deployed Six-layer output contract. Do not reinterpret these as a failed
cloud data path, or label the entire UI flow green.

The narrow correction keeps key authentication disabled. Terraform adds only
Cosmos native Data Reader for the existing deployment principal on the current
test account; the verification probe uses Entra authentication and retains its
exact source-sequence match. Cleanup owns that role. Azure Six-layer status
reads actual registered IoT devices, seeded ADT models/twins, and the L5 Function
registration from deployed outputs. It does not fetch Grafana, modify data or
claim functional success from mere resource presence. Legacy profile behavior
and other providers are not changed. A fresh ordinary full run and UI checks
must validate these corrections; no repeated cloud-runtime rebuild is needed.

The retained capacity-two run completed ordinary Destroy and an independent
zero inventory (resource groups, resources, resource-scoped role assignments).
Its full functional path passed, but its UI E2E result remains failed because
of the two adapter defects above; L5 rendering through the UI was not confirmed.
The cleanup operation has a terminal success record and elapsed-time evidence;
per-resource Destroy timings were not retained for this attempt. Do not infer
those missing timings from the independent inventory or creation timings.
After correcting test-fixture isolation and native mock principal UUIDs, the
complete safe Deployer suite passed: 2,282 tests, one intentional skip.

### 2026-10-24 — Close Azure functional application and ordinary UI verification

A second fresh capacity-two/zero-always-ready deployment passed the complete
downloaded-simulator, correlated command, exact raw/hourly L3, L4 projection
and L5 chart assertions. Its first authenticated L5 response took 7.294 s.
The ordinary UI initially caught an unsupported `DigitalTwinsClient` context
manager in the new read-only status adapter. Commit `1dce3e06` fixes only that
local call and constrains the regression mock to the installed SDK interface;
cloud resources and runtime packages were unchanged. Rechecking the same
deployment gave 12/12 UI infrastructure checks and three persisted telemetry
phase passes, with no fail or skip. The full safe suite remained 2,282 passed,
one intentional skip.

Normal UI Destroy succeeded, with 224 creation/deletion timing observations
and independent zero experiment groups/resources/scoped roles. The genuine
L5 HTML was also rendered offline; the embedded browser's separate popup and
download-file handoff are explicitly qualified, not silently counted as visual
browser proof. See `docs/research/evaluation/application-closeout-results.md`
for timings, failed precursor observations and the unchanged RQ1–RQ3 scope.
This closes the representative Azure functional/UI-verification observation,
not every remaining scenario or a multi-browser compatibility claim.
