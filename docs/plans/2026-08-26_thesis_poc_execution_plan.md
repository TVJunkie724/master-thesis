---
title: "Twin2MultiCloud Thesis PoC Execution Plan"
description: "Dependency-ordered implementation and evaluation plan for the final research proof of concept."
tags: [implementation-plan, thesis-scope, six-layer, evaluation]
lastUpdated: "2026-10-25"
version: "2.5"
---

# Twin2MultiCloud thesis PoC execution plan

Status: active execution source; bounded Core, local command, AWS/Azure Event-to-L4
and historical HTML/SVG L5 observations passed. On 2026-10-25 the user requested
restoring managed Grafana for AWS/Azure; implementation and offline checks pass,
but affected Grafana cloud/UI E2E is not yet complete. Earlier L5/application passes
must not be relabeled as Grafana evidence. Renewed UI-inclusive verification was requested on 2026-10-17;
the dated checkpoints below distinguish repaired local findings, renewed live
observations and remaining campaign work.

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

### Managed Grafana restoration — 2026-10-25, live verification in progress

The normal AWS/Azure Terraform, SDK postapply, access contracts and cost catalog
again select managed Grafana. Existing Raw/Hourly panels and UI external links
are reused. L3 owns authenticated history; native L4 services are unchanged;
GCP L4/L5 stay excluded. No RQ changes or product redesign.

Offline checks: 2,274 Deployer tests passed and one skipped, plus eight separate
native Terraform tests (including 26 mock plans); 470 Optimizer tests passed and
five skipped; 717 Management tests and 833 Flutter tests passed. Flutter analyze,
Web/macOS release builds and contract synchronization pass. Real local Grafana
12.4.0 with Infinity 4.1.3/JSON API 1.4.0 verifies synthetic reader data and
rendered panels; this is **not cloud simulator evidence**.

Fresh AWS/Azure drafts use new graph/cost snapshots without modifying historical
selected results. The reviewed Azure plan has 109 create-only Terraform objects,
six on-demand Functions and one Standard managed-Grafana workspace. Three live
attempts identified an overlong Azure workspace name, a mistaken optional-plugin
lookup for the already built-in JSON API datasource, and an unnecessary extra
function-key creation that returned HTTP 400. The fixes bound the name, verify
the installed plugin, and reuse the existing L3 function-scoped key.
The loaded Azure plugin is 1.4.1; the earlier local 1.4.0 check remains synthetic
historical evidence. The name regression passes 27 credential-free native mock
runs; the affected runtime suite passes 56 tests. The complete safe Deployer
suite after these corrections passes 2,276 tests with one intentional skip.
The actual Azure production REST helpers also pass against local Grafana 12.4.0
with JSON API 1.4.1 and an authenticated synthetic reader; that is not a cloud
simulator or user-login observation. Failed attempts are not counted as passes.

The fourth fresh Azure application deployment succeeds with 108 actual Terraform
creations. The downloaded simulator, correlated command, exact raw/hourly L3
values and timestamps, native ADT projection and authenticated Grafana queries
all pass. Existing operator sign-in succeeds in the real Managed Grafana browser;
both Raw and Hourly panels visibly contain those simulator data. The application
infrastructure endpoint reports 12 healthy checks and its typed access endpoint
returns the correct dashboard URL. The read model deliberately leaves its data
probe pending: the empty postapply readiness check is not simulator evidence.
The separate live assertions above must not be represented as a persisted UI
verification. The optional server-side PNG export returned HTTP 500; real
browser-rendered panels and their screenshot succeeded.

The local Flutter Open click remains unverified because browser automation
rejects localhost navigation; a human click was requested without bypassing that
restriction. Azure normal Destroy succeeds with 108 destructions; independent
resource-group, resource and scoped-role inventories are all zero. The retained
logs provide 216 resource creation/destruction timings. The first fresh AWS
attempt created 109 Terraform objects but failed in Grafana postapply before
the simulator ran. The original generic error did not identify the failing
Grafana operation; subsequent code records an allowlisted stage/HTTP/cause
without disclosing upstream bodies. Normal Destroy completed; independent
inspection found an orphan SDK simulator policy/certificate, removed only
after verifying exclusive run ownership. Active residual counts are zero;
one inactive IoT command deletion marker remains, so final null inventory is
not yet claimed. The retained stream has 109 creation and 95 destruction
timings; missing destruction timings are not reconstructed. The corrected
exclusive-identity cleanup and diagnostics pass the complete safe Deployer
suite (2,281 passed, one intentional skip). A local Infinity credential-chain
reproduction is diagnostic evidence only, not the proven managed-AWS cause.
The second fresh AWS attempt also creates 109 Terraform objects and reaches
the actual Grafana backend query. Its safe deployment diagnostic identifies
HTTP 400, `credential-chain-unavailable`, with the intended default AWS SDK
authentication. Independent inspection confirms the pinned Infinity 4.1.3
plugin, datasource and dashboard exist; a follow-up query returns HTTP 404
and is not a successful retry. No simulator or browser-data pass is claimed.
The approved plan's authentication incompatibility stop condition applies;
the user subsequently approved a deployment-scoped, least-privilege reader
identity. Its Terraform/SDK implementation and local signed Grafana fixture
checks replace the unavailable runtime credential-chain assumption. A fresh
managed-cloud simulator/browser run remains required; no additional paid
attempt is admitted until its resource and remaining-budget gates pass.
Normal Destroy then removes all 109 Terraform objects; 218 creation/destruction
timings are retained. Independent inventory across 23 categories reports zero
active residuals and one inactive IoT command deletion marker for this attempt.
Unlike the first attempt, no supplementary simulator policy/certificate cleanup
is required. The inactive marker still prevents a full null-inventory claim.
Completion requires normal Destroy and
independent zero inventory for each provider; API link correctness alone is not
a complete Flutter-to-Grafana browser E2E.

On 2026-10-27 independent rechecks of both earlier AWS attempts report zero
active residuals and zero inactive deletion markers across 24 categories,
including the newly added Grafana reader-user check. These dated null-inventory
observations complete their cleanup, not their failed functional tests.
A fresh admission caught and corrected the stale catalog reference to the old
Grafana IAM role policy before Apply. The catalog now owns the reader user and
its policy; current contract copies and fixture digests are synchronized.
Verification: 2,294 safe Deployer tests passed with one intentional skip, eight
separate native Terraform checks, 34 Optimizer architecture tests and 13
Management architecture tests passed. The third managed AWS attempt creates
110 resources, then fails its first Grafana backend query with HTTP 404 before
the simulator starts. Follow-up plugin/datasource/dashboard reads are HTTP 200;
the later permission-denied query occurs after automatic reader-key revocation
and does not explain the original 404. The bounded query-readiness retry now
also handles datasource/plugin unavailability (404); it is offline verified
with 2,297 passing safe Deployer tests and one intentional skip, not live proven.
Normal Destroy removes all 110 resources. Independent inventory reports zero
active residuals across 24 categories and one inactive IoT deletion marker.
220 per-resource creation/destruction timings are retained. No simulator,
browser chart, Flutter Open-click or final null-inventory pass is claimed for
this attempt. A fresh paid retry requires a remaining-budget admission.

### Renewed application verification — 2026-10-17, incomplete

Baseline: `75f029ec`, primary checkout, unchanged product code. The user requested
a renewed end-to-end check including the UI. Existing dated cloud observations
remain historical evidence, not passes for this new campaign.

Local observations use the real development Management API and Flutter Web,
not the demo adapter. No provider validation or cloud mutation was performed.

- **Passed, bounded draft case:** create/save through the browser, reload,
  import a portable archive through the real file chooser, and reload the
  imported Twin. Source and imported definitions agree except the requested
  new name and materialization of an empty Deployer configuration row. This
  is not a populated scenario/user-function roundtrip observation.
- **Export limitation:** the embedded browser did not produce a confirmed
  download in two attempts. The import fixture was obtained through the real
  Management export endpoint instead. Therefore browser Export -> Import is
  not claimed as a complete pass.
- **Passed rejection:** a deliberately invalid ZIP was rejected; no Twin with
  the negative-test name was persisted. The UI only reported a generic error.
- **Failed, actionable:** Azure JSON selection/parsing works, but persistence
  fails against the existing local database. The native API readiness test
  reports HTTP 409 on import; the browser likewise creates no connection.
  The old `cloud_connections` table retains `is_default_for_pricing BOOLEAN
  NOT NULL` without a default. The current model no longer writes that column,
  and the migration source contains no removal of it. The service maps an
  integrity failure to a generic concurrency conflict. Fresh-schema tests
  do not cover this upgrade path. Do not replace/delete the database or
  credentials to turn this into a pass.
- **Test tooling:** the first macOS gate failed before assertions during Swift
  package resolution. Explicit Xcode resolution succeeded; the direct native
  readiness retry built and ran with **7 passes, 1 failed import**. The root
  gate also fails on macOS Bash when all services already run, because its
  empty `started_services` array is expanded under `set -u`.

**Repair checkpoint — 2026-10-18:** the user approved the bounded migration
and entrypoint correction. Migration 037 removes only the two obsolete
CloudConnection columns and their two obsolete indexes, in one explicit SQLite
transaction. Regression tests preserve an existing synthetic opaque payload,
fingerprint, ID, binding and active index; prove idempotence and complete DDL
rollback on an unexpected dependency; and reproduce HTTP 409 before upgrade
followed by a successful encrypted Azure import after upgrade. The Bash gate
now guards empty-array iteration, with executable stubbed success/failure tests
for already-running, partially-running and stopped services.

The local development API auto-reloaded and applied migration 037 before the
intended operator backup was taken. This is an execution deviation, not a
pre-migration backup claim. The API was stopped and an owner-only SQLite backup
of the **post-migration** database was retained locally. The credential table
was empty at that check; preservation of populated credentials is established
by synthetic regression tests, not a comparison against a pre-upgrade local
snapshot. SQLite integrity and foreign-key checks passed. Future schema work
must stop auto-reloading services and take the backup **before editing** mounted
migration sources.

Verification: **42 targeted Backend tests**, **23 entrypoint/architecture tests**,
Ruff and shell syntax checks passed. The ordinary `thesis.sh test
frontend-integration` now completes all four native groups: **8 + 1 + 1 + 8 = 18
passes**, including Azure import/list/delete, architecture calculation/selection,
user functions and isolated Layer Access fixtures. These remain credential-free
local integration observations, not provider E2E.

The real Web UI also selected and imported the synthetic Azure JSON through
the browser file chooser against the upgraded existing database; the connection
remained visible as `untested` after a full reload. No cloud validation was
invoked. The exact synthetic connection was deleted through the Management API
after the observation, and absence was confirmed. The earlier browser export
limitation and full-cloud verification work remain open.

Remaining steps, in order:

1. Keep the completed migration/entrypoint regression gates green; retain the
   backup-order deviation above instead of rewriting the earlier failed attempt.
2. Repeat local browser credential import/manual entry and persistence with
   synthetic values, populated Twin export/import, configuration/optimization,
   rejection cases and native API contracts. Resolve the download observation
   limitation using a supported browser before claiming that interaction.
3. Prepare fresh, individually bounded UI-led Small runs: AWS and Azure composed
   L1-L5/Event plus downloaded simulator/command; GCP retains its approved
   L1-L3/Event scope. Repeat the six directed Core paths as separately scoped
   observations. Do not imply unsupported GCP L4/L5, cross-cloud L4, directed
   command return or tier transitions from those passes.
4. Before each cloud mutation, show the exact graph/artifact revision, resources,
   regions, cost exposure, cumulative allowance remaining, functional deadline
   and cleanup reserve. Earlier allowance is not reset by this campaign.
   Start via UI, verify reconnect without duplicate operations, retain exact
   telemetry/command/L3/L4/L5 assertions applicable to that run, then Destroy
   and independently inventory residuals, including simulator identities.

Retain failed attempts, timings and cleanup retries. Map conclusions to the
existing RQ1-RQ3 and keep mocks, local integration, live observations and
unverified claims separate. No research-question change or product expansion.

#### Populated local workflow checkpoint — 2026-10-18

At `84b07246`, the real Flutter Web release build and Management API accepted
the frozen Small scenario in EUR, a dependency-free Python processor archive,
and `scale_factor = 1`. The browser validation returned ten successful checks;
the saved function and completed Scenario phase survived a reload. A portable
archive obtained from Management was imported through the actual browser file
chooser into a separate Twin. Both exported definitions match exactly after
removing only `source_name`, including workload, regions, source files and
configuration. The imported Twin calculated and displayed an immutable native
result with independent GCP Eventing, Azure Twin state and AWS remaining
components. This is a model observation, not a deployment or live path pass.

Manual Azure entry also rejected missing fields and persisted synthetic values
as an `untested` connection across reload. The exact test connection was then
deleted (HTTP 204); a filtered inventory confirmed zero remaining matches.
No real credential was entered or provider validation invoked.

Two limits remain: the embedded browser again exposed no confirmed ZIP download
even in the release build, and the imported/reopened User logic panel shows an
empty configuration field despite the retained value in the backend/archive.
The latter is a presentation/state restoration defect: the panel reads only
the transient source draft, not the saved function configuration. It must not
be described as data loss or as a fully successful UI roundtrip. Flutter analyze
and the Web release build passed before any proposed fix. No cloud mutation or
new frontend runtime change was made in this checkpoint.

#### Approved repair and renewed admission — 2026-10-18

The approved restoration plan is completed in `cc3427b4`: saved non-secret
configuration initializes the existing form and replacement draft; subsequent
edits, including explicit removal, remain authoritative. Asynchronous loading
updates the form without resetting ordinary keystrokes. No API, layout,
workflow, dependency or architecture contract changed.

Verification: **808 Flutter tests**, including seven added regressions;
analyze and architecture checker clean; Web/macOS release builds passed;
**18 native frontend-integration checks** passed against the real local API.
The real browser restored the scale factor and validated/saved a replacement.
Native macOS Export saved an actual ZIP; native Import consumed that same file.
Re-exported definitions match exactly except Twin name. This closes native
export/import, not the embedded browser's unqualified download behavior.

The fresh AWS-only candidate was selected via the explicit supervised hook,
bound and configured. Read-only preflight exposed another legacy SQLite
constraint. Migration 038 (`331db469`) removes only the two retired preflight
permission-version columns. Management was stopped and a verified private backup
taken **before editing**. All retained application-table values matched afterward;
integrity and foreign keys passed. **704 backend tests** passed, including the
service regression that fails before migration and passes afterward.

Independent authentication exposed a false-positive AWS preflight: STS was marked
ready before GetCallerIdentity succeeded, and a successful partial check could
conceal overall failure. `c84be449` fixes both boundaries and rejects non-valid
checker results for every provider. **65 targeted tests** passed. The final safe
Deployer suite passed **2,207 tests**, with one intentional skip and one existing
TLS deprecation warning. The first run's missing-repository-mount failure remains
retained; the eight native Terraform mock-plan tests and then the complete suite
passed with the required read-only mount. No production resources were created
by these mock plans.

Live admission is blocked: AWS returns `InvalidClientTokenId`; Azure returns
`AADSTS7000215` (invalid secret). The corrected API and real UI show AWS as
invalid. No prerequisite was falsely acknowledged and no Terraform Apply ran.
Resume after local credential refresh: authenticate/check quotas, review the
exact bounded resource plan, then ordinary UI Deploy, downloaded simulator,
correlated telemetry/command assertions, L3/L4/L5 readback, immediate Destroy and
independent inventory. No new full cloud pass or current billing total is claimed;
historical dated successes remain separate evidence.

#### Renewed AWS application observation — 2026-10-19

The credential rejection above used the obsolete root bundle. The current
ignored authority authenticates AWS and Azure successfully; no user credential
expiration is inferred. Commits `343c9a9d` and `6aad6d3a` repair the normal
Configure transport and empty legacy-map package boundary respectively.

The actual Web UI started the AWS-only composed deployment. Deployment took
292.6154 seconds; 110 Terraform resource-creation completions are retained with
per-resource durations. The downloaded simulator's unmodified transmission code
sent real MQTT telemetry and received its correlated command after 9.63888
seconds. Verification took 15.297624 seconds. Exact value 42, source sequence
and event timestamp were checked in hot history, hourly aggregation, active
TwinMaker projection and both L5 HTML sections. No storage/projection fixture
was injected to make this application observation pass.

The browser also downloaded the simulator ZIP. Its executable/configuration/
identity/payload files match the executed Management download; only README text
differs. The existing UI infrastructure action reports 12/12 passed. The UI
data-flow action persists three passed phases, zero failures and zero skips
(3.4 seconds). Failed verification attempts remain retained separately.

Bounded repairs expose download metadata through existing CORS policy, recognize
the actual enabled shared S3 archive lifecycle rule, send canonical device/time
fields in UI verification and use the existing TwinMaker evidence-kind contract.
The L5 response was rendered unchanged on a local proof page; an actual in-app
popup was not observed and is not claimed. Archive-rule presence is not evidence
of a completed retention-tier transition. Neither billing totals nor statistical
latency guarantees are inferred from this single observation.

The exact simulator certificate/policy/thing were removed. Final independent
inventory covers 24 categories with **zero active resources and one inactive
IoT Command pending-deletion marker**. Cleanup is therefore not strict-zero.
A local Management auto-reload interrupted the first Destroy stream; that
operation is retained as failed, not overwritten. A TwinMaker pre-destroy SDK
pagination defect was corrected before regular Destroy retries (104.554918 s
and 42.942686 s). AWS Cloud Control still rejects deletion of the pending command
with AlreadyExists; one Terraform state entry remains and the application
correctly reports incomplete cleanup. No state entry was manually removed to
manufacture success. The interrupted stream also exposed a missing-ID detached
SSE control frame; automatic restart/reconnect recovery remains unqualified.

Next cleanup action: read-only confirmation that the marker has disappeared,
then the existing Destroy operation to reconcile its remaining state entry and
repeat independent inventory. Do not redeploy this namespace meanwhile.
Temporary supervised admission and the additional provider-auth mount were
removed after evidence capture; the timeout guard was stopped to avoid repeated
attempts while AWS deletion is pending.

Final offline gates: 814 Flutter tests, 717 Management tests, 2,214 Deployer
tests passed; one Deployer test intentionally skipped and one existing TLS
deprecation warning. Analysis/architecture checks and Web/macOS builds passed.
No paid cloud operation was triggered by those regression gates. Do not label
the whole renewed campaign complete: Azure composed, GCP Core and six directed
Core repetitions remain separate run scopes subject to fresh admission and
cumulative allowance.

##### AUDIT PASSED — bounded User logic restoration only

#### AWS cleanup reconciliation — 2026-10-20

The pending IoT Command marker has disappeared. The first ordinary Destroy
retry (29.518 s) still failed because the previously removed auxiliary Azure
authentication mount is needed by the shared Terraform root. Restoring that
existing opt-in mount, without changing credentials, rights or resource
placement, allowed the next ordinary Destroy to succeed in 32.293 s. Terraform
refreshed the absent command normally and persisted an empty state; no manual
state removal or lifecycle override was used. Management now reports
`destroyed`, successful Destroy and complete cleanup with zero residuals.
The subsequent independent AWS inventory reports zero in all 24 categories,
including inactive commands, TwinMaker and simulator identity. The temporary
authentication mount was removed again. Both attempts and the final inventory
are retained privately. This closes the renewed AWS cleanup finding, not the
remaining Azure/GCP/directed application campaign or detached SSE limitation.

#### Renewed provider-local GCP Core observation — 2026-10-20

The existing bounded Core runner passed the renewed GCP-local observation on
source revision `f5173e7b`: ten real MQTT messages were read back exactly through
the deployed L1–L3/Event path. Deployment took 726.180 s, verification 17.429 s,
observed delivery/readback 17.237 s, and ordinary Terraform Destroy 541.682 s.
The complete observation, including preparation/builds and cleanup, took
1,796.543 s; 236 Terraform resource lifecycle timing records are retained.
Independent inventory found zero active residuals across all checked categories,
but one log bucket remains `DELETE_REQUESTED`. Strict-zero cleanup therefore
remains unqualified; the original report correctly retains `green=false`.

Two earlier supervisor attempts stopped at plan admission, before allowance
reservation or cloud mutation (stale in-memory plan-count lookup and a read-only
atomic ledger replacement boundary). Their failures are retained separately.
The corrected supervisor compares the fresh native plan with the reviewed
resource-type counts and supports the existing atomic ledger writer. It does
not modify the application or relax functional/cleanup assertions.

This is RQ1 lifecycle/measurement and RQ2 Core functional evidence, with one RQ3
delivery observation, not a statistical latency claim or billed cost. It is not
a Management/UI-led full deployment, command-return test, storage-transition
test, or GCP L4/L5 qualification. Directed repetitions and the composed Azure
application observation remain separate and unfinished.

#### Renewed directed Core observations — 2026-10-20

The renewed AWS→Azure Core observation passed on `f5173e7b`: all ten distinct
test values were read back correctly after crossing the deployed provider
boundary. Terraform recorded 161 creation and 161 deletion completions.
Deployment took 422.390 s, verification 148.443 s, and ordinary Destroy
956.601 s; total supervised time was 1,767.472 s. Observed delivery/readback
was 148.176 s. The reader made 20 polls without transport timeouts; the ten
per-message persistence measurements are retained, rather than attributing all
waiting to an HTTP cold start.

Independent AWS, Azure and Entra inventories found zero active residuals.
One newly deleted AWS IoT Command remains an inactive pending-deletion marker,
so this report retains `green=false` despite successful verification and
Destroy. This marker belongs to the new directed run, not the previously closed
AWS application cleanup. A later inventory must qualify strict-zero cleanup;
the original observation is immutable. This is Core telemetry evidence only:
no directed command-return, L4/L5, storage-transition or complete UI pass is
inferred.

Azure→AWS then passed on `af17dcf7` (the application code is unchanged from
`f5173e7b`). All ten values matched, and both received/processed event streams
contained ten entries. Main Apply took 412.080 s, verification 32.236 s,
delivery/readback 28.269 s, and Destroy 232.055 s; total time was 881.984 s.
All 155 creations and 155 deletions have resource timing records. Independent
inventory reports zero across all 24 categories, including inactive commands
and directional trust objects: this observation is strictly green. No additional
application correction was needed.

AWS→GCP passed on `19a54ae2` with ten exact values, 559.767 s main Apply,
61.303 s verification (61.000 s delivery/readback), 447.716 s Destroy and
1,502.229 s total supervised time. All 151 creation and 151 deletion completions
have timing records. The original 37-category inventory found zero active
residuals and two inactive markers (AWS IoT Command and GCP Logging bucket).

A plan-to-inventory cross-check then identified an omitted independent check
for the run-owned GCP workload-identity pool in the AWS→GCP direction. The
already implemented reverse-direction check now lives in the shared inventory
and is reused by both directions; 50 targeted runner/runtime/directed tests
pass, including exact pool scope, unknown state and permission failure handling.
A supplementary read-only check, bound to the original plan's project and run
prefix, confirmed zero active pools and one additional `DELETED` pool marker.
The original report is preserved; no deploy or message replay was needed.
Strict-zero cleanup remains unqualified for this run.

Azure→GCP passed on `38730a79`: ten exact values, 836.227 s main Apply,
41.691 s verification (37.039 s delivery/readback), 468.661 s Destroy and
1,649.577 s total time. All 149 creations and 149 deletions retain timing
records. Independent inventory found zero active residuals, with one inactive
Logging bucket and one `DELETED` workload-identity pool; strict-zero cleanup
is therefore not claimed. No application correction or cloud retry was needed.
The first renewed GCP→AWS attempt reached ten exact AWS hot-storage values,
then failed the additional Kinesis received/processed-stream assertion after
19.693 s of verification. Its reader treated the first empty `GetRecords` page
as the end of the stream. A read-only cursor diagnostic subsequently found ten
correlated records in each stream, after four and one empty pages respectively.
AWS explicitly documents that empty pages can precede retained records and
that consumers must continue using `NextShardIterator` ([API reference](https://docs.aws.amazon.com/kinesis/latest/APIReference/API_GetRecords.html)).

The bounded research reader now advances that cursor, waits one second between
reads and stops after at most 20 reads per shard. Exact value and processed
quality assertions are unchanged; missing records still fail with safe count
and timing diagnostics. All 56 targeted runner/runtime/directed-reader tests
pass. This changes only evidence collection, not the deployed application.
The cursor diagnostic retained counts, not a fresh complete payload/quality
verification. The attempted complete corrected read then found the streams
already removed by ordinary Destroy. Therefore the original failed attempt
is retained and is not relabelled as a full functional pass; the bounded renewed
observation below supplies that verification. GCP→Azure subsequently passed
as recorded below.

That failed attempt (`1a9457bf`) was fully torn down: Kubernetes removal took
76.005 s and ordinary Destroy 568.447 s; independent inventory reports zero
active resources and one inactive `DELETED` federation pool. Main Apply was
483.673 s and Kubernetes Apply 106.015 s; total time was 1,568.380 s, with 358
resource timing records retained. The original sequence stopped on the failed
assertion as designed. Only after this cleanup and the reader regression gate
was a new bounded observation admitted under a fresh run namespace.

The GCP→AWS retry passed on `674a05ad`: ten exact hot-storage values and ten
received plus ten processed stream records, with unchanged payload/quality
assertions. Main Apply took 470.102 s, Kubernetes Apply 85.690 s, verification
29.650 s and delivery/readback 18.460 s. The bounded event-stream read took
0.713 s; the ten persistence samples span 14.719–15.827 s. Kubernetes removal
took 76.797 s and ordinary Destroy 537.452 s; total supervised time was
1,510.136 s, with all 179 creation and 179 deletion completions retained.
Independent inventory found zero active residuals and one inactive `DELETED`
federation pool. Functional verification and Destroy passed, but strict-zero
cleanup is not asserted. Both attempts remain part of the cost and operational
history; the successful retry does not erase the failed reader observation.

The final GCP→Azure observation passed on `f4b24b43`: ten exact values,
550.196 s main Apply, 95.824 s Kubernetes Apply, 185.447 s verification and
176.252 s delivery/readback. Its 22 readback polls had no transport timeouts;
172.910 s was spent waiting for the complete result. Kubernetes removal took
77.180 s and ordinary Destroy 967.514 s; total supervised time was 2,126.159 s.
All 183 creation and 183 deletion completions retain timing records.
Independent inventory found zero active resources, no Entra applications or
service principals, and one inactive `DELETED` GCP federation pool. Strict-zero
cleanup is not claimed while that marker remains.

This completes the seven renewed Core functional observations (GCP local and
six directed edges), with successful Destroy in each case. It does not complete
the Azure composed application observation below or turn research-runner results
into seven Management/UI-led full-profile passes. The historical AWS/Azure-local
Core observations retain their own dates and conditions.

The final read-only follow-up rechecked all eight deployed attempt namespaces
(seven successful observations plus the failed first GCP→AWS attempt), bound
to each original plan's scope. All inventories completed without errors and
found zero active residuals; only the documented inactive markers remain.
The consolidated measurements are in
[Core telemetry results](../research/evaluation/core-telemetry-results.md), and
the dated account-billing check is in
[application closeout results](../research/evaluation/application-closeout-results.md).

#### Renewed Azure application attempt — 2026-10-20

The actual UI started the Azure-only composed deployment after native plan
review. ACR published the storage-mover image; 89 resource creations completed
before Azure rejected the L4 human-reader assignment: the supplied principal
was a ServicePrincipal while the resource explicitly requires a User. This is
an input-selection failure, not functional evidence. The retry will reference
the existing subscription-owner User; no new identity or broader grant is needed.
The attempt, immutable image digest, build queue/runtime, per-resource creation
times and operation logs are retained privately. No simulator verification ran.

Ordinary Destroy then exposed an independent orchestration defect: a fresh
operation package regenerated an empty Azure storage-mover image variable,
which the provider rejects even when the failed apply created no job. The
bounded SDK fallback is retained as cleanup, not a successful Terraform Destroy.
The narrow correction supplies a schema-valid digest-shaped value only during
destroy when the variable is absent; it never publishes/pulls an image and is
not deployment or functional evidence. Existing image references and unrelated
profiles are preserved. Cleanup regression tests pass (25), with 84 adjacent
Terraform/image/runtime tests also passing. Live retries additionally exposed
`ResourceGroupBeingDeleted` conflicts and a fallback reference that did not
match the ACR variable format after the registry disappeared. The latter is
corrected in `921303eb`; the conflicts were allowed to finish, not suppressed.
The final ordinary Destroy succeeded with empty Terraform state and complete
cleanup. Independent resource-group, resource and scoped role-assignment
inventories are all zero. Failed cleanup attempts remain part of the evidence.

The second UI-led Azure attempt successfully applied Terraform, including the
corrected human-reader assignment. Its ACR build took 37.056 s after 0.445 s in
the queue. SDK postapply then failed before DTDL/model upload. A focused live
reproduction found that function `listkeys` returned a flat dictionary containing
the existing function-scoped default key, whereas the client only read a
`properties` envelope and attempted an unnecessary additional key creation
(HTTP 400). The lean correction accepts both response shapes and reuses a
function-scoped existing key for L3 and L5, never a host/master key. It no longer
creates credentials; initial lookup retries are bounded and permission errors
remain terminal. The targeted runtime/access/API gate passes 71 tests. Live key
lookup works, but a data read during concurrent teardown is not functional
evidence. This attempt remains failed. Ordinary Destroy subsequently completed
with 109 recorded resource deletions, empty state and complete provider cleanup;
the independent resource-group/resource/role-assignment inventory is also zero.
The real UI displays `DESTROYED` / `COMPLETE` and correctly retains no telemetry
success for this failed attempt. The expanded Terraform/runtime/access/API gate
passes 490 tests, including the native Terraform tests with their required
repository mount. A fresh composed observation is still required.

A subsequent SDK-boundary inspection found another concrete Azure mismatch:
postapply device registration still derived the historical Hub name and prefixed
device IDs, while the graph-selected Terraform Hub has its own suffix and the
canonical event/device contract uses the configured ID. The bounded correction
passes the existing ingestion output into SDK registration, requires its actual
Hub name/hostname and preserves canonical IDs for the active profile. Historical
defaults remain unchanged. Five focused tests cover missing-output rejection,
actual binding, existing/new devices and legacy behavior; the adjacent runtime
gate also passes (55 tests total). This is not yet a renewed live pass; an
already-running process is not restarted mid-apply to adopt the change.

The third UI-led attempt, started before that registration correction was loaded,
confirmed the mismatch live: Terraform applied successfully, the authenticated
L3 reader returned HTTP 200 with `raw-history-query.v1`, and one DTDL model was
present. SDK registration then timed out after 180 seconds looking for the
historical Hub name. No simulator/command/full functional pass is claimed.
The correction is committed in `4136e12e`; the expanded offline gate passes
495 tests, and 43 existing Core-runner/runtime/directed-path tests also pass.
Ordinary Destroy then succeeded with 109 recorded deletion completions and
complete cleanup; the independent resource-group/resource/role inventory is
zero. Deployment, per-resource and destroy timings remain attached to this
failed attempt rather than being replaced by a later successful observation.

The fourth bounded Azure attempt progressed through device registration but
hit a 30-second transport timeout on the first L5 request. Initial Azure L5
readiness now retries transient connection/timeouts and HTTP 502/503/504 at most
three times, with 30-second request timeouts and 3-second pauses. Authorization,
unexpected public access and invalid-content failures are not retried; ordinary
UI reads and AWS behavior remain single-attempt. The targeted access/API gate
passes 27 tests. This correction is not itself a successful functional result.
Three bounded live readiness attempts still timed out. ARM reports both L3 and
L5 registered, Running and Normal, with matching hostnames. The previous narrow
Azure L5 fixture has one always-ready HTTP instance, whereas normal composed L5
explicitly has none. This is a configuration difference to investigate, not
proof that warming fixes the composed path. The normal baseline remains
scale-to-zero by the subsequent scope decision; no composed Azure functional
success is claimed.

A read-only retry plan was rejected before mutation because Azure reported the
IoT Hub TLS floor as `1.2` while the omitted configuration value planned a Hub
replacement. Pinning the same TLS floor prevents that known drift without
weakening transport security. The original failed operation and rejected retry
plan are retained separately; no same-state retry was executed.
The combined offline Terraform/runtime/access/API gate passes 502 tests.
The subsequent complete safe Deployer suite (`tests/`, excluding `tests/e2e`)
passes 2,235 tests with one intentional skip and the existing no-network MQTT
TLS deprecation warning (115.62 s). This is regression evidence, not an additional
live cloud result.
The fourth attempt was destroyed successfully (109 recorded deletion
completions); independent resource-group, resource and scoped role inventories
are all zero. Its timing/image/diagnostic evidence is retained, and the temporary
auxiliary AWS credential mount used by the shared Terraform root was removed.

The fifth composed Azure attempt retained zero always-ready workers and failed
L5 readiness after **932.330 s**, with 109 creation-completion observations.
Phase-specific, secret-free transport logging distinguishes the first accepted
negative-auth check from the subsequent authenticated timeout. Supplementary
reads then returned valid empty L5 HTML intermittently (43.258, 15.889 and
10.029 s), but also generic Azure HTTP 503 responses after approximately 60 s;
unauthenticated requests were affected too. A separate authenticated L3 query
returned HTTP 200 in 4.720 s. These observations do not prove the root cause or
an operational full simulator/command/L4/L5 path.

A bounded diagnostic changed only L5's on-demand ceiling from one to two,
keeping zero always-ready workers. It did not reliably improve availability
and was **not adopted** as the production configuration. A sequence overlapping
that change is excluded from before/after comparison. Missing L5 host-log
routing was added to the existing diagnostic workspace; no workspace or warm
capacity was added. The access/API/diagnostic gate passes 33 tests and Terraform
validation succeeds. Local SDK import timing (0.191 s) does not justify a
speculative package rewrite or establish cloud cold-start performance.

Ordinary Destroy succeeded in **945.057 s**, with 109 deletion-completion
observations, empty Terraform state and complete persisted cleanup. Independent
resource-group/resource/scoped-role inventory is zero. The temporary diagnostic
ceiling and log attachment were removed with their resources. Original credentials
were unchanged; the auxiliary credential mount and its temporary copy were
removed. The UI initiated this attempt, but supplementary SSE capture owned its
completion; the original browser view required refresh. This is not an
uninterrupted UI lifecycle pass. A separate minimal authenticated HTTP host
comparison is the next bounded diagnostic, not a substitute for application E2E.

The completed host diagnostics and their per-client outcomes are recorded in
the [application closeout results](../research/evaluation/application-closeout-results.md).
A minimal function with no application logic reproduced intermittent timeouts;
host-native `curl` and Docker `urllib` also failed individual requests. The
without-bundle variant did not reach its HTTP probes because the function key
was not ready. All three diagnostic deployments were destroyed with empty state
and independently absent resource groups. Neither a speculative application
rewrite nor a blanket timeout/warm-worker change is justified by these results.
The separately approved North Europe comparison was completed on October 21
without changing the application baseline. It used identical package contents,
zero always-ready instances and the same three clients. Only two of six
authenticated requests returned the exact expected response; the other four
timed out at approximately 30 s. Unauthenticated access correctly returned 401.
Apply took 190.707 s and Destroy 113.998 s, with eight creation and eight deletion
timing observations, empty Terraform state and independently absent resource
group. The temporary key copy was removed. This diagnostic failed; a region
change is not a demonstrated fix. The composed Azure E2E remains open, and no
additional full deployment or permanent region change followed this experiment.
The October 22 long-timeout diagnostic below identifies a prematurely short
client cutoff while retaining the historical 503 cause as unresolved.

The approved long-timeout diagnostic observed one West Europe minimal HTTP
function for ten minutes after package publication, with zero always-ready
capacity and at most 180 s per request (the final request was capped by the
remaining observation window). All six sequential, uniquely correlated requests
passed. Client durations were 1.198, 36.240, 10.562, 0.814, 0.437 and 0.613 s;
anonymous access correctly returned 401. Application Insights correlates all six
to successful handler invocations on the same role instance. The 36 s client's
DNS/connect/TLS completed within 0.224 s; the handler trace appears approximately
36 s after client start, and its server request duration was only 9.406 ms.
This establishes that the former 30 s client timeout can reject a valid response
and places this observed delay before handler execution. It does not identify
the exact Azure-internal routing/scheduling component, establish a cold start,
or explain the historical 503 responses, which did not recur in this sample.

Commit `f84a043c` increases only initial Azure L5 readiness HTTP timeouts to
180 s per request, retaining the existing three-attempt bound and strict
authentication/content checks. Ordinary UI requests and AWS remain at 30 s.
The focused access/API suite passes 29 tests. This minimal-host pass and offline
correction do not close the composed Azure UI/simulator/command/L4/L5 E2E gap.
Apply took 203.120 s and Destroy 521.916 s, with eleven creation and eleven
deletion completion timings. During Destroy, independent inventory found one
additional Insights action group, created outside the Terraform graph in this
fresh diagnostic resource group. Its exact scoped deletion returned HTTP 200;
the ongoing Terraform Destroy then completed. State is empty and independent
resource-group lookup returns 404. The temporary function-key copy was removed.
The extended Destroy time includes this supplementary cleanup, not only managed
resource deletion. Detailed host/client evidence remains private.

Two subsequent composed attempts are recorded in the
[application closeout results](../research/evaluation/application-closeout-results.md#composed-azure-retry-after-the-http-diagnostic--2026-10-22).
The sixth failed during unidentified SDK postapply (887.430 s); its Destroy
completed in 988.226 s. The seventh passed normal UI deployment and all four
SDK readiness phases in 674.338 s, retaining zero always-ready capacity.
Its external functional runner failed at startup, then an operator retry
overlapped the already-started Destroy. That simulator/command observation is
excluded, not a valid application failure or success. The corrected research
invocation passes a credential-free dependency check and watches lifecycle
state during verification. The seventh Destroy completed in 981.157 s; both
attempts have empty state and independent zero RG/resource/scoped-role counts.
The remaining closeout item is one fresh, non-overlapping Azure
UI/simulator/command/L3/Event-to-L4/L5 observation. No architecture rewrite or
additional warm capacity is required by the evidence captured here.

The next fresh attempt (`3acbadfe`) passed infrastructure creation and SDK
L3/Twin-seed/IoT checks but failed authenticated L5 readiness in 819.385 s.
Its final `_L5NotReady` identifies a transient HTTP 502/503/504 response; the
exact status and whether it came from hosting or L5's own failed L3 read were
not retained. No simulator/command test started. Ordinary Destroy completed
in 1,009.468 s, with empty state and independent zero run-owned inventories.
The [closeout record](../research/evaluation/application-closeout-results.md#fresh-bounded-azure-application-observation--2026-10-22)
retains phase/image/resource timings and this limitation. Narrow, offline-tested
diagnostics now retain exact HTTP phase/status and distinguish the fixed L5
data-error body; no retry, timeout or warm-worker change was adopted.
The full safe Deployer gate passes 2,254 tests with one intentional skip after
refreshing the canonical source pins. The composed Azure E2E remains open;
isolate L3-to-L5 with the new diagnostics before another full live attempt.

**Diagnostic preparation — 2026-10-23:** reuse the existing fixed L3/L5 research
cut rather than rebuilding the complete Twin. The Azure fixture now has zero
always-ready instances, matching the normal profile's capacity policy; the
historical October 5 fixture had one always-ready instance per app and its pass
is not relabeled. Plan admission rejects warm, unknown or increased capacity.
Per-request status, duration and a fixed response-origin classification are
retained privately. Direct raw/hourly reader comparisons follow L5 observation,
never pre-warm it or substitute for a graphical pass. Azure authenticated reads
allow 180 s inside the unchanged 30-minute functional deadline; the application
handler's separate ten-second upstream bound is unchanged pending evidence.
Destroy retains its separate 30-minute reserve, recursive managed-state check
and independent resource-group absence check. Preparation is not live evidence;
the exact saved plan and external allowance must clear before execution.
The focused runner/renderer/L4 regression group passes 72 offline tests.

**Diagnostic finding — 2026-10-23:** the isolated zero-always-ready cut
reproduced nine fixed L5 data-error responses. Direct L3 data can be correct
yet take longer than the handler's ten-second bound; the unchanged handler
reproduced an actual reader `TimeoutError` in a host-side client. A controlled
60-second/one-retry comparison returned both exact data panels, but is not a
cloud L5 or composed E2E pass. The narrow offline Azure correction retains
authentication/data gates, uses a shared reader budget and does not add warm
capacity. The research runner now stops Azure polling after three attempts so
reader diagnostics fit its deadline. The qualified observation and steering
deviation are retained in the
[closeout results](../research/evaluation/application-closeout-results.md#isolated-zero-always-ready-l3l5-diagnosis--2026-10-23).
A fresh ordinary Azure application run must still validate the deployed fix;
no success is backfilled into the failed baseline.
The offline fix is committed as `9c9cc74e`; the safe Deployer gate passes 2,267
tests with one intentional skip. Destroy completed in 684.716 s; empty managed
state and independent exact-scope ARM resource-group/resource/role counts are
all zero. The supplemental inventory excludes three inherited ancestor-scope
roles without modifying them. No live diagnostic resources remain.

**Normal application retry with the fix — 2026-10-23:** the fresh Azure-local
candidate at `c8835c36` packaged `9c9cc74e` correctly and ran the normal UI-led
111-entry plan without always-ready instances. Initial L3/Twin/IoT readiness
passed, but three authenticated L5 requests returned unclassified HTTP 503
after approximately sixty seconds, not the application's fixed data-error body.
The composed verifier was not started; Azure full application E2E remains open.
Deployment failed after 896.535648 s; immediate ordinary Destroy succeeded in
978.274303 s. Empty managed state, provider inventory and a separate exact-scope
ARM null inventory are confirmed; the UI shows cleanup COMPLETE. The
[application record](../research/evaluation/application-closeout-results.md#ordinary-azure-application-with-bounded-l5-reader-fix--2026-10-23)
retains timings and diagnostic limits. Identify the unclassified L5 hosting/
request boundary before another full-stack retry; do not manufacture a pass by
relaxing authentication/content gates or adding warm capacity.

Date: 2026-10-18. Commit: `cc3427b4`. Branch:
`codex/phase-8-deployer-graph-resolver`. Approved plan: the preceding bounded
restoration plan retained in `cb519309` in this document.

Evidence paths below are relative to `twin2multicloud_flutter/`:
`panel` = `lib/features/configuration_workspace/presentation/deployment/user_function_extension_panel.dart`;
`panel_test` = `test/features/configuration_workspace/user_function_extension_panel_test.dart`.

| Phase | Verified evidence |
|---|---|
| 1 Plan integrity | Twelve-section plan in `cb519309`; explicit user approval before implementation. |
| 2 Structure | `cc3427b4` changes exactly three existing production files and two existing test files. |
| 3 Widget tree | `panel:98`: existing form reused, only key and values changed; constructors unchanged. |
| 4 Visual/layout | `panel:54`: existing semantics/layout/theme retained; commit diff adds no visual tokens. |
| 5 Responsive | `panel:66` retains breakpoint; `panel_test:32` covers async restoration at 420/900 px. |
| 6 BLoC | `lib/bloc/wizard/wizard_state.dart:407` and `lib/bloc/wizard/handlers/wizard_user_function_extension_handlers.dart:78`: draft-first values and event-owned changes. |
| 7 Interaction | `panel_test:83`: edits retain focus and override saved values; real replacement validated/saved. |
| 8 Accessibility | `panel_test:131`: semantic status and keyboard traversal; labels/contrast unchanged. |
| 9 Integration | Existing Management DTOs only; real API/native roundtrip and 18 integration checks passed. |
| 10 Quality | Analyze, 808 tests, architecture check and both release builds passed; known dependency build warning retained. |
| 11 Completeness | All bounded-plan items verified; no source bytes, validation results or new features fabricated. |

**APPROVED FOR HANDOFF** for this repair, not for the still-blocked cloud campaign.

### Primary-checkout consolidation — 2026-10-14

Work continues only in the original `master-thesis` checkout on
`codex/phase-8-deployer-graph-resolver`. No additional worktrees remain
registered. Do not create new worktrees without an explicit user request.

- `71df5300` preserves the 37 original tracked documentation edits.
- `5f2edcfa` joins that history with the verified Six-layer/frontend history
  through `ef76a79b`. Runtime code, contracts and tests are unchanged from that
  verified revision; current documentation retains applicable quickstart,
  authoring and navigation improvements instead of restoring superseded
  default-off/Grafana/profile-selection descriptions.
- `3a063939` also retains the older checkout's four tracked Flutter tooling
  edits as snapshot `17dadce7`. The current Swift-package support and pinned
  test dependencies already include their functional changes.
- The other retired branch heads are ancestors of the consolidated branch.
  Former directory contents and registration metadata were moved into an
  owner-only local recovery directory, not discarded. Active evaluation
  evidence was moved into the primary checkout; conflicting pre-existing
  evidence versions remain in the recovery copy. Credentials and encryption
  keys were not overwritten. Three original untracked user documents remain
  byte-identical and uncommitted.
- Primary-checkout verification: **801 Flutter tests passed**, analyze clean,
  architecture gate and shell syntax check passed, Web/macOS demo release
  builds succeeded, and MkDocs strict build passed with networking disabled.
  The three idle closeout containers using retired bind paths were stopped;
  their volumes were retained and unrelated containers left running.

This consolidation changes no cloud evidence or scientific claim. No provider
mutation, E2E run, push or master update occurred. Start the app from the
original repository root with `./thesis.sh demo --setup` (offline) or the
explicitly selected integrated local mode. The recovery copy is not a second
development workspace.

### Frontend architecture alignment — completed, 2026-10-10

The user requested planning followed by implementation of the necessary
screen-by-screen corrections. This is a bounded follow-up to Phase 6, not a
redesign, new feature set or new live evaluation. Every step below is required.
The user-authorized sequence includes implementation after this plan's review.

#### 0. Git and delivery

Continue `codex/gcp-l4-iap-bootstrap` from `4b518bf5`; no master edits, merge or
push. Preserve unrelated work. Commit the plan, architecture/cost correction,
lifecycle correction, and remaining screen/verification corrections separately.

#### 1. Summary and boundaries

Use the existing resolved Six-layer graph and monetary evidence in the active
optimizer and lifecycle screens. Align mutation eligibility with Management's
immutable deployed-Twin rule. Correct misleading configuration/access/test
wording. Keep the shell, routes, four phases, existing controls and API surface.
Do not add billing, scope selectors, automatic cloud checks or new dashboards.

#### 2. Layout (Web and desktop unchanged)

```text
Optimizer result                 Twin lifecycle
+----------------------------+   +--------------------------------+
| Monthly estimate / currency|   | State / next safe action       |
| Selection / error / retry  |   | Existing operation controls    |
| Resolved graph + Eventing  |   | Verification / L4 / L5         |
| Components / cost evidence|   | Destroy / recorded cleanup     |
| Existing technical details|   | Configuration: same graph/cost |
+----------------------------+   +--------------------------------+
Scenario / Prepare / Cloud access: same forms and task navigation;
only inaccurate text, required-field presentation and legacy diagrams change.
```

#### 3. Widget tree

```text
[MODIFY] Step2Optimizer / _buildResultsSection
  [REUSE] DeploymentSelectionStatus
  [REUSE] ResolvedArchitectureReview
    [REUSE] LogicalResolvedFlow / component rows / cost and evidence
[MODIFY] TwinOverviewConfigurationReview
  [REUSE] LogicalResolvedFlow (native result; legacy path is historical only)
  [MODIFY] OptimizationSummary (currency from immutable result)
[MODIFY] TwinLifecycleSummary / existing controls
  [MODIFY] lifecycle permission projection (history-aware)
[MODIFY] existing configuration / verification / cleanup text
  [REUSE] existing dialogs, layer-access cards, file controls and status rows
```

#### 4. Component contracts

No new network DTO, route, dependency or generic UI framework. Native result
screens consume existing `ResolvedTwinArchitectureRead` / `ResolvedTwinArchitecture`
values. The overview view model carries the existing resolved architecture and
currency; historical results keep their read-only fallback without implying
current completeness. Use the existing result review for selected components,
Eventing, connections and server-calculated costs instead of pseudo comparisons.
Lifecycle eligibility takes both current state and `deployedAt`; destroyed
Twins cannot directly Deploy, and previously deployed definitions cannot Edit
or Deploy again. Existing Duplicate remains the new-experiment route. Match
the backend's separate Delete rule, without inventing stricter backend policy.

#### 5. Responsive behavior

Retain `logicalProfileFlowCompactBreakpoint`,
`resolvedDeploymentWideBreakpoint`, `twinOverviewCompactBreakpoint` and their
existing graph/list and stacked layouts. Verify compact 640 px, wide 1280 px,
and increased text scale. No new fixed dimensions.

#### 6. State ownership

`WizardBloc` retains result loading/retry/selection. `TwinOverviewBloc` retains
commands, history-aware permissions, operation replay and access launch.
Read-only widgets receive existing immutable data; they never recalculate costs
or invent graph edges. No auto-Deploy, auto-verification or auto-Cleanup.

#### 7. Tokens

Reuse `AppSpacing`, `AppColors`, `ThemeData` and Material icons. Group new copy
with the relevant existing screen strings where shared. No new visual tokens.

#### 8. Interactions and states

Keep existing click, keyboard, hover and focus behavior; add no animations.
Retain loading, empty, incompatible and failed result states and retry actions.
Keep the reserved isolated L5 popup and its failure path unless a local browser
check proves a defect requiring a minimal correction. No public proxy or login
replacement. Explicitly state that a returned snapshot is not persisted proof.

#### 9. Accessibility

Retain ordered focus traversal, button labels, keyboard activation and status
semantics. Status meaning must be textual, not color-only. Existing responsive
and high-text-scale tests remain regression gates.

#### 10. Management integration

Reuse existing selected-run/resolved-architecture reads and
`GET /twins/{id}/deployment-access/visualization`. Deploy/Destroy, verification,
simulator download, CloudConnection import and SSE commands remain unchanged.
Current cleanup v1 does not classify provider tombstones or private research
inventories: disclose that boundary instead of adding unsupported UI fields.
No backend changes or mutations are needed for this alignment.

#### 11. Required tests and review

Before editing code, analyze and Web build must pass. Per slice run analysis and
focused unit/widget tests; finish with the full suite, architecture checker,
Web and macOS release builds. Use existing fixtures only for client tests and
label demo/browser checks as offline, never live provider evidence. Do not run
integration tests that can Deploy; no API transport change needs a new cloud run.

Architecture/cost tests: native USD/EUR, Eventing and actual edges, missing/error
and incompatible result, legacy fallback, empty edges, exclusions without fake
prices, compact width and large text. Lifecycle tests: configured and failed
first attempt; previously deployed error/destroyed/configured; transient, draft,
unknown state, safe Delete and stale responses. Copy/access tests: scope and
cost wording, popup success/failure, duplicate/stale action and empty snapshot.
For copy-only controls the existing interaction tests plus exact-copy assertions
are sufficient; a fresh nine-case matrix per label would not add evidence.

Architect/builder review covers all plan-review criteria: API types and reusable
components are present, changes are scoped, no new providers/features are exposed,
and existing research planning hierarchy replaces superseded pillar roadmaps.

#### 12. Definition of done

- Native result and overview show the server-owned graph including Eventing,
  correct currency, and no fabricated linear topology/provider comparison.
- Actions match current lifecycle/history and remain explicitly confirmed.
- Configuration, L4/L5, verification and cleanup copy state actual scope/limits.
- Cloud access, inventory, import/export and reconnect regressions stay green.
- Required analysis/tests/builds pass; browser observations and any unavailable
  checks are reported honestly. Update current architecture/decision log and
  retain clean intermediate commits. No cloud resources or private data added.

#### Completion and scoped self-audit — 2026-10-10

**APPROVED FOR HANDOFF within the client-only scope above.** Plan commit
`884996fa`; implementation slices `b404dc29` (graph/cost), `a75b5d8f`
(history-aware lifecycle), `45ae8beb` (configuration/access/verification).
Branch: `codex/gcp-l4-iap-bootstrap`. No backend, Terraform, API schema,
dependency, credential or cloud-resource changes. No push or merge.

| Audit phase | Verified evidence and bounded result |
|---|---|
| 1. Plan integrity | Sections 0–12 above and architect/builder plan review; user authorized plan followed by implementation. |
| 2. Structure | Changed-file review: existing Flutter owners, tests and current documentation only; no new route or feature. |
| 3. Widget tree | `twin2multicloud_flutter/lib/screens/wizard/step2_optimizer.dart:292` reuses the resolved review; overview reuses `LogicalResolvedFlow`. |
| 4. Layout/tokens | Existing four surfaces and tokens preserved; added confirmation content scrolls. Local inventory, Scenario and Cloud access rendered without visible clipping. |
| 5. Responsive | Native result tests at 640/1280 px; existing graph, access, cleanup and overview breakpoint/text-scale regressions pass. |
| 6. State | `twin2multicloud_flutter/lib/models/twin.dart:83` and history-aware BLoC/Wizard tests match Management immutability; no new state owner. |
| 7. Interaction | Existing command, replay, stale/duplicate response, confirmation, retry and file/import tests pass; no new animation. |
| 8. Accessibility | Existing theme/semantic controls retained; keyboard dialog/focus and large-text tests pass. No independent assistive-device certification is claimed. |
| 9. Integration | Architecture gate passes; Management-only transport and API shapes unchanged. Confirmation uses available connection names, not unavailable account-scope IDs. |
| 10. Quality | Analyze: zero issues. Full suite: **801 passed**. Web and macOS release builds succeeded with secret-free demo configuration. |
| 11. Completeness | Every scoped DoD item addressed; current architecture/README/decision log updated, historical fallbacks labeled, evidence limitations retained. |

Test evidence is reproducible from committed tests, notably
`twin2multicloud_flutter/test/screens/six_layer_result_alignment_test.dart:1`,
the model/lifecycle/Wizard suites and
`twin2multicloud_flutter/test/widgets/twin_overview/twin_overview_operation_dialogs_test.dart:1`.
Native USD/EUR rendering and overview graph/currency are asserted; test fixtures
are not new financial or cloud measurements. The macOS build emitted an upstream
`objective_c` framework-name warning but packaged successfully.

Local browser check used only the offline Showcase adapter. Inventory navigation,
Scenario wording, lifecycle scope text and Cloud access manual/import controls
were inspected; no browser console errors were observed. Showcase's historical
allocation correctly carries its historical-only label; the native graph is
covered by widget fixtures. Clicking L5 did not expose a separate popup in the
In-App Browser's tab inventory, and Chrome automation was unavailable. Therefore
popup rendering remains **not visually proven by this check**; success/failure,
empty response and stale/duplicate handling remain covered by existing tests.
No launcher rewrite or new live run was justified. The test server/tab were
closed; the user's Azure tab was left untouched.

**Completion checkpoint — 2026-10-09:**

1. Normal AWS/Azure minimal L5 integration is implemented and offline-verified.
2. One AWS application deployment (`cd4e7b39`) passed the real downloaded
   simulator/command, exact L3 raw/hourly, Event→L4 and L5 content assertions.
   Reconnect retained one operation. UI access fetched HTTP 200; its separate
   blob popup was not exposed to browser automation, so the unchanged returned
   HTML was rendered independently. The [application record](../research/evaluation/application-closeout-results.md)
   retains that limit, five earlier failed Deploy attempts and all timings.
   Journaled simulator identity cleanup preceded normal Destroy. Its first
   strict cleanup failed after fallback; a second normal Destroy succeeded.
   Final independent checks found zero active resources in the successful
   namespace (24 categories, including certificate) and original namespace
   (23 categories). Each still has one inactive IoT deletion marker; the old
   failed namespace also retains its tombstone-related Terraform entry. This
   is zero-active-resource cleanup, not a tombstone-free global all-clear.
3. [Frozen cost comparisons](../research/evaluation/poc-cost-model-results.md)
   reproduce 24 placement/scale records (22 priced, two excluded). RQ conclusions
   distinguish modeled allocation, real functional evidence and delayed bills.
   AWS/Azure month-to-date totals were read; current GCP reconciliation and
   per-run billing attribution remain unavailable, not assumed zero.
4. Results, architecture, discussion and conclusion are updated without changing
   RQs. Strict docs and the multi-file thesis build pass; changed result pages
   are visually inspected. Intermediate commits retain implementation defects
   and corrections. No product expansion or automatic nine-case rerun follows.

The eight-case JSON remains the frozen **planning input**, not an execution
ledger. The result records distinguish this single application observation from
the unexecuted complete-profile permutations. Directed commands, cross-cloud
L4, tier transitions, universal popup behavior and billing attribution remain
disclosed limitations; no unsupported thesis claim depends on their completion.

Historical checkpoint (reconciled 2026-10-06, observations through 2026-10-05): all three local and six directed Core telemetry
cases passed their ten-message assertion. The [compact Core results](../research/evaluation/core-telemetry-results.md)
consolidate successful phase timings, measurement gaps, dated zero-active-resource
inventories and inactive provider deletion markers. Actual billed attribution
remains pending. These are not complete-profile E2E passes. The separately
approved [bounded AWS/Azure L4 checks](2026-10-04_poc_l4_evaluation.md) now also
passed live: real service/model creation, local-adapter state update/replay,
authenticated readback, Destroy and independent zero-active-resource inventory.
The deployed AWS and Azure Event-to-L4 edges also passed, including Destroy and independent
zero inventory. The real simulator/command roundtrip and exact authenticated L3
readback now passed on all three local providers. Destroy and independent zero
active inventory passed. A later read-only reconciliation found zero AWS command
deletion markers across all five attempts; GCP's inactive Logging deletion markers
remain a dated open observation. Azure passed strict zero inventory.
The [minimal AWS/Azure graphical L5 checks](2026-10-05_minimal_l5_evidence.md)
also passed: actual stored fixtures, authenticated L3 reads, two rendered curves,
unauthenticated-access rejection, Destroy and independent null inventory.
Those fixed Terraform research cuts do not yet integrate L5 into the normal
Management/Deployer graph or establish simulator-to-L5 delivery. No directed
command or complete-profile result is inferred from these local checks.
No Core reruns or new dashboard platform are
implied. The [integration close-out](2026-10-04_poc_integration_closeout.md)
records successful and failed attempts, actual coverage, lifecycle measurements
and remaining gates. The dated checkpoints below remain historical observations,
not current coverage counts.

Historical supervised Core checkpoint (2026-09-19): AWS, Azure and GCP have passed the real
ten-message provider-local L1–L3/Event-Layer telemetry path. AWS/Azure independent
inventories are empty. GCP Destroy succeeded with zero active residuals; its
provider-managed pending Logging-bucket deletion remains explicitly open.
Azure uses the documented warm HTTP integration condition. Per-run outcomes,
lifecycle measurements, failed
attempts and the older AWS per-message-latency evidence gap are recorded in the
[Core evaluation plan](2026-09-16_poc_core_evaluation.md). This checkpoint does
not establish command roundtrip, storage-tier transitions, directed Core cases,
L4/L5 or a complete-profile deployment, and does not authorize those runs.

Historical first separately authorized directed Core slice (Azure to AWS, 2026-09-19):
passed with all ten messages at authenticated AWS readback and ten matching
received/processed events. The corrected source Event Hubs receiver permission
is live-validated. Destroy succeeded with zero independent AWS/Azure/active-Entra
residuals, including the temporary OIDC provider. Phase/resource timings and ten
message-latency samples are retained. The other five directed Core cases remain
unrun; no command-roundtrip or L4/L5 result is implied. See the Core evaluation
plan for successful and failed-attempt measurements and their limitations.

Historical scope revision (2026-09-16): the [bounded separation plan](2026-09-16_poc_l3_read_access_separation.md)
assigns authenticated history readers, lifecycle and charges to L3. L5 is an
independent consumer, with graphical implementation still pending. No remote
L5-to-L3 authentication adapter is claimed. GCP L4/L5 are excluded without
replacement infrastructure; GCP L1–L3/Eventing remain in scope. The active
matrix now has two complete local baselines and six directed cases, not a
complete GCP-local run. A separate [fixed Core evaluation scope](2026-09-16_poc_core_evaluation.md)
now omits L4/L5 at infrastructure and runtime level and prepares nine Small
research input sets offline. Provider-local Core execution is now supervised
under the checkpoint above; directed cases still require their own live-plan
admission. This does not make a complete-profile Management deployment ready.
The dated checkpoints below are historical and do not clear the new graph's
implementation gate or authorize reusing old candidate/budget/image approvals.

Historical L5 exception (2026-09-07; experiment superseded by the approved October 5 minimal L5 cut): the
[minimal visualization feasibility review](../research/evaluation/l5-visualization-feasibility.md)
is complete as a pre-implementation cost/integration check, not as live
readiness. AWS Managed Grafana restoration violates the unchanged technical
caps without verified credits. The current graph remains JSON-only; functional
visualization equivalence, a final dashboard-inclusive budget and implementation
are unresolved. Do not use the historical phase checkpoints below as approval
to bypass this blocker.

| Phase | Status on 2026-09-01 | Evidence boundary |
|---|---|---|
| 0–2 | Implemented offline | standalone contracts, cost-only path, graph-derived deployment evidence |
| 3 | Implemented offline | connection selection, graph-bound preflight, confirmed preparation, manual acknowledgement, and retry-safe repair |
| 4–5 | Implemented offline | bounded Twin interchange, durable operations, access and verification contracts |
| 6 | Implemented offline | product surfaces removed; bounded readiness and repair presentation connected to the existing overview |
| 7 | Implemented and container-verified | the 14-stage credential-free deployment-contract gate, repository hygiene, strict documentation build, and LaTeX build pass from a clean commit |
| 8 | Account and read-only provider checks are complete for AWS, Azure and GCP; the one-administrator Azure contract is live-revalidated; offline candidates, budgets, runtime images, federation plans, the GCP L4 bootstrap decision, and all six directed federation probes are complete | real principals, scopes, permissions, Regions, provider APIs, quota/capacity inventories, and AWS/Azure L4/L5 prerequisites were checked without Apply; the Azure administrator passes Owner and Microsoft Graph authority checks; GCP capacity is sufficient and its no-organization L4 path has an approved but unexecuted manual IAP/OAuth bootstrap; the active L5 is an authenticated bounded JSON readback with no dashboard minimum; six static images and the scenario-bound GCP processor image build locally, while GCP publication uses at most four bounded `e2-standard-2` builds and remains unexecuted |
| 9 | Pending supervision | nine cost-controlled Small deployments |
| 10 | Offline preparation complete; results pending live evidence | chapter structure, RQ framing, limitations, and repository cleanup aligned; empirical answers remain pending |

No row in this table upgrades offline fixtures or mocks to live-cloud evidence.

## Completion plan — 2026-10-06

This is the proposed implementation and evaluation sequence for the four
remaining points. This planning change performs no cloud action and does not
mark the broader complete-profile matrix later in this document as executed.
The existing separate live observations remain valid within their recorded
revision, placement and workload. RQ1–RQ3 and the historical FiveLayer reference
remain unchanged; GCP L4/L5 stay excluded.

### 1. Integrate the proven minimal L5 into the regular workflow

First align the active status and acceptance wording in this plan, the live
protocol and scenario matrix with the agreed split evaluation. Preserve the
original evidence and distinguish implemented, live-verified and excluded scope.
Retain one active completion checklist here.

Reuse the existing renderer and AWS/Azure handlers from the successful L5 cut.
Move their small resource definitions into the ordinary graph-selected Terraform
path and existing package builders. Readers, storage lifecycle and read charges
stay in L3; L5 owns its consumer, hosting and invocation permissions. Admit only
the implemented provider-local AWS/Azure L3-to-L5 combinations.

Update the authoritative component/service mapping and cost terms to match the
actual Lambda/Functions consumer, including any explicitly selected Azure warm
capacity. Regenerate dependent contracts through the existing process. A cost
estimate must describe the deployed mapping; the old dashboard-service pricing
cannot label the new consumer.

Wire real L5 outputs, graphical runtime verification and access handoff through
the existing Deployer and Management services. Verify how the authenticated user
opens the result: an unsigned AWS IAM URL alone is insufficient. Reuse the
existing owner-scoped Management access path; if an adapter is necessary, limit
it to the fixed L5 HTML response. Keep credentials server-side. Flutter continues
to call Management only and uses the existing result/access surface.

Relevant implementation points include the optimizer's
`backend/deployment_specification/six_layer_builder.py`, canonical component
definitions, `3-cloud-deployer/src/terraform/{aws,azure}_six_layer.tf`, provider
verification and `src/deployment_access/{runtime_evidence,projector}.py`.
Replace `gate.implementation.l5-visualization-pending` only for supported,
fully wired combinations; retain rejection of unsupported combinations and
L3 JSON falsely labelled as graphical evidence.

**Done when:** focused contract/cost/graph/access tests and native Terraform
plans pass for both AWS and Azure; unauthorized and wrong-owner access fail;
L5 adds no resources to the existing Core-only cut; generated contracts agree;
the ordinary deployment path emits a usable graphical access result. Commit
this implementation before the representative live run.

#### Fixed HTML access implementation detail (2026-10-08)

This is the bounded adapter already included in the approved completion scope;
all items below are required. No new screen or dashboard administration is added.

0. **Git:** continue `codex/gcp-l4-iap-bootstrap`, base `07bed2a5`; no push or merge.
1. **Purpose:** make the existing L5 action usable without exposing provider
   credentials. The result is a static, newly fetched HTML/SVG snapshot, not an
   auto-refreshing dashboard or provider SSO session.
2. **Layout:** preserve the existing Desktop/Web layout and compact boundary:

   ```text
   Verify and access
   + L4 semantic state +  + L5 raw and hourly history +
   | existing Open    |  | existing Open -> snapshot |
   +------------------+  +---------------------------+
   Compact (< AppSpacing.twinOverviewCompactBreakpoint): same cards stacked.
   ```
3. **Tree:** `[REUSE] TwinOverviewView -> TwinOverviewContent -> LayerAccessPanel
   -> LayerAccessCard -> Open`. Only the existing L5 action dispatch changes;
   no constructor, layout or route addition is required.
4. **Components:** add `ManagementApi.getVisualization(twinId): Future<String>`
   and `ExternalAuthLaunchHandle.renderHtml(html): Future<bool>`. Reserve the
   existing external window at the user gesture, then pass its service handle
   to a `TwinOverviewOpenVisualization` event. No widget performs HTTP.
5. **Responsive behavior:** retain current card widths, stacking, wrapping and
   high-text-scale behavior on all supported targets.
6. **State:** `TwinOverviewBloc` owns the request, duplicate suppression, existing
   loading/error banner and stale-Twin rejection. It closes a reserved window on
   failure/cancellation; successful HTML is not retained in application state.
7. **Tokens:** reuse existing spacing, theme, Material icons and focus styles;
   no new visual tokens or dependencies.
8. **Interaction:** L4 keeps its existing external URL action. L5 obtains one
   bounded HTML response through Management. Web opens a blob in the reserved
   window; Desktop opens a temporary self-contained HTML file. Cleanup releases
   these local artifacts after opening. No extra animation or automatic polling.
9. **Accessibility:** preserve card semantics, ordered keyboard traversal and
   Enter activation; failures use the existing dismissible message banner.
10. **Boundary:** `GET /twins/{id}/deployment-access/visualization`, bearer/owner/
    deployed-state checks, returns at most 1 MiB `text/html`, no-store, restrictive
    CSP. Management stages the existing one-request credential package; Deployer
    reads only its own persisted L5 URL, signs server-side, rejects redirects
    and non-HTML responses. Neither API accepts an arbitrary destination URL.
11. **Tests:** AWS/Azure success; wrong owner, unauthenticated, non-deployed and
    upstream failure; empty panels, oversized response, malformed HTML, duplicate
    clicks, stale Twin/Destroy and blocked popup. Existing unit/widget tests
    cover unchanged layout; the representative real Management run covers the
    integrated action and reconnect. Run analysis, focused/full Flutter tests,
    Web/macOS builds and the architecture checker; no mock counts as live proof.
12. **Done:** all above checks pass, server-side credentials remain private,
    data readiness stays pending until separately verified, current architecture
    and handbook reflect snapshots, and no unrelated screen changes are present.

Architect/builder review: this reuses the existing action and browser adapter;
the only new API returns fixed HTML. Existing loading/failure/lifecycle handling
is retained. Provider login, arbitrary proxying and embedded dashboard state are
outside the approved scope.

**Offline implementation checkpoint (2026-10-08):** the normal AWS/Azure L5
resources, cost mapping and fixed owner-scoped HTML adapter are implemented.
Verification: Optimizer 470 passed / 5 skipped; Deployer 2106 passed / 63 skipped;
Management 695 passed; Flutter 778 passed plus four new transport assertions;
script regressions 373 passed plus 37 subtests. Subsequent package/accessor
regressions passed 101 tests. Flutter analysis, Web/macOS builds, native mock
plans and generated-contract checks passed. These checks are not live evidence.

The first read-only native AWS application plan exposed an additional integration
dependency: the shared Terraform root initializes AzureRM/AzAPI even for an
AWS-only selection. Its zero-UUID fallback cannot authenticate. The historical
Core runner supplied Azure credentials explicitly for this reason; the normal
graph-scoped application package correctly contains AWS credentials only.
No Apply occurred. The user subsequently approved the documented PoC
authentication dependency without structural provider isolation. An explicitly
enabled local Deployer credential file supplies only the unused Azure provider's
four authentication fields, never credentials for graph-selected Azure resources.
Verify the full native AWS plan contains no Azure resource creations; neither a
targeted plan nor mock credentials count as that verification.
The live workflow/reconnect/rendering audit therefore remains open.

The subsequent complete, non-targeted native AWS plan passed with the approved
auxiliary authentication: 110 managed creation entries and no Azure or GCP
resource creations. This includes the normal AWS L4/L5, eventing and image-build
foundations. The read-only resource-shape plan deliberately uses a non-deployable
placeholder storage-mover image digest; it must never be applied. The normal
lifecycle must publish its actual immutable image and create a fresh plan.
This is provider-authentication and resource-shape evidence, not runtime evidence.

### 2. Verify one representative complete application workflow

Prefer an AWS-local Small case, given the measured provisioning/cleanup times;
confirm its actual graph, current provider prerequisites and cost before Apply.
Use the regular UI → Management → Deployer operation path. The isolated L5
research script cannot substitute for this observation.

Before mutation, record the exact resource plan, artifact/graph revisions,
expected charges, cumulative allowance remaining, functional deadline and
cleanup allowance. Prior session authorization applies within its scope;
planning this run does not reset the cumulative allowance. Keep personal
financial constraints and credentials out of repository documentation.

During that one deployment:

1. Start through the application and retain operation/candidate references.
2. Reconnect once during a running operation. Confirm persisted progress resumes
   and that no duplicate Apply or other cost-incurring action is started.
3. Send one uniquely identifiable simulator sample after listeners are ready.
   Verify the existing Core/Event path, correlated command receipt and exact L3
   readback, then the deployed Event-to-L4 update and the matching L5 raw point.
4. Verify the second L5 panel against a real persisted hourly record. If the
   normal aggregation cannot finish in the bounded window, report that stage as
   incomplete; a separately seeded record is not simulator-to-rollup evidence.
5. Open the graph through the authenticated application access path. Preserve
   the minimal rendered observation and exact data assertions.
6. Destroy immediately and independently query the run-owned inventory.

Record readiness, packaging/publication where applicable, Apply, individual
resource creation, functional stages, message/command latency, Destroy and
inventory timings in the existing metrics format. Keep failed attempts and
retry cost distinct from the successful sample.

**Done when:** the representative workflow, reconnect, simulator assertions,
graphical access and cleanup have actual evidence. One successful local case
does not turn the other provider or directed cases into complete-profile passes.
Repeat only a failed or materially affected check; rerunning all nine successful
Core cases is not a default requirement.

### 3. Complete the evaluation against RQ1–RQ3

Create one compact coverage/claim table using the existing nine Core results,
three local command observations, AWS/Azure L4 and L5 observations, and the new
application run. Bind observations to their actual revisions and test conditions.
Keep unknown measurements empty. In particular, the older AWS Core run lacks
individual latency samples, and the successful attempts are not benchmark trials.

- RQ1: trace configuration through the normal application deployment; summarize
  provisioning defects, reconnect behavior, lifecycle timings and cleanup.
- RQ2: state which contracts and provider combinations were actually exercised;
  describe the reduced graphical responsibility and GCP exclusions explicitly.
- RQ3: reconcile available provider billing against run windows/resources, include
  failed-attempt overhead, and separate estimates, reservations and billed totals.
  Where attribution is unavailable, record that limitation. Use reproducible
  model calculations for the defined comparisons/sensitivity checks and label
  them as modeled; the current evidence does not isolate a causal Event-Layer
  cost effect or establish a paired live FiveLayer comparison.

Directed command return, cross-cloud L4 projection and storage-tier transitions
remain explicitly unverified unless a named final thesis claim requires one.
For such a claim, define the smallest targeted check and its acceptance condition
before extending execution. Otherwise constrain the conclusion to the evidence.
Do not expand the test matrix merely to remove an honest limitation.

**Done when:** each research conclusion has a traceable evidence/model reference
and stated limits; delayed billing and inactive provider deletion markers have
dated reconciliation or an explicit unresolved status. No functional rerun is
needed solely to await billing or deletion-marker expiry.

### 4. Close documentation and the repository

Reconcile current plan/protocol/matrix status with the final coverage table;
historical checkpoints remain recognizable as historical. Update the thesis
results/discussion and provider-service deviations, keeping RQ wording intact.
Use the existing documentation and thesis structure. Consolidate completed
implementation notes into durable method, decisions and results instead of
creating another roadmap.

Run the relevant final documentation/LaTeX and affected contract checks, inspect
the resulting thesis output, and make clean intermediate/final commits. Preserve
the original checkout's user files; keep credentials and raw private evidence
ignored. Push/merge only when requested.

**Completion condition:** the scoped application workflow works, required claims
are supported, remaining exclusions are explicit, run-owned active cloud resources
are removed, and the thesis/repository tell the same evidence-backed story.
Unexecuted complete-profile permutations are not labelled successful. Once these
conditions hold, stop feature work and finalize the thesis.

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
full Twin and stop on the first unresolved provider blocker. They do not turn
post-deployment Small runtime observations into a prerequisite for the first
deployment; Medium/Large capacity remains fail-closed.

### Supervised checkpoint — 2026-08-29

The account-level part of this phase has been executed without a Terraform
Apply or workload-resource creation:

- all three configured principals authenticate against their intended account,
  subscription, or project scope;
- AWS is active, its selected Region and regional STS endpoint are ready, IAM
  Identity Center is present in the configured Region, and the credential
  checker reports 108 of 108 required permissions;
- Azure is enabled, all configured Regions and Microsoft Graph authority are
  ready, all 16 required resource providers are registered, and all eight
  permission groups validate;
- GCP is active with billing and Region checked, all 18 Six-layer APIs are
  enabled, and all 80 project-testable permissions validate; and
- the credential-free Deployer regression gate passes with 2,072 tests and one
  intentional skip.

The secret-free local record is
`.evidence/provider-bootstrap-2026-08-29/provider-free-final-readiness.json`
with SHA-256
`f8dbf103e4b0878ba1d16375d61872594b968576ae034a3a947860eb67c926a4`.
The `.evidence/` directory is intentionally ignored and is available only in
the supervised local worktree. This checkpoint proves bounded account
preparation and read-only readiness; it is not federation, runtime, L4/L5, or
full-scenario evidence.

The subsequent credential-free checkpoint materialized all nine exact Small
candidates and produced the schema- and digest-bound
`docs/research/evaluation/small-scenario-budget-proposal.json`. Its numerical
proposals range from USD 2 to USD 3 and total USD 20 across all nine scenarios.
They scale the complete monthly candidate estimate to the 60-minute window,
apply threefold headroom, add a one-dollar uncertainty buffer, and round upward
to half-dollar increments. Unverified non-prorated or minimum charges block the
affected scenario instead of increasing its cap. The proposals remain pending
operator approval: the tracked matrix still has nine `null` caps and execution
remains disabled. The paired external timer warns at minute 45, triggers
Destroy at minute 50, and keeps the 60-minute cleanup deadline. No provider or
Deployer call was made for this checkpoint.

The refreshed credential-free checkpoint resolves the public broker image and
four build inputs at their immutable registry digests and retains all six
static custom runtime images locally for `linux/amd64`. Its schema- and
digest-bound record is
`docs/research/evaluation/small-runtime-image-readiness.json`. The superseded
GCP Grafana image is not part of the active PoC runtime set.
The canonical evaluation function is now also packaged deterministically and
its GCP processor extension is built locally for `linux/amd64` and
contract-checked. No image was pushed and no provider registry was changed.

The subsequent provider check used only control-plane GET, LIST, and DESCRIBE
operations. AWS exposes sufficient Small headroom for the checked Lambda,
TwinMaker, and Kinesis requirements. Azure exposes the required resource types
in the configured Regions and its Microsoft.Web usage endpoint is readable;
four other Azure control planes expose relevant quota usage only after a
resource exists, so those checks remain explicitly partial rather than being
inferred as passed. GCP exposes the required machine types and sufficient
Small compute, disk, address, zonal-cluster, Firestore, and Cloud Run quota.
No provider identifier, resource name, credential path, or credential value is
part of the tracked result.

AWS L4/L5 and Azure L4/L5 account/Region prerequisites pass. GCP L5 remains an
Apply-time access check. For GCP L4, the approved PoC path is one supervised
console bootstrap of custom IAP OAuth after the first approved scenario has
created its Cloud Run Twin Explorer and before L4 verification. It introduces
no application OAuth code, load balancer, or placeholder resource. The exact
five-minute, USD 0.00 incremental-cap, secret-free procedure and rollback are
frozen in
`docs/research/evaluation/gcp-l4-iap-bootstrap-runbook.md`. This is a resolved
design decision, not a passed live prerequisite; no cloud change was made.

All six directed identity checks are now individually specified in
`docs/research/evaluation/directed-federation-probe-plan.json`. The schema- and
digest-bound plan permits no Terraform Apply, Twin workload, message transfer,
static secret, or destination data permission. Four local-runner probes have a
direct technical cost cap of USD 0.00. The two exact Azure managed-identity
source paths each use at most one no-ingress 1-vCPU/1-GiB container for five
minutes with a USD 0.01 per-attempt cap; the original one-attempt-per-direction
aggregate cap is USD 0.02. Prices must be refreshed before execution. The exact
plan received supervised approval for run `26083001`. All six probes passed
with clean active residual inventory; only the expected non-usable GCP
soft-delete tombstones remain.

The following paragraphs preserve the earlier split-authority checkpoint as
historical evidence. The active single-administrator contract is recorded
below and supersedes it for future runs.

The follow-up provider-access implementation was complete offline. Azure then
uses one encrypted bundle with a resource-only deployment principal and a
separate preparation principal for exact conditional RBAC and the three
graph-required application permissions. All active Azure role assignments use
the preparation Terraform provider alias; the nonexistent `IoT Hub Data
Receiver` reference was corrected to the public `IoT Hub Data Reader` role.
The read-only readiness runner and all directed-federation harness slices use
the same deployment-versus-preparation boundary and reject legacy one-principal
compatibility files.
The complete credential-free Deployer suite passes with 2,085 tests and one
intentional skip. The same offline gate covers an idempotent SQLite migration
that removes the three obsolete production-auth user columns while preserving
active user data. Provider setup guides and the Settings links now cover AWS,
Azure, and GCP.

The completed two-principal Azure bundle was revalidated live and read-only on
2026-09-01. Authentication, exact Microsoft Graph consent, deployment
authority, conditional preparation RBAC and all eight deployment layers pass.
The obsolete custom deployment-role assignment was removed under supervision;
the supported deployment prerequisite is the built-in Contributor role, whose
effective exclusions prevent role-assignment mutation. ADT data-plane access
is not required at subscription scope: the atomic graph grants it to the
deployment principal only on the created ADT instance through the preparation
provider. No Terraform Apply or Twin workload was created.

The following Azure-to-AWS retry reached the approved identity-only mutation
path but stopped before the billable ACI runner: ARM had created the managed
identity before its service principal became readable through Microsoft Graph.
Cleanup completed, and one still-visible application required one exact
object-bound delete retry before AWS, Azure Resource Manager and active Graph
inventories were clean. Direct cost was USD 0.00. The harness now waits for
this provider propagation before creating the audience application and can
repeat only that known application delete during residual reconciliation. No
further cloud retry was started because the approved stop condition is
`first_exchange_failed`.

The explicitly re-approved retry passed the managed-identity visibility gate
but stopped before the ACI runner because the new audience service principal
and its app role were not yet readable for assignment. Cleanup and residual
inventory were immediately clean, and direct cost again remained USD 0.00.
The same bounded harness now waits for the exact audience service principal to
expose the expected app-role ID before assigning it. No additional cloud retry
was started.

The following explicitly approved attempt again stopped before the billable
ACI runner and incurred USD 0.00. Read-only deleted-object evidence narrows the
HTTP 403 to service-principal creation: the preparation principal had already
created the audience application and set its identifier URI. Its access token
contains exactly the three approved Graph permissions, and Microsoft lists
`Application.ReadWrite.OwnedBy` as the least-privileged application permission
for that operation. The runner now creates the service principal with only its
required `appId`; it omits the default-false `appRoleAssignmentRequired` write
because the AWS/GCP trust policy already enforces the assigned
`EventBridge.Exchange` claim. It also records all three Graph mutations as
separate stages. Cleanup and active residual inventory were clean. A new live
attempt still requires renewed approval under `first_exchange_failed`.

The next approved attempt stopped one stage earlier: Graph created the
audience application but returned HTTP 404 when its identifier URI was patched
immediately afterward. No ACI or AWS trust resource was created, cleanup and
active residual inventory were clean, and direct cost was USD 0.00. The runner
now retries only this idempotent PATCH on 404 within the unchanged overall
deadline and still fails immediately on all other responses. Another live
attempt requires renewed approval.

The first screen-by-screen Flutter simplification checkpoint is implemented
offline. **Settings → Cloud access** now removes the non-actionable local
profile card, makes provider-file import primary and keeps manual entry and the
provider guides as fallbacks. Azure accepts a standard service-principal JSON
or the complete allowlisted compatibility shape, explains both with
placeholder-only examples, prefills known values locally and uploads only a
rebuilt administrator document. The one-administrator Management contract and
provider-validation boundary are now aligned; no provider call or Terraform
action is part of this checkpoint.

The second screen checkpoint is also implemented offline. **Twin experiments**
is now a bounded start-or-resume inventory: `New Twin` is the sole primary
action, each Twin has one state-specific continuation, and portable
Duplicate/Export plus safe Delete remain in a secondary overflow. The former
filter strip, sortable five-column table, provider-irrelevant deployment column
and duplicate icon cluster are removed. Existing Management endpoints, routes
and mutation semantics are unchanged; this checkpoint performs no provider
operation.

The third screen checkpoint is implemented offline. **Configuration
Workspace** now exposes the complete dependency-aware workflow through four
stable thesis phases while the task selector is scoped to the active phase.
Task status is no longer overwritten by UI selection, blocked phases explain
their dependency, the artificial profile menu is replaced by direct Cloud
access, and the bottom bar has one filled primary action. All 15 tasks and the
existing Wizard BLoC, invalidation, save, calculation, immutable-selection,
CloudConnection, validation and finish contracts remain unchanged. This
checkpoint performs no provider operation.

The fourth screen checkpoint is implemented offline. **Twin lifecycle** now
uses one identity/state/next-step summary and one lifecycle command at a time.
Configured Twins prepare and deploy; deployed Twins verify L1–L3/Event,
L4/L5, telemetry and commands before Destroy; failed Twins clean up before a
later attempt; and destroyed Twins expose cleanup evidence before another
approved run. Configuration evidence remains last. The app bar owns Back,
theme and Cloud access, while Edit/Delete remain secondary. Existing BLoC,
Management API, durable operation, SSE, access, simulator, verification and
cleanup contracts are unchanged; this checkpoint performs no provider
operation.

The final cross-screen audit is complete offline. Cloud access, Twin
experiments, Configuration Workspace and Twin lifecycle now share app-bar
utilities, top-aligned bounded content, one dominant next outcome, secondary
management actions and responsive 640-pixel behavior. The audit corrected the
remaining wide-screen vertical centering in Cloud access and verified all four
surfaces in the deterministic Desktop/Web demo. The unused login screen was
subsequently removed. No provider call or Terraform action is part of this audit.

On 2026-09-10, bounded maintenance removed 21 unreachable Flutter libraries
and their exclusive tests, removed the inactive five-layer calculation form
while preserving historical DTO reads, and removed two unused Management test
simulation helpers. Missing or unsupported profile pins now block workload
emission. Simulator packages include all per-device runtime mounts and explicit
configuration arguments, exclude credentials from image builds, and stop rather
than restart after the supervised session. Provider wire contracts, frozen
prices, Terraform resources, migration/cleanup paths and live authorization
remain unchanged. Verification is recorded in decision D-26.

The approved Azure PoC simplification is implemented across
Management, Deployer, Terraform, the federation runner and Flutter. One Azure
service principal supplies subscription Owner plus the consented Microsoft
Graph permissions `Application.ReadWrite.All` and
`AppRoleAssignment.ReadWrite.All`. Retired preparation fields are not part of
the active API or Terraform contract. The local compatibility parser may
discard them when reading an older file, but never uploads them. This change
itself made no provider call. On 2026-09-04, a one-time supervised operator
session applied that
authority to the existing PoC application and removed its four redundant
subscription roles. No application, secret or workload resource was created,
no Terraform action ran and no direct charge was incurred. After the operator
session was removed, the application credential passed the non-mutating Owner,
Microsoft Graph, Region, six-control-plane and L4/L5 readiness checks. Azure
quota evidence remains explicitly partial where usage is exposed only after
resource creation. The offline gate passes with 684 Management tests, 2,084
Deployer tests plus one intentional skip, 812 Flutter tests, 42 focused runner
tests, eight Management integration checks, Terraform validation, Flutter
architecture, Web/macOS builds and strict documentation.

The first supervised Azure-to-AWS probe under the one-administrator contract
stopped before AWS role or billable Azure runner creation. AWS returned the
new OIDC provider ARN with a trailing-slash normalization that the harness
rejected. The strict stop was correct, but the returned object had not yet been
marked as cleanup-owned, so the initial result incorrectly reported clean
residual inventory. A separate exact tag- and issuer-bound reconciliation
found and deleted that one provider; subsequent AWS, Azure Resource Manager
and Microsoft Graph inventories are clean and direct cost was USD 0.00. The
harness now accepts only the two equivalent trailing-slash ARN forms and owns
the returned provider before validation. No retry was started.

On 2026-09-06 the user approved repeated, individually cleaned Azure-to-AWS
retries under the unchanged plan. One retry reached the ACI runner for 57.237
seconds and exposed that the AWS condition key must preserve the complete
Azure issuer path. Two subsequent pre-ACI retries exposed bounded propagation
at audience service-principal creation and app-role assignment. They incurred
USD 0.00 direct cost; the latter required one exact service-principal delete
retry before an independent six-class inventory was clean. The harness now
retries only these exact Graph 400/404 propagation responses and reissues only
the cleanup-owned delete during reconciliation. The final retry passed the
managed-identity token, AWS web-identity exchange, and session-identity check
in 40.320 seconds. Immediate cleanup and a separate inventory check were clean
across all six AWS, ARM, and Graph classes. The two billable retries each
remained under the frozen USD 0.01 technical cap. This establishes five of six
directed identity paths without Terraform Apply or a Twin workload; at that
checkpoint only Azure-to-GCP remained.

The subsequent Azure-to-GCP sequence completed on 2026-09-06. An initial
51.225-second ACI attempt was not counted as an exchange because the immediate
terminated-container log read returned HTTP 400; cleanup and the independent
active inventory were clean. The next attempt created and then removed its GCP
provider but stopped before ACI on a stale exact-name validator, with USD 0.00
direct cost. The retry-safe harness now waits only for the one-line ACI result
on empty/400/404 responses and uses a bounded two-digit pool/provider suffix
because GCP prevents reuse of soft-deleted names for approximately 30 days.

The next attempt passed managed identity and GCP STS but stopped at target
service-account impersonation after 33.908 seconds; cleanup and independent
inventory were clean. A bounded ten-by-five-second retry now covers only that
known IAM propagation window. The final attempt passed all three stages in
57.268 seconds. Immediate cleanup and a separate ten-class inventory found no
active Azure, Entra, or GCP probe resource; the four expected GCP tombstones
were deleted and unusable. Three Azure-to-GCP attempts reached ACI and each
remained under its USD 0.01 cap. Across both Azure-source directions, five
runner-reaching attempts give a conservative cumulative technical ceiling of
USD 0.05; no exact provider invoice is inferred. All six standalone federation
directions are now complete without Terraform Apply or Twin deployment.

Continue Phase 8 in this order:

1. verify the refreshed nine-candidate pack, budget proposal, runtime-image
   record, and provider-local mock plans;
2. review the exact Terraform plan, current Cloud Build free-tier usage, and
   the bounded publication steps for the first candidate without mutating a
   provider;
3. only after those gates pass, set the matrix to
   `approved_for_supervised_execution` and begin one supervised scenario at a
   time; during the first approved GCP run, apply the separately approved IAP
   bootstrap only after L1--L3/Event Layer pass and before L4 verification.

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
  Azure→GCP, GCP→AWS, and GCP→Azure;
- perform read-only L4/L5 account and regional readiness for all providers; and
- immediately remove probe resources and record residual state.

### Exit criteria

- every live prerequisite is ready or has an explicit, thesis-reportable
  blocker;
- all six directed federation paths have provider evidence independent of a
  full deployment;
- no full Small environment has been left running while a prerequisite is
  unresolved.

## 13. Phase 9 — nine supervised Small deployments

### Scenario set

- three provider-local scenarios: AWS, Azure, and GCP;
- six multi-cloud scenarios covering each directed provider pair exactly once
  on a required cross-cloud Eventing or Twin-projection boundary. L3 hot, cool,
  archive, and L5 remain one provider-local PoC bundle; cross-cloud storage
  migration is not part of the executable profile.

The concrete assignments and their primary edge focus are frozen in
`docs/research/evaluation/small-scenario-matrix.json`. The checked matrix shows
which architecture edge, edge-contract class, and provider direction each
scenario evaluates. Exact non-winning candidates are admitted only through the
disabled-by-default, digest-bound supervised Management endpoint; after
materialization they use the normal selection and deployment lifecycle.
Redundant permutations are not added without a specific RQ
or risk justification. The matrix remains non-executable until every numerical
budget cap and candidate trace has been reviewed.

### Execution and evidence

Follow the [live-evaluation protocol](../research/evaluation/live-evaluation-protocol.md)
for prerequisites, confirmation, budget/timer, staged checks, cleanup and
evidence validation. It is the sole operational checklist. Each attempt has
one metrics record; separate component reports are not required. Shared
application reconnect/replay is demonstrated once for the evaluated revision.
The four core summary tables are sufficient; extra diagnostics are optional.

Apply the [target concept's implementation freeze](2026-08-26_thesis_poc_target_concept.md#implementation-freeze):
fix evaluation blockers, preserve working convenience features, and add no
further product capabilities. Resolve the outstanding L5/original-comparison
decision before claiming a final functional scope. This protocol reduction
does not change L5, provider assignments, budget approval or Cloud Apply authority.

### Exit criteria

- all nine scenarios have complete comparable evidence, or an honest provider
  blocker is documented without substituting mocked success;
- each provider-local baseline and each directed pair is covered; and
- cleanup is reconciled before the next scenario; delayed provider billing is
  reconciled before final analysis rather than blocking a cleaned run sequence.

## 14. Phase 10 — thesis analysis and final repository cleanup

### Work

- Answer RQ1 from the intent-to-deployment trace and operationalization gaps.
- Answer RQ2 from capability gates, common roundtrip behavior, and deviations.
- Answer RQ3/RQ3.1 from paired provider-local and selected multi-cloud costs.
- Answer RQ3.2 from Eventing topology, directed route behavior, and explicit
  Eventing cost attribution.
- Compare provider-local and directed multi-cloud deployment/readiness time,
  end-to-end and stage latency, command/outcome behavior, reliability, resource
  count, Destroy time, and observed cost without turning latency into an
  Optimizer objective.
- Add sensitivity analysis for workload, transfer, region, price snapshot, and
  the hosted GCP device boundary.
- Separate implementation defects, provider blockers, model limitations,
  threats to validity, and future product work.
- Synthesize every material provider-service change from the predecessor
  mapping to the evaluated bundle, including protocol, durability, access,
  pricing, credential, and deployment consequences.
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
