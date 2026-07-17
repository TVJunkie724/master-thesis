# Phase 7: GCP Terraform Alignment

**Issue:** [#120](https://github.com/TVJunkie724/master-thesis/issues/120)  
**Status:** Reviewed and implementation-ready  
**Blocked by:** #131

## Target

GCP formulas and Terraform agree on function runtime profiles, storage classes,
and Firestore mode. L4 and L5 remain explicitly unsupported.

## Implementation

- Add validated standard and mover Function memory variables.
- Add bounded min/max instance variables only where the cost model records the
  same scaling assumption.
- Apply standard settings to dispatcher, connector, ingestion, processing,
  readers, event functions, and glue.
- Apply mover settings to lifecycle mover functions.
- Add validated Firestore Native mode.
- Add validated Nearline and Archive storage classes.
- Replace the L3 archive Coldline calculator/pricing intent with the reviewed
  Archive model, or change Terraform only if evidence proves the model should be
  Coldline. The final state must contain one explicit choice, never a mismatch.
- Reject any GCP L4/L5 component in the contract and Deployer.

## Required File Boundaries

- `src/terraform/variables.tf`
- `src/terraform/gcp_iot.tf`
- `src/terraform/gcp_compute.tf`
- `src/terraform/gcp_storage.tf`
- `src/terraform/gcp_glue.tf`
- Optimizer GCP Cloud Functions and Cloud Storage calculators/contracts
- focused GCP Terraform and capability tests

## Tests and Gates

- formula-memory and tfvars-memory equality;
- min/max instance bounds and ordering;
- Nearline/Archive cost-model and HCL equality;
- unsupported L4/L5 negative fixtures;
- GCP provider package and function tests;
- Terraform fmt plus credential-free init/validate.

## Definition of Done

- [ ] Formula and Terraform function runtime profiles agree.
- [ ] Firestore mode and storage classes are specification-derived.
- [ ] L3 archive uses one reviewed Archive model end to end.
- [ ] GCP L4/L5 remain impossible to materialize.
- [ ] GCP tests and credential-free Terraform gates pass.
- [ ] #120 is closed with commit and verification evidence.
