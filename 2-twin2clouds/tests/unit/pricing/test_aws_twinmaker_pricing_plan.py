from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from backend.aws_twinmaker_pricing_plan import (
    AwsTwinMakerPricingPlanError,
    observe_aws_twinmaker_pricing_plan,
)


def _credentials():
    return {
        "aws_access_key_id": "access-key",
        "aws_secret_access_key": "secret-key",
        "aws_session_token": "session-token",
    }


def _session(plan=None):
    sts = MagicMock()
    sts.get_caller_identity.return_value = {
        "Account": "123456789012",
        "Arn": "arn:aws:sts::123456789012:assumed-role/pricing/session",
    }
    twinmaker = MagicMock()
    twinmaker.get_pricing_plan.return_value = plan or {
        "currentPricingPlan": {
            "pricingMode": "STANDARD",
            "billableEntityCount": 42,
            "effectiveDateTime": datetime(
                2026,
                7,
                1,
                tzinfo=timezone.utc,
            ),
        }
    }
    session = MagicMock()
    session.client.side_effect = lambda service, **kwargs: {
        "sts": sts,
        "iottwinmaker": twinmaker,
    }[service]
    return session, sts, twinmaker


def test_observer_returns_secret_free_normalized_standard_context():
    session, sts, twinmaker = _session()

    result = observe_aws_twinmaker_pricing_plan(
        _credentials(),
        "eu-central-1",
        configured_account_id="123456789012",
        session=session,
        observed_at=datetime(2026, 7, 17, 12, tzinfo=timezone.utc),
    )

    assert result == {
        "schema_version": "aws-twinmaker-account-pricing-context.v1",
        "provider": "aws",
        "service": "iot_twinmaker",
        "region": "eu-central-1",
        "verified_account_id": "123456789012",
        "observed_at": "2026-07-17T12:00:00Z",
        "current_plan": {
            "mode": "STANDARD",
            "billable_entity_count": 42,
            "effective_at": "2026-07-01T00:00:00Z",
            "updated_at": None,
            "update_reason": None,
            "bundle": None,
        },
        "pending_plan": None,
    }
    sts.get_caller_identity.assert_called_once_with()
    twinmaker.get_pricing_plan.assert_called_once_with()
    session.client.assert_any_call(
        "iottwinmaker",
        region_name="eu-central-1",
    )
    assert "secret-key" not in str(result)


def test_observer_normalizes_tiered_bundle_and_pending_plan():
    session, _, _ = _session(
        {
            "currentPricingPlan": {
                "pricingMode": "TIERED_BUNDLE",
                "billableEntityCount": 1_200,
                "bundleInformation": {
                    "pricingTier": "TIER_2",
                    "bundleNames": ["alpha", "beta"],
                },
            },
            "pendingPricingPlan": {
                "pricingMode": "STANDARD",
                "billableEntityCount": 1_200,
                "updateReason": "scheduled migration",
            },
        }
    )

    result = observe_aws_twinmaker_pricing_plan(
        _credentials(),
        "eu-central-1",
        session=session,
    )

    assert result["current_plan"]["bundle"] == {
        "tier": "TIER_2",
        "names": ["alpha", "beta"],
    }
    assert result["pending_plan"]["mode"] == "STANDARD"


def test_observer_redacts_known_credentials_from_provider_free_text():
    session, _, _ = _session(
        {
            "currentPricingPlan": {
                "pricingMode": "TIERED_BUNDLE",
                "billableEntityCount": 1,
                "updateReason": "migration secret-key",
                "bundleInformation": {
                    "pricingTier": "TIER_1",
                    "bundleNames": ["bundle-secret-key"],
                },
            },
        }
    )

    result = observe_aws_twinmaker_pricing_plan(
        _credentials(),
        "eu-central-1",
        session=session,
    )

    assert "secret-key" not in str(result)
    assert "[REDACTED]" in result["current_plan"]["update_reason"]
    assert "[REDACTED]" in result["current_plan"]["bundle"]["names"][0]


def test_observer_rejects_configured_account_mismatch_before_plan_lookup():
    session, _, twinmaker = _session()

    with pytest.raises(AwsTwinMakerPricingPlanError) as raised:
        observe_aws_twinmaker_pricing_plan(
            _credentials(),
            "eu-central-1",
            configured_account_id="999999999999",
            session=session,
        )

    assert raised.value.code == "AWS_TWINMAKER_PLAN_ACCOUNT_MISMATCH"
    assert raised.value.identity_verified is True
    twinmaker.get_pricing_plan.assert_not_called()


def test_observer_maps_access_denied_without_provider_detail_or_secret():
    session, _, twinmaker = _session()
    twinmaker.get_pricing_plan.side_effect = ClientError(
        {
            "Error": {
                "Code": "AccessDeniedException",
                "Message": "secret-key is denied",
            }
        },
        "GetPricingPlan",
    )

    with pytest.raises(AwsTwinMakerPricingPlanError) as raised:
        observe_aws_twinmaker_pricing_plan(
            _credentials(),
            "eu-central-1",
            session=session,
        )

    assert raised.value.code == "AWS_TWINMAKER_PLAN_PERMISSION_DENIED"
    assert raised.value.identity_verified is True
    assert "secret-key" not in str(raised.value)


@pytest.mark.parametrize(
    ("plan", "message"),
    [
        (
            {
                "currentPricingPlan": {
                    "pricingMode": "UNKNOWN",
                    "billableEntityCount": 0,
                }
            },
            "unsupported pricing mode",
        ),
        (
            {
                "currentPricingPlan": {
                    "pricingMode": "STANDARD",
                    "billableEntityCount": -1,
                }
            },
            "non-negative integer",
        ),
        (
            {
                "currentPricingPlan": {
                    "pricingMode": "TIERED_BUNDLE",
                    "billableEntityCount": 1,
                }
            },
            "bundle information",
        ),
    ],
)
def test_observer_rejects_malformed_provider_contract(plan, message):
    session, _, _ = _session(plan)

    with pytest.raises(AwsTwinMakerPricingPlanError, match=message):
        observe_aws_twinmaker_pricing_plan(
            _credentials(),
            "eu-central-1",
            session=session,
        )


def test_observer_rejects_missing_target_region():
    with pytest.raises(AwsTwinMakerPricingPlanError, match="target region"):
        observe_aws_twinmaker_pricing_plan(_credentials(), "")
