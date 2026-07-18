"""Read-only AWS IoT TwinMaker account pricing-plan observation."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
import re
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError

from backend.secret_redaction import credential_strings, redact_secret_like_text


ACCOUNT_CONTEXT_SCHEMA_VERSION = "aws-twinmaker-account-pricing-context.v1"
MAX_BUNDLE_NAMES = 20
MAX_BUNDLE_NAME_LENGTH = 128
MAX_UPDATE_REASON_LENGTH = 500
AWS_ACCOUNT_ID_PATTERN = re.compile(r"^\d{12}$")
AWS_REGION_PATTERN = re.compile(r"^[a-z]{2}(?:-gov)?-[a-z0-9-]+-\d+$")


class AwsTwinMakerPricingMode(str, Enum):
    BASIC = "BASIC"
    STANDARD = "STANDARD"
    TIERED_BUNDLE = "TIERED_BUNDLE"


class AwsTwinMakerBundleTier(str, Enum):
    TIER_1 = "TIER_1"
    TIER_2 = "TIER_2"
    TIER_3 = "TIER_3"
    TIER_4 = "TIER_4"


class AwsTwinMakerPricingPlanError(RuntimeError):
    """Stable, redacted provider-observation error."""

    def __init__(
        self,
        code: str,
        public_message: str,
        identity_verified: bool = False,
    ) -> None:
        super().__init__(public_message)
        self.code = code
        self.public_message = public_message
        self.identity_verified = identity_verified

    def __str__(self) -> str:
        return self.public_message


def build_aws_session(credentials: dict[str, Any], region: str):
    """Create one AWS session without reading local credential files."""

    normalized_region = _required_region(region)
    missing = [
        field
        for field in ("aws_access_key_id", "aws_secret_access_key")
        if not credentials.get(field)
    ]
    if missing:
        raise AwsTwinMakerPricingPlanError(
            "AWS_TWINMAKER_PLAN_AUTHENTICATION_FAILED",
            f"Missing AWS credential fields: {', '.join(missing)}",
        )

    kwargs = {
        "aws_access_key_id": credentials["aws_access_key_id"],
        "aws_secret_access_key": credentials["aws_secret_access_key"],
        "region_name": normalized_region,
    }
    session_token = credentials.get("aws_session_token")
    if session_token:
        kwargs["aws_session_token"] = session_token
    return boto3.Session(**kwargs)


def observe_aws_twinmaker_pricing_plan(
    credentials: dict[str, Any],
    region: str,
    *,
    configured_account_id: str | None = None,
    session: Any | None = None,
    observed_at: datetime | None = None,
) -> dict[str, Any]:
    """Observe account identity and TwinMaker pricing mode using read-only APIs."""

    normalized_region = _required_region(region)
    aws_session = session or build_aws_session(credentials, normalized_region)
    secrets = credential_strings(credentials)

    try:
        identity = aws_session.client("sts").get_caller_identity()
    except (ClientError, NoCredentialsError, BotoCoreError) as exc:
        raise _map_provider_error(exc, secrets, identity_verified=False) from exc
    except Exception as exc:
        raise _unexpected_provider_error(exc, secrets, identity_verified=False) from exc

    verified_account_id = _account_id(identity.get("Account"))
    if configured_account_id is not None:
        normalized_configured = _account_id(configured_account_id)
        if normalized_configured != verified_account_id:
            raise AwsTwinMakerPricingPlanError(
                "AWS_TWINMAKER_PLAN_ACCOUNT_MISMATCH",
                "Configured AWS account does not match the authenticated pricing identity.",
                identity_verified=True,
            )

    try:
        response = aws_session.client(
            "iottwinmaker",
            region_name=normalized_region,
        ).get_pricing_plan()
    except (ClientError, NoCredentialsError, BotoCoreError) as exc:
        raise _map_provider_error(exc, secrets, identity_verified=True) from exc
    except Exception as exc:
        raise _unexpected_provider_error(exc, secrets, identity_verified=True) from exc

    if not isinstance(response, dict):
        raise _invalid_response("TwinMaker returned a non-object pricing plan.")

    current = _normalize_plan(
        response.get("currentPricingPlan"),
        required=True,
        secrets=secrets,
    )
    pending = _normalize_plan(
        response.get("pendingPricingPlan"),
        required=False,
        secrets=secrets,
    )
    timestamp = _utc_timestamp(observed_at or datetime.now(timezone.utc))
    return {
        "schema_version": ACCOUNT_CONTEXT_SCHEMA_VERSION,
        "provider": "aws",
        "service": "iot_twinmaker",
        "region": normalized_region,
        "verified_account_id": verified_account_id,
        "observed_at": timestamp,
        "current_plan": current,
        "pending_plan": pending,
    }


def _normalize_plan(
    value: Any,
    *,
    required: bool,
    secrets: tuple[str, ...],
) -> dict[str, Any] | None:
    if value is None and not required:
        return None
    if not isinstance(value, dict):
        raise _invalid_response("TwinMaker pricing plan is missing or malformed.")

    try:
        mode = AwsTwinMakerPricingMode(str(value.get("pricingMode"))).value
    except ValueError as exc:
        raise _invalid_response("TwinMaker returned an unsupported pricing mode.") from exc

    count = value.get("billableEntityCount")
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise _invalid_response(
            "TwinMaker billableEntityCount must be a non-negative integer."
        )

    bundle = _normalize_bundle(
        value.get("bundleInformation"),
        required=mode == "TIERED_BUNDLE",
        secrets=secrets,
    )
    if mode != "TIERED_BUNDLE" and bundle is not None:
        raise _invalid_response(
            "TwinMaker returned bundle information for a non-bundle pricing mode."
        )

    reason = value.get("updateReason")
    if reason is not None:
        if not isinstance(reason, str) or len(reason) > MAX_UPDATE_REASON_LENGTH:
            raise _invalid_response("TwinMaker updateReason is malformed or too long.")
        reason = redact_secret_like_text(reason, extra_secrets=secrets)

    return {
        "mode": mode,
        "billable_entity_count": count,
        "effective_at": _optional_utc_timestamp(value.get("effectiveDateTime")),
        "updated_at": _optional_utc_timestamp(value.get("updateDateTime")),
        "update_reason": reason,
        "bundle": bundle,
    }


def _normalize_bundle(
    value: Any,
    *,
    required: bool,
    secrets: tuple[str, ...],
) -> dict[str, Any] | None:
    if value is None and not required:
        return None
    if not isinstance(value, dict):
        raise _invalid_response("TwinMaker bundle information is missing or malformed.")

    try:
        tier = AwsTwinMakerBundleTier(str(value.get("pricingTier"))).value
    except ValueError as exc:
        raise _invalid_response("TwinMaker returned an unsupported bundle tier.") from exc

    raw_names = value.get("bundleNames")
    if not isinstance(raw_names, list) or len(raw_names) > MAX_BUNDLE_NAMES:
        raise _invalid_response("TwinMaker bundleNames is malformed or too large.")
    names: list[str] = []
    for name in raw_names:
        if (
            not isinstance(name, str)
            or not name.strip()
            or len(name) > MAX_BUNDLE_NAME_LENGTH
        ):
            raise _invalid_response("TwinMaker returned an invalid bundle name.")
        names.append(
            redact_secret_like_text(name.strip(), extra_secrets=secrets)
        )

    return {"tier": tier, "names": names}


def _required_region(value: Any) -> str:
    if not isinstance(value, str) or not AWS_REGION_PATTERN.fullmatch(value.strip()):
        raise AwsTwinMakerPricingPlanError(
            "AWS_TWINMAKER_PLAN_RESPONSE_INVALID",
            "A valid AWS target region is required for TwinMaker pricing.",
        )
    return value.strip()


def _account_id(value: Any) -> str:
    normalized = str(value or "").strip()
    if not AWS_ACCOUNT_ID_PATTERN.fullmatch(normalized):
        raise _invalid_response("AWS STS returned an invalid account identifier.")
    return normalized


def _optional_utc_timestamp(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise _invalid_response("TwinMaker returned an invalid timestamp.") from exc
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise _invalid_response("TwinMaker timestamps must include a timezone.")
    return _utc_timestamp(value)


def _utc_timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        raise _invalid_response("Observation timestamp must include a timezone.")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _map_provider_error(
    exc: Exception,
    secrets: tuple[str, ...],
    *,
    identity_verified: bool,
) -> AwsTwinMakerPricingPlanError:
    code = ""
    if isinstance(exc, ClientError):
        code = str(exc.response.get("Error", {}).get("Code", ""))
    normalized = code.lower()

    if "accessdenied" in normalized or "unauthorized" in normalized:
        return AwsTwinMakerPricingPlanError(
            "AWS_TWINMAKER_PLAN_PERMISSION_DENIED",
            "AWS pricing credentials cannot read the TwinMaker pricing plan.",
            identity_verified=identity_verified,
        )
    if "throttl" in normalized or "toomanyrequests" in normalized:
        return AwsTwinMakerPricingPlanError(
            "AWS_TWINMAKER_PLAN_THROTTLED",
            "AWS throttled the TwinMaker pricing-plan request. Retry later.",
            identity_verified=identity_verified,
        )
    if (
        isinstance(exc, NoCredentialsError)
        or "invalidclienttoken" in normalized
        or "unrecognizedclient" in normalized
        or "expiredtoken" in normalized
        or "signature" in normalized
    ):
        return AwsTwinMakerPricingPlanError(
            "AWS_TWINMAKER_PLAN_AUTHENTICATION_FAILED",
            "AWS pricing credentials are invalid or expired.",
            identity_verified=False,
        )
    return _unexpected_provider_error(
        exc,
        secrets,
        identity_verified=identity_verified,
    )


def _unexpected_provider_error(
    exc: Exception,
    secrets: tuple[str, ...],
    *,
    identity_verified: bool,
) -> AwsTwinMakerPricingPlanError:
    # Redaction is deliberately performed even though raw provider detail is
    # not returned; this prevents accidental future reuse of unsafe text.
    redact_secret_like_text(exc, extra_secrets=secrets)
    return AwsTwinMakerPricingPlanError(
        "AWS_TWINMAKER_PLAN_RESPONSE_INVALID",
        "AWS TwinMaker pricing-plan observation failed.",
        identity_verified=identity_verified,
    )


def _invalid_response(message: str) -> AwsTwinMakerPricingPlanError:
    return AwsTwinMakerPricingPlanError(
        "AWS_TWINMAKER_PLAN_RESPONSE_INVALID",
        message,
        identity_verified=True,
    )
