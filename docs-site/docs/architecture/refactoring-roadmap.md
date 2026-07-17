# Refactoring Roadmap

This page is the narrative index for the Twin2MultiCloud refactoring roadmap.
GitHub Issues remain the operational source of truth for concrete work,
status, discussion, blockers, and commit references.

## Ownership Rule

| Source | Responsibility |
|--------|----------------|
| GitHub Milestones | Phase planning and operational roadmap |
| GitHub Issues | Concrete implementation work, bugs, future work, dependencies, verification |
| This page | Maintainer-readable overview with issue numbers and current phase order |
| Historical TODO/Future Work files | Input material only; do not add new active work there |

Do not duplicate detailed task lists in Markdown. Add or update a GitHub Issue
when work becomes actionable, then reference the issue here.

## Roadmap Epic

| Issue | Status | Purpose |
|-------|--------|---------|
| [#77](https://github.com/TVJunkie724/master-thesis/issues/77) | Open | Architecture refactoring roadmap and epic index |

## Phase Overview

| Phase | Milestone | Status | Primary Outcome |
|-------|-----------|--------|-----------------|
| Phase 0 | Assessment & Backlog SSOT | Active | Keep the assessment, issues, milestones, and this roadmap aligned |
| Phase 1 | Deployer Canonical Path | Mostly done | One productive Deployer provider/Terraform path |
| Phase 2 | Deployer Contract Hardening | Mostly done | Typed deploy/destroy/SSE/error contracts |
| Phase 3 | Repository Hygiene & Docs Site | Active | Separate docs, templates, runtime artifacts, and historical material |
| Phase 4 | Runtime Credentials & Deployment State | Active | Credential SSOT, bootstrap, explicit deployment package/context, operation state |
| Phase 5 | Backend Orchestrator Disentanglement | Done | Thin HTTP routes with repositories, services, clients, orchestrators, and a typed deployment lifecycle |
| Phase 6 | Brain Contracts & Pricing Reliability | Active | Layer contracts complete; capability and expanded provider pricing coverage remain |
| Phase 7 | Flutter Wizard & Twin Views | Done | Core architecture, configuration workspace, typed boundaries, demo, and all-desktop delivery gates completed |
| Phase 8 | Twin Architecture Profiles & Eventing | Planned | Freeze the hardened five-layer baseline, introduce closed-world architecture profiles, and evaluate one bounded Eventing extension |
| Later | Platform Extensions | Backlog | Non-blocking provider and operational extensions |

## Completed Refactorings

| Issue | Status | Result |
|-------|--------|--------|
| [#15](https://github.com/TVJunkie724/master-thesis/issues/15) | Done | Canonical Deployer path audited and guarded as Terraform-first |
| [#2](https://github.com/TVJunkie724/master-thesis/issues/2) | Done | Deployer template and runtime upload ownership separated |
| [#74](https://github.com/TVJunkie724/master-thesis/issues/74) | Done | Deployer observability and error boundaries hardened |
| [#75](https://github.com/TVJunkie724/master-thesis/issues/75) | Done | Backend deployment operation metadata persisted |
| [#37](https://github.com/TVJunkie724/master-thesis/issues/37) | Done | Deployment-ready package is generated from persisted backend state |
| [#76](https://github.com/TVJunkie724/master-thesis/issues/76) | Done | Typed wizard configuration contract and deployment package boundary completed |
| [#38](https://github.com/TVJunkie724/master-thesis/issues/38) | Done | Flutter architecture and large UI modules decomposed and release-gated |
| [#73](https://github.com/TVJunkie724/master-thesis/issues/73) | Done | Twin Overview split into typed operation, output, log, and utility slices |
| [#108](https://github.com/TVJunkie724/master-thesis/issues/108) | Done | Cross-cutting Flutter architecture, test, build, and local contract gate |
| [#72](https://github.com/TVJunkie724/master-thesis/issues/72) | Done | Stable twin, configuration, optimizer, pricing-export, and deployer response boundaries are typed and live-contract verified |
| [#39](https://github.com/TVJunkie724/master-thesis/issues/39) | Done | Deployment and destroy lifecycle, persisted status, safe confirmations, and Management API log streaming reconciled |
| [#9](https://github.com/TVJunkie724/master-thesis/issues/9) | Done | Durable local JWT/encryption secrets are generated safely while production remains fail-closed |
| [#4](https://github.com/TVJunkie724/master-thesis/issues/4) | Done | Legacy service HTML content migrated into the canonical docs site with provenance |
| [#30](https://github.com/TVJunkie724/master-thesis/issues/30) | Done | Multi-cloud walkthrough, troubleshooting, references, and project documentation completed |
| [#70](https://github.com/TVJunkie724/master-thesis/issues/70) | Done | Federated Optimizer/Deployer provider capability contracts, fail-closed Management API aggregation, and Flutter enforcement completed |
| [#100](https://github.com/TVJunkie724/master-thesis/issues/100) | Done | Compact and field-level intent-to-result pricing traceability across Optimizer, persisted Management API runs, and collapsed Flutter diagnostics |

## Active And Planned Refactoring Issues

### Phase 0: Assessment & Backlog SSOT

| Issue | Status | Notes |
|-------|--------|-------|
| [#77](https://github.com/TVJunkie724/master-thesis/issues/77) | Open | Central roadmap/epic index |
| [#5](https://github.com/TVJunkie724/master-thesis/issues/5) | Open | Archive historical plans and retire TODO files |

### Phase 1: Deployer Canonical Path

| Issue | Status | Notes |
|-------|--------|-------|
| [#15](https://github.com/TVJunkie724/master-thesis/issues/15) | Done | Canonical deployment path and Terraform-first guard |
| [#46](https://github.com/TVJunkie724/master-thesis/issues/46) | Open | Decide final fate of legacy CLI workflow |

### Phase 2: Deployer Contract Hardening

| Issue | Status | Notes |
|-------|--------|-------|
| [#74](https://github.com/TVJunkie724/master-thesis/issues/74) | Done | Operation-scoped Deployer logging/error boundary |
| [#19](https://github.com/TVJunkie724/master-thesis/issues/19) | Open | Structured deploy result including post-Terraform status |
| [#24](https://github.com/TVJunkie724/master-thesis/issues/24) | Open | Consolidate Terraform storage names and layer suffix strings |
| [#27](https://github.com/TVJunkie724/master-thesis/issues/27) | Open | Azure event checker redeployment support |
| [#45](https://github.com/TVJunkie724/master-thesis/issues/45) | Open | Deployer project asset lifecycle endpoints |

### Phase 3: Repository Hygiene & Docs Site

| Issue | Status | Notes |
|-------|--------|-------|
| [#1](https://github.com/TVJunkie724/master-thesis/issues/1) | Open | MkDocs/docs-site and repository hygiene umbrella |
| [#2](https://github.com/TVJunkie724/master-thesis/issues/2) | Done | Template/runtime upload separation |
| [#3](https://github.com/TVJunkie724/master-thesis/issues/3) | Open | Non-destructive hygiene guardrail check |
| [#4](https://github.com/TVJunkie724/master-thesis/issues/4) | Done | Migrate service HTML documentation into docs-site |
| [#30](https://github.com/TVJunkie724/master-thesis/issues/30) | Done | Multi-cloud examples, troubleshooting, walkthrough docs |
| [#49](https://github.com/TVJunkie724/master-thesis/issues/49) | Open | UIBK login prerequisites |

### Phase 4: Runtime Credentials & Deployment State

| Issue | Status | Notes |
|-------|--------|-------|
| [#6](https://github.com/TVJunkie724/master-thesis/issues/6) | Active | CloudConnection credential SSOT and Compose split. Runtime fallback removal is complete (#78), and purpose-aware pricing/deployment credentials, transactional pricing defaults, purpose-specific validation, and secret-free inventory options are implemented. Bootstrap output splitting and profile management remain. Plans: [`docs/plans/2026-05-19_credential_ssot_compose_split.md`](https://github.com/TVJunkie724/master-thesis/blob/master/docs/plans/2026-05-19_credential_ssot_compose_split.md), `docs/plans/provider_access_pricing_review/` |
| [#7](https://github.com/TVJunkie724/master-thesis/issues/7) | Done | Provider bootstrap and permission preflight checks. Slices 1-4 add static dry-run-first bootstrap artifacts, the Management API plan/import contract, normalized CloudConnection/Deployer preflight results, and offline provider permission artifact guardrails. Plan: [`docs/plans/2026-05-21_provider_bootstrap_preflight_plan.md`](https://github.com/TVJunkie724/master-thesis/blob/master/docs/plans/2026-05-21_provider_bootstrap_preflight_plan.md) |
| [#79](https://github.com/TVJunkie724/master-thesis/issues/79) | Active | Stage 2 for provider credentials: `thesis-demo-v1` is implemented as the active versioned permission-set contract across bootstrap output, Deployer preflight, Management API CloudConnections, and docs. AWS, Azure, and GCP pre-E2E hardening now include provider-specific scope reviews and checker/artifact drift gates; final least-privilege still requires supervised provider validation. The permission-checker implementations remain a planned follow-up review/refactor target before final E2E sign-off. Plan: [`docs/plans/2026-06-04_permission_set_version_contract.md`](https://github.com/TVJunkie724/master-thesis/blob/master/docs/plans/2026-06-04_permission_set_version_contract.md) |
| [#8](https://github.com/TVJunkie724/master-thesis/issues/8) | Done | Production HTTPS/trusted-proxy boundary, distributed per-user credential rate limits, request correlation, and append-only secret-free audit evidence. Plan: `twin2multicloud_backend/implementation_plans/2026-07-16_production_credential_security_controls.md` |
| [#9](https://github.com/TVJunkie724/master-thesis/issues/9) | Done | Atomic local JWT/encryption secret bootstrap, read-only Compose mounts, and production fail-closed validation |
| [#10](https://github.com/TVJunkie724/master-thesis/issues/10) | Active | Durable provider-neutral login transactions, Google PKCE, correlated UIBK SAML callbacks, revocable sessions, and Flutter browser exchange are implemented; live UIBK activation remains blocked by #49 |
| [#78](https://github.com/TVJunkie724/master-thesis/issues/78) | Done | Legacy encrypted per-twin credential fallback removed; CloudConnections are the only runtime credential source |
| [#11](https://github.com/TVJunkie724/master-thesis/issues/11) | Done | ProjectStorage abstraction for Deployer project data |
| [#12](https://github.com/TVJunkie724/master-thesis/issues/12) | Done | Legacy global state replaced by explicit deployment context |
| [#13](https://github.com/TVJunkie724/master-thesis/issues/13) | Done | Config loading unified through deployment context |
| [#14](https://github.com/TVJunkie724/master-thesis/issues/14) | Open | Reduce monolithic Deployer modules |
| [#16](https://github.com/TVJunkie724/master-thesis/issues/16) | Open | Optimize L0 glue conditional deployment |
| [#20](https://github.com/TVJunkie724/master-thesis/issues/20) | Open | Observability variables through config/API/UI |
| [#21](https://github.com/TVJunkie724/master-thesis/issues/21) | Open | Multi-user Grafana provisioning |
| [#22](https://github.com/TVJunkie724/master-thesis/issues/22) | Open | Grafana dashboards and datasources via Terraform |
| [#23](https://github.com/TVJunkie724/master-thesis/issues/23) | Open | AWS IAM Identity Center setup for Managed Grafana |
| [#37](https://github.com/TVJunkie724/master-thesis/issues/37) | Done | DB-backed deployment package generation |
| [#53](https://github.com/TVJunkie724/master-thesis/issues/53) | Open | Replace inter-cloud shared-secret auth |
| [#57](https://github.com/TVJunkie724/master-thesis/issues/57) | Open | Inter-cloud envelope metadata and trace propagation |
| [#60](https://github.com/TVJunkie724/master-thesis/issues/60) | Open | DLQ and retry handling for failed cross-cloud calls |
| [#75](https://github.com/TVJunkie724/master-thesis/issues/75) | Done | Backend deployment operation state |

### Phase 5: Backend Orchestrator Disentanglement

| Issue | Status | Notes |
|-------|--------|-------|
| [#63](https://github.com/TVJunkie724/master-thesis/issues/63) | Done | Repositories own persistence and routes no longer own queries |
| [#64](https://github.com/TVJunkie724/master-thesis/issues/64) | Done | Twin state transitions live in `TwinLifecycleService` |
| [#65](https://github.com/TVJunkie724/master-thesis/issues/65) | Done | Typed `OptimizerClient` and `DeployerClient` boundaries |
| [#66](https://github.com/TVJunkie724/master-thesis/issues/66) | Done | Deployment orchestration is isolated behind `DeploymentOrchestrator` |
| [#67](https://github.com/TVJunkie724/master-thesis/issues/67) | Done | Twin routes are split into focused HTTP adapters |
| [#35](https://github.com/TVJunkie724/master-thesis/issues/35) | Done | Management API compatibility with Optimizer and Deployer verified |
| [#39](https://github.com/TVJunkie724/master-thesis/issues/39) | Done | Canonical deployment lifecycle, retry/recovery, explicit destroy confirmation, and Management API-only log streaming completed through #73 |

### Phase 6: Brain Contracts & Pricing Reliability

| Issue | Status | Notes |
|-------|--------|-------|
| [#68](https://github.com/TVJunkie724/master-thesis/issues/68) | Done | Canonical immutable `LayerResult`, shared calculator/capability contract, fail-closed selection, and 21-combination provider-layer matrix |
| [#69](https://github.com/TVJunkie724/master-thesis/issues/69) | Open | Explicit pricing failures and schema versions |
| [#70](https://github.com/TVJunkie724/master-thesis/issues/70) | Done | Explicit 3 x 7 provider-layer capability matrix and unsupported-path enforcement |
| [#100](https://github.com/TVJunkie724/master-thesis/issues/100) | Done | Honest intent-to-result trace with typed persisted field audit and non-additive contribution semantics |
| [#31](https://github.com/TVJunkie724/master-thesis/issues/31) | Open epic | Provider billing-model finalization, split into Azure quantities (#114), AWS account pricing plans (#115), and route-aware transfer (#116) |
| [#114](https://github.com/TVJunkie724/master-thesis/issues/114) | Done | Replaced fabricated Azure Digital Twins query tiers with explicit operation, routed-message, and query-unit quantities; exact live meter evidence, shared API validation, trace provenance, compact Flutter controls, and OpenAPI drift gates are verified |
| [#115](https://github.com/TVJunkie724/master-thesis/issues/115) | Implemented locally; platform CI pending | Separate public TwinMaker Price List evidence from owner-scoped account plan observations; gate Basic, pending changes, and unallocated bundles before AWS L4 selection |
| [#119](https://github.com/TVJunkie724/master-thesis/issues/119) | Local implementation and gates complete; platform CI pending | Immutable provider-region catalogs now drive exact owner-safe calculation, persistence, deployment selection, health, review, and reference-only Flutter diagnostics. Full pricing blobs and client-authored pricing evidence are outside the live contract. Reviewed plan: `2-twin2clouds/implementation_plans/2026-07-17_immutable_region_pricing_catalogs.md` |
| [#116](https://github.com/TVJunkie724/master-thesis/issues/116) | Done | Exact routes, regions, network tiers, provider units, aggregate transfer pools, six baseline edges, global path scoring, trusted Management validation, atomic durable run persistence, server-owned deployment-path projection, and collapsed typed Flutter evidence are implemented. Plans: `2-twin2clouds/implementation_plans/2026-07-18_route_aware_transfer_pricing.md` and `twin2multicloud_flutter/implementation_plans/2026-07-18_durable_optimizer_runs_and_transfer_evidence.md` |
| [#118](https://github.com/TVJunkie724/master-thesis/issues/118) | Active pre-Phase-8 blocker | Propagate a versioned resolved service deployment specification from the selected cost model through the Management API and DeploymentManifest into Terraform. Mini-roadmap and reviewed plans: `docs/plans/resolved_deployment_specification/` |
| [#127](https://github.com/TVJunkie724/master-thesis/issues/127) | Done | Canonical v1 schema, deployment-dimension registry, full provider/slot matrix, golden fixtures, and byte-identical service copies |
| [#129](https://github.com/TVJunkie724/master-thesis/issues/129) | Done | Emit exact resolved deployment selections from the Optimizer winner, including formula-bound runtime values, archive classes, and Azure IoT Hub SKU/capacity with provider billing-block normalization |
| [#130](https://github.com/TVJunkie724/master-thesis/issues/130) | Blocked by #127 and #129 | Validate, persist, freeze, and manifest the specification in the Management API |
| [#131](https://github.com/TVJunkie724/master-thesis/issues/131) | Blocked by #127 and #130 | Fail-closed Deployer preflight and typed tfvars translation |
| [#132](https://github.com/TVJunkie724/master-thesis/issues/132) | Blocked by #131 | Align AWS formula assumptions and Terraform resource values |
| [#133](https://github.com/TVJunkie724/master-thesis/issues/133) | Blocked by #131 | Align Azure IoT Hub and other modeled Azure resource values |
| [#120](https://github.com/TVJunkie724/master-thesis/issues/120) | Blocked by #131 | Align GCP runtime profiles and archive storage model |
| [#134](https://github.com/TVJunkie724/master-thesis/issues/134) | Blocked by #130 | Add compact read-only Flutter deployment review |
| [#128](https://github.com/TVJunkie724/master-thesis/issues/128) | Final gate | Prove Optimizer-to-Terraform continuity with credential-free drift tests |
| [#117](https://github.com/TVJunkie724/master-thesis/issues/117) | Done | Removed the unreachable Azure ADT Updater path; Azure L4 now has one package-, Terraform-, runtime-, security-, and documentation-tested Persister-to-ADT-Pusher topology |
| [#32](https://github.com/TVJunkie724/master-thesis/issues/32) | Open | Refresh pricing schema and provider fetchers; includes a dedicated review/refactor of pricing-fetcher correctness, provider parsing, failure propagation, and tests |
| [#110](https://github.com/TVJunkie724/master-thesis/issues/110) | Done | Azure Cosmos/Blob storage and bandwidth tier sources now use exact reviewed catalog evidence, collision-safe candidate identity, fail-closed publication, and a publishable live baseline |
| [#33](https://github.com/TVJunkie724/master-thesis/issues/33) | Open | Pricing and region freshness in UI |
| [#34](https://github.com/TVJunkie724/master-thesis/issues/34) | Open | Manual provider override with cost warnings |
| [#42](https://github.com/TVJunkie724/master-thesis/issues/42) | Open | Validate theoretical cost formulas against real deployed data |
| [#43](https://github.com/TVJunkie724/master-thesis/issues/43) | Open | Real-time cost and billing tracking |
| [#50](https://github.com/TVJunkie724/master-thesis/issues/50) | Open | Optimizer strategy encapsulation |
| [#56](https://github.com/TVJunkie724/master-thesis/issues/56) | Open | High-frequency orchestration cost optimization |

### Phase 7: Flutter Wizard & Twin Views

| Issue | Status | Notes |
|-------|--------|-------|
| [#76](https://github.com/TVJunkie724/master-thesis/issues/76) | Done | Typed wizard configuration contract foundation |
| [#38](https://github.com/TVJunkie724/master-thesis/issues/38) | Done | Flutter wizard and large UI decomposition completed |
| [#40](https://github.com/TVJunkie724/master-thesis/issues/40) | Open | Twin operations dashboard |
| [#41](https://github.com/TVJunkie724/master-thesis/issues/41) | Open | Centralized error notification and UI alerts |
| [#71](https://github.com/TVJunkie724/master-thesis/issues/71) | Done | Frontend state-management boundaries and dev auth |
| [#72](https://github.com/TVJunkie724/master-thesis/issues/72) | Done | Typed Flutter API responses and contained raw-payload exceptions |
| [#73](https://github.com/TVJunkie724/master-thesis/issues/73) | Done | Twin Overview split into typed operation and presentation slices |
| [#108](https://github.com/TVJunkie724/master-thesis/issues/108) | Done | Frontend cross-cutting quality and thesis evidence gate |
| [#109 Establish Web and all-desktop Flutter support gates](https://github.com/TVJunkie724/master-thesis/issues/109) | Done | One application contract and native build evidence for Web, macOS, Windows, and Linux |
| [#111 Run final manual visual audit of the Flutter application](https://github.com/TVJunkie724/master-thesis/issues/111) | Planned | User-led visual and interaction audit after functional issue work, before final E2E |

### Phase 8: Twin Architecture Profiles & Eventing

| Issue | Status | Notes |
|-------|--------|-------|
| [#112 Audit and redesign the Digital Twin reference architecture beyond the bachelor baseline](https://github.com/TVJunkie724/master-thesis/issues/112) | Planned | Reconstruct the implemented graph, freeze a hardened `five-layer-baseline@1`, define closed-world architecture-profile contracts, and evaluate `six-layer-eventing@1` separately |
| [#113 Define and harden the user-function extension and packaging contract](https://github.com/TVJunkie724/master-thesis/issues/113) | Active prerequisite | Establish the platform-owned component and user-code boundary required before resolved architecture profiles can bind extension slots safely |

### Later: Platform Extensions

| Issue | Status | Notes |
|-------|--------|-------|
| [#17](https://github.com/TVJunkie724/master-thesis/issues/17) | Open | Azure/GCP hot reader functions |
| [#18](https://github.com/TVJunkie724/master-thesis/issues/18) | Open | Azure L4/L5 and Grafana cross-cloud patterns |
| [#25](https://github.com/TVJunkie724/master-thesis/issues/25) | Blocked | Azure Diagnostic Settings 409 conflict |
| [#26](https://github.com/TVJunkie724/master-thesis/issues/26) | Open | Azure API helper support |
| [#28](https://github.com/TVJunkie724/master-thesis/issues/28) | Open | Clean provider template default processors |
| [#29](https://github.com/TVJunkie724/master-thesis/issues/29) | Open | Deployer performance for multi-cloud deployments |
| [#44](https://github.com/TVJunkie724/master-thesis/issues/44) | Open | User-adaptable IoT simulator export |
| [#47](https://github.com/TVJunkie724/master-thesis/issues/47) | Open | Optional Swagger dark theme |
| [#51](https://github.com/TVJunkie724/master-thesis/issues/51) | Blocked | Azure Functions Flex Consumption migration |
| [#52](https://github.com/TVJunkie724/master-thesis/issues/52) | Open | Azure Functions `WEBSITE_RUN_FROM_PACKAGE` evaluation |
| [#54](https://github.com/TVJunkie724/master-thesis/issues/54) | Open | GCP L4/L5 provider support |
| [#55](https://github.com/TVJunkie724/master-thesis/issues/55) | Open | GCP hot reader query-format support |
| [#58](https://github.com/TVJunkie724/master-thesis/issues/58) | Open | Reconcile Azure L0 gap-fix future work |
| [#59](https://github.com/TVJunkie724/master-thesis/issues/59) | Open | Azure/GCP inter-cloud glue functions |
| [#61](https://github.com/TVJunkie724/master-thesis/issues/61) | Open | Cross-cloud storage lifecycle mover functions |
| [#62](https://github.com/TVJunkie724/master-thesis/issues/62) | Open | Closed-loop redeployment from cost pattern changes |

## Next Recommended Sequence

1. Complete the resolved-deployment-specification sequence
   [#127](https://github.com/TVJunkie724/master-thesis/issues/127) through
   [#128](https://github.com/TVJunkie724/master-thesis/issues/128), closing
   [#118](https://github.com/TVJunkie724/master-thesis/issues/118) only after
   its no-apply drift gate passes.
2. Reconcile the remaining service/tier scope in
   [#31](https://github.com/TVJunkie724/master-thesis/issues/31) and
   [#32](https://github.com/TVJunkie724/master-thesis/issues/32).
3. Build pricing freshness and manual override UX only after these Optimizer
   contracts are stable (#33 and #34).
4. Complete the remaining functional issues, then run the user-led visual audit in
   [#111](https://github.com/TVJunkie724/master-thesis/issues/111).
5. Complete the current-system hardening prerequisites, including the
   user-function boundary in
   [#113](https://github.com/TVJunkie724/master-thesis/issues/113), without
   prematurely redesigning runtime topology.
6. Execute Phase 8 through
   [#112](https://github.com/TVJunkie724/master-thesis/issues/112): reconstruct
   the current graph, freeze the hardened five-layer baseline, and only then
   design and evaluate the Eventing extension and its multi-cloud bridge.
7. Keep live-cloud E2E and finalization deferred until both the manual UI audit
   and architecture-profile work are complete.
