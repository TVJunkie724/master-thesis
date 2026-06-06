from backend.pricing_intent_registry import AMBIGUOUS, CHANGED, FAILED, MATCHED, MISSING
from backend.pricing_publication_state import (
    FALLBACK_STATIC,
    FALLBACK_STATIC_STATUS,
    FRESH,
    LAST_KNOWN_GOOD,
    PUBLISHABLE,
    REVIEW_REQUIRED,
    STALE,
    UNAVAILABLE,
    build_pricing_publication_decision,
    select_calculation_snapshot,
)


def _match_result(intent_id="api.request_million", status=MATCHED, **overrides):
    result = {
        "intent_id": intent_id,
        "provider": "azure",
        "mapping_version": "2026.06.06",
        "status": status,
        "selected_candidate": {
            "candidate_id": f"{intent_id}-candidate",
            "raw_price": 3.5,
        }
        if status == MATCHED
        else None,
        "candidate_count": 1 if status == MATCHED else 0,
        "errors": [],
    }
    result.update(overrides)
    return result


def _fresh_snapshot(**overrides):
    snapshot = {
        "snapshot_id": "fresh-azure-20260606",
        "schema_version": "pricing-catalog-snapshot.v1",
        "provider": "azure",
        "source_api": "azure-retail-prices",
        "fetched_at": "2026-06-06T10:00:00+00:00",
        "mapping_version": "2026.06.06",
        "candidate_count": 12,
        "raw_item_count": 120,
    }
    snapshot.update(overrides)
    return snapshot


def _last_known_good(**overrides):
    snapshot = {
        "snapshot_id": "lkg-azure-20260601",
        "schema_version": "pricing-calculation-snapshot.v1",
        "provider": "azure",
        "source_api": "azure-retail-prices",
        "published_at": "2026-06-01T10:00:00+00:00",
        "mapping_version": "2026.06.01",
        "is_stale": False,
    }
    snapshot.update(overrides)
    return snapshot


def test_publishable_when_all_intents_match_and_fresh_snapshot_exists():
    fresh = _fresh_snapshot()
    decision = build_pricing_publication_decision(
        "azure",
        [
            _match_result("api.request_million"),
            _match_result("functions.request"),
        ],
        fresh_snapshot=fresh,
        evaluated_at="2026-06-06T11:00:00+00:00",
    )

    assert decision["status"] == PUBLISHABLE
    assert decision["calculation_source"] == FRESH
    assert decision["pricing_freshness"] == FRESH
    assert decision["can_calculate"] is True
    assert decision["review_required"] is False
    assert decision["published_snapshot"]["snapshot_id"] == "fresh-azure-20260606"
    assert decision["match_summary"]["status_counts"] == {MATCHED: 2}
    assert select_calculation_snapshot(decision, fresh_snapshot=fresh) == fresh


def test_ambiguous_candidate_requires_review_and_keeps_last_known_good():
    fresh = _fresh_snapshot()
    lkg = _last_known_good()
    decision = build_pricing_publication_decision(
        "azure",
        [_match_result(status=AMBIGUOUS, candidate_count=2)],
        fresh_snapshot=fresh,
        last_known_good_snapshot=lkg,
    )

    assert decision["status"] == REVIEW_REQUIRED
    assert decision["calculation_source"] == LAST_KNOWN_GOOD
    assert decision["can_calculate"] is True
    assert decision["review_reasons"][0]["status"] == AMBIGUOUS
    assert decision["published_snapshot"]["snapshot_id"] == "lkg-azure-20260601"
    assert select_calculation_snapshot(
        decision,
        fresh_snapshot=fresh,
        last_known_good_snapshot=lkg,
    ) == lkg


def test_missing_mapping_without_last_known_good_is_unavailable():
    decision = build_pricing_publication_decision(
        "azure",
        [_match_result(status=MISSING)],
        fresh_snapshot=_fresh_snapshot(),
    )

    assert decision["status"] == UNAVAILABLE
    assert decision["calculation_source"] == UNAVAILABLE
    assert decision["can_calculate"] is False
    assert decision["review_reasons"][0]["status"] == MISSING
    assert select_calculation_snapshot(decision, fresh_snapshot=_fresh_snapshot()) is None


def test_changed_intent_preserves_stale_last_known_good_metadata():
    lkg = _last_known_good(is_stale=True, stale_reason="older than 7 days")
    decision = build_pricing_publication_decision(
        "azure",
        [_match_result(status=CHANGED)],
        fresh_snapshot=_fresh_snapshot(),
        last_known_good_snapshot=lkg,
    )

    assert decision["status"] == REVIEW_REQUIRED
    assert decision["last_known_good_snapshot"]["is_stale"] is True
    assert decision["last_known_good_snapshot"]["stale_reason"] == "older than 7 days"
    assert decision["pricing_freshness"] == STALE
    assert decision["match_summary"]["status_counts"] == {CHANGED: 1}


def test_failed_refresh_requires_review_and_surfaces_errors():
    decision = build_pricing_publication_decision(
        "aws",
        [
            _match_result(
                "transfer.egress_gb",
                status=FAILED,
                errors=["Unsupported mapping schema_version: old"],
            )
        ],
        last_known_good_snapshot=_last_known_good(provider="aws"),
    )

    assert decision["status"] == REVIEW_REQUIRED
    assert decision["review_reasons"][0]["status"] == FAILED
    assert decision["review_reasons"][0]["errors"] == [
        "Unsupported mapping schema_version: old"
    ]


def test_fallback_static_is_review_required_but_calculable_with_lkg():
    decision = build_pricing_publication_decision(
        "gcp",
        [
            _match_result(
                "digital_twin.query_unit",
                status=FALLBACK_STATIC_STATUS,
            )
        ],
        last_known_good_snapshot=_last_known_good(provider="gcp", source_api=FALLBACK_STATIC),
    )

    assert decision["status"] == REVIEW_REQUIRED
    assert decision["calculation_source"] == FALLBACK_STATIC
    assert decision["pricing_freshness"] == LAST_KNOWN_GOOD
    assert decision["review_reasons"][0]["status"] == FALLBACK_STATIC_STATUS


def test_empty_match_results_are_not_publishable():
    decision = build_pricing_publication_decision(
        "azure",
        [],
        fresh_snapshot=_fresh_snapshot(),
    )

    assert decision["status"] == UNAVAILABLE
    assert decision["can_calculate"] is False
    assert decision["review_reasons"] == [
        {
            "status": FAILED,
            "intent_id": None,
            "reason": "No pricing intent match results were provided.",
        }
    ]


def test_all_matches_without_fresh_snapshot_keep_lkg_and_explain_review_reason():
    decision = build_pricing_publication_decision(
        "azure",
        [_match_result()],
        last_known_good_snapshot=_last_known_good(),
    )

    assert decision["status"] == REVIEW_REQUIRED
    assert decision["calculation_source"] == LAST_KNOWN_GOOD
    assert decision["pricing_freshness"] == LAST_KNOWN_GOOD
    assert decision["review_reasons"] == [
        {
            "status": FAILED,
            "intent_id": None,
            "reason": "Fresh pricing snapshot is missing.",
        }
    ]


def test_unknown_match_status_is_normalized_to_failed():
    decision = build_pricing_publication_decision(
        "azure",
        [_match_result(status="provider-surprise")],
        last_known_good_snapshot=_last_known_good(),
    )

    assert decision["status"] == REVIEW_REQUIRED
    assert decision["match_summary"]["status_counts"] == {FAILED: 1}
    assert decision["review_reasons"][0]["status"] == FAILED
