# Repository Hygiene Cleanup Plan

**Datum:** 2026-04-26
**Scope:** Repository root, `3-cloud-deployer`, `2-twin2clouds`, docs, historical plans, runtime artifacts
**Status:** Cleanup-Plan / Inventory

---

## 1. Ziel

Dieses Dokument legt fest, was bei der Repository-Hygiene-Phase konkret ausgemistet, migriert, archiviert oder behalten wird.

Es ist bewusst ein Plan, keine sofortige Loeschliste. Jeder Eintrag bekommt vor Umsetzung eine technische Verifikation, damit keine aktive Vorlage, kein Test-Fixture und kein noch benoetigter Deployment-Bestandteil versehentlich entfernt wird.

---

## 2. Entscheidungen

| Entscheidung | Bedeutung |
|--------------|-----------|
| keep | bleibt im aktiven Produktpfad |
| migrate | wird in eine neue Zielstruktur verschoben oder in MkDocs ueberfuehrt |
| archive | bleibt als historische Referenz, aber nicht als aktive Quelle |
| delete | wird entfernt; bei ignorierten lokalen Dateien ohne Git-Historie reicht lokale Bereinigung |

---

## 3. Reihenfolge

1. Inventar einfrieren und diesen Plan reviewen.
2. MkDocs-Grundstruktur anlegen.
3. HTML-Dokumentation nach Markdown/MkDocs migrieren oder archivieren.
4. `upload/template` als Deployment-Vorlage sichern und von Runtime trennen.
5. Runtime-Artefakte aus `upload/` entfernen oder ignoriert halten.
6. Historische Implementation Plans archivieren.
7. README-Dateien auf kurze Einstiegspunkte reduzieren.
8. Guardrails einfuehren: keine echten Credentials, keine Terraform State Files, keine Runtime-ZIPs in aktiven Pfaden.

---

## 4. Keep

Diese Dateien/Strukturen bleiben aktive Quellen:

- `ASSESSMENT.md`
- `README.md`
- `ONBOARDING.md`
- `FRONTEND_ARCHITECTURE.md`
- `integration_vision.md`
- `docs/plans/2026-04-26_repository_hygiene_documentation_architecture.md`
- `docs/plans/2026-04-26_repository_hygiene_cleanup_plan.md`
- `docs/plans/2026-04-26_runtime_credentials_deployment_state_hardening.md`
- `twin2multicloud-latex/**` as the active thesis source
- `EDT_25__CloudDT_engineering.pdf` and referenced copies under service docs as the EDTConf'25 paper source
- `3-cloud-deployer/docs/references/bachelor_digital_twins.pdf` as referenced Deployer thesis source
- `3-cloud-deployer/implementation_plans/2026-04-24_14-40_deployer_architecture_canonicalization.md`
- `3-cloud-deployer/implementation_plans/2026-04-25_16-11_deployer_contract_hardening.md`
- `twin2multicloud_backend/implementation_plans/2026-04-26_10-18_backend_orchestrator_disentanglement.md`
- `3-cloud-deployer/upload/template/**` only as current canonical deployment template until migrated
- `.codex/skills/**` project-specific Codex skills
- `.agent/workflows/**` until the team explicitly decides to replace them with `.codex/skills`

---

## 5. Migrate

### 5.1 Deployment Template

Move the tracked template source from:

```text
3-cloud-deployer/upload/template/
```

to:

```text
3-cloud-deployer/templates/deployment_project/
```

Tracked template contents to migrate:

```text
3-cloud-deployer/upload/template/azure_functions/event-feedback/function_app.py
3-cloud-deployer/upload/template/azure_functions/event-feedback/requirements.txt
3-cloud-deployer/upload/template/azure_functions/event_actions/high-temperature-callback-2/function_app.py
3-cloud-deployer/upload/template/azure_functions/event_actions/high-temperature-callback-2/requirements.txt
3-cloud-deployer/upload/template/azure_functions/event_actions/high-temperature-callback/function_app.py
3-cloud-deployer/upload/template/azure_functions/event_actions/high-temperature-callback/requirements.txt
3-cloud-deployer/upload/template/azure_functions/processors/default_processor/function_app.py
3-cloud-deployer/upload/template/azure_functions/processors/default_processor/requirements.txt
3-cloud-deployer/upload/template/azure_functions/processors/pressure-sensor-1/function_app.py
3-cloud-deployer/upload/template/azure_functions/processors/pressure-sensor-1/requirements.txt
3-cloud-deployer/upload/template/azure_functions/processors/temperature-sensor-1/function_app.py
3-cloud-deployer/upload/template/azure_functions/processors/temperature-sensor-1/requirements.txt
3-cloud-deployer/upload/template/azure_functions/processors/temperature-sensor-2/function_app.py
3-cloud-deployer/upload/template/azure_functions/processors/temperature-sensor-2/requirements.txt
3-cloud-deployer/upload/template/cloud_functions/event-feedback/main.py
3-cloud-deployer/upload/template/cloud_functions/event-feedback/requirements.txt
3-cloud-deployer/upload/template/cloud_functions/event_actions/high-temperature-callback-2/main.py
3-cloud-deployer/upload/template/cloud_functions/event_actions/high-temperature-callback-2/requirements.txt
3-cloud-deployer/upload/template/cloud_functions/event_actions/high-temperature-callback/main.py
3-cloud-deployer/upload/template/cloud_functions/event_actions/high-temperature-callback/requirements.txt
3-cloud-deployer/upload/template/cloud_functions/processors/default_processor/main.py
3-cloud-deployer/upload/template/cloud_functions/processors/default_processor/requirements.txt
3-cloud-deployer/upload/template/cloud_functions/processors/pressure-sensor-1/main.py
3-cloud-deployer/upload/template/cloud_functions/processors/pressure-sensor-1/requirements.txt
3-cloud-deployer/upload/template/cloud_functions/processors/temperature-sensor-1/main.py
3-cloud-deployer/upload/template/cloud_functions/processors/temperature-sensor-1/requirements.txt
3-cloud-deployer/upload/template/cloud_functions/processors/temperature-sensor-2/main.py
3-cloud-deployer/upload/template/cloud_functions/processors/temperature-sensor-2/requirements.txt
3-cloud-deployer/upload/template/config.json
3-cloud-deployer/upload/template/config.json.example
3-cloud-deployer/upload/template/config_credentials.json.example
3-cloud-deployer/upload/template/config_events.json
3-cloud-deployer/upload/template/config_events.json.example
3-cloud-deployer/upload/template/config_inter_cloud.json
3-cloud-deployer/upload/template/config_iot_devices.json
3-cloud-deployer/upload/template/config_optimization.json
3-cloud-deployer/upload/template/config_providers.json
3-cloud-deployer/upload/template/config_user.json
3-cloud-deployer/upload/template/config_user.json.example
3-cloud-deployer/upload/template/iot_device_simulator/aws/config.json.example
3-cloud-deployer/upload/template/iot_device_simulator/azure/config.json.example
3-cloud-deployer/upload/template/iot_device_simulator/payloads.json
3-cloud-deployer/upload/template/lambda_functions/event-feedback/lambda_function.py
3-cloud-deployer/upload/template/lambda_functions/event_actions/high-temperature-callback-2/lambda_function.py
3-cloud-deployer/upload/template/lambda_functions/event_actions/high-temperature-callback/lambda_function.py
3-cloud-deployer/upload/template/lambda_functions/processors/default_processor/lambda_function.py
3-cloud-deployer/upload/template/lambda_functions/processors/pressure-sensor-1/lambda_function.py
3-cloud-deployer/upload/template/lambda_functions/processors/temperature-sensor-1/lambda_function.py
3-cloud-deployer/upload/template/lambda_functions/processors/temperature-sensor-2/lambda_function.py
3-cloud-deployer/upload/template/project_info.json
3-cloud-deployer/upload/template/scene_assets/README.md
3-cloud-deployer/upload/template/scene_assets/aws/scene.glb
3-cloud-deployer/upload/template/scene_assets/aws/scene.json
3-cloud-deployer/upload/template/scene_assets/azure/3DScenesConfiguration.json
3-cloud-deployer/upload/template/scene_assets/azure/home__room.glb
3-cloud-deployer/upload/template/scene_assets/azure/mini_room.glb
3-cloud-deployer/upload/template/scene_assets/azure/scene.glb
3-cloud-deployer/upload/template/scene_assets/azure/source.txt
3-cloud-deployer/upload/template/scene_assets/scene_preview.png
3-cloud-deployer/upload/template/state_machines/aws_step_function.json
3-cloud-deployer/upload/template/state_machines/azure_logic_app.json
3-cloud-deployer/upload/template/state_machines/google_cloud_workflow.yaml
3-cloud-deployer/upload/template/twin_hierarchy/aws_hierarchy.json
3-cloud-deployer/upload/template/twin_hierarchy/aws_hierarchy.json.example
3-cloud-deployer/upload/template/twin_hierarchy/aws_hierarchy_README.md
3-cloud-deployer/upload/template/twin_hierarchy/azure_hierarchy.json
3-cloud-deployer/upload/template/twin_hierarchy/azure_hierarchy_final.ndjson.example
```

Template migration guardrails:

- Real credential files are not migrated to the versioned template target.
- Current valid local admin credentials in `upload/template` are not deleted in this phase.
- Local credential files are never moved automatically. Local cloud tests use `.secrets/local/` after the operator manually copies or moves the needed files.
- `config_credentials.json.example` may remain as schema example until CloudConnection replaces file-based credentials.
- Deployer path resolution must read from `templates/deployment_project`, not from `upload/template`.
- `upload/` must become runtime-only after migration.

### 5.2 HTML Documentation To MkDocs

Create:

```text
docs-site/
  Dockerfile
  mkdocs.yml
  docs/
```

Reference PDFs are not legacy trash. Copy the currently referenced scientific sources into the Docs Site and keep stable links:

```text
docs-site/docs/references/EDT_25__CloudDT_engineering.pdf
docs-site/docs/references/bachelor_digital_twins.pdf
```

Existing copies may remain during transition:

```text
EDT_25__CloudDT_engineering.pdf
2-twin2clouds/docs/references/EDT_25__CloudDT_engineering.pdf
3-cloud-deployer/docs/references/EDT_25__CloudDT_engineering.pdf
3-cloud-deployer/docs/references/bachelor_digital_twins.pdf
```

After the Docs Site is canonical, duplicate PDF locations may be removed only after every documentation link points to `docs-site/docs/references/` and the files are verified to be identical. Do not delete the EDTConf'25 paper or the Deployer thesis PDF as part of generic documentation cleanup.

Migrate or rewrite these 57 HTML pages into Markdown pages in the MkDocs site.

`docs-site/` is the complete source tree for the published documentation site. The Docker container must mount and serve only `docs-site/`. Project-local documentation may remain as developer notes, historical originals or temporary duplicates, but it is not the published docs source of truth.

`2-twin2clouds/docs` HTML pages:

```text
2-twin2clouds/docs/docs-api-reference.html
2-twin2clouds/docs/docs-architecture.html
2-twin2clouds/docs/docs-aws-pricing.html
2-twin2clouds/docs/docs-azure-pricing.html
2-twin2clouds/docs/docs-calculation-logic.html
2-twin2clouds/docs/docs-credentials-aws.html
2-twin2clouds/docs/docs-credentials-azure.html
2-twin2clouds/docs/docs-credentials-gcp.html
2-twin2clouds/docs/docs-credentials-setup.html
2-twin2clouds/docs/docs-formulas.html
2-twin2clouds/docs/docs-future-work.html
2-twin2clouds/docs/docs-google-pricing.html
2-twin2clouds/docs/docs-nav.html
2-twin2clouds/docs/docs-overview.html
2-twin2clouds/docs/docs-pattern-component.html
2-twin2clouds/docs/docs-pattern-dataclass.html
2-twin2clouds/docs/docs-pattern-facade.html
2-twin2clouds/docs/docs-pattern-factory.html
2-twin2clouds/docs/docs-pattern-frontend.html
2-twin2clouds/docs/docs-pattern-protocol.html
2-twin2clouds/docs/docs-pattern-pure-functions.html
2-twin2clouds/docs/docs-patterns.html
2-twin2clouds/docs/docs-project-structure.html
2-twin2clouds/docs/docs-setup-usage.html
2-twin2clouds/docs/docs-testing.html
2-twin2clouds/docs/docs-ui-guide.html
```

`3-cloud-deployer/docs` HTML pages:

```text
3-cloud-deployer/docs/docs-api-reference.html
3-cloud-deployer/docs/docs-architecture.html
3-cloud-deployer/docs/docs-aws-deployment.html
3-cloud-deployer/docs/docs-aws-user-functions.html
3-cloud-deployer/docs/docs-azure-deployment.html
3-cloud-deployer/docs/docs-azure-user-functions.html
3-cloud-deployer/docs/docs-cli-reference.html
3-cloud-deployer/docs/docs-config-core.html
3-cloud-deployer/docs/docs-config-credentials.html
3-cloud-deployer/docs/docs-config-iot.html
3-cloud-deployer/docs/docs-configuration.html
3-cloud-deployer/docs/docs-credentials-aws.html
3-cloud-deployer/docs/docs-credentials-azure.html
3-cloud-deployer/docs/docs-credentials-gcp-org.html
3-cloud-deployer/docs/docs-credentials-gcp-private.html
3-cloud-deployer/docs/docs-credentials-gcp.html
3-cloud-deployer/docs/docs-credentials-setup.html
3-cloud-deployer/docs/docs-design-patterns.html
3-cloud-deployer/docs/docs-gcp-deployment.html
3-cloud-deployer/docs/docs-gcp-user-functions.html
3-cloud-deployer/docs/docs-iot-simulator.html
3-cloud-deployer/docs/docs-multi-cloud.html
3-cloud-deployer/docs/docs-nav.html
3-cloud-deployer/docs/docs-overview.html
3-cloud-deployer/docs/docs-pattern-di.html
3-cloud-deployer/docs/docs-pattern-provider.html
3-cloud-deployer/docs/docs-pattern-registry.html
3-cloud-deployer/docs/docs-pattern-strategy.html
3-cloud-deployer/docs/docs-setup-usage.html
3-cloud-deployer/docs/docs-testing.html
3-cloud-deployer/docs/docs-twin2clouds-integration.html
```

After migration, these HTML files are deleted or moved to `docs-site/docs/archive/html/` if exact historical rendering is still needed.

### 5.3 Markdown Documentation To MkDocs

Migrate or link these existing Markdown docs into the MkDocs navigation:

```text
ASSESSMENT.md
FRONTEND_ARCHITECTURE.md
integration_vision.md
docs/codebase_investigation_findings.md
docs/design_patterns_inventory.md
docs/future-work.md
docs/manual-steps-3d-scenes.md
docs/thesis_structure_proposal.md
docs/thesis_structure_review.md
documentation/concepts/CONCEPT_ENTERPRISE_TARGET_ARCHITECTURE.md
2-twin2clouds/docs/calculation_logic_and_changes.md
2-twin2clouds/docs/high_l3_cost_investigation.md
2-twin2clouds/docs/optimization_logic_v2.md
3-cloud-deployer/docs/ai-layer-implementation-guide.md
3-cloud-deployer/docs/azure-functions-python-blueprints.md
3-cloud-deployer/docs/azure_flex_consumption_migration.md
3-cloud-deployer/docs/e2e_handoff.md
3-cloud-deployer/docs/future-work-resolved.md
3-cloud-deployer/docs/gap-analysis-guide.md
3-cloud-deployer/docs/hardcoded_configurations.md
3-cloud-deployer/docs/processor_dataflow.md
3-cloud-deployer/docs/user_functions_aws.md
3-cloud-deployer/docs/user_functions_azure.md
3-cloud-deployer/docs/user_functions_gcp.md
twin2multicloud_backend/docs/TODO_infrastructure_deployment.md
twin2multicloud_backend/docs/enable-uibk-login.md
twin2multicloud_backend/docs/uibk-authentication.md
twin2multicloud_flutter/docs/TODO_infrastructure_deployment.md
```

---

## 6. Archive

### 6.1 Historical Implementation Plans

Archive these directories under a clearly marked historical area, for example:

```text
docs-site/docs/archive/implementation-plans/
```

or:

```text
docs/archive/implementation_plans/
```

Archive all old implementation plans except the current active 2026 plans listed in `Keep`.

Full archive set by directory:

```text
2-twin2clouds/implementation_plans/*.md
3-cloud-deployer/docs/implementation-plans/*.md
3-cloud-deployer/implementation_plans/2025-*.md
3-cloud-deployer/implementation_plans/PROPOSAL_MULTI_CLOUD.md
3-cloud-deployer/implementation_plans/roadmap_verification_report.md
twin2multicloud_backend/implementation_plans/SPRINT1_COMPLETE.md
twin2multicloud_backend/implementation_plans/sprint1_foundation.md
twin2multicloud_backend/implementation_plans/sprint2_wizard_step1.md
```

Keep active and do not archive:

```text
3-cloud-deployer/implementation_plans/2026-04-24_14-40_deployer_architecture_canonicalization.md
3-cloud-deployer/implementation_plans/2026-04-25_16-11_deployer_contract_hardening.md
twin2multicloud_backend/implementation_plans/2026-04-26_10-18_backend_orchestrator_disentanglement.md
```

### 6.2 Legacy Service-Specific Documentation

After MkDocs migration, archive or delete service-local docs that are no longer canonical:

```text
2-twin2clouds/docs/docs-*.html
3-cloud-deployer/docs/docs-*.html
```

Markdown files may remain only if they are active source files for MkDocs. Otherwise they move to the archive.

---

## 7. Delete

### 7.1 Runtime Upload Artifacts

Delete from the active repository/workspace:

```text
3-cloud-deployer/upload/digital-twin/
```

Observed local runtime contents include:

```text
3-cloud-deployer/upload/digital-twin/.build/
3-cloud-deployer/upload/digital-twin/.terraform_zips/
3-cloud-deployer/upload/digital-twin/config_credentials.json
3-cloud-deployer/upload/digital-twin/gcp_credentials.json
3-cloud-deployer/upload/digital-twin/terraform/generated.tfvars.json
3-cloud-deployer/upload/digital-twin/terraform/terraform.tfstate
3-cloud-deployer/upload/digital-twin/terraform/terraform.tfstate.backup
3-cloud-deployer/upload/digital-twin/versions/
```

These are generated deployment/runtime artifacts. They must not be used as canonical template or source state.

### 7.2 Local Real Credential Files

Do not delete these immediately and do not migrate them automatically. After verifying the local setup, the operator may manually copy or move the still-needed files to `.secrets/local/`:

```text
config_credentials.json
gcp_credentials.json
google-credentials.json
3-cloud-deployer/upload/template/config_credentials.json
3-cloud-deployer/upload/template/gcp_credentials.json
3-cloud-deployer/upload/template/google-credentials.json
```

These are ignored by Git, but they are still unsafe workspace state. The cleanup phase should not read or print their contents, and it should not remove them before the replacement test path is available.

### 7.3 Local OS / Build / Cache Artifacts

Delete locally and keep ignored:

```text
.DS_Store
3-cloud-deployer/.DS_Store
3-cloud-deployer/upload/.DS_Store
3-cloud-deployer/upload/template/.DS_Store
3-cloud-deployer/upload/template/azure_functions/.DS_Store
3-cloud-deployer/upload/template/cloud_functions/.DS_Store
3-cloud-deployer/upload/template/iot_device_simulator/.DS_Store
3-cloud-deployer/upload/template/lambda_functions/.DS_Store
3-cloud-deployer/upload/template/scene_assets/.DS_Store
3-cloud-deployer/upload/template/Archive.zip
twin2multicloud_flutter/.dart_tool/
twin2multicloud_flutter/macos/Pods/
**/__pycache__/
**/.pytest_cache/
```

### 7.4 README Legacy Blocks

Do not delete READMEs. Reduce them after MkDocs exists:

```text
README.md
2-twin2clouds/README.md
3-cloud-deployer/README.md
twin2multicloud_backend/DEVELOPMENT_GUIDE.md
twin2multicloud_flutter/README.md
```

Remove long legacy procedure sections from these files only after equivalent MkDocs pages exist.

---

## 8. Guardrails After Cleanup

Add checks that fail if any of these paths reappear:

```text
3-cloud-deployer/upload/*/terraform.tfstate
3-cloud-deployer/upload/*/terraform.tfstate.backup
3-cloud-deployer/upload/*/.build/
3-cloud-deployer/upload/*/.terraform_zips/
3-cloud-deployer/upload/*/versions/
3-cloud-deployer/upload/**/config_credentials.json
3-cloud-deployer/upload/**/gcp_credentials.json
3-cloud-deployer/upload/**/google-credentials.json
config_credentials.json
gcp_credentials.json
google-credentials.json
```

Add checks that warn if new service-local HTML docs are introduced:

```text
2-twin2clouds/docs/*.html
3-cloud-deployer/docs/*.html
```

After MkDocs is canonical, all new published documentation should be Markdown under `docs-site/docs/`. Project-local docs can remain as developer notes or transition duplicates, but the published website must not read from scattered project directories.

---

## 9. First Implementation Batch

The first cleanup implementation should be small and reversible:

1. Add `docs-site/` with MkDocs skeleton and Dockerfile.
2. Add docs landing pages for Architecture, Cloud Setup, Runtime, Deployer, Optimizer, Backend and Flutter.
3. Move no template files yet; only document target paths and add readme notes.
4. Add a non-destructive repo hygiene check that reports forbidden artifacts.
5. Run the check and review its output before deleting anything.

The second batch can migrate `upload/template` to `templates/deployment_project` once all code references are known and tests cover the new path.
