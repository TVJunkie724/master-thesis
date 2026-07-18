# Phase 5: AWS Terraform Alignment

**Issue:** [#132](https://github.com/TVJunkie724/master-thesis/issues/132)  
**Status:** Reviewed and implementation-ready  
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
- Align archive calculation and Terraform on `DEEP_ARCHIVE` unless the reviewed
  pricing model is deliberately changed to Glacier Flexible Retrieval.
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
- `src/tfvars_generator.py` only through the phase-4 translator
- focused AWS Terraform contract tests

## Tests and Gates

- exact tfvars-to-HCL source assertions for every target;
- negative invalid memory, billing mode, and storage-class tests;
- AWS provider package and function tests;
- Terraform fmt plus credential-free init/validate;
- no literal conflicting resource values remain outside the invariant registry.

## Definition of Done

- [ ] Formula and Terraform memory profiles agree.
- [ ] DynamoDB billing mode and S3 storage classes are specification-derived.
- [ ] Archive pricing and HCL use the same AWS storage class.
- [ ] TwinMaker account plans remain evidence-only.
- [ ] AWS tests and credential-free Terraform gates pass.
- [ ] #132 is closed with commit and verification evidence.
