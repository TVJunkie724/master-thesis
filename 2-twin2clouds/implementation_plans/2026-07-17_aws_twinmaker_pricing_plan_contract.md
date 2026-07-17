---
title: "AWS IoT TwinMaker Pricing Plan Contract"
description: "Model public TwinMaker rates and user-scoped account pricing-plan observations without treating account bundles as per-twin prices."
tags: [optimizer, aws, pricing, credentials, management-api]
lastUpdated: "2026-07-17"
version: "1.0"
---

<!-- SOURCES:
- GitHub issue #115 "Model AWS IoT TwinMaker pricing-plan and account-scope semantics"
- GitHub epic #31 "Implement tiered pricing for additional optimizer services"
- docs/plans/2026-06-08_pricing_evidence_and_optimization_strategy_roadmap.md
- 2-twin2clouds/backend/calculation_v2/components/aws/twinmaker.py
- 2-twin2clouds/backend/calculation_v2/engine.py
- 2-twin2clouds/backend/fetch_data/cloud_price_fetcher_aws.py
- 2-twin2clouds/backend/fetch_data/calculate_up_to_date_pricing.py
- 2-twin2clouds/backend/credentials_checker.py
- twin2multicloud_backend/src/models/pricing_refresh_run.py
- twin2multicloud_backend/src/services/pricing_refresh_run_service.py
- twin2multicloud_backend/src/services/cost_calculation_run_service.py
- FRONTEND_ARCHITECTURE.md
- twin2multicloud_flutter/docs/frontend_delta/phases/PHASE_04_PRICING_REVIEW_CENTER.md
- twin2multicloud_flutter/lib/models/pricing_refresh_run.dart
- twin2multicloud_flutter/lib/widgets/pricing/pricing_refresh_run_summary.dart
- AWS IoT TwinMaker pricing documentation
- AWS IoT TwinMaker pricing-mode documentation
- AWS IoT TwinMaker GetPricingPlan API documentation
- Read-only AWS Price List and GetPricingPlan observations on 2026-07-17
EXTRACTED: 2026-07-17 | VERSION: 1.0
-->

# AWS IoT TwinMaker Pricing Plan Contract

## Issue Context

GitHub issue:
[115](https://github.com/TVJunkie724/master-thesis/issues/115)

Parent epic:
[31](https://github.com/TVJunkie724/master-thesis/issues/31)

Roadmap:
`docs/plans/2026-06-08_pricing_evidence_and_optimization_strategy_roadmap.md`

This is Phase 18 of the pricing evidence and optimization strategy roadmap.
It is pre-Phase-8 hardening: the current Five-Layer baseline must not optimize
AWS L4 with a pricing plan that the target AWS account does not use.

Downstream deployment-specification work:
[118](https://github.com/TVJunkie724/master-thesis/issues/118) will freeze the
resolved service configuration and carry it to Terraform. This phase produces
the authoritative TwinMaker pricing-plan evidence and compatibility state that
the later specification must reference. It must not introduce a second
deployment-selection contract.

## Goal

The platform must distinguish two evidence domains:

1. Public, region-scoped AWS Price List rates and bundle schedules.
2. User- and account-scoped `GetPricingPlan` observations.

The public pricing snapshot must never contain account observations. A user
refresh must never overwrite another user's account context. A calculation
must use AWS TwinMaker L4 only when the Management API can provide a fresh,
owner-scoped pricing-plan observation compatible with the Five-Layer baseline.

## Evidence Boundary

The implementation must use these official references:

- AWS IoT TwinMaker pricing:
  <https://aws.amazon.com/iot-twinmaker/pricing/>
- TwinMaker pricing modes:
  <https://docs.aws.amazon.com/iot-twinmaker/latest/guide/tm-pricing-mode.html>
- `GetPricingPlan`:
  <https://docs.aws.amazon.com/iot-twinmaker/latest/apireference/API_GetPricingPlan.html>
- `PricingPlan`:
  <https://docs.aws.amazon.com/iot-twinmaker/latest/apireference/API_PricingPlan.html>
- `BundleInformation`:
  <https://docs.aws.amazon.com/iot-twinmaker/latest/apireference/API_BundleInformation.html>

The provider evidence establishes:

- `BASIC`, `STANDARD`, and `TIERED_BUNDLE` are distinct account modes;
- `STANDARD` is the default;
- Basic charges unified data access calls but does not support Knowledge Graph;
- Standard charges unified data access calls, entities, and queries;
- Tiered Bundle has an account-wide entity tier, fixed monthly charge,
  included query/API usage, overage rates, automatic tier movement, proration,
  and a three-month commitment;
- the current and pending account plans are observable through
  `GetPricingPlan`;
- changing a plan is a separate mutating operation and is not part of pricing
  retrieval.

Read-only verification on 2026-07-17 established:

- the available test account reports `STANDARD` in `eu-central-1`;
- the Frankfurt Price List exposes Standard entity, query, and unified-data
  rates;
- the Frankfurt Price List exposes four bundle base prices and query/API
  overage dimensions;
- query/API dimension `beginRange` values encode included bundle usage;
- bundle entity boundaries are documented by AWS rather than encoded in the
  base-price Price List rows.

The exact Frankfurt evidence used as the implementation fixture is:

| Mode/tier | Entity range | Monthly base | Included queries | Included API calls |
|---|---:|---:|---:|---:|
| `STANDARD` | usage based | n/a | n/a | n/a |
| `TIER_1` | 1-1,000 | USD 231.00 | 3,800,000 | 25,000,000 |
| `TIER_2` | 1,001-5,000 | USD 682.50 | 9,000,000 | 60,000,000 |
| `TIER_3` | 5,001-10,000 | USD 1,155.00 | 14,300,000 | 95,000,000 |
| `TIER_4` | 10,001-20,000 | USD 2,047.50 | 24,000,000 | 160,000,000 |

Frankfurt Standard and bundle-overage rates are:

| Dimension | USD price |
|---|---:|
| Standard entity-month | 0.0525 |
| Standard query | 0.0000525 |
| Standard unified-data API call | 0.00000165 |
| Bundle query overage | 0.0000525 |
| Bundle unified-data API-call overage | 0.00000165 |

These values are evidence fixtures, not permanent constants. The live
extractor must reproduce them from the exact Price List dimensions for
`eu-central-1`, while the committed snapshot records region and digest.

No credential value, access-key identifier, ARN, or secret response field may
be copied into committed evidence.

## Scope

| Area | In scope | Out of scope |
|---|---|---|
| Public pricing | Exact Standard rates and complete TIER_1-TIER_4 bundle schedules for the configured region | Account observations in global JSON |
| Account observation | Read-only `GetPricingPlan`, current and pending plan, billable entity count, bundle metadata | `UpdatePricingPlan` or any automatic mode change |
| Credentials | Add only `iottwinmaker:GetPricingPlan` to AWS pricing credentials and preflight | Add permission to deployment credentials |
| Calculation | Basic functional gate, Standard usage cost, pure Tiered Bundle account calculator, explicit non-comparable states | Guessed per-twin bundle allocation |
| Management API | Owner-scoped observation persistence and deterministic context resolution | New credential store or separate pricing database |
| Deployment handoff | Persist plan compatibility and block selection when account evidence is stale or incompatible | Full `ResolvedDeploymentSpecification`; owned by #118 |
| Flutter | Compact current/pending AWS plan diagnostics in existing pricing review details | Editable pricing-plan controls |
| Documentation | Pricing, credentials, data flow, failure behavior, extension contract | Thesis evaluation conclusions |
| Verification | Unit, API, contract, security, migration-free persistence, Flutter, docs, read-only AWS smoke | Real deployment or paid E2E |

The broader mutable provider-cache problem is owned by
[#119](https://github.com/TVJunkie724/master-thesis/issues/119). That issue
introduces immutable provider-and-region keyed catalogs before route-aware
transfer work in #116. This phase must not implement that broader storage
migration, but it must bind the current AWS snapshot to one canonical region
and digest and reject an account/catalog region mismatch. This prevents #115
from silently calculating TwinMaker against another user's last-refreshed
region while keeping the regional catalog migration independently reviewable.

## Required File Boundaries

Every listed production boundary is mandatory. References discovered by `rg`
must be migrated in the same slice rather than retained as undocumented flat
aliases.

| Project | Required files or boundaries |
|---|---|
| Optimizer API | `2-twin2clouds/api/calculation.py`, `api/pricing.py`, `api/credentials.py`, OpenAPI fixtures |
| Optimizer account observation | new `2-twin2clouds/backend/aws_twinmaker_pricing_plan.py`; `backend/credentials_checker.py`; `backend/secret_redaction.py`; typed error mapping |
| AWS fetch and publication | `backend/fetch_data/cloud_price_fetcher_aws.py`, `backend/fetch_data/calculate_up_to_date_pricing.py`, `backend/pricing_schema.py`, `backend/pricing_publication_state.py`, committed AWS pricing JSON |
| Calculation | `backend/calculation_v2/components/aws/twinmaker.py`, `layers/aws_layers.py`, `engine.py`, result/intent trace projections, strategy contracts |
| Pricing registry | `pricing_registry/intents.yaml`, `workload_contracts.yaml`, `price_source_classifications.yaml`, `provider_pricing_contracts.yaml`, `service_models.yaml`, `formula_sets.yaml`, `providers/aws/mappings.yaml`, and `optimization_bundles.yaml` |
| AWS pricing policy | `2-twin2clouds/docs/references/aws_pricing_policy.json`, bootstrap policy source if distinct, permission inventory tests |
| Management schemas | `src/schemas/pricing_refresh.py`, `src/schemas/optimizer_calculation.py`, `src/schemas/cost_calculation.py` |
| Management services | `src/services/pricing_refresh_run_service.py`, new `aws_twinmaker_pricing_context_service.py`, `optimizer_calculation_service.py`, `cost_calculation_run_service.py` |
| Management routes/clients | `src/api/routes/optimizer.py`, `src/api/routes/optimizer_runs.py`, `src/clients/optimizer_client.py`, error contracts |
| Management persistence | existing `PricingRefreshRun.result_summary_json` and `CostCalculationRun.result_summary_json`; no new table or migration |
| Flutter model | `lib/models/pricing_refresh_run.dart`; a typed nested value object, not map traversal in widgets |
| Flutter UI | extend `lib/widgets/pricing/pricing_refresh_run_summary.dart`; update `pricing_review_strings.dart`; no new screen and no direct service call |
| Flutter state | reuse `PricingReviewBloc.latestRuns`; no new event or provider is required for a read-only projection |
| Optimizer tests | new `tests/unit/pricing/test_aws_twinmaker_pricing_plan.py`; extend pricing schema/fetcher/calculation/API/credential/trace contract tests discovered from the referenced production paths |
| Management tests | new `tests/test_aws_twinmaker_pricing_context.py`; extend refresh, direct calculation, persisted calculation, deployment-selection, OpenAPI, and secret-redaction tests |
| Flutter demo/tests | pricing refresh demo payloads; `test/models/pricing_contract_models_test.dart`; `test/widgets/pricing/pricing_provider_widgets_test.dart`; `test/screens/pricing_review_screen_test.dart`; existing Pricing Review BLoC tests |
| Documentation | this plan, pricing mini-roadmap, docs-site Optimizer/Credentials/Pricing Review/component pages, standalone Optimizer compatibility docs |

## Mandatory Implementation Sequence

Each step must be completed, tested, reviewed, and committed before the next
step begins. Do not skip or combine review gates.

1. **Public pricing and observer foundation**
   - implement exact Price List extraction and the nested public schema;
   - implement the read-only account-plan observer and typed errors;
   - update credential preflight and least-privilege policy;
   - migrate registry contracts and focused tests.
2. **Optimizer calculation contract**
   - add the internal typed account context;
   - implement Basic/Standard/Tiered semantics and candidate exclusion;
   - add result and trace diagnostics;
   - migrate all flat-key fixtures and run the full Optimizer suite.
3. **Management ownership boundary**
   - persist secret-free connection binding in refresh-run result metadata;
   - implement owner/default/fingerprint/account/freshness resolution;
   - inject context into both calculation paths;
   - make pricing-run reference server-owned;
   - add selection-for-deployment compatibility checks.
4. **Flutter diagnostics**
   - add typed context parsing;
   - extend the existing latest-refresh expansion;
   - update demo fixtures and model/widget/BLoC regression tests.
5. **Documentation and generated contracts**
   - regenerate committed OpenAPI contracts;
   - update current user/developer documentation and roadmaps;
   - do not place thesis evaluation conclusions in docs-site.
6. **Review pass 1**
   - perform line-by-line plan compliance and cross-project data-flow review;
   - fix every finding and rerun targeted suites.
7. **Review pass 2 and final gates**
   - perform independent security, error, stale-data, UX, and regression review;
   - fix every finding;
   - run all full gates and the bounded read-only AWS smoke.

## Canonical Data Ownership

### Public Pricing SSOT

`2-twin2clouds/json/fetched_data/pricing_dynamic_aws.json` remains the committed
and runtime SSOT for public AWS catalog prices. Its TwinMaker section must use
this final shape:

```json
{
  "__schema__": {
    "schema_version": "pricing-provider-schema.v1",
    "contract_version": "2026.07.17",
    "provider": "aws",
    "pricing_region": "eu-central-1",
    "snapshot_digest": "sha256:2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e7ae",
    "generated_at": "2026-07-17T00:00:00Z"
  },
  "iotTwinMaker": {
    "usageRates": {
      "entityPricePerMonth": 0.0,
      "queryPrice": 0.0,
      "unifiedDataAccessApiCallPrice": 0.0
    },
    "tieredBundle": {
      "tiers": [
        {
          "tierId": "TIER_1",
          "minimumEntities": 1,
          "maximumEntities": 1000,
          "monthlyBasePrice": 0.0,
          "includedQueries": 0,
          "includedApiCalls": 0,
          "queryOveragePrice": 0.0,
          "apiCallOveragePrice": 0.0
        }
      ]
    }
  }
}
```

`pricing_region` must be the canonical AWS region code used for all rows in the
snapshot. `snapshot_digest` must be computed from the canonical public pricing
payload and stable schema metadata, excluding volatile timestamps and the
digest field itself. Validation must reject a missing region, malformed digest,
or payload whose recomputed digest differs. Until #119 replaces the single AWS
file with immutable region-keyed catalogs, publication may replace only an AWS
snapshot for the same canonical region; a request for another region must fail
with a structured migration-required diagnostic rather than overwrite the
current file. The digest shown above is a format-only SHA-256 example; the
committed snapshot must contain the digest computed from its actual canonical
content.

The final implementation must contain exactly four ordered tiers:

| Tier | Entity range |
|---|---:|
| `TIER_1` | 1-1,000 |
| `TIER_2` | 1,001-5,000 |
| `TIER_3` | 5,001-10,000 |
| `TIER_4` | 10,001-20,000 |

Entity ranges are curated official contract data. Prices, included query/API
limits, and overage rates are dynamic Price List evidence. The schema and
registry must label those source types separately.

The old flat top-level `entityPrice`, `queryPrice`, and
`unifiedDataAccessAPICallsPrice` keys are not part of the final contract.
Production code, fixtures, generated examples, and documentation must migrate
to the nested model in one atomic slice.

### Account Observation SSOT

Successful, user-scoped `PricingRefreshRun` records in the Management API are
the historical SSOT for account observations. The Optimizer response adds a
reserved, secret-free metadata object after the public snapshot has been
written:

```json
{
  "__account_pricing_context__": {
    "schema_version": "aws-twinmaker-account-pricing-context.v1",
    "provider": "aws",
    "service": "iot_twinmaker",
    "region": "eu-central-1",
    "verified_account_id": "123456789012",
    "catalog_snapshot_digest": "sha256:2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e7ae",
    "observed_at": "2026-07-17T00:00:00Z",
    "current_plan": {
      "mode": "STANDARD",
      "billable_entity_count": 0,
      "effective_at": null,
      "updated_at": null,
      "update_reason": null,
      "bundle": null
    },
    "pending_plan": null
  }
}
```

The object may contain only:

- normalized plan enums;
- integer billable entity counts;
- normalized bundle tier and bundle names;
- UTC timestamps;
- bounded provider reason text;
- configured provider region;
- STS-verified twelve-digit provider account ID;
- digest of the exact public catalog snapshot published by the same refresh;
- observation timestamp.

Management enriches the persisted run with its own non-secret binding:

- row ownership through the existing `PricingRefreshRun.user_id`;
- existing owner-visible `credential_summary`;
- the following nested `management_binding`:

```json
{
  "management_binding": {
    "schema_version": "aws-twinmaker-management-binding.v1",
    "pricing_connection_id": "7f62e6f0-36ec-4e90-8f94-f8658afb04ca",
    "connection_fingerprint": "sha256:486ea46224d1bb4fb680f34f7c9ad96a8f24ec88be73ea8e5a6c65260e9cb8a7",
    "verified_account_id": "123456789012",
    "configured_account_id": "123456789012"
  }
}
```

The binding must be added by Management after the Optimizer response returns.
The Optimizer must not accept or construct a Management connection ID or
fingerprint. `configured_account_id` is retained only for mismatch evidence;
the STS value is authoritative. No decrypted credential payload or credential
access-key identifier enters the context.

No new table is required. The existing refresh-run history already provides
owner isolation, connection binding, timestamps, status, and immutable result
evidence. Calculation resolution must query this table; it must not copy the
latest observation into a global singleton or Flutter state.

## Read-Only Provider Boundary

Introduce one Optimizer service boundary responsible for observing the plan:

```text
AwsTwinMakerPricingPlanObserver.observe(credentials, region)
  -> AwsTwinMakerAccountPricingContext
```

The observer must:

- use the provided temporary or long-lived AWS credentials;
- forward the session token when present;
- call `sts:GetCallerIdentity` and normalize its twelve-digit account ID;
- create the TwinMaker client in the configured deployment region;
- call only read-only `GetCallerIdentity` and `GetPricingPlan` operations;
- reject the observation when a configured `cloud_scope.account_id` differs
  from the STS-verified account ID;
- normalize boto3 datetime objects to UTC ISO-8601 strings;
- reject unknown modes and bundle tiers;
- bound list and string fields;
- redact provider error messages;
- distinguish access denied, throttling, authentication, and malformed
  provider response errors;
- never call `UpdatePricingPlan`;
- expose no boto3 response metadata.

The credential checker must exercise:

- `sts:GetCallerIdentity`;
- `pricing:DescribeServices`;
- `pricing:GetAttributeValues`;
- `pricing:GetProducts`;
- `iottwinmaker:GetPricingPlan`.

`aws_region` is mandatory for AWS pricing-purpose credentials. The Pricing API
client may still use its supported endpoint region, but the TwinMaker observer
and resulting public catalog evidence must use the configured target region.
Neither the credential checker nor refresh path may silently default a missing
target region.

`iottwinmaker:GetPricingPlan` belongs only to the pricing-purpose policy and
bootstrap output. It must not be added to `thesis-demo-v1` deployment
permissions.

The credential-based AWS refresh must observe the plan before it performs and
publishes the public catalog refresh. A failed observation fails the user
refresh with a structured, redacted error and must not mutate the cached
pricing file. After successful same-region publication, the Optimizer must add
the computed public snapshot digest to the response-only account context. It
must never write that context into the public pricing file.

## Management Context Resolution

Add a dedicated Management service:

```text
AwsTwinMakerPricingContextService.resolve(user_id)
  -> ResolvedAwsTwinMakerPricingContext
```

Resolution rules:

1. Find the user's current default AWS pricing-purpose CloudConnection.
2. Require `validation_status == valid`.
3. Find the latest successful AWS `PricingRefreshRun` for that exact
   connection.
4. Require the run to contain the versioned account-pricing context.
5. Require the persisted credential fingerprint to match the current
   connection fingerprint.
6. Require observation age not to exceed seven days.
7. Require the STS-verified provider account ID to equal the configured
   `cloud_scope.account_id` when a configured value exists.
8. Require the observation region to equal both the current connection region
   and the public AWS catalog `pricing_region`.
9. Recompute and verify the public catalog `snapshot_digest`.
10. Return an explicit unavailable context with a stable reason code when any
   gate fails.

The public Flutter calculation request remains provider-neutral and cannot
supply this context. The authenticated Management API resolves it and appends a
private `providerPricingContexts.awsTwinMaker` object only to the internal
Optimizer request.

Both calculation paths must use the same resolver:

- `PUT /optimizer/calculate`;
- `POST /twins/{twin_id}/optimizer-runs/`.

The server, not the client, owns the pricing refresh reference. New calculation
runs must persist the resolved AWS refresh-run ID automatically. Arbitrary
client-provided pricing-run references must not establish account trust.
`pricing_run_reference` must be removed from
`CostCalculationRunCreate`; old clients sending it receive the existing
extra-field validation error rather than having the value ignored. The
response field remains for persisted-history compatibility and contains only
the server-resolved reference.

The cross-project data flow is:

```text
AWS Price List API ---- exact public rows ----+
                                             |
                                             v
                                  pricing_dynamic_aws.json
                                  region + immutable digest
                                             |
                                             +----------------------+
                                                                    |
AWS STS + GetPricingPlan -- account proof --> Optimizer refresh     |
                                             response metadata      |
                                                    |               |
                                                    v               v
Flutter --> Management API --> user PricingRefreshRun --> resolver
                                  owner + connection       |
                                  fingerprint + account    |
                                                           v
                                             internal calculation request
                                             public rates + trusted plan
                                                           |
                                                           v
                                             comparable provider candidates
                                             + persisted result trace
```

At no point does Flutter call the Optimizer directly. At no point does an
account observation enter the global pricing file.

## Optimizer Input Contract

The Optimizer accepts this internal-only additive field:

```json
{
  "providerPricingContexts": {
    "awsTwinMaker": {
      "schemaVersion": "aws-twinmaker-account-pricing-context.v1",
      "status": "available",
      "sourceRefreshRunId": "849ad123-68fd-4a9d-90da-82f47c5e11f9",
      "connectionFingerprint": "sha256:486ea46224d1bb4fb680f34f7c9ad96a8f24ec88be73ea8e5a6c65260e9cb8a7",
      "providerAccountId": "123456789012",
      "pricingRegion": "eu-central-1",
      "catalogSnapshotDigest": "sha256:2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e7ae",
      "observedAt": "2026-07-17T00:00:00Z",
      "currentPlan": {
        "mode": "STANDARD",
        "billableEntityCount": 0,
        "effectiveAt": null,
        "updatedAt": null,
        "updateReason": null,
        "bundle": null
      },
      "pendingPlan": null
    }
  }
}
```

The Optimizer Pydantic contract must forbid unknown fields at every nested
level. Context timestamps must be timezone-aware. Modes and tiers must be
enums. Counts must be non-negative integers. The account ID is diagnostic only
and must never participate in arithmetic. The region and catalog digest are
trust gates and must agree with the loaded pricing snapshot.

When Management has no trusted observation it sends:

```json
{
  "status": "unavailable",
  "reasonCode": "NO_SUCCESSFUL_ACCOUNT_PLAN_OBSERVATION"
}
```

The Optimizer must not substitute `STANDARD` for an unavailable context.

## Calculation Semantics

### Functional Completeness Gate

The current Five-Layer baseline requires TwinMaker Knowledge Graph semantics.

| Observed state | AWS L4 comparable? | Behavior |
|---|---|---|
| unavailable/stale/mismatched | no | unsupported with stable reason |
| `BASIC` | no | unsupported: Knowledge Graph unavailable |
| `STANDARD` | yes | usage-based calculation |
| `TIERED_BUNDLE` without allocation inputs | no | non-comparable account-scoped plan |
| any non-null pending plan | no | non-comparable until the pending transition is resolved |
| account/catalog region mismatch | no | contract error; refresh/migrate the matching catalog |
| unknown provider value | no | contract error, never fallback |

An unsupported AWS L4 remains visible in provider diagnostics but is excluded
from optimizer candidate selection through the existing `LayerResult.supported`
contract.

### Standard

```text
standard_cost =
    entity_count * entity_price_per_month
  + queries_per_month * query_price
  + unified_data_api_calls_per_month * api_call_price
```

The calculation remains deterministic, but it must report:

- observed and modeled mode `STANDARD`;
- account scope;
- source refresh-run ID;
- observation age;
- each quantity, unit price, and contribution;
- functional compatibility `compatible`;
- pending-plan state.

### Basic

Basic may expose unified data API pricing, but the current L4 requires
Knowledge Graph. Its AWS L4 result is therefore unsupported regardless of
numeric API-call cost. The result must not assign a zero or partial L4 cost.

### Tiered Bundle

Implement a pure calculator with this explicit contract:

```text
calculate_tiered_bundle_account_cost(
    observed_tier,
    account_entity_count,
    account_queries_per_month,
    account_api_calls_per_month,
    allocation_policy,
    pricing
)
```

Initially supported allocation policy:

`DEDICATED_ACCOUNT_FULL_COST`

This policy means the supplied workload represents the full AWS account usage
and the full account bundle cost belongs to that calculation. No proportional,
equal-share, marginal, or residual allocation may be inferred.

```text
query_overage =
    max(0, account_queries_per_month - included_queries)

api_overage =
    max(0, account_api_calls_per_month - included_api_calls)

account_monthly_cost =
    monthly_base_price
  + query_overage * query_overage_price
  + api_overage * api_overage_price
```

The pure calculator must validate:

- known tier;
- entity count lies within the official tier boundary;
- observed tier agrees with entity count;
- finite, non-negative usage;
- complete Price List evidence;
- explicit allocation policy.

The current UI and Management workflow do not collect authoritative aggregate
account query/API usage and must not infer dedicated-account ownership.
Therefore an observed Tiered Bundle is non-comparable in the executable
Five-Layer optimization until a later bounded account-usage source supplies
that contract. The pure calculator and tests establish the extension point
without presenting guessed costs as production output.

Proration and mid-month tier movement are outside the steady-state monthly
comparison. The trace must state this limitation when a Tiered Bundle is
calculated through the explicit pure contract.

## Public Price List Extraction

TwinMaker extraction must use exact product attributes, not general description
keywords:

- exact configured AWS location;
- service code `IOTTwinMaker`;
- Standard suffixes:
  - `IoTTwinMaker-Entities`;
  - `IoTTwinMaker-Queries`;
  - `IoTTwinMaker-UnifiedDataAccess`;
- Bundle suffixes:
  - `IoTTwinMaker-BaseTier{1..4}-Entities`;
  - `IoTTwinMaker-BaseTier{1..4}-Queries`;
  - `IoTTwinMaker-BaseTier{1..4}-UnifiedDataAccess`.

The extractor must require exactly:

- three Standard dimensions;
- four bundle base dimensions;
- four query overage dimensions;
- four API overage dimensions.

It must reject:

- duplicate positive dimensions for one semantic key;
- missing tiers;
- unknown tier suffixes;
- non-positive prices;
- non-integer or non-monotonic included limits;
- inconsistent overage rates within the same region;
- a location mismatch;
- accidental GovCloud or another-region rows.

Descriptions remain preserved in selected evidence for review but are not the
selection key.

The AWS publication path must fail closed and preserve last-known-good pricing
when the complete TwinMaker contract cannot be constructed. It must not use
static TwinMaker fallbacks in a publishable snapshot.

## Result And Trace Contract

The calculation result adds:

```json
{
  "providerPricingContexts": {
    "awsTwinMaker": {
      "status": "compatible",
      "observedMode": "STANDARD",
      "modeledMode": "STANDARD",
      "scope": "account",
      "sourceRefreshRunId": "uuid",
      "observedAt": "timestamp",
      "pendingPlan": null,
      "functionalCompatibility": "compatible",
      "allocationPolicy": null,
      "reasonCode": null
    }
  }
}
```

Allowed status values:

- `compatible`;
- `unavailable`;
- `functionally_incomplete`;
- `account_allocation_required`;
- `pending_change`;
- `contract_invalid`.

The object must be:

- secret-free;
- persisted in calculation result JSON;
- included in Management pricing-evidence detail metadata;
- included in the AWS L4 intent/result trace;
- retained when AWS L4 is not selected;
- visible through compact, collapsed Flutter diagnostics.

No confidence score may determine compatibility.

## Deployment Selection Gate

Before a calculation run can be selected for deployment:

- if AWS L4 is selected, its TwinMaker context status must be `compatible`;
- the current Management resolver must return the same mode, connection
  fingerprint, account ID when known, and source refresh run;
- the current account observation region and selected public catalog
  region/digest must equal the persisted calculation evidence;
- the observation must still satisfy the seven-day freshness gate;
- no pending plan may exist;
- mismatch returns a typed HTTP 409 with the action to refresh AWS pricing and
  recalculate.

This phase does not pass a Terraform variable. Phase #118 must carry the
persisted expected mode and evidence reference in the
`ResolvedDeploymentSpecification`. The Deployer must never call
`UpdatePricingPlan`.

## Flutter Diagnostics

The existing Pricing Review screen remains the only UI surface. It must not add
a wizard field or pricing-plan selector.

The latest AWS refresh details show a compact summary:

```text
AWS TwinMaker plan
Current: Standard
Account: 123456789012
Observed: 4 minutes ago
Pending: None
[Show technical details]
```

Collapsed details show:

- context schema version;
- current mode and billable entity count;
- bundle tier/names when present;
- pending mode/effective timestamp when present;
- refresh-run ID;
- pricing region;
- compatibility note.

The UI must never imply that the user can change the AWS plan from the app.
Basic, Tiered Bundle, pending changes, stale evidence, and missing permission
states require concise actionable text.

### Desktop Layout

The existing Pricing Review page and provider workspace remain unchanged. Only
the latest-refresh expansion is enriched:

```text
+--------------------------------------------------------------------------+
| Latest refresh                                                    [v]    |
| succeeded - AWS Pricing Account                                           |
+--------------------------------------------------------------------------+
| AWS TwinMaker plan                                                        |
| Current: Standard          Account: 123456789012                          |
| Observed: 4 minutes ago    Pending: None                                  |
|                                                                          |
| Technical details                                                 [v]    |
|   Region: eu-central-1                                                   |
|   Billable entities: 0                                                   |
|   Context schema: aws-twinmaker-account-pricing-context.v1               |
|   Refresh run: 849ad123-68fd-4a9d-90da-82f47c5e11f9                     |
+--------------------------------------------------------------------------+
```

### Narrow Web Layout

The app does not target mobile, but a narrow browser window must remain usable.
Summary values wrap into one vertical column; text must never clip or overlap.

```text
+-------------------------------------------+
| Latest refresh                       [v]  |
| succeeded - AWS Pricing Account           |
+-------------------------------------------+
| AWS TwinMaker plan                        |
| Current: Standard                         |
| Account: 123456789012                     |
| Observed: 4 minutes ago                   |
| Pending: None                             |
|                                           |
| Technical details                    [v]  |
|   Region: eu-central-1                    |
|   Billable entities: 0                    |
|   Context schema: ...                     |
|   Refresh run: ...                        |
+-------------------------------------------+
```

### Widget Tree

```text
PricingReviewScreen [REUSE]
`-- BlocProvider<PricingReviewBloc> [REUSE]
    `-- _PricingReviewView [REUSE]
        `-- PricingRefreshRunSummary [MODIFY]
            |-- ExpansionTile "Latest refresh" [REUSE]
            |   |-- status/access subtitle [REUSE]
            |   |-- AwsTwinMakerPlanSummary [NEW, dumb/private]
            |   |   |-- Wrap [desktop] / Column through responsive Wrap [web]
            |   |   |   `-- label/value text pairs [NEW]
            |   |   `-- ExpansionTile "Technical details" [NEW]
            |   |       `-- SelectableText rows [NEW]
            |   `-- existing run ID [REUSE]
            `-- PricingRefreshRun.awsTwinMakerContext [NEW typed getter/value]
```

`PricingRefreshRunSummary` is extended instead of introducing a second card or
screen because it already owns latest-run diagnostics and the BLoC already
provides the complete run. The private dumb summary receives a typed value and
contains no JSON traversal, HTTP call, business decision, or BLoC access.

All spacing, icon sizes, breakpoints, and radii must reuse `AppSpacing`.
Typography and semantic colors must use `Theme.of(context)`. Only Material
`Icons` may be used. User-facing strings must remain in
`pricing_review_strings.dart`. No inline color literal, numeric layout token,
or `TextStyle` constructor is permitted.

The existing `PricingReviewBloc` remains the state owner. The existing
Management API request is sufficient; no new event, service method, polling,
or direct Optimizer request is allowed.

### API And Dart Field Compatibility

The existing `PricingRefreshRun.result_summary` JSON boundary remains additive.
Flutter must parse the nested value once in the model and expose an immutable
typed value; widgets must not traverse maps.

| Management API JSON | Dart model field | Type and validation |
|---|---|---|
| `result_summary.__account_pricing_context__.schema_version` | `schemaVersion` | non-empty `String` matching the supported version |
| `provider` / `service` | `provider` / `service` | exact normalized `String`; context is omitted unless `aws` / `iot_twinmaker` |
| `region` | `region` | non-empty canonical region `String` |
| `verified_account_id` | `verifiedAccountId` | nullable twelve-digit `String` |
| `observed_at` | `observedAt` | timezone-aware `DateTime`; malformed value invalidates the typed context |
| `current_plan.mode` | `currentMode` | enum-like normalized `String` parsed from the supported set |
| `current_plan.billable_entity_count` | `billableEntityCount` | non-negative `int` |
| `current_plan.bundle` | `currentBundle` | nullable typed bundle value |
| `pending_plan` | `pendingPlan` | nullable typed plan value |
| `management_binding.pricing_connection_id` | `connectionId` | nullable `String`; must match the existing credential summary when present |
| current refresh run ID | existing `refreshRunId` | existing non-empty `String` |

Malformed optional nested context must not make the complete refresh run
unreadable. `PricingRefreshRun` remains valid, exposes no typed TwinMaker
context, and the UI shows the existing run/error summary. Valid context must
round-trip all supported fields exactly.

## Error Contract

Stable reason/error codes:

- `AWS_TWINMAKER_PLAN_PERMISSION_DENIED`;
- `AWS_TWINMAKER_PLAN_THROTTLED`;
- `AWS_TWINMAKER_PLAN_RESPONSE_INVALID`;
- `AWS_TWINMAKER_PLAN_UNOBSERVED`;
- `AWS_TWINMAKER_PLAN_STALE`;
- `AWS_TWINMAKER_PLAN_CONNECTION_CHANGED`;
- `AWS_TWINMAKER_PLAN_ACCOUNT_MISMATCH`;
- `AWS_TWINMAKER_CATALOG_REGION_MISMATCH`;
- `AWS_TWINMAKER_CATALOG_DIGEST_MISMATCH`;
- `AWS_TWINMAKER_BASIC_FUNCTIONALLY_INCOMPLETE`;
- `AWS_TWINMAKER_BUNDLE_ALLOCATION_REQUIRED`;
- `AWS_TWINMAKER_PENDING_PLAN_CHANGE`;
- `AWS_TWINMAKER_BUNDLE_TIER_MISMATCH`.

Client-facing messages must not include raw AWS provider messages. Logs may
include error code, operation, provider, region, correlation ID, and bounded
redacted detail.

## Test Matrix

### Optimizer Unit Tests

- normalize Standard, Basic, Tiered Bundle, current/pending responses;
- reject unknown mode, unknown tier, malformed count, naive timestamps, and
  oversized bundle-name/reason values;
- forward session token and configured region;
- AccessDenied, throttling, authentication, and malformed response errors are
  stable and redacted;
- assert `UpdatePricingPlan` is never referenced or invoked;
- exact Standard Price List row selection;
- exact TIER_1-TIER_4 row selection for Frankfurt and representative US rates;
- duplicate, missing, wrong-region, wrong-tier, and non-monotonic rows fail;
- exact Frankfurt fixture values match the evidence tables in this plan;
- catalog schema requires canonical region and digest and rejects tampering;
- another-region refresh cannot overwrite the current single-region AWS file
  before #119 is implemented;
- schema validation requires the complete nested contract;
- Standard formula dimensions and zero boundaries;
- Basic is functionally incomplete;
- no context, stale context, fingerprint mismatch, account mismatch, pending
  change, and Tiered without allocation are unsupported;
- pure bundle calculator at every entity boundary:
  `1`, `1000`, `1001`, `5000`, `5001`, `10000`, `10001`, `20000`;
- each included query/API boundary and first overage unit;
- simultaneous query/API overage;
- invalid tier/entity pair and unsupported allocation policy;
- unsupported AWS L4 is excluded while other provider candidates remain
  calculable;
- traces preserve plan diagnostics whether AWS wins or loses.

### Management API Tests

- successful AWS refresh persists account context only in the owner's run;
- context is absent from the global pricing snapshot export;
- another user cannot resolve or read it;
- resolver uses only the current default validated pricing connection;
- wrong connection, deleted connection, changed fingerprint, account mismatch,
  account/catalog region mismatch, catalog digest mismatch, failed run, stale
  run, malformed context, and missing run fail closed;
- direct authenticated calculation and persisted run calculation inject the
  same internal context;
- Flutter/public request cannot inject `providerPricingContexts`;
- calculation run stores the server-selected refresh reference;
- AWS L4 deployment selection rejects stale or changed plan context with 409;
- non-AWS L4 selection does not require an AWS plan context;
- refresh/result/evidence responses remain secret-free.

### Flutter Tests

| Kind | Required case | Hard assertion |
|---|---|---|
| Happy | Standard, no pending plan | Current plan, verified account, region, observation, and refresh ID render exactly |
| Happy | Tiered context diagnostics | Tier and billable entity count render, while no mutation action exists |
| Unhappy | Basic/incomplete | Actionable incompatibility text renders |
| Unhappy | Permission denied/unavailable | Stable user message renders without provider detail |
| Edge | pending plan | Pending mode/effective timestamp render and compatibility is blocked |
| Edge | malformed nested context | Widget remains stable and omits invalid technical rows |
| Edge | long account/status text | Desktop and narrow Web layouts do not overflow |
| Edge | region mismatch | Catalog/account region mismatch is explicit |
| Edge | stale context | Refresh action is indicated through existing workflow |
| Edge | missing context | Existing refresh run remains inspectable |
| Edge | demo degraded scenario | Missing-plan case is deterministic |

### Regression And Security Gates

Run from repository root unless a command changes directory:

```bash
docker compose up -d
docker compose ps

docker compose exec -T 2twin2clouds \
  python -m pytest tests/ -q
docker compose exec -T management-api \
  python -m pytest tests/ -q
docker compose exec -T 3cloud-deployer \
  python -m pytest tests/ --ignore=tests/e2e -q

docker compose exec -T 2twin2clouds \
  bandit -q -r api backend
docker compose exec -T management-api \
  bandit -q -r src
docker compose exec -T 3cloud-deployer \
  bandit -q -r src

cd twin2multicloud_flutter
flutter analyze
flutter test
flutter build web --release
flutter build macos --debug
cd ..

docker compose exec -T docs mkdocs build --strict
```

The live Flutter integration gate must start from `docker compose up -d`, use
the real Management API at port 5005, assert exact returned schema values, and
must not mock dio:

```bash
cd twin2multicloud_flutter
flutter test integration_test/management_api_readiness_test.dart -d macos \
  --dart-define-from-file=config/dev.json
cd ..
```

The read-only AWS smoke must assert:

- `GetPricingPlan` returns a recognized normalized mode;
- Frankfurt extraction returns exactly three Standard and twelve bundle
  dimensions;
- TIER_1-TIER_4 limits and prices equal the selected rows;
- the pricing file contains no account context;
- the snapshot records `eu-central-1`, its digest recomputes exactly, and the
  observed account context reports the same region;
- the STS account ID is normalized and no configured-account mismatch is
  accepted;
- changed-file secret scan finds no credential value;
- CloudTrail/API instrumentation or an explicit mocked-call assertion confirms
  no `UpdatePricingPlan` call;
- no deployment endpoint and no real cloud resource operation is invoked.

If a host does not support the macOS build, Linux and Windows builds remain
mandatory CI gates after push. This local environment must still build Web and
macOS before handoff.

Docker services may remain running for the next pre-Phase-8 slice. Do not run
the repository's real deployment E2E tests.

## Documentation Impact

Update:

- Optimizer pricing architecture and formula documentation;
- AWS pricing credential setup and policy reference;
- Pricing Review user guide;
- existing
  `twin2multicloud_flutter/docs/frontend_delta/phases/PHASE_04_PRICING_REVIEW_CENTER.md`
  with the implemented account-plan diagnostics;
- Management API data-flow and persistence documentation;
- component interaction documentation;
- refactoring roadmap and this mini-roadmap;
- legacy standalone Optimizer HTML only where it still serves as a compatibility
  reference.

Developer documentation must explain the implemented contract and extension
point. Thesis reasoning and evaluation remain in thesis-specific research
documents, not the general user/developer documentation.

## Review Gates

### Plan Review

- [x] Deep concept and roadmap alignment is explicit.
- [x] Every account/global ownership boundary is explicit.
- [x] Account identity is STS-verified rather than trusted from user input.
- [x] Catalog region and digest are explicit and mismatch fails closed.
- [x] No user input can establish trusted account plan context.
- [x] No per-twin bundle allocation is inferred.
- [x] Basic functional incompleteness is explicit.
- [x] Pending-plan behavior is deterministic.
- [x] #118 and #119 ownership is not duplicated.
- [x] Required production and test file boundaries are concrete.
- [x] Optimizer, Management, and Flutter datatypes are field-compatible.
- [x] Existing screens, BLoC ownership, services, and theme tokens are reused.
- [x] Desktop and narrow-Web layouts plus widget tree are complete.
- [x] Flutter calls only the Management API.
- [x] Loading/error/malformed states remain explicit and non-blocking.
- [x] Unit, API, integration, security, build, docs, and read-only smoke gates
  contain hard assertions.
- [x] No real deployment E2E or mutating provider operation is scheduled.
- [x] Documentation updates are separated from thesis evaluation.
- [x] Test matrix covers every mode, tier, boundary, trust failure, and output.
- [x] Architect and builder reviews both reached zero open plan findings.

### Implementation Review Pass 1

- [ ] Compare implementation line-by-line with this contract.
- [ ] Trace all AWS TwinMaker pricing keys and remove flat production aliases.
- [ ] Trace every account-context write/read path for owner isolation.
- [ ] Verify no mutating TwinMaker API exists.
- [ ] Run targeted tests and fix all findings.

### Implementation Review Pass 2

- [ ] Review error handling, redaction, timestamps, concurrency, and stale data.
- [ ] Review calculation comparability and candidate exclusion.
- [ ] Review API/UI diagnostics for misleading plan-change affordances.
- [ ] Run full project gates and fix all findings.

## Definition Of Done

- [ ] Public TwinMaker rates and account plan observations have separate SSOTs.
- [ ] The full Standard and TIER_1-TIER_4 Price List contract is exact and
  evidence-backed.
- [ ] `GetPricingPlan` is least-privilege, read-only, tested, and redacted.
- [ ] Basic cannot participate in the semantic L4 comparison.
- [ ] Standard calculation uses the observed account mode.
- [ ] Tiered Bundle has a correct pure account calculator but remains
  non-comparable without explicit aggregate allocation context.
- [ ] Pending changes and stale/mismatched evidence fail closed.
- [ ] AWS account observation, connection, and public catalog use the same
  canonical region and verified digest.
- [ ] Calculation traces and Flutter diagnostics expose the relevant plan state.
- [ ] AWS L4 deployment selection cannot use a stale or different observed plan.
- [ ] No plan is changed, no cloud resource is deployed, and no secret is
  persisted outside the existing encrypted CloudConnection store.
- [ ] Optimizer, Management API, and Deployer non-E2E test suites pass.
- [ ] Flutter analyze, tests, Web build, and local desktop build pass.
- [ ] Linux and Windows Flutter CI gates pass after push.
- [ ] Bandit, OpenAPI, MkDocs strict, link, and secret-scan gates pass.
- [ ] The bounded read-only AWS smoke verifies plan and exact price extraction.
