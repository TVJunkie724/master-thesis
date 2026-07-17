---
title: "Immutable Region-Scoped Pricing Catalogs"
description: "Replace mutable provider-wide pricing files with immutable, reviewed catalog snapshots that every calculation resolves by exact identity."
tags: [optimizer, management-api, flutter, pricing, architecture]
lastUpdated: "2026-07-17"
version: "1.0"
---

<!-- SOURCES:
- GitHub issue #119 "Make provider pricing catalogs immutable and region-scoped"
- GitHub epic #31 "Implement tiered pricing for additional optimizer services"
- docs/plans/2026-06-06_pricing_catalog_reliability.md
- docs/plans/2026-06-08_pricing_evidence_and_optimization_strategy_roadmap.md
- FRONTEND_ARCHITECTURE.md
- integration_vision.md
- 2-twin2clouds/DEVELOPMENT_GUIDE.md
- twin2multicloud_backend/DEVELOPMENT_GUIDE.md
- twin2multicloud_flutter/docs/frontend_delta/ROADMAP_FRONTEND_DELTA.md
- 2-twin2clouds/backend/config_loader.py
- 2-twin2clouds/backend/constants.py
- 2-twin2clouds/backend/pricing_cache.py
- 2-twin2clouds/backend/pricing_catalog_candidates.py
- 2-twin2clouds/backend/pricing_publication_state.py
- 2-twin2clouds/backend/pricing_schema.py
- 2-twin2clouds/backend/fetch_data/calculate_up_to_date_pricing.py
- 2-twin2clouds/api/calculation.py
- 2-twin2clouds/api/pricing.py
- twin2multicloud_backend/src/services/optimizer_calculation_service.py
- twin2multicloud_backend/src/services/cost_calculation_run_service.py
- twin2multicloud_backend/src/services/pricing_refresh_run_service.py
- twin2multicloud_backend/src/services/optimizer_configuration_service.py
- twin2multicloud_backend/src/services/pricing_review_state_service.py
- twin2multicloud_backend/src/services/pricing_health_service.py
- twin2multicloud_flutter/lib/services/api_service.dart
- twin2multicloud_flutter/lib/models/pricing_export_snapshot.dart
- twin2multicloud_flutter/lib/models/optimizer_config.dart
- twin2multicloud_flutter/lib/models/twin_configuration_view.dart
- twin2multicloud_flutter/lib/bloc/wizard/handlers/wizard_optimization_persistence_handlers.dart
- twin2multicloud_flutter/lib/widgets/twin_overview/twin_overview_configuration_review.dart
- compose.yaml
EXTRACTED: 2026-07-17 | VERSION: 1.0
-->

# Immutable Region-Scoped Pricing Catalogs

## Issue Context

GitHub issue:
[#119](https://github.com/TVJunkie724/master-thesis/issues/119)

Parent epic:
[#31](https://github.com/TVJunkie724/master-thesis/issues/31)

This is Phase 18.1 of the pricing evidence roadmap and a mandatory
pre-Phase-8 hardening slice. Route-aware transfer pricing in
[#116](https://github.com/TVJunkie724/master-thesis/issues/116) and resolved
deployment specifications in
[#118](https://github.com/TVJunkie724/master-thesis/issues/118) must consume
stable pricing evidence rather than mutable global files.

## Current Finding

The present calculation path is not snapshot-bound:

1. provider refreshes replace one global file per provider;
2. `load_combined_pricing()` reads those three files during calculation;
3. Flutter exports the files only after calculation;
4. the Management API accepts those client-provided exports and stores them in
   compatibility fields;
5. neither the stored exports nor their timestamps prove which bytes the
   calculation actually used.

This creates three concrete integrity risks:

- refreshing another region can change the global pricing source;
- a refresh can race with a calculation between provider file reads;
- a client can persist pricing evidence different from the evidence used by
  the Optimizer.

The existing AWS region guard prevents one particular overwrite by rejecting a
second region. It does not provide a multi-region catalog, exact calculation
binding, or a provider-neutral solution.

## Goal

Every cost calculation must resolve exactly one immutable, reviewed pricing
snapshot for AWS, Azure, and GCP before formula execution starts. The
calculation result, Management API persistence, audit detail, and Flutter read
models must carry the same three references.

Refreshing or reviewing a catalog may create and publish a new snapshot. It
must never alter a prior snapshot or change the bytes resolved through an
already selected reference.

## Scope

| In scope | Out of scope |
|---|---|
| ✅ Immutable public pricing snapshots keyed by provider and canonical region | ❌ Region as an optimization decision variable |
| ✅ Exact calculation binding and persisted catalog references | ❌ Eventing Layer or Architecture Profile implementation |
| ✅ Provider-neutral refresh, publication, LKG, stale, and tamper behavior | ❌ Route-aware transfer formulas owned by #116 |
| ✅ Pinned, reviewed Europe baseline migration | ❌ New provider services or pricing intents |
| ✅ Durable single-instance runtime catalog volume | ❌ Horizontally distributed catalog storage |
| ✅ Owner-safe Management context resolution | ❌ New role/permission model |
| ✅ Compact read-only Flutter evidence | ❌ Pricing catalog editor or global publish control |
| ✅ Deterministic mocked/provider-read-only verification | ❌ Real deployment or paid cloud E2E |

## Non-Goals

- no region optimization;
- no dynamic architecture or Eventing Layer;
- no pricing editor;
- no database or distributed object store in the Optimizer;
- no multi-host or multi-writer Optimizer deployment;
- no provider credentials in catalog documents;
- no automatic acceptance of review-required candidates;
- no account-scoped observations in public catalog snapshots;
- no real cloud deployment E2E;
- no route-aware transfer formula implementation; that remains #116;
- no selected deployment SKU/tier propagation; that remains #118.

## Final Ownership

| Data | Owner | Persistence | Mutability |
|---|---|---|---|
| Pricing registry and mappings | Optimizer repository | versioned YAML | changed by reviewed code changes |
| Public provider pricing payload | Optimizer catalog repository | immutable JSON in durable runtime volume | never mutated |
| Published pointer per provider and region | Optimizer catalog repository | atomic JSON pointer in durable runtime volume | replaceable |
| Pinned thesis/dev baseline references and seed snapshots | Optimizer repository | versioned read-only seed package | changed by reviewed code changes |
| Account-scoped pricing observations | Management API | encrypted CloudConnection plus owner-scoped refresh run | user scoped |
| Calculation catalog references | Management API | calculation run and optimizer config JSON reference set | immutable per run |
| Pricing display state | Flutter | typed API read model | never authoritative |

Flutter is not a pricing evidence writer. The Management API is not a public
catalog store. The Optimizer does not persist credentials or account-scoped
observations.

## Canonical Data Flow

```text
Provider catalog API
        |
        v
provider fetch + deterministic normalization
        |
        v
immutable candidate snapshot
        |
        +-- review required --> stored candidate only
        |                       published pointer unchanged
        |
        `-- reviewed/publishable
                |
                v
       atomic provider+region pointer

Management calculation request
        |
        v
PricingCatalogContextService
        |
        +-- latest usable owner refresh reference
        `-- pinned baseline reference when no owner refresh exists
                |
                v
exact three-reference context injected into Optimizer
                |
                v
Optimizer resolves and verifies all immutable documents
                |
                v
formula execution
                |
                v
result carries exact references
                |
                +--> Management calculation-run persistence
                +--> optimizer-config projection
                `--> Flutter read-only diagnostics
```

## Catalog Storage Layout

The Optimizer owns two deliberately separate roots.

The source-controlled, read-only baseline seed package is:

```text
2-twin2clouds/json/pricing_catalog_baselines/
|-- baseline.json
|-- aws/
|   `-- eu-central-1/
|       `-- snapshots/
|           `-- pcs_<64 lowercase hex>.json
|-- azure/
|   `-- westeurope/
|       `-- snapshots/
|           `-- pcs_<64 lowercase hex>.json
`-- gcp/
    `-- europe-west1/
        `-- snapshots/
            `-- pcs_<64 lowercase hex>.json
```

The durable runtime store is configured through
`PRICING_CATALOG_STORE_ROOT` and defaults in Compose to:

```text
/var/lib/twin2multicloud-optimizer/pricing-catalogs/
|-- baseline.json
|-- aws/
|   `-- eu-central-1/
|       |-- published.json
|       |-- refresh.lock
|       `-- snapshots/
|           `-- pcs_<64 lowercase hex>.json
|-- azure/
|   `-- westeurope/
|       |-- published.json
|       |-- refresh.lock
|       `-- snapshots/
|           `-- pcs_<64 lowercase hex>.json
`-- gcp/
    `-- europe-west1/
        |-- published.json
        |-- refresh.lock
        `-- snapshots/
            `-- pcs_<64 lowercase hex>.json
```

Rules:

- `compose.yaml` mounts a named `optimizer_pricing_catalogs` volume at the
  runtime root;
- startup seeds an empty runtime root from the read-only baseline package
  idempotently and verifies canonical bytes and digests before publishing
  baseline pointers;
- startup never replaces an existing runtime snapshot or published pointer;
- unit tests inject a temporary runtime root and never touch the repository or
  shared Compose volume;
- provider and region path segments are canonicalized and allowlist-validated;
- callers never construct paths directly;
- snapshot creation uses exclusive creation and a byte-equality collision
  check;
- an existing snapshot is never replaced;
- `published.json` is written with fsync and same-directory atomic replace;
- a pointer contains only an immutable reference, never pricing values;
- one region has one pointer file, so publishing another region cannot replace
  it;
- `baseline.json` pins the reviewed repository defaults and is not changed by
  runtime refreshes;
- runtime `baseline.json` is an exact initialized copy of the committed
  manifest and is rejected if its bytes or references drift;
- account context, credentials, access-key identifiers, project secrets, and
  subscription secrets are forbidden in every catalog document.

The following provider-wide files are removed from production lookup and from
the repository after migration:

```text
json/fetched_data/pricing_dynamic_aws.json
json/fetched_data/pricing_dynamic_azure.json
json/fetched_data/pricing_dynamic_gcp.json
```

There is no symlink, compatibility copy, implicit fallback path, or duplicated
runtime SSOT.

## Snapshot Contract

Each immutable document has this envelope:

```json
{
  "schema_version": "pricing-catalog-snapshot.v2",
  "reference": {
    "schema_version": "pricing-catalog-reference.v1",
    "snapshot_id": "pcs_<64 lowercase hex>",
    "provider": "aws",
    "pricing_region": "eu-central-1",
    "provider_schema_version": "pricing-provider-schema.v1",
    "contract_version": "2026.07.17",
    "registry_version": "2026.07.17",
    "mapping_versions": ["2026.07.17"],
    "fetched_at": "2026-07-17T16:00:19.568525Z",
    "content_digest": "sha256:<64 lowercase hex>",
    "source": "provider_api",
    "review_status": "reviewed",
    "publication_status": "published",
    "calculation_source": "fresh"
  },
  "pricing": {}
}
```

### Reference Invariants

- schema version is exact;
- provider is one of `aws`, `azure`, `gcp`;
- region is canonical and non-empty;
- provider schema, contract, registry version, and at least one mapping version
  are present;
- mapping versions are unique and lexicographically sorted;
- `fetched_at` is UTC and timezone-aware;
- content digest matches the canonical pricing payload;
- snapshot ID is the SHA-256 identity of provider, region, all versions,
  `fetched_at`, content digest, source, and review status;
- only `review_status=reviewed` and `publication_status=published` references
  may enter calculation;
- `calculation_source` is one of `fresh`, `last_known_good`, or
  `reviewed_baseline`;
- the complete reference is immutable.

### Digest Invariants

The canonical pricing content digest:

- removes `__account_pricing_context__`;
- removes volatile `generated_at`, embedded digest, and publication decision
  timestamps;
- retains quality and provider evidence because they affect trust;
- serializes with sorted keys, compact separators, ASCII, and disallows
  non-finite values;
- is recomputed on every read.

The snapshot ID is computed separately from the immutable reference identity.
This permits two observations with identical pricing bytes but different fetch
times to remain distinct audit events.

### Review-Required Candidates

A valid but unreviewed candidate may be stored as an immutable snapshot with:

```text
review_status      = review_required
publication_status = candidate
```

It may be returned in refresh diagnostics but:

- cannot replace `published.json`;
- cannot be returned as a calculation reference;
- cannot be selected by latest/last-known-good resolution;
- cannot become publishable through a Flutter request.

The existing user review workflow does not publish a global pointer in this
slice. It records a user-scoped decision in the Management API. Without an
authorization/role model, no Flutter action may change the shared Optimizer
catalog. A future governed publication capability must create a distinct
reviewed reference and atomically update only the matching provider-region
pointer.

## Baseline Migration

Migration is deterministic and committed:

1. convert the current evidence-backed AWS Frankfurt and Azure West Europe
   payloads into v2 baseline seed envelopes;
2. attempt to regenerate the GCP Europe West 1 baseline through the bounded
   read-only Billing Catalog path because the old file has no trustworthy fetch
   metadata;
3. if Google rejects every retained credential, preserve the legacy GCP
   calculation payload only as an explicit curated emergency baseline: use the
   human review timestamp rather than claiming an API fetch, retain
   `fallback_static` quality state, add `curated_legacy_review` provenance, and
   document that provider fetcher/mapping hardening must replace it;
4. add missing provider-region metadata and content digests consistently;
5. mark the repository-approved starting snapshots as
   `reviewed_baseline`, including explicit quality/evidence state;
6. pin all three references in the committed `baseline.json`;
7. initialize matching provider-region pointers only when a runtime volume is
   empty;
8. verify every migrated payload produces the same cost outputs for the
   committed Europe regression scenarios;
9. delete the provider-wide production files and constants.

Migration never derives `fetched_at` from filesystem mtime, Git commit time, or
the migration clock for an older payload. Those timestamps do not prove a
provider observation. Every baseline reference must identify either a real
read-only provider retrieval or a separately documented curated static source
with an explicit review timestamp and source classification.

Static or curated price sources are not hidden. A reviewed baseline may remain
calculable while its quality metadata lists static sources. A newly fetched
candidate with unresolved fields remains review-required and cannot silently
replace that baseline.

The 2026-07-17 GCP preflight result is `401 UNAUTHENTICATED` for every retained
service-account file. The implementation therefore uses the explicit curated
emergency-baseline branch above. It does not relabel the payload as fresh
Billing Catalog evidence and does not close provider fetcher/mapping hardening.

## Optimizer Domain Boundary

Add a focused `PricingCatalogRepository` and immutable dataclasses/Pydantic
models under the Optimizer backend. It owns:

- canonical provider/region validation;
- reference and snapshot construction;
- content and identity digest calculation;
- immutable write;
- pointer publication;
- pinned baseline resolution;
- exact-reference resolution;
- latest published resolution;
- freshness evaluation;
- tamper detection;
- safe metadata projection.

No fetcher, route, calculation engine, or Flutter-facing adapter may open a
catalog path directly.

The repository accepts explicit baseline and runtime roots. Runtime
configuration is validated at process startup. A missing, unwritable, or
inconsistently seeded runtime root fails readiness rather than falling back to
the source tree.

### Required Operations

```text
store_candidate(provider, region, pricing, review_state, source)
    -> PricingCatalogSnapshot

publish(reference)
    -> PricingCatalogReference

resolve_exact(reference, require_fresh=True)
    -> PricingCatalogSnapshot

resolve_published(provider, region, require_fresh=True)
    -> PricingCatalogSnapshot

resolve_baseline(provider, require_fresh=True)
    -> PricingCatalogSnapshot

status(provider, region)
    -> PricingCatalogStatus
```

Reads return deep immutable/copy-safe values. No caller receives a mutable
repository-owned object.

## Refresh And Publication

All three provider refresh paths use one orchestration boundary:

```text
determine canonical region
  -> acquire provider+region refresh guard
  -> fetch and normalize
  -> validate provider schema/evidence
  -> store immutable candidate
  -> build publication decision against same-region LKG
  -> publish only when reviewed/publishable
  -> return candidate + active calculation reference
```

### Region Rules

- AWS region is mandatory and credential-bound.
- GCP region is mandatory and credential-bound.
- Azure receives an explicit public pricing region, defaulting to
  `westeurope` only at the Management API/UI boundary.
- region aliases are normalized before storage;
- a snapshot cannot contain rows for an undocumented fallback region;
- provider rows that are global remain tagged as global evidence inside a
  region-scoped request;
- service-specific Azure deployment-region overrides are not optimized here.
  Their pricing and topology implications remain explicit downstream inputs
  for #116/#118; this slice must not silently claim that one primary region
  proves a different service-region price.

### Concurrency

The refresh guard key is `(provider, pricing_region)`, not provider alone:

- duplicate same-region refresh returns a stable conflict;
- different regions may refresh concurrently;
- a Linux advisory file lock in the durable store coordinates API workers in
  the single Optimizer container; the in-process lock is not the sole guard;
- immutable file creation is collision-safe;
- pointer replacement is atomic;
- a calculation that already owns exact references is unaffected by pointer
  movement.

The Compose deployment intentionally runs one Optimizer writer instance.
Replacing the local durable volume with a distributed object store and
distributed lock is a separate scaling architecture, not hidden behind this
filesystem repository.

## Optimizer API Contract

### Internal Calculation Context

The calculation request adds a Management-injected object:

```json
{
  "providerPricingCatalogs": {
    "schemaVersion": "provider-pricing-catalog-context.v1",
    "catalogs": {
      "aws": {"...": "PricingCatalogReference"},
      "azure": {"...": "PricingCatalogReference"},
      "gcp": {"...": "PricingCatalogReference"}
    }
  }
}
```

The object is strict:

- exactly three providers;
- map key equals reference provider;
- no extra providers or fields;
- all references are reviewed, published, fresh, and exact;
- AWS catalog region/digest equals the owner-scoped TwinMaker account context;
- no client-facing Management schema accepts this trusted context.

`load_combined_pricing()` is replaced by:

```text
PricingCatalogResolver.resolve_context(context)
    -> immutable combined pricing + exact reference set
```

The calculation endpoint resolves all three documents before invoking any
formula. Any missing, stale, altered, unreviewed, unknown, or mismatched
reference fails the entire calculation. It never substitutes `{}`, zero, a
different pointer, or a provider-wide default.

The result contains:

```json
{
  "pricingCatalogs": {
    "schemaVersion": "provider-pricing-catalog-context.v1",
    "catalogs": {
      "aws": {},
      "azure": {},
      "gcp": {}
    }
  }
}
```

The result references must byte-for-byte equal the validated input references.

### Catalog Read Endpoints

Provide:

- baseline reference per provider;
- published reference and status for a provider-region;
- exact snapshot export by provider, region, and snapshot ID.

Full snapshot export is diagnostic and read-only. Existing unscoped
`/pricing/export/{provider}` is removed; callers must identify a region or an
exact snapshot.

Pricing age/status endpoints become region-aware and return catalog identity,
freshness, review state, and active calculation reference. File mtime is not a
business timestamp.

## Stable Errors

Optimizer uses structured, secret-free codes:

| Code | Meaning |
|---|---|
| `PRICING_CATALOG_CONTEXT_MISSING` | calculation did not receive all three references |
| `PRICING_CATALOG_REFERENCE_INVALID` | malformed or internally inconsistent reference |
| `PRICING_CATALOG_NOT_FOUND` | exact immutable document does not exist |
| `PRICING_CATALOG_STALE` | reference exceeds the allowed freshness policy |
| `PRICING_CATALOG_TAMPERED` | content or identity digest mismatch |
| `PRICING_CATALOG_UNREVIEWED` | candidate is not approved for calculation |
| `PRICING_CATALOG_REGION_MISMATCH` | requested and stored region differ |
| `PRICING_CATALOG_VERSION_UNSUPPORTED` | schema/contract version cannot execute |
| `PRICING_CATALOG_REFRESH_IN_PROGRESS` | same provider-region refresh is active |

Management maps prerequisite conflicts to 409, malformed public requests to
422, downstream integrity/contract failures to 502, and Optimizer
unavailability to 503. Provider or raw filesystem errors are logged after
redaction and are not returned verbatim.

## Management API Boundary

Add `PricingCatalogContextService`.

For each provider it resolves:

1. the newest usable, owner-scoped successful pricing refresh reference;
2. otherwise the pinned repository baseline reference;
3. never another user's refresh run;
4. never a review-required candidate;
5. never a client-provided full pricing object.

It verifies the three references with the Optimizer read boundary and injects
them into:

- direct `/optimizer/calculate`;
- persisted `CostCalculationRunService.create_run`.

The AWS account-plan context and AWS catalog context are resolved together and
must agree on region and digest before one downstream request is made.

### Persistence

Add one explicit JSON column to:

- `cost_calculation_runs`;
- `optimizer_configurations`.

The column stores only the strict three-reference context, not full provider
payloads. An idempotent migration adds and backfills it from trustworthy
existing result JSON where possible; unverifiable old rows remain readable but
cannot be newly selected for deployment.

The application stops reading or writing the old client-supplied full snapshot
and timestamp fields. Physical removal may use a later destructive migration,
but these columns are outside the live application contract after this slice.

`pricing_run_reference` remains the AWS account-observation reference owned by
#115 and is not overloaded with public catalog IDs.

### Existing Save Contract

`OptimizerResultUpdate` no longer accepts:

- `pricing_snapshots`;
- `pricing_timestamps`.

The Management API validates `result.pricingCatalogs`, persists its exact
reference set, and rejects a result without a complete trusted context. This
removes the current client-authored audit boundary.

Cost-calculation result detail and pricing-evidence detail expose the stored
catalog reference set.

Pricing Health and Pricing Review stop deriving last-known-good state from the
legacy full pricing blobs. Both use the same owner-scoped active catalog
context and immutable references as calculation. A reference is considered
usable only after Optimizer verification; the presence of a legacy blob or
timestamp never implies readiness.

Pricing refresh responses and `PricingRefreshRun.result_summary_json` contain
only:

- the immutable candidate reference;
- the active calculation reference after publication or last-known-good
  retention;
- bounded publication, quality, selected/rejected-count, and error summaries;
- the separate owner-scoped AWS account-plan context where applicable.

They never persist or return the complete provider payload recursively. An
exact full snapshot is available only through the authenticated,
size-bounded, read-only Management diagnostic endpoint for an explicitly
requested snapshot ID.

### Boundary-Compatible Types

All three runtimes use the same field semantics:

| Semantic field | Optimizer JSON / Python | Management Pydantic / DB JSON | Flutter |
|---|---|---|---|
| Context schema | `schemaVersion: str` | `schema_version` model aliasing `schemaVersion` | `String schemaVersion` |
| Provider map | exact `aws`, `azure`, `gcp` object keys | strict typed provider fields | `Map<CloudProvider, PricingCatalogReference>` created from exact keys |
| Snapshot ID | `snapshotId: str` | `snapshot_id` alias | `String snapshotId` |
| Provider | `provider: Literal` | `CloudAccessProvider` | `CloudProvider` |
| Region | `pricingRegion: str` | `pricing_region` alias | `String pricingRegion` |
| Provider schema | `providerSchemaVersion: str` | `provider_schema_version` alias | `String providerSchemaVersion` |
| Contract version | `contractVersion: str` | `contract_version` alias | `String contractVersion` |
| Registry version | `registryVersion: str` | `registry_version` alias | `String registryVersion` |
| Mapping versions | sorted `mappingVersions: list[str]` | immutable tuple/list with exact alias | unmodifiable `List<String>` |
| Fetch time | UTC ISO `fetchedAt` | timezone-aware `datetime` | UTC `DateTime` |
| Digest | `contentDigest: sha256:*` | pattern-validated string | pattern-validated `String` |
| Source | enum string | `Literal` | enum |
| Review/publication/source state | enum strings | `Literal` values | enums |

Serialization uses lower camel case on all HTTP boundaries. Python internal
field names may use snake case only behind aliases. Timestamps are serialized
as UTC ISO-8601. No runtime accepts non-finite numbers, nullable identity
fields, unknown enum values, or additional properties.

## Flutter Boundary

Flutter changes are intentionally small:

- stop exporting three full pricing payloads after a calculation;
- remove `PricingExportSnapshot` and the unscoped export API method;
- parse typed `PricingCatalogReference` values from calculation and persisted
  result contracts;
- show provider, region, fetched time, source, freshness, and shortened digest
  in existing collapsed Pricing Review/evidence details;
- replace Twin Overview's legacy full pricing artifact rows and JSON dialog
  actions with compact immutable catalog-reference rows;
- never send a catalog reference as trusted input;
- retain provider refresh and review workflows;
- retain offline demo parity with deterministic immutable references.

No new screen, router, BLoC, or state-management system is introduced.

### Flutter Layout

Only existing collapsed evidence surfaces change.

#### Desktop / Wide Web

```text
+-----------------------------------------------------------------------+
| Latest refresh                                           [expand v]   |
| succeeded · Pricing account                                           |
|                                                                       |
| Catalog used                                                         |
| AWS     eu-central-1   Fresh   17 Jul 2026   sha256:06603114...        |
|                                                                       |
| AWS TwinMaker plan                                                   |
| Standard     Account 123...     observed today     no pending change |
|                                                                       |
| Technical details                                        [expand >]   |
+-----------------------------------------------------------------------+

+-----------------------------------------------------------------------+
| Calculation trace                                                    |
| [Publishable] [N records] [N selected] [N transfers]                 |
| Trace details                                             [expand v]   |
|                                                                       |
| Pricing catalogs                                                     |
| AWS      eu-central-1  reviewed_baseline  sha256:...                  |
| Azure    westeurope    fresh              sha256:...                  |
| GCP      europe-west1  last_known_good    sha256:...                  |
+-----------------------------------------------------------------------+

+-----------------------------------------------------------------------+
| Twin configuration                                                    |
| Pricing evidence                                          [expand v] |
| AWS      eu-central-1   17 Jul 2026   sha256:06603114...               |
| Azure    westeurope     17 Jul 2026   sha256:a84c10f2...               |
| GCP      europe-west1   unavailable                                      |
+-----------------------------------------------------------------------+
```

#### Compact Web / Narrow Desktop

```text
+--------------------------------------+
| Latest refresh             [expand v]|
| succeeded · Pricing account          |
|                                      |
| Catalog used                         |
| AWS                                  |
| eu-central-1                         |
| Fresh · 17 Jul 2026                  |
| sha256:06603114...                   |
|                                      |
| AWS TwinMaker plan                   |
| Standard                             |
| Account 123...                       |
| observed today                       |
| no pending change                    |
|                                      |
| Technical details         [expand >] |
+--------------------------------------+
```

The calculation trace uses the same single-column provider rows below
`AppSpacing.pricingReviewCardBreakpoint`. Digest text wraps or is shortened;
it never creates horizontal scrolling. Twin Overview uses the same compact
stack and explicit unavailable state. It no longer offers a full pricing
artifact dialog.

### Widget Tree

```text
PricingReviewScreen [REUSE]
`-- BlocProvider<PricingReviewBloc> [REUSE]
    `-- _PricingReviewView [REUSE]
        `-- PricingProviderWorkspace [REUSE]
        `-- PricingRefreshRunSummary [MODIFY]
            |-- ExpansionTile [REUSE]
            |-- _PricingCatalogReferenceSummary [NEW, private dumb widget]
            |   |-- LayoutBuilder [REUSE]
            |   `-- _SummaryField [REUSE]
            |-- _AwsTwinMakerPlanSummary [REUSE]
            `-- _RunDiagnostics [MODIFY]

Wizard optimization result subtree [REUSE]
`-- CalculationTraceSummary [MODIFY]
    `-- ExpansionTile [REUSE]
        |-- _TraceDetails [REUSE]
        `-- _PricingCatalogContextDetails [NEW, private dumb widget]
            `-- LayoutBuilder [REUSE]
                `-- provider reference rows [NEW, private]

TwinOverviewConfigurationReview [MODIFY]
`-- _PricingDataSection [MODIFY]
    `-- _PricingCatalogReferenceRow [NEW, private dumb widget]
        `-- ExpansionTile / SelectableText [REUSE]
```

`_PricingCatalogReferenceSummary` and
`_PricingCatalogContextDetails` are private because they are projections tied
to their parent contracts and have no independent interaction/state.
`_PricingCatalogReferenceRow` replaces the current artifact row because Twin
Overview now projects the same immutable reference contract as Pricing Review;
it does not retain a second snapshot model. Existing `_SummaryField`,
`ExpansionTile`, `LayoutBuilder`, `SelectableText`, and provider color helpers
are reused. No general-purpose card or new screen is justified.

### State And Service Flow

The existing hybrid composition remains unchanged:

- Riverpod provides the application-level `ManagementApi` adapter;
- `PricingReviewBloc` owns the provider refresh/review workflow;
- `WizardBloc` owns calculation and persistence workflow;
- dumb widgets receive typed models only.

```text
Refresh button
  -> PricingReviewProviderRefreshRequested
  -> PricingReviewBloc
  -> ManagementApi
  -> Management API :5005
  -> typed PricingRefreshRun with catalog reference
  -> PricingReviewState.latestRuns
  -> PricingRefreshRunSummary

Calculate button
  -> WizardCalculateRequested
  -> WizardBloc
  -> ManagementApi.calculateCosts
  -> Management API :5005
  -> typed result with three catalog references
  -> WizardState.calcResult
  -> CalculationTraceSummary

Save draft
  -> WizardSaveDraft
  -> WizardBloc
  -> Management API :5005
  -> result persistence without pricing export
```

No widget calls a service. Flutter never calls ports 5003 or 5004.

### Design And Interaction Rules

- spacing uses `AppSpacing.xs/sm/md/lg` and the existing pricing breakpoint;
- provider colors use `AppColors.getProviderColor`;
- status colors use `Theme.of(context).colorScheme` or existing semantic
  tokens;
- typography uses `ThemeData` styles;
- icons use Material `Icons`;
- all new strings live in the existing pricing/result string constants;
- summary regions are collapsed by default;
- expansion uses native `ExpansionTile` behavior and existing animation;
- malformed optional refresh diagnostics show existing run diagnostics;
- a malformed required calculation context is rejected by the model/service
  and surfaces through the existing calculation error state;
- empty state says catalog evidence is unavailable; it never renders blank;
- provider rows have semantic labels containing provider, region, source, and
  freshness;
- keyboard focus follows expansion controls in document order;
- native Enter/Space expansion and visible focus behavior are retained;
- selectable exact IDs remain in the nested technical section;
- no new hardcoded color, spacing, typography, duration, or breakpoint value
  is introduced.

## Security Requirements

- reject path traversal and unknown region/provider path segments;
- never include request credentials in snapshot content, reference identity,
  logs, errors, or filenames;
- recursively scan candidate payload keys for forbidden secret fragments;
- verify canonical JSON before and after persistence;
- read exact snapshots with size limits and JSON object validation;
- use no `pickle`, dynamic import, shell expansion, or user-supplied path;
- redact provider and filesystem exceptions at HTTP boundaries;
- account observations remain only in Management persistence and refresh
  responses;
- full public snapshot exports are authenticated, size-bounded Management API
  diagnostics and are not called by Flutter;
- no mutation endpoint accepts a full snapshot supplied by Flutter.

## Required File Boundaries

### Optimizer

- new `backend/pricing_catalog_repository.py`;
- new `backend/pricing_catalog_models.py` or equivalent focused typed module;
- `backend/constants.py`;
- Optimizer startup/readiness configuration;
- `backend/config_loader.py`;
- `backend/pricing_cache.py`;
- `backend/pricing_schema.py`;
- `backend/pricing_publication_state.py`;
- `backend/fetch_data/calculate_up_to_date_pricing.py`;
- `api/calculation.py`;
- `api/pricing.py`;
- `api/file_status.py`;
- committed `json/pricing_catalog_baselines/**`;
- remove provider-wide pricing JSON files;
- `compose.yaml` durable Optimizer catalog volume and runtime-root environment;
- focused repository, migration, concurrency, refresh, API, calculation, and
  regression tests.

### Management API

- new `src/services/pricing_catalog_context_service.py`;
- `src/clients/optimizer_client.py`;
- `src/services/optimizer_calculation_service.py`;
- `src/services/cost_calculation_run_service.py`;
- `src/services/optimizer_configuration_service.py`;
- `src/services/pricing_refresh_run_service.py`;
- `src/services/pricing_review_state_service.py`;
- `src/services/pricing_health_service.py`;
- remove route helpers that reconstruct trusted state from legacy full pricing
  blobs;
- optimizer/pricing schemas and routes;
- cost-run and optimizer-config models;
- explicit idempotent migration;
- context ownership, persistence, error, OpenAPI, and rollback tests.

### Flutter

- replace `lib/models/pricing_export_snapshot.dart` with typed catalog
  reference/context models;
- replace pricing snapshot fields in `lib/models/optimizer_config.dart` and
  `lib/models/twin_configuration_view.dart` with catalog-reference
  projections;
- update `lib/services/management_api.dart` and `lib/services/api_service.dart`;
- update wizard calculation/persistence handlers;
- extend existing pricing/evidence widgets and
  `lib/widgets/twin_overview/twin_overview_configuration_review.dart`;
- update demo adapter and focused model/BLoC/widget tests.

### Documentation

- Optimizer component and data-flow docs;
- Management API persistence/contract docs;
- Pricing Review user guide;
- testing and extension-point docs;
- pricing mini-roadmap and central refactoring roadmap;
- this plan;
- deterministic OpenAPI snapshots.

Thesis evaluation conclusions remain outside the general developer/user docs.

## Mandatory Implementation Sequence

Each step is implemented, tested, reviewed, and committed before the next one.

### Implementation Status

| Slice | Status | Local evidence |
|---|---|---|
| 1. Catalog Domain And Migration | Complete | 49 focused domain, migration, legacy-parity, schema, cache, restart, Ruff, Bandit, compile, dependency, Compose, readiness, and secret-scan checks passed |
| 2. Refresh, Publication, And Optimizer API | Complete | All provider-region publication, strict calculation resolution, exact read contracts, and 680 Optimizer tests passed |
| 3. Management Ownership And Persistence | Complete | Exact owner-safe resolution, migration 019, calculation/deployment persistence, reference-only diagnostics, and 816 Management API tests passed |
| 4. Flutter Read Model And UX | Planned | Blocked by Slice 3 contracts |
| 5. Documentation And Generated Contracts | In progress | Optimizer and Management API ownership, runtime, flow, and user docs follow each completed boundary |
| 6. Review Pass 1 | Planned | Runs after Slice 5 |
| 7. Review Pass 2 And Full Gates | Planned | Final local and platform gate |

### Slice 1: Catalog Domain And Migration

- implement strict models, digests, repository, path safety, immutable writes,
  pointers, pinned baselines, and region-scoped guards;
- migrate the three committed Europe baselines;
- remove provider-wide lookup constants and files;
- prove cost-regression parity against the pre-migration fixtures.

Commit intent:
`feat(pricing): introduce immutable region catalog repository`

### Slice 2: Refresh, Publication, And Optimizer API

- route all provider refreshes through the repository;
- make metadata/digests provider-neutral;
- keep review-required candidates out of pointers;
- add region-aware status/reference/exact export endpoints;
- require strict catalog context for calculations;
- include exact references in result/trace;
- remove unscoped export and global file lookup.

Commit intent:
`feat(optimizer): bind calculations to exact pricing catalogs`

### Slice 3: Management Ownership And Persistence

- add server-side context resolution;
- inject the same refs into direct and persisted calculations;
- add migration and explicit reference persistence;
- remove client-supplied pricing objects/timestamps;
- align AWS account observation with AWS catalog;
- expose safe reference evidence.

Commit intent:
`feat(management): own pricing catalog resolution`

### Slice 4: Flutter Read Model And UX

- remove full export calls;
- add typed immutable reference parsing;
- extend existing collapsed diagnostics;
- update demo and tests;
- keep the visible workflow compact.

Commit intent:
`feat(flutter): show immutable pricing evidence`

### Slice 5: Documentation And Generated Contracts

- update all current user/developer docs and roadmaps;
- regenerate all affected OpenAPI snapshots;
- record migration and extension procedure;
- keep the docs-site strict build green.

Commit intent:
`docs(pricing): document immutable catalog lifecycle`

### Slice 6: Review Pass 1

- compare all implementation paths line-by-line with this plan;
- trace every snapshot write, pointer update, calculation read, and persisted
  reference;
- search for provider-wide file reads and client-authored pricing evidence;
- fix every finding;
- rerun focused suites.

### Slice 7: Review Pass 2 And Full Gates

- independently review tamper handling, path safety, stale data, owner
  isolation, concurrency, TOCTOU behavior, rollback, UX, and docs;
- fix every finding;
- run all full non-E2E suites and release/build gates.

## Test Matrix

### Catalog Unit Tests

- canonical reference accepts every provider and supported region format;
- invalid provider, region, digest, timestamp, or version is rejected;
- content digest ignores only declared volatile fields;
- content mutation changes digest;
- evidence/quality mutation changes digest;
- snapshot identity is deterministic;
- same pricing with different fetch times has distinct snapshot IDs;
- immutable create is idempotent only for byte-identical content;
- ID collision with different bytes fails;
- path traversal and symlink targets fail;
- empty-volume seed initialization is idempotent across restart;
- corrupt, drifted, or unwritable runtime roots fail readiness;
- pointer publication is atomic;
- exact resolution detects missing and tampered documents;
- reviewed baseline, fresh, and LKG references resolve;
- candidate/unreviewed references never resolve for calculation;
- stale reference fails;
- account context is stripped/rejected from public storage.

### Refresh And Concurrency Tests

- AWS, Azure, and GCP publish to canonical provider-region paths;
- same provider, two regions remain isolated;
- two simultaneous region refreshes cannot overwrite each other;
- cross-worker same-region locking prevents duplicate publication;
- same-region duplicate refresh returns conflict;
- failed/review-required refresh preserves same-region LKG;
- publishing one region does not alter another pointer;
- no provider-wide file is created;
- persisted refresh summaries contain bounded references/counts rather than a
  recursive full provider payload;
- account context appears only in the response/Management run, not snapshot.

### Calculation Contract Tests

- all three exact refs are mandatory;
- missing provider fails;
- map-key/provider mismatch fails;
- stale, unreviewed, unknown, altered, region-mismatched, and unsupported
  versions fail;
- all snapshots are resolved before formula execution;
- pointer movement after reference selection does not alter the result;
- result references equal input references;
- AWS TwinMaker context region/digest equals AWS catalog;
- committed Europe scenarios preserve provider/layer costs and cheapest path.

### Management Tests

- no owner run resolves pinned baseline refs;
- latest usable owner run supersedes only that owner's baseline;
- another user's refresh is never resolved;
- review-required latest run falls back to the owner's previous usable ref or
  pinned baseline;
- direct and persisted calculations inject identical contexts;
- client cannot supply trusted refs or full pricing payloads;
- result/persistence reference mismatch fails;
- DB rollback removes no prior successful state;
- migration is idempotent and safely handles unverifiable legacy rows;
- selection for deployment rejects pre-contract or tampered runs;
- stable errors contain no secrets or raw paths.

### Flutter Tests

- strict parsing of complete three-provider context;
- malformed optional diagnostics do not crash the screen;
- missing required context blocks newly persisted result handling;
- wizard performs no post-calculation pricing export;
- compact and narrow layouts do not overflow;
- collapsed evidence shows region, source, time, and shortened digest;
- Twin Overview exposes compact references and no full pricing artifact
  callback or dialog;
- demo scenarios expose deterministic catalog identities.

Concrete Flutter cases:

| # | Type | Case | Hard assertion |
|---|---|---|---|
| 1 | Happy/model | Parse complete three-provider result context | exact regions, IDs, times, and digests equal fixture |
| 2 | Happy/widget | Expanded refresh summary renders active reference | exactly one provider, region, source, and shortened digest visible |
| 3 | Unhappy/model | Unknown provider/state or malformed digest | `FormatException` with stable contract message |
| 4 | Unhappy/BLoC | Management calculation rejects unavailable catalog | existing error state is emitted and no save call occurs |
| 5 | Edge | Optional refresh reference absent on failed legacy run | run diagnostics render exactly once and screen remains usable |
| 6 | Edge | Context has map-key/provider mismatch | strict parser rejects it |
| 7 | Edge | UTC timestamp includes offset | parser normalizes to UTC exact instant |
| 8 | Edge | Long snapshot ID/digest at compact width | no overflow exception; technical text wraps/selects |
| 9 | Edge | Refresh switches provider while another run is visible | selected provider shows only its own reference |
| 10 | Edge | Save after successful calculation | zero export calls; one Management save call with no pricing payload |
| 11 | Edge | Offline demo showcase/degraded scenarios | deterministic refs or explicit unavailable state match scenario |
| 12 | Edge | Legacy Twin Overview configuration without verifiable refs | three explicit unavailable rows; no artifact action or JSON dialog |

### Full Gates

- Optimizer full pytest, Ruff, Bandit;
- Management API full non-E2E pytest, Ruff, Bandit, migration tests;
- Deployer full non-E2E suite as regression boundary;
- Flutter analyze, full tests, static architecture gate, Web release, local
  desktop release;
- Linux and Windows Flutter CI after push;
- deterministic OpenAPI comparison;
- strict MkDocs build and changed-link check;
- scoped secret scan;
- no real provider resource creation or deployment E2E.

The mandatory local integration sequence is:

```bash
./thesis.sh up --no-flutter
cd twin2multicloud_flutter
flutter test integration_test/management_api_readiness_test.dart \
  --dart-define=API_BASE_URL=http://localhost:5005 \
  --dart-define=OPTIMIZER_API_BASE_URL=http://localhost:5003
cd ..
./thesis.sh down
```

The integration test uses the real Management API for application behavior.
The existing direct Optimizer origin is limited to public OpenAPI contract
comparison and must not be extended for pricing behavior. Unit/widget tests
may use fake `ManagementApi` adapters. No integration test mocks `dio`, and no
test invokes a deployment or provider mutation.

## Implementation Status

| Slice | Status | Evidence |
|---|---|---|
| Slice 1: Catalog domain and migration | Done | immutable repository, reviewed seed package, durable Compose volume, startup readiness and migration tests |
| Slice 2: Optimizer refresh and calculation integration | Done | provider-region refresh publication, exact calculation resolution, regional status/read APIs, removal of provider-wide pricing files; 680-test Optimizer suite green |
| Slice 3: Management ownership and persistence | Done | owner-safe reference resolution, exact calculation and deployment persistence, migration 019, reference-only diagnostics, all 816 Management API tests green |
| Slice 4: Flutter read model and UX | Pending | depends on the final Management API contract |
| Slice 5: Documentation and generated contracts | In progress | Optimizer/runtime docs updated with each completed boundary |
| Slice 6: Review pass 1 | Pending | cross-project flow review after Slices 1-5 |
| Slice 7: Review pass 2 and full gates | Pending | independent final non-E2E audit |

### Slice 2 Verification Evidence

- all three provider refresh paths emit bounded
  `pricing-catalog-refresh-result.v2` summaries;
- provider and canonical pricing region must match the embedded provider
  metadata before a candidate can be stored;
- account-scoped pricing context is excluded from immutable public snapshots
  and bound to the active calculation reference digest;
- calculations require, resolve, integrity-check, and return the same exact
  three-provider reference context;
- provider-wide production pricing files, constants, implicit engine loading,
  and the unscoped export endpoint are removed;
- regional status and exact diagnostic reads use reference timestamps and an
  8 MiB repository read limit rather than file mtime;
- focused catalog, refresh, API, calculation, credential-forwarding, and
  repository suites passed after both review findings were fixed;
- the complete Optimizer suite passed with `680 passed`;
- Ruff, Bandit, `compileall`, `pip check`, Compose validation, and strict
  MkDocs build passed.

### Slice 3 Verification Evidence

- the Management API, not Flutter, resolves the exact AWS, Azure, and GCP
  references used by direct and persisted calculations;
- calculation results must echo the identical three-provider context before
  they may be persisted or selected for deployment;
- migration `019_pricing_catalog_context` adds and idempotently backfills
  reference-only context fields while leaving ambiguous historical rows
  readable but non-selectable;
- Pricing Health, Pricing Review, and account-scoped AWS TwinMaker observations
  use the same exact catalog identity selected by the calculation resolver;
- the authenticated diagnostic endpoint exposes one explicitly addressed,
  integrity-checked catalog with an 8 MiB response bound and no owner secrets;
- the complete Management API suite passed with `816 passed`; all focused
  catalog, migration, calculation, configuration, status, review, error, and
  contract suites passed, including the final 39-test integrity regression
  group;
- Ruff, Bandit, `compileall`, `pip check`, Compose validation, migration 019
  against the runtime SQLite database, strict MkDocs build, and a real
  Management-to-Optimizer local smoke check passed;
- no deployment E2E, provider mutation, or cloud-resource creation was run.

## Review Checklists

### Plan Review

- [x] One authoritative catalog repository and no duplicate runtime SSOT.
- [x] Every data owner and trust boundary is explicit.
- [x] Final contracts contain provider, region, versions, fetch time, and digest.
- [x] Snapshot immutability and pointer mutability are separated.
- [x] Baseline and runtime publication semantics are explicit.
- [x] Review-required candidates cannot enter calculation.
- [x] Account-scoped evidence remains separate.
- [x] Direct and persisted calculations use one resolver contract.
- [x] Client-authored pricing evidence is removed.
- [x] AWS account-plan/catalog compatibility is preserved.
- [x] Region and concurrency behavior is deterministic.
- [x] Migration removes global production lookup without a hidden alias.
- [x] Durable runtime persistence is separate from the read-only image/source
  baseline.
- [x] Errors, redaction, path safety, and tamper behavior are explicit.
- [x] Flutter scope is read-only and reuses existing UX/state.
- [x] Pricing Health, Pricing Review, and Twin Overview legacy side effects are
  explicitly migrated.
- [x] Unit, integration, concurrency, migration, regression, security, build,
  and docs gates have hard assertions.
- [x] #116 and #118 ownership is not duplicated.
- [x] No deployment E2E or provider mutation is scheduled.

### Implementation Review Pass 1

- [ ] Plan compliance review completed.
- [ ] All global file reads and writes removed.
- [ ] All client-authored pricing evidence removed.
- [ ] All exact-reference data flows traced.
- [ ] Focused tests pass after findings are fixed.

### Implementation Review Pass 2

- [ ] Security, tamper, stale, concurrency, and owner-isolation review completed.
- [ ] UX and documentation review completed.
- [ ] Full local gates pass after findings are fixed.

## Definition Of Done

- [ ] Immutable provider-region snapshots are the only calculation pricing
  SSOT.
- [ ] Provider-wide mutable production files and lookup aliases are gone.
- [ ] Every calculation resolves and returns exact reviewed references.
- [ ] Existing runs remain immutable when pointers move.
- [ ] Last-known-good and review-required state are independent by provider and
  region.
- [ ] Account observations remain owner-scoped and outside public snapshots.
- [ ] Management, not Flutter, owns trusted context resolution and persistence.
- [ ] Existing Europe baseline outputs remain deterministic.
- [ ] Migration, concurrency, tamper, stale, contract, and UX tests pass.
- [ ] All full local quality, security, build, OpenAPI, and docs gates pass.
- [ ] Linux and Windows Flutter CI pass after push.
- [ ] No real cloud resource is created.
