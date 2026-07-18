# Phase 7: GCP Terraform Alignment

**Issue:** [#120](https://github.com/TVJunkie724/master-thesis/issues/120)  
**Status:** Completed on 2026-07-18
**Blocked by:** #61, #131

## Target

GCP formulas and Terraform agree on function runtime profiles, storage classes,
and Firestore mode. L4 and L5 remain explicitly unsupported.

## Implementation

- Add validated standard and mover Function memory variables.
- Add bounded min/max instance variables only where the cost model records the
  same scaling assumption.
- Apply L1 settings to the dispatcher and source-owned connector, L2 settings
  to processing and event Functions, L3 reader settings to the hot reader, and
  glue settings to cross-cloud receivers.
- Apply mover settings to lifecycle mover functions.
- Bind both source-owned transition Function and Cloud Scheduler dimensions.
- Remove the current same-cloud cold-to-archive ambiguity. The explicit
  source-owned scheduled mover is the sole transition owner; the cold bucket
  must not also apply a lifecycle storage-class transition.
- Materialize a separate Archive bucket whenever GCP owns the archive slot,
  including same-provider GCP cold-to-archive paths.
- Inject the resolved Nearline/Archive class into local movers and cross-cloud
  receiver Functions. Remote transition paths must not require a local
  destination bucket or storage class.
- Correct Cloud Scheduler to the official USD 0.10 per job-month price and
  include one job-month exactly once per transition runtime. Do not apply the
  billing-account-wide three-job free allowance to an individual Twin without
  account allocation evidence.
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
- `src/providers/gcp/cloud_functions/*storage*`
- Optimizer GCP Cloud Functions and Cloud Storage calculators/contracts
- immutable GCP pricing baseline and official Scheduler evidence
- focused GCP Terraform and capability tests

## Tests and Gates

- formula-memory and tfvars-memory equality;
- min/max instance bounds and ordering;
- Nearline/Archive cost-model and HCL equality;
- local and cross-cloud mover/writer runtime storage-class propagation;
- one Archive bucket plus one scheduled mover and no duplicate lifecycle rule;
- official Scheduler job-month value, provenance, and exactly-once formula use;
- unsupported L4/L5 negative fixtures;
- GCP provider package and function tests;
- Terraform fmt plus credential-free init/validate.

## Definition of Done

- [x] Formula and Terraform function runtime profiles agree.
- [x] Firestore mode and storage classes are specification-derived.
- [x] L3 archive uses one reviewed Archive model end to end.
- [x] GCP L4/L5 remain impossible to materialize.
- [x] GCP tests and credential-free Terraform gates pass.
- [x] #120 is closed with commit and verification evidence.

## Verification Evidence

- Deployer safe suite: `1630 passed, 1 skipped`; live E2E tests excluded.
- Optimizer suite: `804 passed`.
- Focused GCP pricing, strategy, runtime, and Terraform contracts:
  `40 passed` before the complete suites.
- Resolved deployment contract: valid and synchronized across all consumers.
- Terraform: recursive format check and credential-free validation passed.
- Credential-free plans accepted the valid mixed topology and rejected missing
  Firestore mode, invalid Archive class, and unsupported GCP L4/L5 fixtures.
- Bandit passed for both Deployer and Optimizer source trees.
- Ruff and Python compilation passed for every changed Python file.
- MkDocs strict build passed.
- No provider API mutation, Terraform apply, or billable live E2E was run.
