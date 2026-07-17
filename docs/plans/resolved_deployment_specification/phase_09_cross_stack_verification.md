# Phase 9: Cross-Stack Drift Gate

**Issue:** [#128](https://github.com/TVJunkie724/master-thesis/issues/128)  
**Status:** Reviewed and implementation-ready  
**Blocked by:** #120, #127, #129, #130, #131, #132, #133, #134

## Target

Provide one deterministic, credential-free command that proves deployment
selection continuity without creating cloud resources.

## Verification Flow

```text
fixed workload and catalog references
  -> Optimizer calculation
  -> schema and digest assertion
  -> Management persistence and selection
  -> package/manifest creation
  -> Deployer preflight
  -> generated tfvars
  -> Terraform source/plan fixture assertion
```

## Scenario Matrix

- all-AWS supported path;
- all-Azure supported path;
- mixed AWS/Azure/GCP path with Azure or AWS L4/L5;
- Azure IoT Hub F1, S1, S2, and S3 capacity cases;
- AWS Deep Archive path;
- GCP Archive path;
- standard versus mover function runtime profiles;
- legacy, missing, altered, unknown-version, unknown-value, provider-mismatch,
  and digest-mismatch negatives.

## Gates

- full safe Optimizer suite and static analysis;
- full safe Management API suite, migration tests, and Bandit;
- full safe Deployer suite, Ruff, Bandit, compile, and Terraform validate;
- Flutter analyze, tests, demo tests, and Web/all-desktop build checks;
- strict MkDocs and Compose configuration;
- repository scan for secret-like specification fields and stale hardcoded
  deployment values.

No live provider API, Terraform apply, simulator E2E, or billable resource is
allowed.

The gate must be implemented as a repository script using existing project test
commands. It may start the local Docker services with OrbStack, but it must use
fixed local catalog fixtures and must not contact cloud control planes.

## Documentation

Update:

- canonical architecture/data-flow docs;
- Optimizer result and extension contract;
- Management persistence/selection behavior;
- Deployer manifest/preflight/tfvars behavior;
- provider deployment matrices;
- user-facing deployment review guide;
- refactoring roadmap and issue status;
- thesis-method evidence explaining why cost-to-deployment reproducibility is a
  validity requirement.

## Definition of Done

- [ ] One documented command runs the complete no-apply drift gate.
- [ ] Every positive and negative scenario has hard value assertions.
- [ ] All safe project, static-analysis, docs, Compose, and platform gates pass.
- [ ] Two independent review passes report no unresolved finding.
- [ ] Every child issue is closed with commit and verification evidence.
- [ ] Parent #118 and the refactoring roadmap are updated and closed.
- [ ] Only then may repository architecture Phase 8 implementation begin.
