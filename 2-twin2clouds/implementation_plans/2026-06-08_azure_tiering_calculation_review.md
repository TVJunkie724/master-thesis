# Azure Tiering And Calculation Review

## Issue Context

Parent roadmap:
`docs/plans/2026-06-08_pricing_evidence_and_optimization_strategy_roadmap.md`

Depends on:

- `2026-06-08_azure_pricing_evidence_implementation.md`

## Goal

Review Azure service tiering and update cost calculation only where Azure
evidence proves the current calculation model is incomplete or wrong.

## Problem

The current optimizer may treat tiered services as if they had single flat
values. That is not sufficient for services such as:

- Azure Digital Twins
- IoT Hub
- Bandwidth / transfer
- Storage operations
- API Management
- Logic Apps action types

The calculation model must not be changed from assumptions alone. Changes must
be based on Azure evidence captured in the previous phase.

## Scope

This phase is Azure-only and cost-only.

It must not:

- change AWS or GCP calculations
- add non-cost metrics
- introduce manual price overrides
- use static fallbacks as final values

## Review Targets

### Azure Digital Twins

Must verify and model:

- messages
- operations
- query units
- whether query-unit tiering exists in the provider evidence or official cloud
  evidence

### IoT Hub

Must verify and model:

- Free, B1/B2/B3, S1/S2/S3 tiers
- monthly unit prices
- message/unit limits
- whether optimizer workload maps to basic or standard tier family

### Bandwidth / Transfer

Must verify and model:

- free tier
- tier boundaries
- routing preference variants
- selected transfer family for optimizer egress intent

### Storage

Must verify and model:

- read/write operations
- retrieval
- storage GB-month
- archive/cool tier differences
- `10K` operation units

### Logic Apps / Event Grid / API Management

Must verify and model:

- action type selection
- event operation units
- API call units
- per-call versus per-10K/per-100K/per-1M normalization

## Implementation Steps

1. Compare current Azure calculation formulas against Azure evidence.
2. Document each service model decision in `service_models.yaml`.
3. Update only formulas whose current model is proven incomplete or wrong.
4. Add unit tests for each changed formula.
5. Add regression fixtures for representative low, medium, and high usage
   volumes.
6. Ensure all changed calculations reference normalized evidence fields.

## Test Strategy

Required tests:

- Digital Twins messages/operations/query units are calculated separately.
- IoT Hub tier selection changes with workload volume.
- Bandwidth tier selection handles multiple tiers.
- Storage operations normalize `10K` units correctly.
- Logic Apps and API Management normalize action/call units correctly.
- Existing cost-only optimizer output remains deterministic.

## Definition Of Done

- [ ] Azure service model assumptions are documented in the editable SSOT.
- [ ] Azure calculation changes are evidence-backed.
- [ ] No Azure calculation uses fallback_static as publishable data.
- [ ] Tiered service tests cover boundary conditions.
- [ ] Existing optimizer API contract remains compatible.

## Self Review

### Architect Review

- Calculation changes happen after evidence exists.
- Scope is Azure-only to avoid a broad rewrite.
- Tiering and unit boundaries are explicit.

### Builder Review

- Each review target names concrete model dimensions.
- Tests define usage-volume and boundary requirements.
- No provider-specific assumption can be changed without evidence.

### Review Findings

- Fixed: Digital Twins tiering is framed as a verified research item, not an
  assumption.
- Fixed: API Management and Logic Apps unit mismatches are explicitly included.

No open findings after review.
