from backend.pricing_intent_registry import (
    AMBIGUOUS,
    CHANGED,
    FAILED,
    MATCHED,
    MAPPING_SCHEMA_VERSION,
    MISSING,
    match_pricing_intent,
)


def _mapping(**overrides):
    mapping = {
        "schema_version": MAPPING_SCHEMA_VERSION,
        "mapping_version": "2026.06.06",
        "intent_id": "api.request_million",
        "provider": "azure",
        "review_status": "reviewed",
        "match": {
            "provider_identifiers": {"meter_id": "meter-api-consumption"},
            "unit": "1M Calls",
            "price_type": "Consumption",
            "region": "westeurope",
        },
        "normalization": {
            "from_unit": "1M Calls",
            "to_unit": "per_1m_requests",
            "multiplier": 1,
        },
    }
    mapping.update(overrides)
    return mapping


def _candidate(candidate_id="candidate-1", **overrides):
    candidate = {
        "candidate_id": candidate_id,
        "provider": "azure",
        "provider_identifiers": {
            "meter_id": "meter-api-consumption",
            "sku_id": "sku-consumption",
        },
        "provider_service": "API Management",
        "service_name": "API Management",
        "product_name": "API Management",
        "sku_name": "Consumption",
        "meter_name": "Calls",
        "region": "westeurope",
        "unit": "1M Calls",
        "price_type": "Consumption",
        "currency": "USD",
        "raw_price": 3.5,
        "tier": {"tier_minimum_units": 0},
        "evidence": {"is_primary_meter_region": True},
    }
    candidate.update(overrides)
    return candidate


def test_match_pricing_intent_single_match():
    result = match_pricing_intent([_candidate()], _mapping())

    assert result["status"] == MATCHED
    assert result["selected_candidate"]["candidate_id"] == "candidate-1"
    assert result["normalization"]["to_unit"] == "per_1m_requests"


def test_match_pricing_intent_supports_aws_provider_mapping():
    mapping = _mapping(
        provider="aws",
        match={
            "provider_identifiers": {
                "service_code": "AmazonApiGateway",
                "usage_type": "EU-Requests",
            },
            "unit": "Requests",
            "price_type": "OnDemand",
            "region": "EU (Frankfurt)",
        },
    )
    candidate = {
        "candidate_id": "aws-candidate",
        "provider": "aws",
        "provider_identifiers": {
            "sku": "AWS-SKU-1",
            "service_code": "AmazonApiGateway",
            "usage_type": "EU-Requests",
        },
        "provider_service": "AmazonApiGateway",
        "region": "EU (Frankfurt)",
        "unit": "Requests",
        "price_type": "OnDemand",
        "raw_price": 0.000001,
    }

    result = match_pricing_intent([candidate], mapping)

    assert result["status"] == MATCHED
    assert result["selected_candidate"]["candidate_id"] == "aws-candidate"


def test_match_pricing_intent_supports_gcp_provider_mapping():
    mapping = _mapping(
        provider="gcp",
        match={
            "provider_identifiers": {
                "service_id": "6F81-5844-456A",
                "sku_id": "gcp-sku-1",
            },
            "unit": "request",
            "price_type": "OnDemand",
            "region": "europe-west1",
        },
    )
    candidate = {
        "candidate_id": "gcp-candidate",
        "provider": "gcp",
        "provider_identifiers": {
            "service_id": "6F81-5844-456A",
            "sku_id": "gcp-sku-1",
        },
        "provider_service": "6F81-5844-456A",
        "region": "europe-west1",
        "unit": "request",
        "price_type": "OnDemand",
        "raw_price": 0.000003,
    }

    result = match_pricing_intent([candidate], mapping)

    assert result["status"] == MATCHED
    assert result["selected_candidate"]["candidate_id"] == "gcp-candidate"


def test_match_pricing_intent_missing_when_no_candidate_matches():
    result = match_pricing_intent(
        [_candidate(provider_identifiers={"meter_id": "other-meter"})],
        _mapping(),
    )

    assert result["status"] == MISSING
    assert result["selected_candidate"] is None


def test_match_pricing_intent_ambiguous_when_multiple_candidates_match():
    result = match_pricing_intent(
        [_candidate("candidate-b"), _candidate("candidate-a")],
        _mapping(),
    )

    assert result["status"] == AMBIGUOUS
    assert result["selected_candidate"] is None
    assert [candidate["candidate_id"] for candidate in result["candidates"]] == [
        "candidate-a",
        "candidate-b",
    ]


def test_match_pricing_intent_is_independent_of_candidate_order():
    candidates_a = [
        _candidate("candidate-z", provider_identifiers={"meter_id": "other-meter"}),
        _candidate("candidate-a"),
    ]
    candidates_b = list(reversed(candidates_a))

    result_a = match_pricing_intent(candidates_a, _mapping())
    result_b = match_pricing_intent(candidates_b, _mapping())

    assert result_a["status"] == MATCHED
    assert result_a == result_b


def test_match_pricing_intent_changed_when_stable_identity_matches_but_unit_changes():
    result = match_pricing_intent(
        [_candidate(unit="10K Calls")],
        _mapping(),
    )

    assert result["status"] == CHANGED
    assert result["candidates"][0]["candidate_id"] == "candidate-1"
    assert any("unit" in reason for reason in result["rejections"][0]["reasons"])


def test_match_pricing_intent_changed_when_provider_identifier_changes_but_drift_markers_match():
    result = match_pricing_intent(
        [
            _candidate(
                provider_identifiers={"meter_id": "new-meter-id"},
                service_name="API Management",
                meter_name="Calls",
                unit="1M Calls",
            )
        ],
        _mapping(
            drift_markers={
                "service_name": "API Management",
                "meter_name": "Calls",
                "unit": "1M Calls",
            }
        ),
    )

    assert result["status"] == CHANGED
    assert result["candidates"][0]["provider_identifiers"]["meter_id"] == "new-meter-id"


def test_match_pricing_intent_failed_for_invalid_mapping():
    result = match_pricing_intent(
        [_candidate()],
        _mapping(intent_id="unknown.intent"),
    )

    assert result["status"] == FAILED
    assert result["errors"] == ["Unknown pricing intent: unknown.intent"]
