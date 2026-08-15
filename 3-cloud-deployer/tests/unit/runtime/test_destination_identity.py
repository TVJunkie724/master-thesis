"""Short-lived bridge identity tests without live provider calls."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pytest

from src.runtime.eventing.bridge_core import (
    BridgeContractError,
    RetryableBridgeError,
    RouteBlockingBridgeError,
)
from src.runtime.eventing.destination_identity import (
    AWS_REGIONAL_STS_ENDPOINT,
    AWS_REGION,
    AZURE_TOKEN_EXCHANGE_AUDIENCE,
    GCP_AWS_SUBJECT_TOKEN_TYPE,
    GCP_OIDC_SUBJECT_TOKEN_TYPE,
    GCP_PUBSUB_SCOPE,
    GCP_STS_TOKEN_URL,
    AmbientAwsCredentialsSupplier,
    AwsAssumeRoleClientFactory,
    AwsOutboundAssertionSupplier,
    AzureManagedIdentityAssertionSupplier,
    CallableSubjectTokenSupplier,
    GoogleIdTokenAssertionSupplier,
    build_azure_credential,
    build_gcp_credentials,
    load_identity_target,
    raise_safe_identity_error,
)


TENANT_ID = "11111111-1111-4111-8111-111111111111"
CLIENT_ID = "22222222-2222-4222-8222-222222222222"
BRIDGE_AUDIENCE = "api://33333333-3333-4333-8333-333333333333"
ROLE_ARN = "arn:aws:iam::123456789012:role/twin2multicloud/bridge"
PROVIDER_AUDIENCE = (
    "//iam.googleapis.com/projects/123456789012/locations/global/"
    "workloadIdentityPools/twin-pool/providers/azure-bridge"
)
IMPERSONATION_URL = (
    "https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/"
    "bridge@project-1.iam.gserviceaccount.com:generateAccessToken"
)
JWT = "header.payload.signature"


def _aws_target():
    return load_identity_target(
        {"role_arn": ROLE_ARN, "assertion_audience": BRIDGE_AUDIENCE},
        source_provider="gcp",
        destination_provider="aws",
    )


def _azure_target():
    return load_identity_target(
        {"tenant_id": TENANT_ID, "client_id": CLIENT_ID},
        source_provider="aws",
        destination_provider="azure",
    )


def _gcp_target(source="azure"):
    configuration = {
        "provider_audience": PROVIDER_AUDIENCE,
        "service_account_impersonation_url": IMPERSONATION_URL,
    }
    if source == "azure":
        configuration["source_assertion_audience"] = BRIDGE_AUDIENCE
    return load_identity_target(
        configuration,
        source_provider=source,
        destination_provider="gcp",
    )


@pytest.mark.parametrize(
    ("source", "destination", "configuration"),
    [
        (
            "gcp",
            "aws",
            {
                "role_arn": ROLE_ARN,
                "assertion_audience": BRIDGE_AUDIENCE,
                "secret_access_key": "forbidden",
            },
        ),
        (
            "aws",
            "azure",
            {"tenant_id": TENANT_ID, "client_id": CLIENT_ID, "client_secret": "x"},
        ),
        (
            "azure",
            "gcp",
            {
                "provider_audience": PROVIDER_AUDIENCE,
                "service_account_impersonation_url": IMPERSONATION_URL,
                "source_assertion_audience": BRIDGE_AUDIENCE,
                "service_account_key": "x",
            },
        ),
    ],
)
def test_identity_targets_reject_secret_or_unknown_fields(
    source, destination, configuration
):
    with pytest.raises(BridgeContractError, match="INVALID_IDENTITY_CONFIGURATION"):
        load_identity_target(
            configuration,
            source_provider=source,
            destination_provider=destination,
        )


def test_identity_targets_are_directed_and_endpoint_closed():
    assert _aws_target().role_arn == ROLE_ARN
    assert _azure_target().assertion_audience == AZURE_TOKEN_EXCHANGE_AUDIENCE
    assert _gcp_target().provider_audience == PROVIDER_AUDIENCE
    assert _gcp_target().source_assertion_audience == BRIDGE_AUDIENCE
    assert _gcp_target("aws").source_assertion_audience == ""

    with pytest.raises(BridgeContractError, match="INVALID_IDENTITY_CONFIGURATION"):
        load_identity_target(
            {"tenant_id": TENANT_ID, "client_id": CLIENT_ID},
            source_provider="azure",
            destination_provider="azure",
        )
    with pytest.raises(BridgeContractError, match="INVALID_IDENTITY_CONFIGURATION"):
        load_identity_target(
            {
                "provider_audience": PROVIDER_AUDIENCE,
                "service_account_impersonation_url": (
                    "https://proxy.example.test/token"
                ),
            },
            source_provider="aws",
            destination_provider="gcp",
        )


class _OutboundSts:
    def __init__(self):
        self.requests = []

    def get_web_identity_token(self, **request):
        self.requests.append(request)
        return {"WebIdentityToken": JWT}


def test_aws_to_azure_assertion_is_rs256_short_and_regional():
    clients = []
    sts = _OutboundSts()

    def client_factory(service, **configuration):
        clients.append((service, configuration))
        return sts

    supplier = AwsOutboundAssertionSupplier(client_factory=client_factory)

    assert supplier() == JWT
    assert clients == [
        (
            "sts",
            {"region_name": AWS_REGION, "endpoint_url": AWS_REGIONAL_STS_ENDPOINT},
        )
    ]
    assert sts.requests == [
        {
            "Audience": [AZURE_TOKEN_EXCHANGE_AUDIENCE],
            "DurationSeconds": 300,
            "SigningAlgorithm": "RS256",
        }
    ]


def test_azure_credential_uses_callable_source_assertion():
    requests = []

    def factory(**configuration):
        requests.append(configuration)
        return "credential"

    credential = build_azure_credential(
        _azure_target(),
        lambda: JWT,
        credential_factory=factory,
    )

    assert credential == "credential"
    assert requests[0]["tenant_id"] == TENANT_ID
    assert requests[0]["client_id"] == CLIENT_ID
    assert requests[0]["func"]() == JWT


@dataclass
class _Token:
    token: str


class _ManagedIdentity:
    def __init__(self):
        self.scopes = []

    def get_token(self, scope):
        self.scopes.append(scope)
        return _Token(JWT)


def test_azure_source_requests_only_the_bridge_application_scope():
    credential = _ManagedIdentity()
    supplier = AzureManagedIdentityAssertionSupplier(
        CLIENT_ID,
        BRIDGE_AUDIENCE,
        credential=credential,
    )

    assert supplier() == JWT
    assert credential.scopes == [f"{BRIDGE_AUDIENCE}/.default"]


def test_gcp_source_requests_the_exact_destination_audience():
    calls = []
    request = object()

    def fetcher(actual_request, audience):
        calls.append((actual_request, audience))
        return JWT

    supplier = GoogleIdTokenAssertionSupplier(
        AZURE_TOKEN_EXCHANGE_AUDIENCE,
        fetcher=fetcher,
        request=request,
    )

    assert supplier() == JWT
    assert calls == [(request, AZURE_TOKEN_EXCHANGE_AUDIENCE)]


class _AssumeRoleSts:
    def __init__(self, clock):
        self.clock = clock
        self.requests = []

    def assume_role_with_web_identity(self, **request):
        self.requests.append(request)
        generation = len(self.requests)
        return {
            "Credentials": {
                "AccessKeyId": f"access-{generation}",
                "SecretAccessKey": f"secret-{generation}",
                "SessionToken": f"session-{generation}",
                "Expiration": self.clock[0] + timedelta(hours=1),
            }
        }


class _Session:
    def __init__(self, **configuration):
        self.configuration = configuration
        self.clients = []

    def client(self, service, **configuration):
        value = (service, configuration, self.configuration["aws_access_key_id"])
        self.clients.append(value)
        return value


def test_aws_target_session_is_memory_only_and_refreshes_with_skew():
    clock = [datetime(2026, 8, 8, tzinfo=timezone.utc)]
    sts = _AssumeRoleSts(clock)
    sessions = []

    def session_factory(**configuration):
        session = _Session(**configuration)
        sessions.append(session)
        return session

    factory = AwsAssumeRoleClientFactory(
        _aws_target(),
        lambda: JWT,
        sts_client=sts,
        session_factory=session_factory,
        now=lambda: clock[0],
    )

    assert factory("kinesis")[2] == "access-1"
    clock[0] += timedelta(minutes=54)
    assert factory("sns")[2] == "access-1"
    clock[0] += timedelta(minutes=1)
    assert factory("kinesis")[2] == "access-2"
    assert len(sts.requests) == 2
    assert sts.requests[0] == {
        "RoleArn": ROLE_ARN,
        "RoleSessionName": "twin2multicloud-bridge",
        "WebIdentityToken": JWT,
        "DurationSeconds": 3600,
    }
    assert sessions[0].configuration["region_name"] == AWS_REGION


@dataclass
class _FrozenAwsCredentials:
    access_key: str = "ambient-access"
    secret_key: str = "ambient-secret"
    token: str = "ambient-session"


class _AmbientCredentials:
    def get_frozen_credentials(self):
        return _FrozenAwsCredentials()


class _AmbientSession:
    def get_credentials(self):
        return _AmbientCredentials()


def test_aws_to_gcp_supplier_reads_only_ambient_rotating_credentials():
    values = []
    supplier = AmbientAwsCredentialsSupplier(
        session=_AmbientSession(),
        value_factory=lambda *args: values.append(args) or args,
    )

    assert supplier.get_aws_region(object(), object()) == AWS_REGION
    assert supplier.get_aws_security_credentials(object(), object()) == (
        "ambient-access",
        "ambient-secret",
        "ambient-session",
    )
    assert len(values) == 1


def test_gcp_wif_builders_pin_sts_scope_and_service_account_impersonation():
    aws_requests = []
    aws_supplier = object()

    def aws_factory(**configuration):
        aws_requests.append(configuration)
        return "aws-wif"

    assert (
        build_gcp_credentials(
            _gcp_target("aws"),
            source_provider="aws",
            aws_credentials_supplier=aws_supplier,
            aws_credential_factory=aws_factory,
        )
        == "aws-wif"
    )
    assert aws_requests[0]["subject_token_type"] == GCP_AWS_SUBJECT_TOKEN_TYPE
    assert aws_requests[0]["token_url"] == GCP_STS_TOKEN_URL
    assert aws_requests[0]["scopes"] == [GCP_PUBSUB_SCOPE]
    assert aws_requests[0]["aws_security_credentials_supplier"] is aws_supplier
    assert aws_requests[0]["service_account_impersonation_url"] == IMPERSONATION_URL

    oidc_requests = []

    def oidc_factory(**configuration):
        oidc_requests.append(configuration)
        return "azure-wif"

    assert (
        build_gcp_credentials(
            _gcp_target(),
            source_provider="azure",
            assertion_supplier=lambda: JWT,
            oidc_credential_factory=oidc_factory,
        )
        == "azure-wif"
    )
    assert oidc_requests[0]["subject_token_type"] == GCP_OIDC_SUBJECT_TOKEN_TYPE
    subject_supplier = oidc_requests[0]["subject_token_supplier"]
    context = type("Context", (), {"audience": PROVIDER_AUDIENCE})()
    assert subject_supplier.get_subject_token(context, object()) == JWT


def test_subject_supplier_rejects_sdk_audience_drift():
    supplier = CallableSubjectTokenSupplier(PROVIDER_AUDIENCE, lambda: JWT)
    context = type("Context", (), {"audience": "unexpected"})()

    with pytest.raises(RouteBlockingBridgeError, match="IDENTITY_CLAIM_REJECTED"):
        supplier.get_subject_token(context, object())


class _AwsError(Exception):
    def __init__(self, code):
        self.response = {"Error": {"Code": code, "Message": "sensitive"}}


def test_identity_failures_use_only_bounded_error_codes():
    with pytest.raises(RouteBlockingBridgeError) as blocked:
        raise_safe_identity_error(_AwsError("InvalidIdentityToken"))
    assert str(blocked.value) == "IDENTITY_CLAIM_REJECTED"

    with pytest.raises(RetryableBridgeError) as retryable:
        raise_safe_identity_error(RuntimeError("raw token failure"))
    assert str(retryable.value) == "IDENTITY_EXCHANGE_RETRYABLE"
