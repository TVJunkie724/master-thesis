# Phase 4: Deployer Preflight and Typed tfvars

**Issue:** [#131](https://github.com/TVJunkie724/master-thesis/issues/131)  
**Status:** Done
**Blocked by:** #127, #130

## Target

The Deployer validates DeploymentManifest v2 and translates only allowlisted
`deployable_selection` dimensions into Terraform variables. Validation occurs
during archive staging, before package acquisition, bundling, workspace state,
or Terraform execution.

## Implementation

1. Require DeploymentManifest v2 for new deployment operations.
2. Parse the v1 specification with a dedicated domain module.
3. Recompute the canonical digest and verify the manifest binding.
4. Verify all seven selected provider slots against `config_providers.json`.
5. Verify exact component cardinality and allowed values against the canonical
   dimension registry adapter.
6. Reject all `terraform_target` fields on non-deployable classifications.
7. Implement a pure translation function:

```text
ResolvedDeploymentSpecification
  -> DeploymentTerraformVariables
  -> JSON-compatible scalar tfvars
```

8. Merge typed deployment tfvars only after all existing configuration,
   credential, and capability validations succeed.
9. Remove defaults for specification-owned variables. Missing values must not
   fall back to Terraform.

## Required File Boundaries

| Area | Files |
| --- | --- |
| Package validation | `src/validation/core.py`, ZIP/directory validators |
| Manifest loading | `src/core/config_loader.py`, `src/core/context.py` |
| Domain validation | new `src/deployment_specification/` package |
| Translation | focused translator consumed by `src/tfvars_generator.py` |
| API errors | deployment and validation routes plus shared error handlers |
| Contract copies | generated contract files under `src/contracts/generated/` |
| Tests | validation aggregation, config loader, context, tfvars, and deployment route suites |

`tfvars_generator.py` remains orchestration. Schema parsing, semantic validation,
and translation must not be implemented as nested ad hoc dictionary logic.

## Error Contract

Use bounded stable errors:

- unsupported manifest/specification version;
- missing/incomplete specification;
- digest mismatch;
- provider mismatch;
- unsupported component/dimension/value;
- contradictory or duplicate target;
- legacy package not deployable.

API responses expose codes and safe component IDs, not archive content,
credentials, Terraform command lines, or provider payloads.

## Tests

- ZIP and directory accessors accept the same valid fixtures;
- all negative canonical fixtures fail before tfvars generation;
- provider aliases normalize only at the existing boundary;
- every deployable dimension maps to exactly one typed tfvar;
- usage/account/assumption dimensions map to none;
- deterministic output independent of input object order;
- operation package is discarded safely after validation failure;
- deployment API returns stable redacted errors.

## Definition of Done

- [x] Validation finishes before workspace or Terraform side effects.
- [x] Every canonical negative fixture returns a stable redacted failure.
- [x] Every deployable dimension maps to exactly one typed tfvar.
- [x] Non-deployable dimensions map to no tfvar.
- [x] Deployer full safe tests, Ruff, Bandit, compile, and contract synchronization pass.
- [x] #131 is closed with commit and verification evidence.

## Implemented State

- `src/deployment_specification/` owns generated-contract loading, canonical
  digest verification, closed-world semantic validation, and pure tfvars
  translation.
- Operation package staging requires `DeploymentManifest 2.0` and validates
  the exact archive before creating the private package root.
- Deployment, destruction, and detailed drift checks use the validated
  credential-bearing operation package. Durable project definitions remain
  secret-free.
- `tfvars_generator.py` merges only collision-free, allowlisted
  `deployable_selection` targets and writes the generated file atomically with
  owner-only permissions.
- Invalid versions, package inventories, specification digests, provider
  bindings, components, dimensions, and targets fail with stable bounded error
  codes that do not expose archive or credential content.

## Verification Evidence

```text
service quality gate: passed
pytest: 1551 passed, 1 skipped
ruff: passed
bandit: passed
compileall: passed
pip check: passed
contract sync: generated copies valid and byte-identical
MkDocs strict build: passed
OpenAPI snapshot export: passed
```
