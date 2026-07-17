from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json

import pytest
from pydantic import ValidationError

from api.calculation import CalcParams
from backend.calculation_v2.components.aws.twinmaker import (
    MAX_FUTURE_SKEW,
    MAX_OBSERVATION_AGE,
    evaluate_twinmaker_context,
)
from backend.calculation_v2.layers.aws_layers import AWSLayerCalculators


DIGEST = "sha256:" + ("a" * 64)
FINGERPRINT = "sha256:" + ("b" * 64)


def _pricing():
    return {
        "aws": {
            "iotTwinMaker": {
                "usageRates": {
                    "entityPricePerMonth": 0.0525,
                    "queryPrice": 0.0000525,
                    "unifiedDataAccessApiCallPrice": 0.00000165,
                },
                "tieredBundle": {
                    "tiers": [
                        {
                            "tierId": "TIER_1",
                            "minimumEntities": 1,
                            "maximumEntities": 1000,
                            "monthlyBasePrice": 231.0,
                            "includedQueries": 3_800_000,
                            "includedApiCalls": 25_000_000,
                            "queryOveragePrice": 0.0000525,
                            "apiCallOveragePrice": 0.00000165,
                        },
                        {
                            "tierId": "TIER_2",
                            "minimumEntities": 1001,
                            "maximumEntities": 5000,
                            "monthlyBasePrice": 682.5,
                            "includedQueries": 9_000_000,
                            "includedApiCalls": 60_000_000,
                            "queryOveragePrice": 0.0000525,
                            "apiCallOveragePrice": 0.00000165,
                        },
                        {
                            "tierId": "TIER_3",
                            "minimumEntities": 5001,
                            "maximumEntities": 10000,
                            "monthlyBasePrice": 1155.0,
                            "includedQueries": 14_300_000,
                            "includedApiCalls": 95_000_000,
                            "queryOveragePrice": 0.0000525,
                            "apiCallOveragePrice": 0.00000165,
                        },
                        {
                            "tierId": "TIER_4",
                            "minimumEntities": 10001,
                            "maximumEntities": 20000,
                            "monthlyBasePrice": 2047.5,
                            "includedQueries": 24_000_000,
                            "includedApiCalls": 160_000_000,
                            "queryOveragePrice": 0.0000525,
                            "apiCallOveragePrice": 0.00000165,
                        },
                    ]
                },
            }
        },
        "__aws_schema__": {
            "pricing_region": "eu-central-1",
            "snapshot_digest": DIGEST,
        },
    }


def _context(mode="STANDARD"):
    return {
        "schemaVersion": "aws-twinmaker-account-pricing-context.v1",
        "status": "available",
        "sourceRefreshRunId": "refresh-run-1",
        "connectionFingerprint": FINGERPRINT,
        "providerAccountId": "123456789012",
        "pricingRegion": "eu-central-1",
        "catalogSnapshotDigest": DIGEST,
        "observedAt": datetime.now(timezone.utc),
        "currentPlan": {
            "mode": mode,
            "billableEntityCount": 10,
            "effectiveAt": None,
            "updatedAt": None,
            "updateReason": None,
            "bundle": None,
        },
        "pendingPlan": None,
    }


def _calculate(context):
    return AWSLayerCalculators().calculate_l4_cost(
        entity_count=10,
        queries_per_month=20_000,
        api_calls_per_month=30_000,
        pricing=_pricing(),
        account_pricing_context=context,
    )


def _calc_params():
    return {
        "numberOfDevices": 1,
        "deviceSendingIntervalInMinutes": 1,
        "averageSizeOfMessageInKb": 1,
        "hotStorageDurationInMonths": 1,
        "coolStorageDurationInMonths": 2,
        "archiveStorageDurationInMonths": 6,
        "needs3DModel": False,
        "entityCount": 1,
        "amountOfActiveEditors": 0,
        "amountOfActiveViewers": 0,
        "dashboardRefreshesPerHour": 0,
        "dashboardActiveHoursPerDay": 0,
    }


def test_standard_context_is_comparable_and_traces_each_contribution():
    result = _calculate(_context())

    assert result.supported is True
    assert result.total_cost == pytest.approx(
        (10 * 0.0525) + (20_000 * 0.0000525) + (30_000 * 0.00000165)
    )
    assert result.components["twinmaker_entities"] == pytest.approx(0.525)
    assert result.details["pricingContext"]["status"] == "compatible"
    assert result.details["pricingContext"]["modeledMode"] == "STANDARD"
    assert result.details["pricingContext"]["functionalCompatibility"] == (
        "compatible"
    )
    assert result.details["calculation"]["dimensions"][0] == {
        "intentId": "digital_twin.entity_month",
        "quantity": 10,
        "unit": "entity_month",
        "unitPrice": 0.0525,
        "contribution": 0.525,
    }


@pytest.mark.parametrize(
    ("context", "reason"),
    [
        (
            {"status": "unavailable", "reasonCode": "NO_OBSERVATION"},
            "NO_OBSERVATION",
        ),
        (
            _context("BASIC"),
            "AWS_TWINMAKER_BASIC_FUNCTIONALLY_INCOMPLETE",
        ),
        (
            {
                **_context("STANDARD"),
                "pendingPlan": {
                    "mode": "STANDARD",
                    "billableEntityCount": 10,
                    "bundle": None,
                },
            },
            "AWS_TWINMAKER_PENDING_PLAN_CHANGE",
        ),
        (
            {
                **_context("TIERED_BUNDLE"),
                "currentPlan": {
                    "mode": "TIERED_BUNDLE",
                    "billableEntityCount": 10,
                    "bundle": {"tier": "TIER_1", "names": []},
                },
            },
            "AWS_TWINMAKER_BUNDLE_ALLOCATION_REQUIRED",
        ),
    ],
)
def test_non_comparable_contexts_return_explicit_unsupported_result(
    context,
    reason,
):
    result = _calculate(context)

    assert result.supported is False
    assert result.total_cost == 0
    assert result.unsupported_reason == reason


def test_context_rejects_region_and_digest_drift():
    wrong_region = _context()
    wrong_region["pricingRegion"] = "eu-west-1"
    wrong_digest = _context()
    wrong_digest["catalogSnapshotDigest"] = "sha256:" + ("c" * 64)

    assert _calculate(wrong_region).unsupported_reason == (
        "AWS_TWINMAKER_CATALOG_REGION_MISMATCH"
    )
    assert _calculate(wrong_digest).unsupported_reason == (
        "AWS_TWINMAKER_CATALOG_DIGEST_MISMATCH"
    )


def test_stale_observation_is_not_comparable():
    context = _context()
    context["observedAt"] = datetime.now(timezone.utc) - timedelta(days=8)

    result = _calculate(context)

    assert result.supported is False
    assert result.unsupported_reason == "AWS_TWINMAKER_PLAN_STALE"


def test_context_age_and_future_skew_boundaries_are_deterministic():
    now = datetime(2026, 7, 17, 12, tzinfo=timezone.utc)
    context = _context()
    context["observedAt"] = now - MAX_OBSERVATION_AGE

    at_age_limit = evaluate_twinmaker_context(context, _pricing(), now=now)
    assert at_age_limit.comparable is True
    assert at_age_limit.diagnostic["observationAgeSeconds"] == (
        MAX_OBSERVATION_AGE.total_seconds()
    )

    context["observedAt"] = now - MAX_OBSERVATION_AGE - timedelta(microseconds=1)
    assert (
        evaluate_twinmaker_context(context, _pricing(), now=now).reason_code
        == "AWS_TWINMAKER_PLAN_STALE"
    )

    context["observedAt"] = now + MAX_FUTURE_SKEW
    assert evaluate_twinmaker_context(context, _pricing(), now=now).comparable

    context["observedAt"] = now + MAX_FUTURE_SKEW + timedelta(microseconds=1)
    assert (
        evaluate_twinmaker_context(context, _pricing(), now=now).reason_code
        == "AWS_TWINMAKER_OBSERVATION_FROM_FUTURE"
    )


def test_missing_catalog_metadata_fails_closed():
    pricing = _pricing()
    pricing.pop("__aws_schema__")

    result = AWSLayerCalculators().calculate_l4_cost(
        entity_count=10,
        queries_per_month=20_000,
        api_calls_per_month=30_000,
        pricing=pricing,
        account_pricing_context=_context(),
    )

    assert result.supported is False
    assert result.unsupported_reason == "AWS_TWINMAKER_CATALOG_METADATA_MISSING"
    assert result.details["pricingContext"]["status"] == "contract_invalid"


def test_context_diagnostics_are_json_safe_and_preserve_plan_state():
    context = _context()
    context["currentPlan"]["effectiveAt"] = datetime(
        2026,
        7,
        18,
        12,
        tzinfo=timezone.utc,
    )

    diagnostic = _calculate(context).details_as_dict()["pricingContext"]

    assert json.loads(json.dumps(diagnostic))["currentPlan"]["effectiveAt"] == (
        "2026-07-18T12:00:00Z"
    )


def test_api_defaults_to_unavailable_context_instead_of_standard():
    params = CalcParams(**_calc_params())

    assert params.providerPricingContexts.awsTwinMaker.status == "unavailable"


def test_api_rejects_unknown_context_fields_and_naive_timestamps():
    context = _context()
    context["unexpected"] = "value"
    with pytest.raises(ValidationError):
        CalcParams(
            **_calc_params(),
            providerPricingContexts={"awsTwinMaker": context},
        )

    naive = deepcopy(_context())
    naive["observedAt"] = "2026-07-17T12:00:00"
    with pytest.raises(ValidationError, match="timezone-aware"):
        CalcParams(
            **_calc_params(),
            providerPricingContexts={"awsTwinMaker": naive},
        )


@pytest.mark.parametrize(
    "bundle_names",
    [
        [""],
        ["x" * 129],
        ["valid"] * 21,
    ],
)
def test_api_rejects_invalid_bundle_names(bundle_names):
    context = _context("TIERED_BUNDLE")
    context["currentPlan"]["bundle"] = {
        "tier": "TIER_1",
        "names": bundle_names,
    }

    with pytest.raises(ValidationError):
        CalcParams(
            **_calc_params(),
            providerPricingContexts={"awsTwinMaker": context},
        )


def test_api_rejects_invalid_unavailable_reason_code():
    with pytest.raises(ValidationError):
        CalcParams(
            **_calc_params(),
            providerPricingContexts={
                "awsTwinMaker": {
                    "status": "unavailable",
                    "reasonCode": "not canonical",
                }
            },
        )
