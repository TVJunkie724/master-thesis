# Refactoring Roadmap

This page is the narrative index for the Twin2MultiCloud refactoring roadmap.
GitHub Issues remain the operational source of truth for concrete work,
status, discussion, blockers, and commit references.

## Ownership Rule

| Source | Responsibility |
|--------|----------------|
| GitHub Milestones | Phase planning and operational roadmap |
| GitHub Issues | Concrete implementation work, bugs, future work, dependencies, verification |
| This page | Thesis/developer-readable overview with issue numbers and current phase order |
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
| Phase 5 | Backend Orchestrator Disentanglement | Planned | Thin HTTP routes with repositories, services, clients, and orchestrators |
| Phase 6 | Brain Contracts & Pricing Reliability | Planned | Typed optimizer layer/pricing/capability contracts |
| Phase 7 | Flutter Wizard & Twin Views | Active | Core architecture, configuration workspace, Twin Overview, demo, and quality gate done; residual issues remain tracked |
| Later | Multi-Cloud Extensions & Thesis | Backlog | Non-blocking provider extensions, evaluation, and thesis polishing |

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
| [#4](https://github.com/TVJunkie724/master-thesis/issues/4) | Open | Migrate service HTML documentation into docs-site |
| [#30](https://github.com/TVJunkie724/master-thesis/issues/30) | Open | Multi-cloud examples, troubleshooting, walkthrough docs |
| [#49](https://github.com/TVJunkie724/master-thesis/issues/49) | Open | UIBK login prerequisites |

### Phase 4: Runtime Credentials & Deployment State

| Issue | Status | Notes |
|-------|--------|-------|
| [#6](https://github.com/TVJunkie724/master-thesis/issues/6) | Active | CloudConnection credential SSOT and Compose split. Runtime fallback removal is complete (#78), and purpose-aware pricing/deployment credentials, transactional pricing defaults, purpose-specific validation, and secret-free inventory options are implemented. Bootstrap output splitting and profile management remain. Plans: [`docs/plans/2026-05-19_credential_ssot_compose_split.md`](https://github.com/TVJunkie724/master-thesis/blob/master/docs/plans/2026-05-19_credential_ssot_compose_split.md), `docs/plans/provider_access_pricing_review/` |
| [#7](https://github.com/TVJunkie724/master-thesis/issues/7) | Done | Provider bootstrap and permission preflight checks. Slices 1-4 add static dry-run-first bootstrap artifacts, the Management API plan/import contract, normalized CloudConnection/Deployer preflight results, and offline provider permission artifact guardrails. Plan: [`docs/plans/2026-05-21_provider_bootstrap_preflight_plan.md`](https://github.com/TVJunkie724/master-thesis/blob/master/docs/plans/2026-05-21_provider_bootstrap_preflight_plan.md) |
| [#79](https://github.com/TVJunkie724/master-thesis/issues/79) | Active | Stage 2 for provider credentials: `thesis-demo-v1` is implemented as the active versioned permission-set contract across bootstrap output, Deployer preflight, Management API CloudConnections, and docs. AWS, Azure, and GCP pre-E2E hardening now include provider-specific scope reviews and checker/artifact drift gates; final least-privilege still requires supervised provider validation. The permission-checker implementations remain a planned follow-up review/refactor target before final E2E sign-off. Plan: [`docs/plans/2026-06-04_permission_set_version_contract.md`](https://github.com/TVJunkie724/master-thesis/blob/master/docs/plans/2026-06-04_permission_set_version_contract.md) |
| [#8](https://github.com/TVJunkie724/master-thesis/issues/8) | Open | Production credential security controls |
| [#9](https://github.com/TVJunkie724/master-thesis/issues/9) | Open | Local encryption/JWT key generation and persistence |
| [#10](https://github.com/TVJunkie724/master-thesis/issues/10) | Open | Production authentication and UIBK login path |
| [#78](https://github.com/TVJunkie724/master-thesis/issues/78) | Done | Legacy encrypted per-twin credential fallback removed; CloudConnections are the only runtime credential source |
| [#11](https://github.com/TVJunkie724/master-thesis/issues/11) | Open | ProjectStorage abstraction for Deployer project data |
| [#12](https://github.com/TVJunkie724/master-thesis/issues/12) | Open | Remove legacy global state in favor of explicit context |
| [#13](https://github.com/TVJunkie724/master-thesis/issues/13) | Open, blocked by #11/#12 | Context-owned config loading |
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
| [#63](https://github.com/TVJunkie724/master-thesis/issues/63) | Open | Introduce repositories and remove route-owned queries |
| [#64](https://github.com/TVJunkie724/master-thesis/issues/64) | Open | Move twin state transitions into `TwinLifecycleService` |
| [#65](https://github.com/TVJunkie724/master-thesis/issues/65) | Open | Typed `OptimizerClient` and `DeployerClient` boundaries |
| [#66](https://github.com/TVJunkie724/master-thesis/issues/66) | Open, blocked by #63/#64/#65 | DeploymentOrchestrator |
| [#67](https://github.com/TVJunkie724/master-thesis/issues/67) | Open, blocked by #66 | Split backend twin routes into focused adapters |
| [#35](https://github.com/TVJunkie724/master-thesis/issues/35) | Open | Verify Management API compatibility with Optimizer and Deployer |
| [#39](https://github.com/TVJunkie724/master-thesis/issues/39) | Open | Complete deployment lifecycle UI/backend workflow |

### Phase 6: Brain Contracts & Pricing Reliability

| Issue | Status | Notes |
|-------|--------|-------|
| [#68](https://github.com/TVJunkie724/master-thesis/issues/68) | Open | Standardize `LayerResult` and calculator contracts |
| [#69](https://github.com/TVJunkie724/master-thesis/issues/69) | Open | Explicit pricing failures and schema versions |
| [#70](https://github.com/TVJunkie724/master-thesis/issues/70) | Open | Provider capabilities and unsupported layers |
| [#31](https://github.com/TVJunkie724/master-thesis/issues/31) | Open | Tiered pricing for additional optimizer services |
| [#32](https://github.com/TVJunkie724/master-thesis/issues/32) | Open | Refresh pricing schema and provider fetchers; includes a dedicated review/refactor of pricing-fetcher correctness, provider parsing, failure propagation, and tests |
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
| [#71](https://github.com/TVJunkie724/master-thesis/issues/71) | Open | Frontend state-management boundaries and dev auth |
| [#72](https://github.com/TVJunkie724/master-thesis/issues/72) | Open | Typed Flutter API responses |
| [#73](https://github.com/TVJunkie724/master-thesis/issues/73) | Done | Twin Overview split into typed operation and presentation slices |
| [#108](https://github.com/TVJunkie724/master-thesis/issues/108) | Done | Frontend cross-cutting quality and thesis evidence gate |

### Later: Multi-Cloud Extensions & Thesis

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
| [#48](https://github.com/TVJunkie724/master-thesis/issues/48) | Open | Thesis structure and evaluation TODOs |
| [#51](https://github.com/TVJunkie724/master-thesis/issues/51) | Blocked | Azure Functions Flex Consumption migration |
| [#52](https://github.com/TVJunkie724/master-thesis/issues/52) | Open | Azure Functions `WEBSITE_RUN_FROM_PACKAGE` evaluation |
| [#54](https://github.com/TVJunkie724/master-thesis/issues/54) | Open | GCP L4/L5 provider support |
| [#55](https://github.com/TVJunkie724/master-thesis/issues/55) | Open | GCP hot reader query-format support |
| [#58](https://github.com/TVJunkie724/master-thesis/issues/58) | Open | Reconcile Azure L0 gap-fix future work |
| [#59](https://github.com/TVJunkie724/master-thesis/issues/59) | Open | Azure/GCP inter-cloud glue functions |
| [#61](https://github.com/TVJunkie724/master-thesis/issues/61) | Open | Cross-cloud storage lifecycle mover functions |
| [#62](https://github.com/TVJunkie724/master-thesis/issues/62) | Open | Closed-loop redeployment from cost pattern changes |

## Next Recommended Sequence

1. Finish the remaining Phase 4 credential/runtime work: #6, #79, #11, #12, #13.
2. Start backend orchestration disentanglement with #63, #64, and #65 before #66.
3. Split route adapters through #67 after the orchestrator boundary is stable.
4. Finish the explicitly tracked Flutter residuals in #39, #71, and #72; #38,
   #73, and #108 are complete.
5. Move optimizer reliability work into Phase 6 once deployment/runtime boundaries are stable.
