---
title: "Phase 2.3 Review: Optimizer Fetcher Reliability"
description: "Review of provider fetcher reliability hardening for deterministic candidate matching, ambiguity handling, and evidence capture."
tags: [optimizer, pricing, fetcher, evidence, issue-102]
lastUpdated: "2026-06-21"
version: "1.0"
---

<!-- SOURCES:
- docs/plans/service_architecture_audit/phases/subphases/PHASE_02_03_OPTIMIZER_FETCHER_RELIABILITY_AUDIT.md
- 2-twin2clouds/backend/fetch_data/fetch_evidence.py
- 2-twin2clouds/backend/fetch_data/cloud_price_fetcher_aws.py
- 2-twin2clouds/backend/fetch_data/cloud_price_fetcher_azure.py
- 2-twin2clouds/backend/fetch_data/cloud_price_fetcher_google.py
- 2-twin2clouds/tests/unit/pricing/
EXTRACTED: 2026-06-21 | VERSION: 1.0
-->

# Phase 2.3 Review: Optimizer Fetcher Reliability

## Review Result

Phase 2.3 is complete for the provider matching boundary. The fetchers now have
shared evidence models in `2-twin2clouds/backend/fetch_data/fetch_evidence.py`
and provider-specific matching helpers that distinguish selected, no-match, and
ambiguous candidates.

Existing public fetcher functions still return plain pricing dictionaries for
backward compatibility. The new evidence helpers are the runtime bridge for the
later Management API and Pricing Review UI surfaces.

## Implemented Reliability Boundary

| Provider | Hardened function | Behavior |
|---|---|---|
| AWS | `_extract_prices_with_evidence()` and `_extract_prices_from_api_response()` | Field-level price dimensions are evaluated with evidence. Multiple paid matches with distinct prices are marked ambiguous and omitted from the legacy result dict. |
| Azure | `_find_best_match_with_evidence()` and `_find_best_match()` | Retail rows produce selected/no-match/ambiguous evidence. Multiple paid matches with distinct prices return `None` through the compatibility wrapper. |
| GCP | `_select_gcp_sku_with_evidence()` and `fetch_gcp_price()` | SKUs are evaluated with selected/rejected evidence. Multiple paid matches with distinct prices are marked ambiguous, so legacy output falls into the existing default/review path. |

## Evidence Fields

Each field-level evidence record includes:

- provider and service name,
- field key,
- match status,
- selected row, raw selected price, normalized price, and source unit,
- rejected candidates with rejection reasons,
- review-required flag,
- human-readable reason for no-match or ambiguity.

## Candidate Decision Rules

| Rule | Runtime behavior |
|---|---|
| No matching candidates | `no_match`, review required |
| Exactly one paid candidate price | `selected`, not review required |
| Multiple candidates with same paid price | first equivalent candidate can be selected |
| Multiple candidates with distinct paid prices | `ambiguous`, review required |
| Region/unit/keyword/negative keyword mismatch | rejected candidate with reason |
| Zero price candidate | rejected or passed to static/default handling depending on provider path |

## Tests Added

Provider tests now cover:

- AWS ambiguous price dimensions are not returned through the legacy wrapper.
- Azure ambiguous Retail API rows return no automatic match.
- GCP ambiguous SKU matches are review-required.
- GCP selected SKU evidence preserves raw and normalized prices.

Latest provider-focused evidence:

```text
docker run --rm -v /Users/caroline/.codex/worktrees/01ff/master-thesis/2-twin2clouds:/app -v /Users/caroline/.codex/worktrees/01ff/master-thesis/config.json:/config/config.json:ro -w /app -e PYTHONPATH=/app 2twin2clouds:latest python -m pytest tests/unit/pricing/test_price_fetcher_aws.py tests/unit/pricing/test_price_fetcher_azure.py tests/unit/pricing/test_price_fetcher_gcp.py -q

25 passed in 0.24s
```

Latest calculation/pricing evidence:

```text
docker run --rm -v /Users/caroline/.codex/worktrees/01ff/master-thesis/2-twin2clouds:/app -v /Users/caroline/.codex/worktrees/01ff/master-thesis/config.json:/config/config.json:ro -w /app -e PYTHONPATH=/app 2twin2clouds:latest python -m pytest tests/unit/calculation_v2 tests/unit/pricing -q

103 passed in 0.27s
```

Latest full-suite evidence with non-sensitive test config mounts:

```text
tmpdir=$(mktemp -d /tmp/optimizer-test-config.XXXXXX)
printf '{"aws":{}}\n' > "$tmpdir/config_credentials.json"
docker run --rm -v /Users/caroline/.codex/worktrees/01ff/master-thesis/2-twin2clouds:/app -v /Users/caroline/.codex/worktrees/01ff/master-thesis/config.json:/config/config.json:ro -v "$tmpdir/config_credentials.json":/config/config_credentials.json:ro -w /app -e PYTHONPATH=/app 2twin2clouds:latest python -m pytest tests -q

216 passed in 50.67s
```

## Findings Handed To Later Subphases

| Finding | Owner phase |
|---|---|
| Full fetch responses still do not return a structured evidence envelope to API callers. The evidence types are in place, but endpoint contract exposure belongs to the API phase. | Phase 2.5 |
| Fallback/default merging still writes review-required values into legacy pricing JSON. Source policies and evidence now identify the condition; publishability enforcement belongs to API/fetch orchestration hardening. | Phase 2.5 |
| Formula code still consumes normalized numbers without verifying the matching contract and source policy. | Phase 2.4 |
| Live provider API calls can still drift when provider catalogs change. The new fixture tests cover deterministic ambiguity rules; broader provider fixture harvesting belongs to future maintenance and Pricing Review UI workflows. | Phase 2.6 and frontend roadmap |

## Acceptance Review

| Criterion | Result |
|---|---|
| Fetchers never treat ambiguous candidates as successful automatic matches at the hardened matching boundary. | Passed |
| Units such as per million, per 100k, GB/GiB, seconds, and requests are represented in evidence or existing normalizers before calculation. | Passed for matching boundary; formula enforcement scheduled for Phase 2.4 |
| Selected rows can be inspected later by Management API/UI. | Passed at evidence model/helper layer; endpoint exposure scheduled for Phase 2.5 |
| Rejected candidates carry reasons. | Passed |
| No live cloud deployment tests are required. | Passed |

## Residual Risk

This phase hardens provider matching decisions without changing the public API
shape. The next critical step is calculation correctness: formulas must consume
contract-compatible, unit-normalized pricing values and reject source/policy
mismatches before cost totals are produced.
