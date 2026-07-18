# Phase 6: Azure Terraform Alignment

**Issue:** [#133](https://github.com/TVJunkie724/master-thesis/issues/133)
**Status:** Completed on 2026-07-17
**Blocked by:** #61, #131

## Target

Azure Terraform and runtime storage writers consume the exact deployment
selection represented by the active cost model.

## Implementation

- Add validated IoT Hub SKU and capacity variables.
- Propagate the exact F1/S1/S2/S3 capacity result selected by the Optimizer.
- Add validated Function plan variables where the current cost formula is
  specifically Consumption/Y1.
- Bind both source-owned transition bundles to the shared L3 Function App plan
  without contradictory per-slot plan values.
- Derive L0 Function App activation from the registered receiver boundaries
  and Azure L4 pusher ownership. Azure appearing in an unrelated source slot
  must not create an empty, unpriced L0 Function App.
- Resolve the L0 plan from the L4 pusher and cross-cloud glue specification
  dimensions. If both share the app, their values must agree; if neither owns
  it, the app must be absent.
- Make the hot-to-cool and cool-to-archive timer schedules consume resolved
  baseline values through Azure Functions app-setting expressions. The current
  daily Azure cold-to-archive decorator must not remain inconsistent with a
  weekly Optimizer assumption.
- Keep Consumption Function memory and duration as disclosed assumptions because
  Terraform cannot pin the billed runtime memory.
- Add validated Cosmos deployment mode (`serverless`).
- Add storage account tier and replication variables tied to the reviewed Blob
  pricing model.
- Bind those values when Azure owns cool or archive Blob storage. When Azure
  needs only Function App host storage, retain Standard/LRS as an explicit
  non-modeled support-resource invariant and document the missing cost under
  formula validation rather than pretending it came from a selected Blob
  component.
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
- Azure transition timer functions and their shared Function App plan
- Azure L0 activation and shared L4/glue plan selection
- focused Azure Terraform and function contract tests

## Tests and Gates

- F1/S1/S2/S3 and capacity table tests;
- invalid SKU/capacity combination tests;
- Cosmos, storage replication, Blob tier, Function plan, and Grafana mapping
  tests;
- Azure writer tests for exact cool/archive tier;
- topology tests proving L0 is present only for registered Azure receiver
  boundaries or the Azure L4 pusher;
- source tests classifying Function App support storage separately from
  costed Blob storage;
- Terraform fmt plus credential-free init/validate;
- existing canonical Azure L4 topology tests remain green.

## Definition of Done

- [x] IoT Hub SKU/capacity equals the Optimizer result.
- [x] Cosmos, storage, Blob runtime, Function plan, and Grafana choices are aligned.
- [x] ADT and other usage meters remain evidence-only.
- [x] Invalid SKU/capacity/value combinations fail before Terraform.
- [x] Azure topology, function, and credential-free Terraform gates pass.
- [x] #133 is closed with commit and verification evidence.

## Verification Evidence

- implementation commit: `a02cb18f`;
- focused Azure specification, runtime, and topology suite: `79 passed`;
- full Deployer non-E2E suite: `1613 passed, 1 skipped`;
- valid guard plan accepted; missing Cosmos mode and invalid F1/capacity
  combination rejected before provider execution;
- Terraform fmt and credential-free validate passed;
- resolved-deployment contract validation/synchronization passed;
- Ruff, Bandit, compileall, strict MkDocs, and diff checks passed;
- no live cloud apply or billable E2E operation was performed.
