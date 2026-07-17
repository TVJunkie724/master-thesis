---
title: "Phase 1: Resolved Deployment Contract and Matrix"
description: "Defines the versioned wire contract and classifies every optimizer-to-Terraform dimension."
tags: [implementation-plan, optimizer, backend, deployer, terraform, contracts]
lastUpdated: "2026-07-17"
version: "1.0"
---

# Phase 1: Contract and Deployment-Dimension Matrix

**Issue:** [#127](https://github.com/TVJunkie724/master-thesis/issues/127)  
**Status:** Implemented and verified

**Depends on:** None

## 1. Decision

Create a repository-owned wire-contract package:

```text
contracts/resolved-deployment-specification/v1/
  schema.json
  deployment-dimensions.json
  fixtures/
    valid/
    invalid/
```

`schema.json` is the structural SSOT. `deployment-dimensions.json` is the
closed-world semantic SSOT for provider services, allowed values, and
classification. Independent service adapters remain local to each container,
but contract tests must validate them against the same canonical fixtures.

Because the three Python services have independent Docker build contexts, a
repository script must generate byte-identical read-only copies at:

```text
2-twin2clouds/backend/contracts/generated/
twin2multicloud_backend/src/contracts/generated/
3-cloud-deployer/src/contracts/generated/
```

Only `contracts/resolved-deployment-specification/v1/` is edited by hand.
`scripts/sync_resolved_deployment_contract.py --check` must fail on drift.
Production images consume their generated local copy and do not depend on a
host mount outside their build context.

The contract does not make the architecture dynamic. It describes one resolved
deployment of the existing `five-layer-baseline@1`.

## 2. Contract Shape

The top-level object uses `additionalProperties: false` and contains:

| Field | Type | Rule |
| --- | --- | --- |
| `schema_version` | string | Exactly `resolved-deployment-specification.v1` |
| `calculation_run_id` | UUID string | Created by Management before the Optimizer call and echoed unchanged |
| `architecture_profile` | object | Exactly `five-layer-baseline@1`; no Phase 8 registry |
| `optimization_context` | object | Profile, strategy, formula set, workload contract, pricing registry, and exact catalog snapshot, pricing-region, and content-digest references |
| `currency` | string | ISO-style uppercase code used by the calculation |
| `components` | array | Stable, unique component selections in canonical component order |
| `digest` | string | `sha256:` plus lowercase hexadecimal digest |

Each component contains:

| Field | Purpose |
| --- | --- |
| `component_id` | Stable closed-world component identifier |
| `slot_id` | One of the seven baseline slots or `cross_cloud_glue` |
| `provider` | `aws`, `azure`, or `gcp` |
| `service_id` | Canonical provider service or bounded service-bundle ID |
| `required` | Whether the selected path requires the component |
| `dimensions` | Classified values and their exact evidence/formula references |

Each dimension contains:

| Field | Purpose |
| --- | --- |
| `dimension_id` | Registry-owned stable identifier |
| `classification` | `deployable_selection`, `usage_tier`, `account_scope`, or `non_deployable_assumption` |
| `value` | JSON scalar only; objects and unbounded provider payloads are forbidden |
| `unit` | Required when the value is quantitative |
| `terraform_target` | Required only for `deployable_selection` |
| `formula_reference` | Formula/model ID that consumed the value |
| `evidence_reference` | Pricing catalog/evidence ID; secrets and raw rows are forbidden |

## 3. Canonicalization and Digest

The digest input is the specification without its `digest` member.

```text
UTF-8 JSON
  + object keys sorted recursively
  + compact separators "," and ":"
  + no NaN or Infinity
  + no timestamps
  + no locale-dependent formatting
  -> SHA-256
  -> "sha256:<lowercase hex>"
```

The specification intentionally contains no calculated monetary totals or
floating-point cost breakdowns. Quantities that affect deployment are integers
or registry-owned strings, which keeps cross-project canonicalization stable.

## 4. Baseline Slot Registry

| Slot ID | Existing optimizer key | Existing Deployer key |
| --- | --- | --- |
| `l1_ingestion` | `L1` | `layer_1_provider` |
| `l2_processing` | `L2` | `layer_2_provider` |
| `l3_hot_storage` | `L3_hot` | `layer_3_hot_provider` |
| `l3_cool_storage` | `L3_cool` | `layer_3_cold_provider` |
| `l3_archive_storage` | `L3_archive` | `layer_3_archive_provider` |
| `l4_twin_state` | `L4` | `layer_4_provider` |
| `l5_visualization` | `L5` | `layer_5_provider` |

The `cool`/`cold` naming mismatch is normalized only at this adapter boundary.
No additional alias is allowed elsewhere.

## 5. Provider and Slot Matrix

### AWS

| Slot | Costed service bundle | Deployable selections | Evidence-only dimensions | Known drift to resolve |
| --- | --- | --- | --- | --- |
| L1 | IoT Core plus dispatcher Lambda | Standard Lambda memory | IoT message tiers, free allowances, duration | Calculator defaults to 128 MB; Terraform uses 256 MB |
| L2 | Lambda processing bundle, optional Step Functions/EventBridge | Standard Lambda memory | requests, GB-seconds, transitions, events, duration | Calculator defaults to 128 MB; Terraform uses 256 MB |
| L3 hot | DynamoDB plus reader Lambdas | `PAY_PER_REQUEST`, standard Lambda memory | request/storage usage tiers and Lambda duration | Lambda memory mismatch |
| L3 cool | S3 IA plus mover Lambda | `STANDARD_IA`, mover Lambda memory | retrieval/request tiers, duration | Calculator memory differs from Terraform |
| L3 archive | S3 archive plus mover Lambda | archive storage class, mover Lambda memory | retrieval/request tiers, duration | Calculator prices Deep Archive while Terraform uses `GLACIER` |
| L4 | IoT TwinMaker plus connector Lambda | Connector Lambda memory only | TwinMaker account plan and bundle, entity/query/API usage | Account plan must remain account-scoped |
| L5 | Managed Grafana | None in current cost model | editor/viewer licenses | Terraform Grafana version is an invariant, not an optimized SKU |
| Glue | Cross-cloud Lambda bundle | Glue Lambda memory | request/GB-second usage and duration | Calculator defaults to 128 MB; Terraform uses 256 MB |

### Azure

| Slot | Costed service bundle | Deployable selections | Evidence-only dimensions | Known drift to resolve |
| --- | --- | --- | --- | --- |
| L1 | IoT Hub, dispatcher Function, Event Grid | IoT Hub F1/S1/S2/S3 and capacity; Function plan `Y1` | Event Grid usage; Function memory/duration | Optimizer selects a capacity tier; Terraform always uses S1/1 |
| L2 | Function processing bundle, optional Logic Apps/Event Grid | Function plan `Y1` | Function memory/duration and execution usage | Memory is measured but not directly enforceable on Consumption |
| L3 hot | Cosmos DB plus reader Function | Cosmos serverless mode; Function plan `Y1` | request/storage usage and Function memory/duration | Shared storage-account settings require explicit invariant classification |
| L3 cool | Blob Cool plus mover Function | Blob tier `Cool`, storage account `Standard/LRS`, Function plan `Y1` | request/retrieval usage and Function memory/duration | Runtime tier is set in code rather than Terraform |
| L3 archive | Blob Archive plus mover Function | Blob tier `Archive`, storage account `Standard/LRS`, Function plan `Y1` | request/retrieval usage and Function memory/duration | Runtime tier is set in code rather than Terraform |
| L4 | Azure Digital Twins plus ADT Pusher | Pusher Function plan `Y1` | operations, query units, routed messages, Function memory/duration | ADT meters are not SKUs |
| L5 | Azure Managed Grafana | Grafana SKU `Standard` | active-user usage | Terraform hardcodes Standard |
| Glue | Cross-cloud Function bundle | Function plan `Y1` | Function memory/duration and executions | Memory is an assumption, not a Terraform field |

### GCP

| Slot | Costed service bundle | Deployable selections | Evidence-only dimensions | Known drift to resolve |
| --- | --- | --- | --- | --- |
| L1 | Pub/Sub plus dispatcher Cloud Function | Function memory, min instances, max instances | Pub/Sub usage tiers and Function duration | Calculator defaults to 128 MB; Terraform uses 256 MB |
| L2 | Cloud Function bundle plus optional Workflows | Function memory, min instances, max instances | execution/compute tiers and duration | Calculator defaults to 128 MB; Terraform uses 256 MB |
| L3 hot | Firestore Native plus reader Function | Firestore Native mode; Function memory/scaling | read/write/storage tiers and duration | Function memory mismatch |
| L3 cool | GCS Nearline plus mover Function | `NEARLINE`, Function memory/scaling | requests/retrieval and duration | Calculator memory differs from Terraform |
| L3 archive | GCS archive plus mover Function | `ARCHIVE`, Function memory/scaling | requests/retrieval and duration | Optimizer uses a Coldline calculator while Terraform deploys Archive |
| L4 | Unsupported | None | None | Must remain fail-closed |
| L5 | Unsupported | None | None | Must remain fail-closed |
| Glue | Cross-cloud Cloud Function bundle | Function memory/scaling | execution/compute tiers and duration | Calculator defaults to 128 MB; Terraform uses 256 MB |

## 6. Registry Rules

The dimension registry must:

1. enumerate every stable component and allowed slot/provider/service tuple;
2. enumerate deployment parameter types and bounded values;
3. identify exactly one Terraform target for each deployable dimension;
4. forbid `terraform_target` on every other classification;
5. state whether a value is selected by the optimizer or is a baseline
   invariant consumed by both calculator and Deployer;
6. reject account identifiers, credentials, endpoints, and raw catalog rows;
7. preserve canonical component and dimension ordering.

Every function bundle that contributes compute cost must register both the
memory value used by its formula and its runtime-duration assumption. A runtime
value remains `non_deployable_assumption` when the provider resource cannot
enforce it, but omitting it is not allowed: doing so would make the selected
cost irreproducible even if all Terraform-facing values matched.

## 7. Compatibility and Errors

- Missing specification: `legacy_not_deployable`.
- Unknown schema version: `unsupported_specification_version`.
- Unknown component/dimension/value: `unsupported_deployment_selection`.
- Missing selected component: `incomplete_deployment_specification`.
- Digest mismatch: `deployment_specification_digest_mismatch`.
- Provider/slot mismatch: `deployment_specification_provider_mismatch`.

Error messages are stable and contain component/dimension IDs, never credential
content or complete manifest payloads.

## 8. Implementation Files

- `contracts/resolved-deployment-specification/v1/schema.json`
- `contracts/resolved-deployment-specification/v1/deployment-dimensions.json`
- positive and negative contract fixtures
- one repository-level contract test/verification script
- canonical developer documentation explaining the extension process

## 9. Verification

- JSON syntax and schema self-validation.
- Valid all-AWS, all-Azure, and mixed-path fixtures.
- Invalid secret field, unknown field, unknown service, wrong classification,
  invalid value and cross-field combinations, duplicate component, missing
  slot, unsupported GCP L4/L5, and digest-tampering fixtures.
- Deterministic digest test across Optimizer, Management API, and Deployer
  adapters.
- Matrix audit against every calculator component and every Terraform SKU,
  memory, storage class, billing mode, replication, plan, and scaling literal.

## 10. Definition of Done

- [x] #127 is closed with commit and verification evidence.
- [x] The canonical schema, dimension registry, and fixtures are committed.
- [x] Generated project copies are byte-identical and drift-checked.
- [x] Every child plan references this exact contract.
- [x] The complete Terraform literal audit is represented in the matrix.
- [x] No runtime selection, persistence, or Terraform behavior changed.
