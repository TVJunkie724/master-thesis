# Pricing Catalog Reliability

## Purpose

This concept defines the target architecture for reliable cloud pricing in Twin2MultiCloud.
It replaces the current fetch-and-publish mindset with a reviewable pricing data product:
provider catalog data is fetched, normalized, matched, reviewed when needed, and only then
published into optimizer calculations.

Parent epic: GitHub issue #69.

## Problem

The current optimizer pricing path relies on provider-specific string and keyword matching.
That is fragile because AWS, Azure, and GCP catalogs can change service names, SKU labels,
meter names, unit descriptions, pricing modes, tier boundaries, and regional availability.

The main risk is not only a failed fetch. The worse risk is a successful-looking fetch that
selects the wrong catalog row, normalizes it incorrectly, writes a valid-looking pricing file,
and then drives optimizer results with misleading data.

Logs are useful for diagnostics, but they are not a pricing quality contract. A user who
clicks "refresh pricing" in Flutter needs actionable state, not only a stream of log lines.

## Target Architecture

```
Provider pricing API
        |
        v
Catalog snapshot
        |
        v
Candidate extraction
        |
        v
Versioned pricing intent registry
        |
        v
Deterministic matcher
        |
        +--> matched --------------------+
        |                                |
        +--> missing / ambiguous / drift |
        |                                v
        |                         Review required
        |                                |
        v                                v
Last-known-good pricing <------ publish decision
        |
        v
Optimizer calculation snapshot
```

The key rule is:

```
Fetching latest provider data is not the same as publishing pricing for calculations.
```

Refresh can complete successfully while still producing `review_required` if the new catalog
data is missing, ambiguous, changed, or only usable through a static fallback.

## Core Concepts

### Pricing Intent

A pricing intent is the provider-neutral cost component used by the optimizer, such as:

- `transfer.egress_gb`
- `iot.message_ingest`
- `functions.request`
- `functions.compute_gb_second`
- `storage.hot.storage_gb_month`
- `storage.hot.read_request`
- `storage.archive.write_request`
- `api.request_million`
- `orchestration.state_transition`
- `event_bus.event_million`
- `digital_twin.query_unit`
- `grafana.editor_user_month`

The intent is owned by the optimizer cost model, not by any provider catalog.

### Catalog Snapshot

A catalog snapshot records the provider response used during a refresh run. It must be
secrets-free and should retain enough metadata to reproduce candidate extraction:

- provider
- fetch timestamp
- region or region scope
- raw provider identifiers where available
- source API and request scope
- sanitized raw rows or references to sanitized raw rows

### Pricing Candidate

A candidate is a normalized provider row that might satisfy one or more pricing intents.
It preserves evidence instead of collapsing immediately to a single number:

- provider
- provider service name/code
- SKU, meter, product, term, or equivalent stable identifier
- region or region scope
- unit and unit description
- price type or pricing mode
- tier/quantity information
- raw price and currency
- source snapshot identifier
- extraction reason/evidence

### Mapping Registry

The mapping registry is versioned and curated. It describes how a provider candidate maps to
a pricing intent, including expected identifiers, acceptable units, tier assumptions, and
normalization rules.

Runtime matching must be deterministic. It may score evidence, but it must not silently pick
between multiple plausible rows. Ambiguity is a state, not a hidden implementation detail.

### Publication State

Pricing refresh outcomes must be explicit:

- `matched`: catalog data matched the curated mapping and can be published
- `missing`: expected mapping target was not found
- `ambiguous`: multiple plausible candidates exist
- `changed`: identifiers, units, tiers, or pricing mode changed
- `failed`: provider/API/auth/network failure
- `fallback_static`: a reviewed static fallback is used
- `last_known_good`: calculations use the last reviewed published price
- `review_required`: user or maintainer action is needed before publishing new data

## UI Principle

Flutter logs remain diagnostic. They do not carry business state.

The pricing area in Step 2 needs typed review state from the Management API. A user should be
able to see whether calculation will use fresh pricing, stale pricing, last-known-good pricing,
or a fallback. When drift occurs, the UI must show that refresh produced review-required data
instead of implying that the user can solve it by reading log lines.

The first review UI should stay thesis-appropriate:

- show provider and intent status
- explain whether calculation can continue with last-known-good data
- expose selected candidate and alternatives when the API supports it
- allow deliberate keep/accept/fallback decisions only after the backend contract exists

## LLM Position

An LLM may be useful as an offline catalog curation assistant, for example to explain why a
candidate likely maps to an intent. It must not be a runtime dependency for optimizer results.
The production path remains deterministic and reproducible.

## Issue Roadmap

| Issue | Role |
|---|---|
| #69 | Epic: Pricing Catalog Reliability |
| #85 | Fix credential-forward pricing refresh boundaries |
| #86 | Align optimizer permission checks with pricing fetch operations |
| #81 | Introduce provider catalog snapshots and pricing candidate extraction |
| #82 | Create versioned pricing intent registry and deterministic matcher |
| #83 | Add pricing drift detection and last-known-good publishing |
| #84 | Expose pricing review state in Management API and Flutter |
| #32 | Refresh optimizer pricing schema and provider fetchers for expanded services |

## Implementation Order

1. Fix credential-forward boundaries first so pricing refresh uses the intended identity.
2. Align permission checks with the actual fetch operations.
3. Add snapshots and candidates so raw provider data becomes inspectable.
4. Add the mapping registry and deterministic matcher.
5. Add drift detection and last-known-good publication.
6. Expose typed review state through the Management API and Flutter.
7. Refresh provider fetchers against the new registry instead of direct keyword publishing.

## Verification Strategy

No live cloud E2E tests are required for these slices.

Use deterministic tests with mocked provider payloads:

- credential-forward refresh never reads local credential files
- Azure public pricing does not require local credentials
- AWS session tokens are forwarded consistently
- candidate extraction preserves ambiguous rows
- matcher produces stable outcomes independent of row order
- missing/ambiguous/changed/failure states are explicit
- last-known-good data is not overwritten by uncertain refreshes
- Flutter renders typed review state instead of parsing log text

## Non-Goals

- No full cost-model rewrite in this concept.
- No GPT runtime matcher.
- No broad catalog administration product.
- No live provider E2E until the refactoring roadmap reaches final validation.
