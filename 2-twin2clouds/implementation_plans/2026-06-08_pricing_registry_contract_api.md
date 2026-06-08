# Pricing Registry Contract And Read API

## Issue Context

Parent roadmap:
`docs/plans/2026-06-08_pricing_evidence_and_optimization_strategy_roadmap.md`

Depends on:

- `2026-06-08_pricing_evidence_registry_foundation.md`

Related epic: GitHub issue #69

Issue for this phase: TBD

## Goal

Expose the pricing registry through a typed internal contract for cost
calculation and through read-only API endpoints for diagnostics, Management API
integration, and a future Flutter Pricing Evidence Inspector.

The registry files remain the editable SSOT. This phase makes access to them
explicit, validated, typed, and inspectable.

## Problem

If cost calculation reads registry YAML, provider mappings, normalization rules,
and service models directly from scattered file paths, the architecture becomes
fragile again:

- calculation code can bypass validation
- provider fetchers can invent their own interpretation of mappings
- future UI/API inspection has no stable contract
- tests cannot easily assert which registry version was used
- Management API cannot reference registry metadata in calculation runs

The target is a single access boundary, not many ad-hoc file reads.

## Target Architecture

```text
pricing_registry/*.yaml
        |
        v
PricingRegistryLoader
        |
        v
PricingRegistryValidator
        |
        v
PricingRegistryService
        |
        +--> internal typed contract for CostCalculationModel
        +--> internal typed contract for provider evidence fetchers
        +--> read-only REST API for diagnostics / Management / future UI
```

Cost calculation must use the internal service contract. It must not call local
REST endpoints to read its own registry.

## Internal Contract

The optimizer must expose typed registry access inside the process:

```text
PricingRegistryService
  get_intent(intent_id)
  list_intents(metric=None)
  get_service_model(service_model_id)
  get_normalization_rule(rule_id)
  get_provider_mapping(provider, intent_id)
  list_provider_mappings(provider)
  get_registry_version()
  validate_publishability(evidence_report)
```

The exact names may be adjusted to local Python style, but the responsibilities
must remain explicit.

## Read-Only API Target

Proposed Optimizer endpoints:

```text
GET /pricing-registry/status
GET /pricing-registry/intents
GET /pricing-registry/intents/{intent_id}
GET /pricing-registry/service-models
GET /pricing-registry/service-models/{service_model_id}
GET /pricing-registry/providers/{provider}/mappings
GET /pricing-registry/providers/{provider}/mappings/{intent_id}
GET /pricing-registry/normalization-rules
```

These endpoints are read-only. They must never write mapping decisions, price
overrides, generated evidence, or runtime state.

## Management API Integration

The Management API may use these endpoints later to:

- display registry configuration in a Flutter read-only inspector
- attach `pricing_registry_version` to `CostCalculationRun`
- show which mapping/service model supported a result item
- diagnose `review_required` provider pricing states

Management API remains the owner of User/Twin calculation history. The optimizer
registry API remains the owner of read-only registry metadata.

## Scope

This phase includes typed registry access and read-only endpoint contracts.

It must not:

- build a Flutter UI
- create a database for registry mappings
- move mappings/intents out of files
- implement a UI editor
- run provider pricing refreshes
- rewrite tiering formulas
- create runtime LLM matching
- allow API writes to registry files

## Implementation Steps

1. Add typed Pydantic/dataclass models for intents, normalization rules, service
   models, provider mappings, and registry status.
2. Add a registry loader that reads only the approved registry directory.
3. Add validation at load time and return structured validation errors.
4. Add `PricingRegistryService` as the internal access boundary.
5. Refactor cost-calculation code only enough to obtain registry metadata
   through the service where this phase requires it.
6. Add read-only REST endpoints for registry status/intents/mappings/service
   models/normalization rules.
7. Add tests for loader validation, service access, endpoint responses, unknown
   ids, invalid providers, and read-only behavior.
8. Document that registry writes are intentionally file/Git driven.

## Error Handling

Required behavior:

- invalid registry file: structured validation error with file/key context
- unknown intent id: 404 with stable error code
- unknown provider: 404 or 422 with stable error code
- invalid mapping cardinality: registry validation failure
- malformed YAML: startup/refresh validation failure without partial state
- endpoint write attempt: unsupported method, no mutation path

Error responses must not include local secret paths or credential material.

## Test Strategy

No live cloud E2E is required.

Required tests:

- valid registry fixture loads successfully
- malformed YAML fails with structured error
- unknown normalization rule referenced by a mapping fails validation
- duplicate intent ids fail validation
- provider mapping endpoint returns deterministic data
- unknown intent endpoint returns stable 404
- unknown provider endpoint returns stable error
- registry version changes when registry content changes
- cost calculation can receive registry metadata through
  `PricingRegistryService`
- REST endpoints are read-only and expose no mutation route

## Definition Of Done

- [ ] Registry files remain the editable SSOT.
- [ ] Cost calculation has a typed internal registry access boundary.
- [ ] Provider evidence fetchers can use the same registry service.
- [ ] Read-only registry endpoints expose intents, mappings, normalization
  rules, service models, and registry status.
- [ ] Endpoint responses are typed and stable enough for Management API/UI
  consumption.
- [ ] Invalid registry content fails before publishable pricing is produced.
- [ ] Tests cover validation, access, endpoint contracts, and read-only
  behavior.
- [ ] Documentation explains that API access is read-only and Git/file changes
  remain the write path.

## Self Review

### Architect Review

- The phase creates one explicit registry boundary instead of scattered file
  reads.
- The cost calculation uses an internal service, avoiding unnecessary HTTP
  coupling inside the optimizer.
- The REST API is read-only and therefore does not undermine file-based SSOT.
- Management API integration is prepared without moving Twin/User history into
  the optimizer.

### Builder Review

- The endpoint list, internal service responsibilities, and validation errors
  are concrete.
- Tests are deterministic and do not require cloud access.
- Scope excludes UI editor and provider refresh work to keep the slice focused.

### Review Findings

- Fixed: registry access is planned as a typed service boundary, not scattered
  YAML reads.
- Fixed: REST API is read-only and cannot mutate SSOT files.
- Fixed: cost calculation does not call local HTTP endpoints for registry data.
- Fixed: Management API can consume registry metadata later without owning the
  registry itself.

No open findings after review.
