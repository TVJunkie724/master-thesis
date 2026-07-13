# Cloud Pricing Industry Context

## Purpose

This note captures the external context behind the Twin2MultiCloud pricing
roadmap. It is intended as thesis input, not as an implementation plan.

The core question is whether an evidence-backed pricing catalog, explicit
pricing model classifications, source classifications, calculation contracts,
and traceable result attribution are unnecessarily complex or aligned with
established cloud-cost engineering practice.

## Observed Industry Patterns

### Centralized pricing catalogs

Infracost uses a centralized Cloud Pricing API containing public AWS, Azure, and
Google prices that are updated regularly. This supports the architectural
decision to avoid scattered runtime-only provider calls and instead build an
inspectable pricing/evidence catalog before calculation.

Reference: https://www.infracost.io/docs/supported_resources/cloud_pricing_api/

### Vendor-neutral cost normalization

FOCUS, the FinOps Open Cost and Usage Specification, standardizes cost and usage
data across vendors. It targets billing and usage datasets rather than
pre-deployment estimation, but it supports the same core principle: raw provider
fields are not directly comparable without normalization and a shared semantic
schema.

Reference: https://focus.finops.org/

### Separation of price, usage, allocation, and result

OpenCost combines pricing data with usage and allocation models for Kubernetes
and cloud cost reporting. This supports the separation used in Twin2MultiCloud:
price evidence, workload inputs, calculation formulas, scoring, and result
attribution should remain distinct concepts.

Reference: https://opencost.io/docs/integrations/api/

### Provider calculators as references, not portable contracts

Provider calculators such as AWS Pricing Calculator are useful references for
estimation semantics, but they are provider-specific tools rather than portable
multi-cloud contracts. They should inform service-specific assumptions where
appropriate, but they cannot replace a provider-neutral calculation contract.

Reference: https://docs.aws.amazon.com/pricing-calculator/latest/userguide/getting-started.html

## Thesis Implication

Provider pricing APIs alone do not solve multi-cloud cost comparison. The
defensible contribution is an auditable pipeline that:

- classifies provider pricing models explicitly
- classifies price sources explicitly
- distinguishes API-fetched prices from official static documentation, curated
  non-price constants, derived values, not-applicable fields, unsupported
  fields, and emergency fallback diagnostics
- binds classifications to calculation strategies and formula sets
- validates publishability before calculation results are trusted
- emits inspectable traces from intent to selected evidence, normalization,
  formula application, and final cost result

## Scope Boundary For This Thesis

The implementation should remain deliberately smaller than a full FinOps
platform.

In scope:

- cost minimization only
- supported Twin2MultiCloud services only
- source-controlled registry files as SSOT
- deterministic validation and tests
- read-only diagnostics and traceability

Out of scope for the current thesis implementation:

- full billing reconciliation
- custom enterprise price books
- dynamic GPT-based price matching
- editable pricing UI
- complete provider billing coverage
- live deployment E2E as part of pricing validation

This keeps the architecture enterprise-grade and explainable without turning the
thesis into a general-purpose billing platform.
