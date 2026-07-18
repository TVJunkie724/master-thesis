# Future Work

Consolidated future work items across the entire Twin2MultiCloud platform, organized by project.

**Last Updated:** 2026-02-10

> [!TIP]
> See [3-cloud-deployer/docs/future-work-resolved.md](../3-cloud-deployer/docs/future-work-resolved.md) for completed items.

---

## Table of Contents

| Priority | Project | Item | Checked |
|----------|---------|------|---------|
| 🔴 High | Deployer | [ProjectStorage Abstraction Layer](#projectstorage-abstraction-layer) | ✅ |
| 🔴 High | Deployer | [L0 Glue Layer Conditional Deployment Optimization](#l0-glue-layer-conditional-deployment-optimization) | ✅ |
| 🟡 Medium | Deployer | [Deploy API Return Value Enhancement](#deploy-api-return-value-enhancement) | ✅ |
| 🟡 Medium | Deployer | [Observability Variables API Wiring](#observability-variables-api-wiring) | ✅ |
| 🟡 Medium | Deployer | [Multi-User Grafana Provisioning (N Users)](#multi-user-grafana-provisioning-n-users) | ✅ |
| 🟡 Medium | Full Stack | [Requirements.txt Validation for User Functions](#requirementstxt-validation-for-user-functions) | ✅ |
| 🟡 Medium | Full Stack | [Deployment File Generation from Database](#deployment-file-generation-from-database) | ✅ |
| 🟢 Low | Deployer | [Grafana Dashboard & Datasource Automation](#grafana-dashboard--datasource-automation-via-terraform) | ✅ |
| 🟢 Low | Deployer | [Automated IAM Identity Center (SSO) Setup](#automated-iam-identity-center-sso-setup) | ✅ |
| 🟢 Low | Deployer | [Terraform String Consolidation (Phases 3–4)](#terraform-string-consolidation-phases-34) | ✅ |
| 🟢 Low | Deployer | [Legacy globals.py Cleanup](#legacy-globalspy-cleanup) | ✅ |
| 🟢 Low | Deployer | [Unified Config Loading via Context](#unified-config-loading-via-context) | ✅ |
| 🔵 Blocked | Deployer | [Azure Diagnostic Settings 409 Conflict](#azure-diagnostic-settings-409-conflict) | ✅ |
| 🟢 Low | Deployer | [Deprecated Code Cleanup](#deprecated-code-cleanup) | ✅ |
| 🟢 Low | Deployer | [Azure API Helper Functions](#azure-api-helper-functions) | ✅ |
| 🟢 Low | Deployer | [Event Checker Azure Support](#event-checker-azure-support) | ✅ |
| 🟢 Low | Deployer | [Template Processor Cleanup](#template-processor-cleanup) | ✅ |
| 🟢 Low | Deployer | [Codebase Refactoring — Monolith Reduction (Deployer)](#codebase-refactoring--monolith-reduction-deployer) | ✅ |
| 🟢 Low | Deployer | [Performance Improvements](#performance-improvements) | ✅ |
| 🟢 Low | Backend | [Security Enhancements — Credential Management](#security-enhancements--credential-management) | ✅ |
| 🟢 Low | Backend | [Auto-Generated Encryption Keys](#auto-generated-encryption-keys) | ✅ |
| 🟢 Low | Full Stack | [Codebase Refactoring — Monolith Reduction (Flutter)](#codebase-refactoring--monolith-reduction-flutter) | ✅ |
| Ongoing | Deployer | [Documentation](#documentation) | ✅ |
| 🟡 Medium | Optimizer | [Tiered Pricing for Additional Services](#tiered-pricing-for-additional-services) | ❌ |

---

# 3-cloud-deployer

## ProjectStorage Abstraction Layer

**Status:** Planned — [detailed implementation plan](plans/project_storage_abstraction.md)

Introduce a `ProjectStorage` protocol that abstracts all per-project file I/O. Implement `FileSystemStorage` (wrapping current behavior, zero functional change) and a stub `DatabaseStorage` (`NotImplementedError`). Enables switching storage backends by changing a single line in `dependencies.py`.

**Scope:** 31 files (3 new, 28 modified) across 7 phases.

---

## L0 Glue Layer Conditional Deployment Optimization

> [!CAUTION]
> Current implementation deploys empty L0 Function Apps even in single-cloud scenarios.

**Status:** Needs Implementation

L0 Glue Layer deploys whenever a provider appears in **any** layer, even when no cross-cloud communication is needed.

**Fix:** Add granular boundary detection locals in `main.tf`:

| L0 Function | Deploy When |
|-------------|-------------|
| `ingestion` | L1 ≠ L2 |
| `hot-writer` | L2 ≠ L3 Hot |
| `cold-writer` | L3 Hot ≠ L3 Cold |
| `archive-writer` | L3 Cold ≠ L3 Archive |
| `hot-reader` | L4 ≠ L3 Hot |

**Files:** `main.tf`, `aws_glue.tf`, `azure_glue.tf`, `gcp_glue.tf`, optionally `tfvars_generator.py`

---

## Deploy API Return Value Enhancement

**Status:** Planned

`deploy_all()` only returns Terraform outputs. Post-deployment SDK operations log warnings on failure but don't report status in the return value.

**Proposed:** Return structured result including SDK operation status alongside Terraform outputs.

**Files:** `deployer_strategy.py`, `azure_deployer.py`, `aws_deployer.py` (~1–2 days)

---

## Observability Variables API Wiring

> [!NOTE]
> Observability implementation (Jan 2026) added Terraform variables with hardcoded defaults. Variables NOT exposed via API or config.json yet.

**Status:** Not Implemented

4 Terraform variables (`enable_aws_logging`, `enable_azure_logging`, `enable_gcp_logging`, `log_retention_days`) are always enabled with 7-day retention. Need wiring through `tfvars_generator.py` and optionally a Flutter UI toggle.

---

## Multi-User Grafana Provisioning (N Users)

> [!NOTE]
> Current implementation supports **single admin user** per cloud.

**Status:** Documented, Not Implemented

Extend Grafana provisioning from single admin to N users with roles (Admin, Editor, Viewer). AWS creates users in IAM Identity Center; Azure looks up existing Entra ID users. Config evolves to `users[]` array.

**Effort:** ~3–4 days

---

## Grafana Dashboard & Datasource Automation via Terraform

**Status:** Research Complete (Dec 2024), Not Implemented

Use Terraform Grafana Provider to automate dashboard/datasource creation in AWS Managed Grafana.

---

## Automated IAM Identity Center (SSO) Setup

**Status:** Research Complete (Dec 2024), Not Implemented

AWS Managed Grafana requires IAM Identity Center (currently manual). The `sso-admin` SDK can create instances programmatically. Constraint: one instance per AWS account, region-specific.

**Effort:** ~0.5 day

---

## Terraform String Consolidation (Phases 3–4)

> [!NOTE]
> Phases 1 (Auth/Routing) and 2 (API Paths) completed January 2026.

**Status:** Deferred (Post-Thesis)

- **Phase 3 — Storage Names:** ~19 occurrences, ~3–4 hours
- **Phase 4 — Layer Suffixes:** ~40+ occurrences, ~10–12 hours

---

## Legacy globals.py Cleanup

> [!WARNING]
> `src/globals.py` contains deprecated config loading patterns that bypass `config_loader.py`.

**Status:** Pending

Global mutable state anti-pattern. 18 importers (mostly for `logger_proxy`). High-risk churn.

- [ ] Audit all usages of `globals.py` functions
- [ ] Migrate callers to `DeploymentContext`
- [ ] Deprecate and remove `globals.py`

---

## Unified Config Loading via Context

**Status:** Architectural Improvement

Multiple subsystems load configs independently. Should unify to `config_loader.py` as single source of truth via `ProjectConfig`.

**Effort:** ~3–4 days

---

## Azure Diagnostic Settings 409 Conflict

> [!CAUTION]
> Causes intermittent E2E test failures.

**Status:** Blocked / Under Investigation

Terraform gets 409 conflicts for EventGrid and Storage diagnostic settings after a run with cleanup disabled left orphaned settings.

**Recommended fix:** Comment out problematic resources — function logs captured via App Insights anyway.

**References:** [GitHub #15734](https://github.com/hashicorp/terraform-provider-azurerm/issues/15734), [GitHub #23453](https://github.com/hashicorp/terraform-provider-azurerm/issues/23453)

---

## Deprecated Code Cleanup

**Status:** Pending

- [ ] Audit for remaining SDK deployment methods that should be Terraform-only

---

## Azure API Helper Functions

**Status:** Partially Missing

`src/api/deployment.py` helper dispatcher functions only support AWS. Most handled by Terraform for Azure. Only `_deploy_init_values()` might need Azure implementation.

---

## Event Checker Azure Support

**Status:** Not Implemented

Event checker redeployment only supports AWS. **File:** `src/providers/deployer.py:267`

---

## Template Processor Cleanup

**Status:** Not Implemented

Built-in default processors at `src/providers/*/default-processor/` contain full boilerplate; should only contain `process(event)` function.

---

## Codebase Refactoring — Monolith Reduction (Deployer)

> [!NOTE]
> Phase 1 partially complete (Jan 2026). TODO comments added.

**Status:** Deferred

| File | Lines | Suggested Extraction |
|------|-------|---------------------|
| `validation.py` | 1377 | Domain-specific modules |
| `functions.py` | 1115 | Function discovery/upload/hash modules |
| `package_builder.py` | 1151 | Provider-specific bundlers |
| `core_deployer_aws.py` | 1636 | IoT/TwinMaker/Lambda/IAM Managers |

---

## Performance Improvements

- [ ] Parallel Terraform plan/apply for multi-cloud
- [ ] Cache hot path configs for faster status checks
- [ ] Optimize function package building

---

## Documentation

- [ ] Document multi-cloud configuration examples
- [ ] Add troubleshooting guide for common deployment issues
- [ ] Create video walkthrough of deployment process

---

# 2-twin2clouds (Cost Optimizer)

## Tiered Pricing for Additional Services

**Status:** In Progress — [GitHub #116](https://github.com/TVJunkie724/master-thesis/issues/116)

Provider-specific service tiering has been hardened incrementally. The
remaining blocker in this section is the transfer model:

| Service | Current Formula | Issue |
|---------|----------------|-------|
| Cross-cloud egress | Source-provider tier tables | Destination, region, route class, and network tier are not yet part of the selection key |

**Impact:** Source-only egress pricing can select the wrong route-specific rate.
It also repeats provider free allowances per segment and is added only after
greedy per-layer selection, which can select a non-optimal complete path.

Azure Digital Twins is no longer part of this item. Its official operation,
routed-message, and query-unit meters are normalized from 1K billing blocks to
per-unit prices; query units are workload consumption, not a pricing tier.
AWS IoT TwinMaker public rates and account pricing-plan semantics are handled
by the completed #115 implementation.

**Fix:** Implement the reviewed Phase 19
[`Route-Aware Transfer Pricing`](../2-twin2clouds/implementation_plans/2026-07-18_route_aware_transfer_pricing.md)
plan. Do not infer tier breakpoints for services whose official model is a flat
usage meter.

**Files:** `components/aws/twinmaker.py`, transfer route contracts,
`engine.py`, `formulas/core_formulas.py`

---

# twin2multicloud_backend

## Security Enhancements — Credential Management

**Status:** Documented

The thesis uses **Fernet symmetric encryption** with per-user, per-twin key derivation. Production recommendations:

| Option | Approach | Best For |
|--------|----------|----------|
| **1. Cloud Secrets Managers** | AWS Secrets Manager / Azure Key Vault / GCP Secret Manager | Recommended |
| **2. HashiCorp Vault** | Dynamic secrets, lease-based TTL, full audit | Enterprise |
| **3. IAM Role Assumption** | Zero-credential via STS AssumeRole / Workload Identity | Zero-trust |
| **4. OAuth/OIDC Delegation** | User authenticates directly to cloud providers | User-managed |

**Security Audit Checklist:**
- [ ] Master encryption key rotated from development value
- [ ] Key stored in secure secrets manager (not .env)
- [ ] TLS enabled for all API endpoints
- [ ] Rate limiting on credential endpoints
- [ ] Audit logging for credential operations

---

## Auto-Generated Encryption Keys

**Status:** Enhancement Documented

Auto-generate `ENCRYPTION_KEY` and `JWT_SECRET_KEY` on first startup, eliminating manual `.env` configuration. Keys persisted in `data/` with restrictive permissions (0o400).

**Files:** New `src/utils/key_manager.py`, update `src/config.py`, `.env.example`, `compose.yaml`

---

# Full Stack (Cross-Project)

## Requirements.txt Validation for User Functions

> [!NOTE]
> Deferred from Phase 1 (Jan 2026). Currently stored but not validated.

**Status:** Not Implemented

Flutter UI allows users to add `requirements.txt` to function blocks. Stored in database but **not validated** before deployment.

**Recommended approach:** Use Python `packaging` library for format parsing, skip PyPI check, add provider-specific warnings.

**Files:** `validation.py` (deployer), `deployer.py` (backend routes), `function_package_block.dart` (Flutter)

---

## Deployment File Generation from Database

**Status:** Not Implemented

Generate complete deployment-ready ZIP from stored database content (Python code, requirements.txt, state machines, configs).

**Endpoint:** `POST /twins/{id}/generate-deployment`

**Effort:** ~6 hours

---

## Codebase Refactoring — Monolith Reduction (Flutter)

**Status:** Deferred

| File | Lines | Suggested Extraction |
|------|-------|---------------------|
| `wizard_bloc.dart` | 1437 | `WizardSaveService` |
| `step3_deployer.dart` | 1265 | L1-L5 Section widgets |

**Completed:** `twins.py` reduced 2065→837 lines, `wizard_bloc.dart` extracted `WizardInitService`/`WizardZipService`.

---

## Priority Order

> ProjectStorage Abstraction > L0 Optimization > Deploy API Enhancement > N-User Grafana > SSO Automation > Config Unification > Codebase Refactoring > Legacy Cleanup > Security Enhancements
