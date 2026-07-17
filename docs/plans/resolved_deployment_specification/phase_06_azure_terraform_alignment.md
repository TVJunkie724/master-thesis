# Phase 6: Azure Terraform Alignment

**Issue:** [#133](https://github.com/TVJunkie724/master-thesis/issues/133)  
**Status:** Reviewed and implementation-ready  
**Blocked by:** #131

## Target

Azure Terraform and runtime storage writers consume the exact deployment
selection represented by the active cost model.

## Implementation

- Add validated IoT Hub SKU and capacity variables.
- Propagate the exact F1/S1/S2/S3 capacity result selected by the Optimizer.
- Add validated Function plan variables where the current cost formula is
  specifically Consumption/Y1.
- Keep Consumption Function memory and duration as disclosed assumptions because
  Terraform cannot pin the billed runtime memory.
- Add validated Cosmos deployment mode (`serverless`).
- Add storage account tier and replication variables tied to the reviewed Blob
  pricing model.
- Add runtime Blob cool/archive tier configuration through the same validated
  specification rather than independent string literals.
- Add validated Managed Grafana SKU.
- Keep ADT operation/query/message tiers as usage evidence only.

## Required File Boundaries

- `src/terraform/variables.tf`
- `src/terraform/azure_iot.tf`
- `src/terraform/azure_compute.tf`
- `src/terraform/azure_storage.tf`
- `src/terraform/azure_glue.tf`
- `src/terraform/azure_grafana.tf`
- Azure Blob writer/mover functions that apply runtime tiers
- focused Azure Terraform and function contract tests

## Tests and Gates

- F1/S1/S2/S3 and capacity table tests;
- invalid SKU/capacity combination tests;
- Cosmos, storage replication, Blob tier, Function plan, and Grafana mapping
  tests;
- Azure writer tests for exact cool/archive tier;
- Terraform fmt plus credential-free init/validate;
- existing canonical Azure L4 topology tests remain green.

## Definition of Done

- [ ] IoT Hub SKU/capacity equals the Optimizer result.
- [ ] Cosmos, storage, Blob runtime, Function plan, and Grafana choices are aligned.
- [ ] ADT and other usage meters remain evidence-only.
- [ ] Invalid SKU/capacity/value combinations fail before Terraform.
- [ ] Azure topology, function, and credential-free Terraform gates pass.
- [ ] #133 is closed with commit and verification evidence.
