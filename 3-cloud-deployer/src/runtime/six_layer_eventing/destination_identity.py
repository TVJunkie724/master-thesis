"""Short-lived workload identities for the six directed Phase 8 bridges.

The module accepts only non-secret identifiers. Source assertions and target
credentials are obtained through official provider SDKs and remain in memory.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import re
from typing import Any, Callable, Mapping

from .bridge_core import (
    BridgeContractError,
    RetryableBridgeError,
    RouteBlockingBridgeError,
)


AWS_REGION = "eu-central-1"
AWS_REGIONAL_STS_ENDPOINT = f"https://sts.{AWS_REGION}.amazonaws.com"
AZURE_TOKEN_EXCHANGE_AUDIENCE = "api://AzureADTokenExchange"  # nosec B105
GCP_STS_TOKEN_URL = "https://sts.googleapis.com/v1/token"  # nosec B105
GCP_AWS_SUBJECT_TOKEN_TYPE = (  # nosec B105
    "urn:ietf:params:aws:token-type:aws4_request"
)
GCP_OIDC_SUBJECT_TOKEN_TYPE = "urn:ietf:params:oauth:token-type:jwt"  # nosec B105
GCP_PUBSUB_SCOPE = "https://www.googleapis.com/auth/pubsub"
_REFRESH_SKEW = timedelta(minutes=5)
_MAX_CACHE_AGE = timedelta(hours=1)
_GCP_IMPERSONATION_LIFETIME_SECONDS = int(timedelta(hours=1).total_seconds())
_AWS_ROLE_ARN = re.compile(
    r"^arn:aws:iam::(?P<account>\d{12}):role/(?P<role>[A-Za-z0-9+=,.@_/-]{1,512})$"
)
_BRIDGE_AUDIENCE = re.compile(
    r"^api://[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
_UUID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
_GCP_PROVIDER_AUDIENCE = re.compile(
    r"^//iam\.googleapis\.com/projects/(?P<number>[1-9]\d{5,29})/locations/global/"
    r"workloadIdentityPools/(?P<pool>[a-z][a-z0-9-]{2,31})/providers/"
    r"(?P<provider>[a-z][a-z0-9-]{2,31})$"
)
_GCP_IMPERSONATION_URL = re.compile(
    r"^https://iamcredentials\.googleapis\.com/v1/projects/-/serviceAccounts/"
    r"(?P<account>[a-z][a-z0-9-]{4,28}[a-z0-9]@[a-z][a-z0-9-]{4,28}[a-z0-9]"
    r"\.iam\.gserviceaccount\.com):generateAccessToken$"
)
_BLOCKING_AWS_CODES = frozenset(
    {
        "accessdenied",
        "invalididentitytoken",
        "malformedpolicydocument",
        "regiondisabled",
    }
)
_RETRYABLE_AWS_CODES = frozenset(
    {
        "expiredtoken",
        "idpcommunicationerror",
        "requesttimeout",
        "serviceunavailable",
        "throttling",
        "throttlingexception",
    }
)


@dataclass(frozen=True, slots=True)
class AwsRoleTarget:
    role_arn: str
    assertion_audience: str


@dataclass(frozen=True, slots=True)
class AzureFederatedTarget:
    tenant_id: str
    client_id: str
    assertion_audience: str = AZURE_TOKEN_EXCHANGE_AUDIENCE


@dataclass(frozen=True, slots=True)
class GcpFederatedTarget:
    provider_audience: str
    service_account_impersonation_url: str
    source_assertion_audience: str = ""


def load_identity_target(
    raw: object,
    *,
    source_provider: str,
    destination_provider: str,
) -> AwsRoleTarget | AzureFederatedTarget | GcpFederatedTarget:
    """Validate one directed identity target without accepting credentials."""

    if (
        source_provider not in {"aws", "azure", "gcp"}
        or destination_provider not in {"aws", "azure", "gcp"}
        or source_provider == destination_provider
        or not isinstance(raw, Mapping)
    ):
        raise BridgeContractError("INVALID_IDENTITY_CONFIGURATION")
    if destination_provider == "aws":
        if set(raw) != {"role_arn", "assertion_audience"}:
            raise BridgeContractError("INVALID_IDENTITY_CONFIGURATION")
        role_arn = raw.get("role_arn")
        audience = raw.get("assertion_audience")
        if (
            not isinstance(role_arn, str)
            or not _AWS_ROLE_ARN.fullmatch(role_arn)
            or not isinstance(audience, str)
            or not _BRIDGE_AUDIENCE.fullmatch(audience)
        ):
            raise BridgeContractError("INVALID_IDENTITY_CONFIGURATION")
        return AwsRoleTarget(role_arn, audience)
    if destination_provider == "azure":
        if set(raw) != {"tenant_id", "client_id"}:
            raise BridgeContractError("INVALID_IDENTITY_CONFIGURATION")
        tenant_id = raw.get("tenant_id")
        client_id = raw.get("client_id")
        if (
            not isinstance(tenant_id, str)
            or not _UUID.fullmatch(tenant_id)
            or not isinstance(client_id, str)
            or not _UUID.fullmatch(client_id)
        ):
            raise BridgeContractError("INVALID_IDENTITY_CONFIGURATION")
        return AzureFederatedTarget(tenant_id, client_id)
    required = {
        "provider_audience",
        "service_account_impersonation_url",
    }
    if source_provider == "azure":
        required.add("source_assertion_audience")
    if set(raw) != required:
        raise BridgeContractError("INVALID_IDENTITY_CONFIGURATION")
    audience = raw.get("provider_audience")
    impersonation_url = raw.get("service_account_impersonation_url")
    assertion_audience = raw.get("source_assertion_audience", "")
    if (
        not isinstance(audience, str)
        or not _GCP_PROVIDER_AUDIENCE.fullmatch(audience)
        or not isinstance(impersonation_url, str)
        or not _GCP_IMPERSONATION_URL.fullmatch(impersonation_url)
        or not isinstance(assertion_audience, str)
        or (
            source_provider == "azure"
            and not _BRIDGE_AUDIENCE.fullmatch(assertion_audience)
        )
    ):
        raise BridgeContractError("INVALID_IDENTITY_CONFIGURATION")
    return GcpFederatedTarget(audience, impersonation_url, assertion_audience)


def _aws_error_code(exc: Exception) -> str:
    response = getattr(exc, "response", None)
    if not isinstance(response, Mapping):
        return ""
    error = response.get("Error")
    return str(error.get("Code", "")).lower() if isinstance(error, Mapping) else ""


def raise_safe_identity_error(exc: Exception) -> None:
    """Translate SDK failures without exposing tokens, claims, or raw errors."""

    status = getattr(exc, "status_code", None)
    aws_code = _aws_error_code(exc)
    if aws_code in _RETRYABLE_AWS_CODES or status in {408, 429} or (
        isinstance(status, int) and status >= 500
    ):
        raise RetryableBridgeError("IDENTITY_EXCHANGE_RETRYABLE") from None
    if status in {400, 401, 403} or aws_code in _BLOCKING_AWS_CODES:
        raise RouteBlockingBridgeError("IDENTITY_CLAIM_REJECTED") from None
    raise RetryableBridgeError("IDENTITY_EXCHANGE_RETRYABLE") from None


def _assertion(value: object) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value.encode("utf-8")) > 16 * 1024
        or value.count(".") != 2
    ):
        raise RouteBlockingBridgeError("IDENTITY_CLAIM_REJECTED")
    return value


class AwsOutboundAssertionSupplier:
    """Obtain an AWS-signed RS256 assertion from regional STS."""

    def __init__(
        self,
        audience: str = AZURE_TOKEN_EXCHANGE_AUDIENCE,
        *,
        sts_client: object | None = None,
        client_factory: Callable[..., object] | None = None,
    ) -> None:
        if audience != AZURE_TOKEN_EXCHANGE_AUDIENCE:
            raise BridgeContractError("INVALID_IDENTITY_CONFIGURATION")
        if sts_client is None:
            if client_factory is None:
                import boto3

                client_factory = boto3.client
            sts_client = client_factory(
                "sts",
                region_name=AWS_REGION,
                endpoint_url=AWS_REGIONAL_STS_ENDPOINT,
            )
        self._audience = audience
        self._sts_client = sts_client

    def __call__(self) -> str:
        try:
            result = self._sts_client.get_web_identity_token(
                Audience=[self._audience],
                DurationSeconds=300,
                SigningAlgorithm="RS256",
            )
            token = result.get("WebIdentityToken") if isinstance(result, Mapping) else None
            return _assertion(token)
        except (BridgeContractError, RouteBlockingBridgeError, RetryableBridgeError):
            raise
        except Exception as exc:
            raise_safe_identity_error(exc)


class AzureManagedIdentityAssertionSupplier:
    """Obtain a bridge-only Entra assertion from a user-assigned identity."""

    def __init__(
        self,
        client_id: str,
        audience: str,
        *,
        credential: object | None = None,
        credential_factory: Callable[..., object] | None = None,
    ) -> None:
        if not _UUID.fullmatch(client_id) or not _BRIDGE_AUDIENCE.fullmatch(audience):
            raise BridgeContractError("INVALID_IDENTITY_CONFIGURATION")
        if credential is None:
            if credential_factory is None:
                from azure.identity import ManagedIdentityCredential

                credential_factory = ManagedIdentityCredential
            credential = credential_factory(client_id=client_id)
        self._credential = credential
        self._scope = f"{audience}/.default"

    def __call__(self) -> str:
        try:
            result = self._credential.get_token(self._scope)
            return _assertion(getattr(result, "token", None))
        except (BridgeContractError, RouteBlockingBridgeError, RetryableBridgeError):
            raise
        except Exception as exc:
            raise_safe_identity_error(exc)


class GoogleIdTokenAssertionSupplier:
    """Obtain a Google-signed workload assertion for AWS or Entra."""

    def __init__(
        self,
        audience: str,
        *,
        fetcher: Callable[[object, str], str] | None = None,
        request: object | None = None,
    ) -> None:
        if audience != AZURE_TOKEN_EXCHANGE_AUDIENCE and not _BRIDGE_AUDIENCE.fullmatch(
            audience
        ):
            raise BridgeContractError("INVALID_IDENTITY_CONFIGURATION")
        if fetcher is None or request is None:
            from google.auth.transport.requests import Request
            from google.oauth2.id_token import fetch_id_token

            fetcher = fetcher or fetch_id_token
            request = request or Request()
        self._audience = audience
        self._fetcher = fetcher
        self._request = request

    def __call__(self) -> str:
        try:
            return _assertion(self._fetcher(self._request, self._audience))
        except (BridgeContractError, RouteBlockingBridgeError, RetryableBridgeError):
            raise
        except Exception as exc:
            raise_safe_identity_error(exc)


def build_azure_credential(
    target: AzureFederatedTarget,
    assertion_supplier: Callable[[], str],
    *,
    credential_factory: Callable[..., object] | None = None,
) -> object:
    """Build an Entra credential backed by a callable source assertion."""

    if credential_factory is None:
        from azure.identity import ClientAssertionCredential

        credential_factory = ClientAssertionCredential
    return credential_factory(
        tenant_id=target.tenant_id,
        client_id=target.client_id,
        func=lambda: _assertion(assertion_supplier()),
    )


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class AwsAssumeRoleClientFactory:
    """Cache one short-lived AssumeRoleWithWebIdentity session in memory."""

    def __init__(
        self,
        target: AwsRoleTarget,
        assertion_supplier: Callable[[], str],
        *,
        sts_client: object | None = None,
        sts_client_factory: Callable[..., object] | None = None,
        session_factory: Callable[..., object] | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        if sts_client is None:
            if sts_client_factory is None:
                import boto3

                sts_client_factory = boto3.client
            sts_client = sts_client_factory("sts", region_name=AWS_REGION)
        if session_factory is None:
            import boto3

            session_factory = boto3.Session
        self._target = target
        self._assertion_supplier = assertion_supplier
        self._sts_client = sts_client
        self._session_factory = session_factory
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._session: object | None = None
        self._refresh_at: datetime | None = None

    def _fresh_session(self) -> object:
        acquired_at = _aware_utc(self._now())
        try:
            result = self._sts_client.assume_role_with_web_identity(
                RoleArn=self._target.role_arn,
                RoleSessionName="twin2multicloud-bridge",
                WebIdentityToken=_assertion(self._assertion_supplier()),
                DurationSeconds=3600,
            )
            credentials = result.get("Credentials") if isinstance(result, Mapping) else None
            if not isinstance(credentials, Mapping):
                raise RetryableBridgeError("IDENTITY_EXCHANGE_RETRYABLE")
            access_key = credentials.get("AccessKeyId")
            secret_key = credentials.get("SecretAccessKey")
            session_token = credentials.get("SessionToken")
            expiration = credentials.get("Expiration")
            if (
                not isinstance(access_key, str)
                or not access_key
                or not isinstance(secret_key, str)
                or not secret_key
                or not isinstance(session_token, str)
                or not session_token
                or not isinstance(expiration, datetime)
            ):
                raise RetryableBridgeError("IDENTITY_EXCHANGE_RETRYABLE")
            refresh_at = min(
                _aware_utc(expiration) - _REFRESH_SKEW,
                acquired_at + _MAX_CACHE_AGE,
            )
            if refresh_at <= acquired_at:
                raise RetryableBridgeError("IDENTITY_EXCHANGE_RETRYABLE")
            session = self._session_factory(
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                aws_session_token=session_token,
                region_name=AWS_REGION,
            )
            self._session = session
            self._refresh_at = refresh_at
            return session
        except (BridgeContractError, RouteBlockingBridgeError, RetryableBridgeError):
            raise
        except Exception as exc:
            raise_safe_identity_error(exc)

    def __call__(self, service: str) -> object:
        if service not in {"kinesis", "sns"}:
            raise BridgeContractError("INVALID_IDENTITY_CONFIGURATION")
        now = _aware_utc(self._now())
        if self._session is None or self._refresh_at is None or now >= self._refresh_at:
            session = self._fresh_session()
        else:
            session = self._session
        return session.client(service, region_name=AWS_REGION)


class AmbientAwsCredentialsSupplier:
    """Adapt the Lambda role's rotating credentials to Google AWS WIF."""

    def __init__(
        self,
        *,
        session: object | None = None,
        session_factory: Callable[[], object] | None = None,
        value_factory: Callable[..., object] | None = None,
    ) -> None:
        if session is None:
            if session_factory is None:
                import boto3

                session_factory = boto3.Session
            session = session_factory()
        if value_factory is None:
            from google.auth.aws import AwsSecurityCredentials

            value_factory = AwsSecurityCredentials
        self._session = session
        self._value_factory = value_factory

    def get_aws_region(self, _context: object, _request: object) -> str:
        return AWS_REGION

    def get_aws_security_credentials(
        self, _context: object, _request: object
    ) -> object:
        try:
            credentials = self._session.get_credentials()
            frozen = credentials.get_frozen_credentials() if credentials else None
            if frozen is None or not all(
                isinstance(getattr(frozen, field, None), str)
                and getattr(frozen, field)
                for field in ("access_key", "secret_key", "token")
            ):
                raise RouteBlockingBridgeError("IDENTITY_CLAIM_REJECTED")
            return self._value_factory(
                frozen.access_key,
                frozen.secret_key,
                frozen.token,
            )
        except (BridgeContractError, RouteBlockingBridgeError, RetryableBridgeError):
            raise
        except Exception as exc:
            raise_safe_identity_error(exc)


class CallableSubjectTokenSupplier:
    """Adapt an in-memory OIDC assertion callable to Google Identity Pool WIF."""

    def __init__(
        self,
        provider_audience: str,
        assertion_supplier: Callable[[], str],
    ) -> None:
        self._provider_audience = provider_audience
        self._assertion_supplier = assertion_supplier

    def get_subject_token(self, context: object, _request: object) -> str:
        if getattr(context, "audience", None) != self._provider_audience:
            raise RouteBlockingBridgeError("IDENTITY_CLAIM_REJECTED")
        return _assertion(self._assertion_supplier())


def build_gcp_credentials(
    target: GcpFederatedTarget,
    *,
    source_provider: str,
    assertion_supplier: Callable[[], str] | None = None,
    aws_credentials_supplier: object | None = None,
    aws_credential_factory: Callable[..., object] | None = None,
    oidc_credential_factory: Callable[..., object] | None = None,
) -> object:
    """Build WIF credentials with service-account impersonation for Pub/Sub."""

    common: dict[str, Any] = {
        "audience": target.provider_audience,
        "token_url": GCP_STS_TOKEN_URL,
        "service_account_impersonation_url": target.service_account_impersonation_url,
        "service_account_impersonation_options": {
            "token_lifetime_seconds": _GCP_IMPERSONATION_LIFETIME_SECONDS
        },
        "scopes": [GCP_PUBSUB_SCOPE],
    }
    if source_provider == "aws":
        if assertion_supplier is not None or target.source_assertion_audience:
            raise BridgeContractError("INVALID_IDENTITY_CONFIGURATION")
        if aws_credentials_supplier is None:
            aws_credentials_supplier = AmbientAwsCredentialsSupplier()
        if aws_credential_factory is None:
            from google.auth.aws import Credentials

            aws_credential_factory = Credentials
        return aws_credential_factory(
            subject_token_type=GCP_AWS_SUBJECT_TOKEN_TYPE,
            aws_security_credentials_supplier=aws_credentials_supplier,
            **common,
        )
    if source_provider == "azure":
        if (
            assertion_supplier is None
            or aws_credentials_supplier is not None
            or not target.source_assertion_audience
        ):
            raise BridgeContractError("INVALID_IDENTITY_CONFIGURATION")
        if oidc_credential_factory is None:
            from google.auth.identity_pool import Credentials

            oidc_credential_factory = Credentials
        return oidc_credential_factory(
            subject_token_type=GCP_OIDC_SUBJECT_TOKEN_TYPE,
            subject_token_supplier=CallableSubjectTokenSupplier(
                target.provider_audience,
                assertion_supplier,
            ),
            **common,
        )
    raise BridgeContractError("INVALID_IDENTITY_CONFIGURATION")


__all__ = [
    "AWS_REGION",
    "AWS_REGIONAL_STS_ENDPOINT",
    "AZURE_TOKEN_EXCHANGE_AUDIENCE",
    "GCP_STS_TOKEN_URL",
    "AmbientAwsCredentialsSupplier",
    "AwsAssumeRoleClientFactory",
    "AwsOutboundAssertionSupplier",
    "AwsRoleTarget",
    "AzureFederatedTarget",
    "AzureManagedIdentityAssertionSupplier",
    "CallableSubjectTokenSupplier",
    "GcpFederatedTarget",
    "GoogleIdTokenAssertionSupplier",
    "build_azure_credential",
    "build_gcp_credentials",
    "load_identity_target",
    "raise_safe_identity_error",
]

