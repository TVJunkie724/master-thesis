# Phase 5: AWS Terraform Alignment

**Issue:** [#132](https://github.com/TVJunkie724/master-thesis/issues/132)
**Status:** Completed
**Blocked by:** #61, #131

## Target

AWS Terraform consumes specification-owned variables for every deployable cost
assumption while preserving account-scoped and progressive pricing semantics as
evidence only.

## Implementation

- Add typed validated variables for standard and mover Lambda memory.
- Bind the hot-to-cool and cool-to-archive transition runtime schedules and
  memory values from their source-owned transition components.
- Verify the EventBridge Scheduler/EventBridge trigger pricing source and ensure
  the trigger contribution used by the Optimizer matches the deployed trigger.
- Apply the standard profile to dispatcher, connector, ingestion, processing,
  reader, event, TwinMaker connector, and glue Lambdas.
- Apply the mover profile only to lifecycle mover Lambdas.
- Assert both transition Lambdas and trigger rules are enabled by the source
  storage provider, never by the destination storage provider.
- Add validated DynamoDB billing mode.
- Add validated S3 cool and archive storage classes.
- Pass both storage classes into every local and cross-cloud AWS writer/mover;
  runtime code must not retain independent storage-class literals.
- Enforce the selected storage class at every AWS writer boundary so an omitted
  or contradictory SDK value cannot silently create cost-model drift.
- Align archive calculation and Terraform on `DEEP_ARCHIVE` unless the reviewed
  pricing model is deliberately changed to Glacier Flexible Retrieval.
- Do not price source-owned scheduled rules with the custom event-bus row. The
  deployed legacy scheduled-rule mechanism, its same-account target semantics,
  and its replacement by EventBridge Scheduler are reviewed explicitly; any
  deferred migration is recorded separately and cannot leave a false formula
  reference in the transition-runtime result.
- Keep TwinMaker pricing plan account-scoped and out of Terraform.
- Keep Managed Grafana version and workspace configuration as documented
  baseline invariants unless a cost formula explicitly models them.

## Required File Boundaries

- `src/terraform/variables.tf`
- `src/terraform/aws_iot.tf`
- `src/terraform/aws_compute.tf`
- `src/terraform/aws_storage.tf`
- `src/terraform/aws_twins.tf`
- `src/terraform/aws_glue.tf`
- `src/terraform/aws_grafana.tf` only for invariant assertions
- `src/providers/aws/lambda_functions/{hot-to-cold-mover,cold-writer,cold-to-archive-mover,archive-writer}`
- `src/providers/aws/lambda_functions/_shared/env_utils.py`
- `src/tfvars_generator.py` only through the phase-4 translator
- focused AWS Terraform contract tests

## Tests and Gates

- exact tfvars-to-HCL source assertions for every target;
- negative invalid memory, billing mode, and storage-class tests;
- runtime tests proving all four S3 write/copy paths consume the injected class;
- negative cold-start tests for missing runtime classes without duplicating the
  canonical class allowlist in Lambda code;
- assertions that transition pricing does not consume an unrelated event-bus
  price row;
- AWS provider package and function tests;
- Terraform fmt plus credential-free init/validate;
- no literal conflicting resource values remain outside the invariant registry.

## Definition of Done

- [x] Formula and Terraform memory profiles agree.
- [x] DynamoDB billing mode and S3 storage classes are specification-derived.
- [x] Archive pricing and HCL use the same AWS storage class.
- [x] TwinMaker account plans remain evidence-only.
- [x] AWS tests and credential-free Terraform gates pass.
- [x] #132 is closed with commit and verification evidence.
