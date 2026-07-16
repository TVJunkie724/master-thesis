# Canonical Layer Result And Calculator Contracts

**Issue:** [#68 Standardize optimizer LayerResult and layer calculator contracts](https://github.com/TVJunkie724/master-thesis/issues/68)  
**Milestone:** Phase 6 - Brain Contracts & Pricing Reliability  
**Base branch:** `master`  
**Implementation branch:** `codex/optimizer-layer-contracts`

## Objective

Complete the Optimizer layer-contract boundary so every provider produces the
same validated result type, declares capabilities through one contract, and can
never enter optimization as a zero-cost candidate when a layer is unsupported.
The public `cost-result.v1` response remains backward compatible.

## Current State

The repository already contains one `LayerResult` dataclass and a structural
`LayerCalculatorSet` protocol. AWS, Azure, and GCP return that result type, and
GCP declares L4/L5 unsupported. The remaining contract debt is:

- the frozen result can still retain a caller-owned mutable component mapping;
- provider identity and component keys are not validated centrally;
- provider classes repeat provider names when constructing results;
- capability checks are attributes rather than a shared operation;
- the engine excludes unsupported providers through GCP-specific flags instead
  of the canonical result capability;
- tests do not exercise the complete provider-layer capability matrix.

## Final Contract

### Canonical Result

`LayerResult` is the only provider layer result model. It guarantees:

- a known provider and architecture layer;
- finite, non-negative costs, usage values, and component values;
- non-empty component identifiers;
- an immutable defensive copy of the component breakdown;
- a reason for unsupported results and no reason for supported results.

### Calculator Boundary

`LayerCalculatorSet` exposes the shared provider identity, supported-layer set,
`supports(layer)`, all seven layer operations, and glue-cost calculation. A
shared base implementation owns capability validation and result construction;
provider classes retain their typed, provider-specific formula inputs.

Provider-specific pricing models and formulas remain provider-owned. This slice
does not force unlike cloud billing inputs into one untyped request object.

### Optimization Boundary

The engine builds candidates from all provider result maps and includes only
entries whose canonical result adapter marks `supported == true`. If no provider
supports a requested layer, calculation fails explicitly. There are no provider
name exceptions and unsupported zero-cost results cannot win scoring.

### API Compatibility

The existing provider cost payload remains:

```text
cost
components
supported
dataSizeInGB        optional
unsupportedReason  unsupported results only
```

No response field is removed or renamed. Provider/layer identity remains an
internal invariant because the enclosing response keys already carry that
identity in `cost-result.v1`.

## Implementation Slices

1. Harden `layers/contracts.py` with provider validation, immutable components,
   a shared base implementation, and a meaningful capability operation.
2. Bind AWS, Azure, and GCP calculator sets to the base implementation and use
   its provider-bound result factory.
3. Replace manual GCP inclusion flags in the engine with capability-driven,
   fail-closed candidate construction.
4. Add result invariant tests, a complete provider-layer matrix, unsupported
   candidate exclusion, no-supported-provider failure, and API compatibility
   regression coverage.
5. Update the Optimizer developer documentation, published docs, architecture
   assessment, roadmap, and GitHub issue state.

## Error Handling

- Unknown provider/layer declarations fail at construction or class definition.
- Invalid numeric/component values fail before they reach scoring.
- Unsupported results without a reason fail contract validation.
- A layer with zero supported providers raises a clear calculation error.
- Pricing lookup and formula exceptions remain unchanged and are not hidden.

## Verification Gates

### Focused

```bash
docker exec -e PYTHONPATH=/app master-thesis-2twin2clouds-1 \
  python -m pytest \
  tests/unit/calculation_v2/test_layer_contracts.py \
  tests/unit/calculation_v2/test_engine.py \
  tests/integration/test_rest_api_calculation_edge_cases.py -q
```

### Complete Optimizer Gate

```bash
docker compose run --rm --no-deps 2twin2clouds sh -lc \
  'python -m pytest tests -q && \
   ruff check api backend rest_api.py && \
   python -m bandit -r api backend rest_api.py -q && \
   python -m compileall -q api backend rest_api.py && \
   python -m pip check'
```

### Cross-Project Compatibility

Run Management API optimizer-client/response tests when the public fixture or
contract files change. No live provider refresh and no deployment E2E are part
of this deterministic slice.

## Definition Of Done

- Exactly one `LayerResult` definition exists.
- AWS, Azure, and GCP satisfy the shared calculator/capability contract.
- Every provider-layer combination has an explicit supported state in tests.
- Unsupported results are excluded by contract data, not provider-specific code.
- Existing Optimizer API response compatibility is proven.
- Optimizer tests, Ruff, Bandit, compileall, and dependency checks pass.
- Canonical documentation and roadmap state match the implementation.
