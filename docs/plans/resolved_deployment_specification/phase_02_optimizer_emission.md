# Phase 2: Optimizer Specification Emission

**Issue:** [#129](https://github.com/TVJunkie724/master-thesis/issues/129)  
**Status:** Implemented and verified
**Blocked by:** #127

## Target

The winning cost path returns one schema-valid
`resolvedDeploymentSpecification`. It is built from typed layer results and the
canonical dimension registry, never inferred later from Terraform defaults.

## Implementation

1. Extend the Management-to-Optimizer request with a server-generated
   `calculationRunId`.
2. Add typed deployment dimensions to `LayerResult` without mixing them into
   monetary `components`.
3. Add provider builders for AWS, Azure, and GCP that map active layer bundles
   to stable component IDs.
4. Make formulas consume the same baseline runtime values emitted as deployment
   selections:
   - AWS standard Lambda 256 MB and mover Lambda 512 MB;
   - GCP standard Function 256 MB and mover Function 512 MB;
   - Azure Function memory remains a disclosed non-deployable assumption;
   - all runtime duration assumptions remain evidence-only.
5. Return the exact selected Azure IoT Hub tier and capacity from the capacity
   calculation rather than only returning its total cost.
6. Correct AWS archive and GCP archive model-to-storage-class drift before they
   can produce a deployable specification.
7. Build the final specification only after the global route-aware winner is
   known, then calculate its canonical digest.
8. Apply currency conversion only to cost fields. Deployment selections and
   their digest must remain unchanged.

## Required File Boundaries

| Area | Files |
| --- | --- |
| Request contract | `api/calculation.py`, optimizer REST request tests |
| Layer result | `backend/calculation_v2/layers/contracts.py` |
| Provider selections | `backend/calculation_v2/layers/aws_layers.py`, `azure_layers.py`, `gcp_layers.py` |
| Tier selection | `backend/calculation_v2/formulas/pricing_units.py`, `components/azure/iot_hub.py` |
| Runtime assumptions | AWS Lambda, Azure Functions, and GCP Cloud Functions calculators |
| Winner assembly | `backend/calculation_v2/engine.py` and a new focused specification builder module |
| Archive correction | AWS S3 and GCP Cloud Storage calculators plus pricing contracts where required |
| Tests | existing calculation/layer/contract suites plus focused specification fixtures |

The engine orchestrates; it must not become the registry, digest, or
provider-mapping implementation.

## Error Handling

The Optimizer fails the request when a winning slot has no complete component
mapping, an unsupported component is selected, a selected deployment value is
not represented by the formula, or the registry cannot resolve evidence/model
references. It must not emit a partial specification.

## Tests

- layer-result immutability and schema validation;
- exact Azure F1/S1/S2/S3 capacity selections;
- Azure F1 0.5 KB and paid-tier 4 KB message-block normalization;
- exact AWS and GCP function-memory formula inputs;
- AWS Deep Archive and GCP Archive storage-class alignment;
- all supported provider/slot combinations;
- GCP L4/L5 fail-closed paths;
- same-provider and multi-provider winner fixtures;
- currency-invariance of deployment digest;
- no secret-like keys or provider payloads.

## Definition of Done

- [x] Every successful result contains one complete v1 specification.
- [x] All 21 provider-slot capability combinations retain fail-closed behavior.
- [x] Formula inputs equal emitted deployment selections where enforceable.
- [x] AWS and GCP archive service models equal emitted storage classes.
- [x] Currency conversion does not alter the specification digest.
- [x] Optimizer unit, integration, Ruff, Bandit, and compile gates pass.
- [x] #129 is closed with commit and verification evidence.
