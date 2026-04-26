# Documentation Migration Matrix

This matrix tracks how the original service-local documentation maps into the curated `docs-site/` documentation. The goal is not a blind copy. Each source is either migrated, partially migrated, rewritten into a new target page, preserved as reference material, or treated as historical/internal material.

Status values:

- **Migrated**: the relevant content is already present in `docs-site/`.
- **Partial**: core ideas are present, but detail still needs migration.
- **Rewrite**: useful content exists, but it must be re-authored for the integrated thesis platform.
- **Superseded**: content should not become current documentation.
- **Preserve**: keep as reference material until a validated target exists.

## Twin2Clouds Sources

| Source | Target | Status | Decision |
|--------|--------|--------|----------|
| `2-twin2clouds/docs/docs-overview.html` | `index.md`, `components/optimizer.md`, `references/index.md` | Partial | Overview concepts are represented, but detailed entry cards are not copied. |
| `2-twin2clouds/docs/docs-setup-usage.html` | `developer-guide/setup.md`, `api/index.md` | Partial | Rewrite around the integrated stack instead of the old standalone optimizer setup. |
| `2-twin2clouds/docs/docs-architecture.html` | `architecture/platform-overview.md`, `components/optimizer.md` | Partial | Diagrams and layer model are migrated; detailed service rationale still needs review. |
| `2-twin2clouds/docs/docs-project-structure.html` | `developer-guide/project-structure.md` | Migrated | Diagram and repository-level explanation are present. |
| `2-twin2clouds/docs/docs-testing.html` | `developer-guide/testing.md` | Partial | Test categories are migrated; detailed commands and examples can be expanded later. |
| `2-twin2clouds/docs/docs-api-reference.html` | `api/index.md` | Rewrite | Current contract should be generated from or checked against the running FastAPI service. |
| `2-twin2clouds/docs/docs-credentials-setup.html` | `cloud-setup/index.md` | Partial | Keep only credential model; rewrite provider steps after credentials SSOT is designed. |
| `2-twin2clouds/docs/docs-credentials-aws.html` | `cloud-setup/index.md`, future AWS setup page | Rewrite | Pricing-only permissions are useful, but must not be confused with deployer permissions. |
| `2-twin2clouds/docs/docs-credentials-azure.html` | `cloud-setup/index.md`, future Azure setup page | Rewrite | Azure pricing access differs from deployment access; separate these clearly. |
| `2-twin2clouds/docs/docs-credentials-gcp.html` | `cloud-setup/index.md`, future GCP setup page | Rewrite | GCP pricing/project setup should be reconciled with deployer bootstrap flow. |
| `2-twin2clouds/docs/docs-aws-pricing.html` | future optimizer pricing page | Rewrite | Preserve formulas and schema ideas, but verify against current code first. |
| `2-twin2clouds/docs/docs-azure-pricing.html` | future optimizer pricing page | Rewrite | Preserve pricing source notes and formula mapping after code validation. |
| `2-twin2clouds/docs/docs-google-pricing.html` | future optimizer pricing page | Rewrite | Preserve GCP pricing notes after checking current fetcher behavior. |
| `2-twin2clouds/docs/docs-formulas.html` | future optimizer formulas page | Rewrite | Important thesis material; should be carefully migrated with current formulas. |
| `2-twin2clouds/docs/docs-calculation-logic.html` | future optimizer calculation page | Rewrite | Decision graph and calculation logic need a proper current-state explanation. |
| `2-twin2clouds/docs/optimization_logic_v2.md` | future optimizer calculation page | Rewrite | Likely high-value thesis explanation; migrate after validating `engine.py`. |
| `2-twin2clouds/docs/calculation_logic_and_changes.md` | future optimizer calculation page or issue notes | Preserve | Session-specific changes should be folded into final logic docs only if still true. |
| `2-twin2clouds/docs/high_l3_cost_investigation.md` | future optimizer limitations/evaluation page | Preserve | Keep as investigation input; do not publish as current fact without validation. |
| `2-twin2clouds/docs/docs-patterns.html` and `docs-pattern-*.html` | future optimizer internals page | Rewrite | Useful for developer onboarding if patterns still match the code. |
| `2-twin2clouds/docs/docs-ui-guide.html` | none or historical note | Superseded | Old web UI is not the thesis UI; current UI is Flutter. |
| `2-twin2clouds/docs/docs-future-work.html` | GitHub Issues/Milestones | Superseded | Active future work belongs in GitHub, not published as a parallel backlog. |
| `2-twin2clouds/docs/docs-nav.html` | `mkdocs.yml` | Superseded | Navigation structure was used as migration input only. |
| `2-twin2clouds/docs/references/EDT_25__CloudDT_engineering.pdf` | `references/EDT_25__CloudDT_engineering.pdf` | Migrated | Preserved in central references. |
| `2-twin2clouds/docs/references/*.png` | `references/diagrams/` and contextual pages | Migrated | Architecture, provider mapping, project structure, and testing diagrams are copied and used in relevant pages. |
| `2-twin2clouds/docs/references/aws_pricing_policy.json` | future cloud setup/bootstrap reference | Preserve | Keep until least-privilege setup is rewritten and verified. |

## Cloud Deployer Sources

| Source | Target | Status | Decision |
|--------|--------|--------|----------|
| `3-cloud-deployer/docs/docs-overview.html` | `components/deployer.md`, `architecture/project-background.md` | Partial | Core role is migrated; old quick navigation is not copied. |
| `3-cloud-deployer/docs/docs-setup-usage.html` | `developer-guide/setup.md`, `runtime/index.md` | Partial | Current setup is documented at repo level; old standalone CLI/API setup needs rewrite. |
| `3-cloud-deployer/docs/docs-architecture.html` | `components/deployer.md`, `architecture/platform-overview.md` | Partial | Provider/layer ideas are present; naming and resource conventions still need migration. |
| `3-cloud-deployer/docs/docs-api-reference.html` | `api/index.md` | Rewrite | Legacy layer and Lambda endpoints must not be published as canonical app contracts. |
| `3-cloud-deployer/docs/docs-cli-reference.html` | none or historical note | Superseded | CLI is not the primary integrated thesis workflow. |
| `3-cloud-deployer/docs/docs-credentials-setup.html` | `cloud-setup/index.md` | Partial | Credential categories are present; detailed provider bootstrap remains. |
| `3-cloud-deployer/docs/docs-credentials-aws.html` | future AWS setup page | Rewrite | Keep IAM/Grafana notes, but align with Cloud Connections and least privilege. |
| `3-cloud-deployer/docs/docs-credentials-azure.html` | future Azure setup page | Rewrite | Preserve service principal and role material after validating current Azure path. |
| `3-cloud-deployer/docs/docs-credentials-gcp.html` | future GCP setup page | Rewrite | Split private account and organization setup explicitly. |
| `3-cloud-deployer/docs/docs-credentials-gcp-private.html` | future GCP setup page | Rewrite | Useful path for existing-project setup. |
| `3-cloud-deployer/docs/docs-credentials-gcp-org.html` | future GCP setup page | Rewrite | Useful path for organization/project-creation setup. |
| `3-cloud-deployer/docs/docs-configuration.html` | future deployer configuration page | Rewrite | Configuration should be described through manifest/template boundaries. |
| `3-cloud-deployer/docs/docs-config-core.html` | future deployer configuration page | Rewrite | Migrate only after current config schema is stabilized. |
| `3-cloud-deployer/docs/docs-config-credentials.html` | future Cloud Connections setup page | Rewrite | Current credential-file model is transitional. |
| `3-cloud-deployer/docs/docs-config-iot.html` | future deployer configuration page | Rewrite | Preserve IoT/hierarchy schema after validating current deployer expectations. |
| `3-cloud-deployer/docs/docs-design-patterns.html` and `docs-pattern-*.html` | future deployer internals page | Rewrite | Useful if Strategy/Provider/DI/Registry still describe current code. |
| `3-cloud-deployer/docs/docs-aws-deployment.html` | future AWS deployment page | Rewrite | High-value content; verify resource list, permissions, and Terraform path first. |
| `3-cloud-deployer/docs/docs-azure-deployment.html` | future Azure deployment page | Rewrite | High-value content; verify Function hosting and role model first. |
| `3-cloud-deployer/docs/docs-gcp-deployment.html` | future GCP deployment page | Rewrite | High-value content; keep GCP limitations visible. |
| `3-cloud-deployer/docs/docs-aws-user-functions.html` | `components/user-functions.md` | Partial | Pattern is migrated; packaging/security details still need targeted migration. |
| `3-cloud-deployer/docs/docs-azure-user-functions.html` | `components/user-functions.md` | Partial | Pattern is migrated; Blueprint and packaging details remain. |
| `3-cloud-deployer/docs/docs-gcp-user-functions.html` | `components/user-functions.md` | Partial | Pattern is migrated; IAM/packaging details remain. |
| `3-cloud-deployer/docs/user_functions_aws.md` | `components/user-functions.md` | Partial | Preserve as source for detailed AWS user-function page. |
| `3-cloud-deployer/docs/user_functions_azure.md` | `components/user-functions.md` | Partial | Preserve as source for detailed Azure user-function page. |
| `3-cloud-deployer/docs/user_functions_gcp.md` | `components/user-functions.md` | Partial | Preserve as source for detailed GCP user-function page. |
| `3-cloud-deployer/docs/docs-multi-cloud.html` | future multi-cloud architecture page | Rewrite | Important thesis material; needs careful integration with current cross-cloud behavior. |
| `3-cloud-deployer/docs/docs-iot-simulator.html` | future user/developer workflow page | Rewrite | Useful for demos and verification once simulator flow is stable. |
| `3-cloud-deployer/docs/docs-testing.html` | `developer-guide/testing.md` | Partial | Risk boundary is migrated; detailed mocked/E2E structure can be expanded. |
| `3-cloud-deployer/docs/docs-twin2clouds-integration.html` | `architecture/project-background.md`, `api/index.md` | Partial | Integration concept is present; example mappings need current contract review. |
| `3-cloud-deployer/docs/processor_dataflow.md` | future deployer/user-functions internals page | Rewrite | Useful implementation detail; validate current processor wrappers first. |
| `3-cloud-deployer/docs/azure-functions-python-blueprints.md` | future Azure user-functions page | Rewrite | High-value Azure-specific deployment note. |
| `3-cloud-deployer/docs/azure_flex_consumption_migration.md` | future Azure setup/limitations page | Preserve | Keep as cautionary material; do not present migration as current plan. |
| `3-cloud-deployer/docs/hardcoded_configurations.md` | future runtime/configuration page or GitHub Issues | Preserve | Use to drive cleanup; avoid publishing stale constants as design. |
| `3-cloud-deployer/docs/future-work-resolved.md` | GitHub Issues/Milestones or historical note | Superseded | Resolved backlog should not define current docs. |
| `3-cloud-deployer/docs/gap-analysis-guide.md` | internal audit workflow or GitHub issue notes | Superseded | Useful for agents, not thesis/developer product documentation. |
| `3-cloud-deployer/docs/ai-layer-implementation-guide.md` | internal agent process only | Superseded | Do not publish as project documentation. |
| `3-cloud-deployer/docs/e2e_handoff.md` | GitHub Issues/Milestones or historical note | Superseded | Handoff content should become issues if still relevant. |
| `3-cloud-deployer/docs/implementation-plans/*.md` | GitHub Issues/Milestones or historical archive | Superseded | Implementation plans are historical, not current docs. |
| `3-cloud-deployer/docs/docs-nav.html` | `mkdocs.yml` | Superseded | Navigation structure was used as migration input only. |
| `3-cloud-deployer/docs/references/EDT_25__CloudDT_engineering.pdf` | `references/EDT_25__CloudDT_engineering.pdf` | Migrated | Central copy is preserved. |
| `3-cloud-deployer/docs/references/bachelor_digital_twins.pdf` | `references/bachelor_digital_twins.pdf` | Migrated | Central copy is preserved. |
| `3-cloud-deployer/docs/references/aws_deployer_policy.json` | future AWS setup/bootstrap reference | Preserve | Keep until least-privilege AWS setup is verified. |
| `3-cloud-deployer/docs/references/azure_custom_role.json` | future Azure setup/bootstrap reference | Preserve | Keep until Azure role bootstrap is verified. |
| `3-cloud-deployer/docs/references/azure_deployer_policy.json` | future Azure setup/bootstrap reference | Preserve | Keep until Azure role model is verified. |
| `3-cloud-deployer/docs/references/azure_role_assignment.json` | future Azure setup/bootstrap reference | Preserve | Keep as setup input, not prose documentation. |
| `3-cloud-deployer/docs/references/gcp_custom_role.yaml` | future GCP setup/bootstrap reference | Preserve | Keep until GCP least-privilege bootstrap is verified. |
| `3-cloud-deployer/docs/references/setup_azure_role.sh` | future Azure setup/bootstrap reference | Preserve | Keep script as source material; validate before documenting as canonical. |

## Next Migration Order

1. Project setup and runtime model.
2. Credentials and provider bootstrap.
3. Provider deployment guides for AWS, Azure, and GCP.
4. Optimizer formulas, calculation logic, and pricing schemas.
5. API contracts generated from or validated against the running services.
6. Multi-cloud behavior and user-function internals.
7. Simulator and demo workflows.
