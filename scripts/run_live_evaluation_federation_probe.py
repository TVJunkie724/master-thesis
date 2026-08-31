#!/usr/bin/env python3
"""Execute one explicitly approved, identity-only Phase 8 federation probe.

The runner is an evaluation harness, not an application deployment path. It
accepts only the frozen run ID and plan digest, emits a secret-free result, and
always attempts dependency-ordered cleanup before returning.

Only explicitly implemented routes are enabled; there is no generic provider
mutation escape hatch.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

import boto3
import requests
from azure.core.exceptions import ClientAuthenticationError, HttpResponseError
from azure.identity import ClientAssertionCredential, ClientSecretCredential
from azure.mgmt.authorization import AuthorizationManagementClient
from azure.mgmt.msi import ManagedServiceIdentityClient
from azure.mgmt.resource.resources import ResourceManagementClient
from botocore.exceptions import ClientError
from google.auth import aws as google_auth_aws
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import service_account
from googleapiclient.discovery import build as build_google_api
from googleapiclient.errors import HttpError


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "docs/research/evaluation/directed-federation-probe-plan.json"
APPROVED_RUN_ID = "26083001"
APPROVED_PLAN_DIGEST = (
    "sha256:29d1024d5180e79b86ff198da4c21c61c83f89c703753b850efe3686c0505754"
)
ENABLED_PROBES = frozenset(
    {
        "federation-gcp-to-aws",
        "federation-gcp-to-azure",
        "federation-aws-to-azure",
        "federation-aws-to-gcp",
    }
)
GCP_TO_AWS_NAMES = {
    "gcp_service_account": "t2mc-p8-gcp-aws-26083001-sa",
    "aws_role": "t2mc-p8-gcp-aws-26083001-role",
}
GCP_TO_AZURE_NAMES = {
    "gcp_service_account": "t2mc-p8-gcp-azure-26083001-sa",
    "azure_resource_group": "t2mc-p8-gcp-azure-26083001-rg",
    "azure_managed_identity": "t2mc-p8-gcp-azure-26083001-mi",
    "azure_federated_credential": "gcp-exchange-26083001",
}
AWS_TO_AZURE_NAMES = {
    "aws_role": "t2mc-p8-aws-azure-26083001-role",
    "aws_inline_policy": "t2mc-p8-aws-azure-26083001-token",
    "azure_resource_group": "t2mc-p8-aws-azure-26083001-rg",
    "azure_managed_identity": "t2mc-p8-aws-azure-26083001-mi",
    "azure_federated_credential": "aws-exchange-26083001",
}
AWS_TO_GCP_NAMES = {
    "aws_role": "t2mc-p8-aws-gcp-26083001-role",
    "gcp_service_account": "t2mc-p8-aws-gcp-26083001-sa",
    "gcp_workload_identity_pool": "t2mc-p8-aws-gcp-26083001",
    "gcp_workload_identity_provider": "t2mc-p8-aws-gcp-26083001",
}
AWS_REGION = "eu-central-1"
AZURE_REGION = "westeurope"
AZURE_FEDERATION_AUDIENCE = "api://AzureADTokenExchange"
AZURE_READER_ROLE_DEFINITION_ID = "acdd72a7-3385-48ef-bd42-f606fba81ae7"
MAXIMUM_ELAPSED_SECONDS = 10 * 60
AWS_PROPAGATION_ATTEMPTS = 8
AWS_PROPAGATION_DELAY_SECONDS = 5
GCP_PERMISSION_PROPAGATION_ATTEMPTS = 30
GCP_PERMISSION_PROPAGATION_DELAY_SECONDS = 5
AZURE_PROPAGATION_ATTEMPTS = 30
AZURE_PROPAGATION_DELAY_SECONDS = 5
SENSITIVE_CREDENTIAL_KEYS = frozenset(
    {
        "aws_access_key_id",
        "aws_secret_access_key",
        "aws_session_token",
        "azure_subscription_id",
        "azure_tenant_id",
        "azure_client_id",
        "azure_client_secret",
        "gcp_project_id",
        "gcp_credentials_file",
        "private_key",
        "private_key_id",
        "client_email",
        "client_id",
    }
)


class ProbeBlocked(RuntimeError):
    """Expected fail-closed boundary with a stable, non-sensitive code."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class _StaticAwsCredentialsSupplier(
    google_auth_aws.AwsSecurityCredentialsSupplier
):
    def __init__(self, credentials: dict[str, str], region: str) -> None:
        self._credentials = credentials
        self._region = region

    def get_aws_security_credentials(
        self,
        context: Any,
        request: Any,
    ) -> google_auth_aws.AwsSecurityCredentials:
        del context, request
        return google_auth_aws.AwsSecurityCredentials(
            access_key_id=self._credentials["AccessKeyId"],
            secret_access_key=self._credentials["SecretAccessKey"],
            session_token=self._credentials["SessionToken"],
        )

    def get_aws_region(self, context: Any, request: Any) -> str:
        del context, request
        return self._region


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(value).encode()).hexdigest()


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("expected a JSON object")
    return value


def _safe_error_code(exc: Exception) -> str:
    if isinstance(exc, ProbeBlocked):
        return exc.code
    if isinstance(exc, ClientError):
        raw = str(exc.response.get("Error", {}).get("Code") or "AWS_CLIENT_ERROR")
    elif isinstance(exc, ClientAuthenticationError):
        raw = "AZURE_CLIENT_AUTHENTICATION_ERROR"
    elif isinstance(exc, HttpResponseError):
        error = getattr(exc, "error", None)
        raw = str(
            getattr(error, "code", None)
            or getattr(exc, "status_code", None)
            or "AZURE_HTTP_ERROR"
        )
    elif isinstance(exc, HttpError):
        raw = f"GCP_HTTP_{getattr(exc.resp, 'status', 'ERROR')}"
        try:
            content = json.loads(exc.content.decode("utf-8"))
            error = content.get("error", {})
            classifications = [str(error.get("status") or "")]
            for detail in error.get("details", []):
                if isinstance(detail, dict) and detail.get("reason"):
                    classifications.append(str(detail["reason"]))
            suffix = "_".join(value for value in classifications if value)
            if suffix:
                raw = f"GCP_{suffix}"
        except (AttributeError, UnicodeDecodeError, json.JSONDecodeError):
            pass
    else:
        raw = type(exc).__name__
    normalized = re.sub(r"[^A-Z0-9_]+", "_", raw.upper()).strip("_")
    return normalized[:80] or "PROVIDER_ERROR"


def _assert_deadline(started_monotonic: float) -> None:
    if time.monotonic() - started_monotonic > MAXIMUM_ELAPSED_SECONDS:
        raise ProbeBlocked("PROBE_DEADLINE_EXCEEDED")


def _load_credentials(
    provider_config_path: Path,
    gcp_credentials_path: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    config = _load_object(provider_config_path)
    try:
        aws = dict(config["aws"])
        gcp = dict(config["gcp"])
        azure = dict(config["azure"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ProbeBlocked("CREDENTIAL_SCHEMA_INVALID") from exc
    gcp_key = _load_object(gcp_credentials_path)
    required_aws = {"aws_access_key_id", "aws_secret_access_key", "aws_region"}
    required_gcp = {"gcp_project_id", "gcp_region"}
    required_key = {"type", "project_id", "private_key", "client_email"}
    required_azure = {
        "azure_subscription_id",
        "azure_tenant_id",
        "azure_client_id",
        "azure_client_secret",
        "azure_region",
    }
    if (
        not required_aws.issubset(aws)
        or not required_gcp.issubset(gcp)
        or not required_azure.issubset(azure)
    ):
        raise ProbeBlocked("CREDENTIAL_SCHEMA_INVALID")
    if not required_key.issubset(gcp_key) or gcp_key.get("type") != "service_account":
        raise ProbeBlocked("CREDENTIAL_SCHEMA_INVALID")
    if gcp_key["project_id"] != gcp["gcp_project_id"]:
        raise ProbeBlocked("GCP_CREDENTIAL_SCOPE_MISMATCH")
    return aws, gcp, gcp_key, azure


def _aws_session(credentials: dict[str, Any]) -> boto3.Session:
    values: dict[str, Any] = {
        "aws_access_key_id": credentials["aws_access_key_id"],
        "aws_secret_access_key": credentials["aws_secret_access_key"],
        "region_name": credentials["aws_region"],
    }
    if credentials.get("aws_session_token"):
        values["aws_session_token"] = credentials["aws_session_token"]
    return boto3.Session(**values)


def _aws_regional_sts(session: boto3.Session, region: str) -> Any:
    return session.client(
        "sts",
        region_name=region,
        endpoint_url=f"https://sts.{region}.amazonaws.com",
    )


def _aws_outbound_issuer(iam: Any) -> str:
    response = iam.get_outbound_web_identity_federation_info()
    if response.get("JwtVendingEnabled") is not True:
        raise ProbeBlocked("AWS_OUTBOUND_IDENTITY_NOT_ENABLED")
    issuer = str(response.get("IssuerIdentifier") or "")
    parsed = urlparse(issuer)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ProbeBlocked("AWS_OUTBOUND_ISSUER_INVALID")
    return issuer.rstrip("/")


def _aws_role_subject(role_arn: str, role_name: str) -> str:
    if not re.fullmatch(
        rf"arn:aws:iam::\d{{12}}:role/{re.escape(role_name)}",
        role_arn,
    ):
        raise ProbeBlocked("AWS_SOURCE_ROLE_ARN_INVALID")
    return role_arn


def _aws_to_gcp_provider_body(account_id: str, role_name: str) -> dict[str, Any]:
    if not re.fullmatch(r"\d{12}", account_id):
        raise ProbeBlocked("AWS_ACCOUNT_ID_INVALID")
    if role_name != AWS_TO_GCP_NAMES["aws_role"]:
        raise ProbeBlocked("AWS_SOURCE_ROLE_NAME_INVALID")
    return {
        "displayName": "Twin2MultiCloud AWS to GCP probe",
        "description": "Ephemeral identity-only thesis evaluation probe",
        "disabled": False,
        "attributeMapping": {
            "google.subject": "assertion.arn",
            "attribute.aws_role": (
                "assertion.arn.extract('assumed-role/{role_name}/')"
            ),
        },
        "attributeCondition": f"attribute.aws_role == '{role_name}'",
        "aws": {"accountId": account_id},
    }


def _aws_to_gcp_principal_set(
    project_number: str,
    pool_id: str,
    role_name: str,
) -> str:
    if not re.fullmatch(r"\d+", project_number):
        raise ProbeBlocked("GCP_PROJECT_NUMBER_INVALID")
    if pool_id != AWS_TO_GCP_NAMES["gcp_workload_identity_pool"]:
        raise ProbeBlocked("GCP_WORKLOAD_IDENTITY_POOL_NAME_INVALID")
    if role_name != AWS_TO_GCP_NAMES["aws_role"]:
        raise ProbeBlocked("AWS_SOURCE_ROLE_NAME_INVALID")
    return (
        "principalSet://iam.googleapis.com/"
        f"projects/{project_number}/locations/global/"
        f"workloadIdentityPools/{pool_id}/attribute.aws_role/{role_name}"
    )


def _jwt_claims(token: str) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) != 3:
        raise ProbeBlocked("IDENTITY_TOKEN_INVALID")
    try:
        payload = parts[1] + "=" * (-len(parts[1]) % 4)
        value = json.loads(base64.urlsafe_b64decode(payload).decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProbeBlocked("IDENTITY_TOKEN_INVALID") from exc
    if not isinstance(value, dict):
        raise ProbeBlocked("IDENTITY_TOKEN_INVALID")
    return value


def _gcp_credentials(key: dict[str, Any]) -> service_account.Credentials:
    return service_account.Credentials.from_service_account_info(
        key,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )


def _azure_credentials(values: dict[str, Any]) -> ClientSecretCredential:
    return ClientSecretCredential(
        tenant_id=values["azure_tenant_id"],
        client_id=values["azure_client_id"],
        client_secret=values["azure_client_secret"],
    )


def _gcp_execute(request: Any) -> dict[str, Any]:
    value = request.execute(num_retries=2)
    return value if isinstance(value, dict) else {}


def _expect_aws_role_absent(iam: Any, role_name: str) -> None:
    try:
        iam.get_role(RoleName=role_name)
    except ClientError as exc:
        if str(exc.response.get("Error", {}).get("Code")) == "NoSuchEntity":
            return
        raise
    raise ProbeBlocked("PREEXISTING_RESOURCE")


def _expect_gcp_service_account_absent(
    iam: Any,
    project_id: str,
    email: str,
) -> None:
    request = iam.projects().serviceAccounts().list(
        name=f"projects/{project_id}",
        pageSize=100,
    )
    while request is not None:
        page = _gcp_execute(request)
        if any(item.get("email") == email for item in page.get("accounts", [])):
            raise ProbeBlocked("PREEXISTING_RESOURCE")
        request = iam.projects().serviceAccounts().list_next(request, page)


def _expect_gcp_workload_identity_pool_absent(
    pools: Any,
    parent: str,
    pool_id: str,
) -> None:
    request = pools.list(parent=parent, pageSize=100, showDeleted=False)
    while request is not None:
        page = _gcp_execute(request)
        if any(
            str(item.get("name") or "").rsplit("/", 1)[-1] == pool_id
            for item in page.get("workloadIdentityPools", [])
        ):
            raise ProbeBlocked("PREEXISTING_RESOURCE")
        request = pools.list_next(request, page)


def _wait_for_gcp_operation(
    operations: Any,
    operation: dict[str, Any],
    started_monotonic: float,
) -> dict[str, Any]:
    name = str(operation.get("name") or "")
    if not name:
        raise ProbeBlocked("GCP_OPERATION_NAME_UNAVAILABLE")
    current = operation
    for attempt in range(60):
        _assert_deadline(started_monotonic)
        if current.get("done") is True:
            if current.get("error"):
                raise ProbeBlocked("GCP_OPERATION_FAILED")
            response = current.get("response") or {}
            return response if isinstance(response, dict) else {}
        if attempt + 1 < 60:
            time.sleep(2)
        current = _gcp_execute(operations.get(name=name))
    raise ProbeBlocked("GCP_OPERATION_TIMEOUT")


def _add_service_account_workload_identity_user(
    iam: Any,
    service_account_name: str,
    member: str,
) -> None:
    policy = _gcp_execute(
        iam.projects().serviceAccounts().getIamPolicy(resource=service_account_name)
    )
    bindings = list(policy.get("bindings", []))
    role = "roles/iam.workloadIdentityUser"
    binding = next(
        (item for item in bindings if item.get("role") == role),
        None,
    )
    if binding is None:
        binding = {"role": role, "members": []}
        bindings.append(binding)
    members = list(binding.get("members", []))
    if member not in members:
        members.append(member)
    binding["members"] = sorted(members)
    policy["bindings"] = bindings
    _gcp_execute(
        iam.projects().serviceAccounts().setIamPolicy(
            resource=service_account_name,
            body={"policy": policy},
        )
    )


def _remove_service_account_workload_identity_user(
    iam: Any,
    service_account_name: str,
    member: str,
) -> None:
    try:
        policy = _gcp_execute(
            iam.projects().serviceAccounts().getIamPolicy(
                resource=service_account_name
            )
        )
    except HttpError as exc:
        if getattr(exc.resp, "status", None) == 404:
            return
        raise
    bindings = []
    for item in policy.get("bindings", []):
        if item.get("role") != "roles/iam.workloadIdentityUser":
            bindings.append(item)
            continue
        remaining = [value for value in item.get("members", []) if value != member]
        if remaining:
            bindings.append({**item, "members": remaining})
    policy["bindings"] = bindings
    _gcp_execute(
        iam.projects().serviceAccounts().setIamPolicy(
            resource=service_account_name,
            body={"policy": policy},
        )
    )


def _add_service_account_oidc_token_creator(
    iam: Any,
    service_account_name: str,
    member: str,
) -> None:
    policy = _gcp_execute(
        iam.projects().serviceAccounts().getIamPolicy(resource=service_account_name)
    )
    bindings = list(policy.get("bindings", []))
    binding = next(
        (
            item
            for item in bindings
            if item.get("role")
            == "roles/iam.serviceAccountOpenIdTokenCreator"
        ),
        None,
    )
    if binding is None:
        binding = {
            "role": "roles/iam.serviceAccountOpenIdTokenCreator",
            "members": [],
        }
        bindings.append(binding)
    members = list(binding.get("members", []))
    if member not in members:
        members.append(member)
    binding["members"] = sorted(members)
    policy["bindings"] = bindings
    _gcp_execute(
        iam.projects().serviceAccounts().setIamPolicy(
            resource=service_account_name,
            body={"policy": policy},
        )
    )


def _remove_service_account_oidc_token_creator(
    iam: Any,
    service_account_name: str,
    member: str,
) -> None:
    try:
        policy = _gcp_execute(
            iam.projects().serviceAccounts().getIamPolicy(resource=service_account_name)
        )
    except HttpError as exc:
        if getattr(exc.resp, "status", None) == 404:
            return
        raise
    bindings = []
    for item in policy.get("bindings", []):
        if (
            item.get("role")
            != "roles/iam.serviceAccountOpenIdTokenCreator"
        ):
            bindings.append(item)
            continue
        remaining = [value for value in item.get("members", []) if value != member]
        if remaining:
            bindings.append({**item, "members": remaining})
    policy["bindings"] = bindings
    _gcp_execute(
        iam.projects().serviceAccounts().setIamPolicy(
            resource=service_account_name,
            body={"policy": policy},
        )
    )


def _wait_for_service_account_token_permission(
    iam: Any,
    service_account_name: str,
    started_monotonic: float,
) -> None:
    permission = "iam.serviceAccounts.getOpenIdToken"
    for attempt in range(GCP_PERMISSION_PROPAGATION_ATTEMPTS):
        _assert_deadline(started_monotonic)
        try:
            result = _gcp_execute(
                iam.projects().serviceAccounts().testIamPermissions(
                    resource=service_account_name,
                    body={"permissions": [permission]},
                )
            )
            if permission in result.get("permissions", []):
                return
        except HttpError as exc:
            if getattr(exc.resp, "status", None) != 403:
                raise
        if attempt + 1 < GCP_PERMISSION_PROPAGATION_ATTEMPTS:
            time.sleep(GCP_PERMISSION_PROPAGATION_DELAY_SECONDS)
    raise ProbeBlocked("GCP_TOKEN_CREATOR_PERMISSION_NOT_EFFECTIVE")


def _generate_gcp_id_token(
    iam_credentials: Any,
    service_account_email: str,
    audience: str,
    started_monotonic: float,
) -> str:
    last_error: HttpError | None = None
    for attempt in range(GCP_PERMISSION_PROPAGATION_ATTEMPTS):
        _assert_deadline(started_monotonic)
        try:
            result = _gcp_execute(
                iam_credentials.projects().serviceAccounts().generateIdToken(
                    name=f"projects/-/serviceAccounts/{service_account_email}",
                    body={"audience": audience, "includeEmail": False},
                )
            )
            token = result.get("token")
            if not isinstance(token, str) or token.count(".") != 2:
                raise ProbeBlocked("GCP_ID_TOKEN_UNAVAILABLE")
            return token
        except HttpError as exc:
            if getattr(exc.resp, "status", None) != 403:
                raise
            last_error = exc
        if attempt + 1 < GCP_PERMISSION_PROPAGATION_ATTEMPTS:
            time.sleep(GCP_PERMISSION_PROPAGATION_DELAY_SECONDS)
    if last_error is not None:
        raise last_error
    raise ProbeBlocked("GCP_ID_TOKEN_UNAVAILABLE")


def _delete_aws_role(iam: Any, role_name: str) -> None:
    try:
        for policy_name in iam.list_role_policies(RoleName=role_name).get(
            "PolicyNames", []
        ):
            iam.delete_role_policy(RoleName=role_name, PolicyName=policy_name)
        iam.delete_role(RoleName=role_name)
    except ClientError as exc:
        if str(exc.response.get("Error", {}).get("Code")) != "NoSuchEntity":
            raise


def _delete_gcp_service_account(iam: Any, service_account_name: str) -> None:
    try:
        _gcp_execute(
            iam.projects().serviceAccounts().delete(name=service_account_name)
        )
    except HttpError as exc:
        if getattr(exc.resp, "status", None) != 404:
            raise


def _expect_azure_resource_group_absent(
    resource_client: ResourceManagementClient,
    resource_group_name: str,
) -> None:
    if resource_client.resource_groups.check_existence(resource_group_name):
        raise ProbeBlocked("PREEXISTING_RESOURCE")


def _expect_azure_service_principal_absent(
    credential: ClientSecretCredential,
    principal_id: str,
) -> None:
    token = credential.get_token("https://graph.microsoft.com/.default").token
    response = requests.get(
        f"https://graph.microsoft.com/v1.0/servicePrincipals/{principal_id}",
        headers={"Authorization": f"Bearer {token}"},
        params={"$select": "id"},
        timeout=15,
    )
    if response.status_code == 404:
        return
    if response.status_code == 200:
        raise ProbeBlocked("PREEXISTING_RESOURCE")
    raise ProbeBlocked(f"AZURE_GRAPH_INVENTORY_HTTP_{response.status_code}")


def _assert_no_sensitive_values(
    record: dict[str, Any],
    credentials: tuple[dict[str, Any], dict[str, Any], dict[str, Any]],
) -> None:
    serialized = _canonical_json(record)
    for source in credentials:
        for key, value in source.items():
            if key in SENSITIVE_CREDENTIAL_KEYS and isinstance(value, str):
                if len(value) >= 4 and value in serialized:
                    raise ValueError(f"sensitive field escaped redaction: {key}")


def _run_gcp_to_aws(
    aws: dict[str, Any],
    gcp: dict[str, Any],
    gcp_key: dict[str, Any],
    *,
    now: Callable[[], str] = _utc_now,
) -> dict[str, Any]:
    if aws["aws_region"] != AWS_REGION:
        raise ProbeBlocked("AWS_REGION_OUTSIDE_APPROVED_SCOPE")

    started_monotonic = time.monotonic()
    started_at = now()
    probe = "federation-gcp-to-aws"
    role_name = GCP_TO_AWS_NAMES["aws_role"]
    account_id = GCP_TO_AWS_NAMES["gcp_service_account"]
    service_account_email = f"{account_id}@{gcp['gcp_project_id']}.iam.gserviceaccount.com"
    service_account_name = f"projects/{gcp['gcp_project_id']}/serviceAccounts/{service_account_email}"
    token_creator_member = f"serviceAccount:{gcp_key['client_email']}"
    audience = f"api://{uuid.uuid5(uuid.NAMESPACE_URL, probe + ':' + APPROVED_RUN_ID)}"

    session = _aws_session(aws)
    iam_aws = session.client("iam")
    sts = session.client(
        "sts",
        region_name=aws["aws_region"],
        endpoint_url=f"https://sts.{aws['aws_region']}.amazonaws.com",
    )
    google_credentials = _gcp_credentials(gcp_key)
    iam_gcp = build_google_api(
        "iam", "v1", credentials=google_credentials, cache_discovery=False
    )
    iam_credentials = build_google_api(
        "iamcredentials", "v1", credentials=google_credentials, cache_discovery=False
    )

    role_created = False
    account_created = False
    binding_created = False
    exchange_completed_at: str | None = None
    exchange_error_code: str | None = None
    exchange_stage = "preflight"
    result_code = "PROBE_BLOCKED"
    cleanup_errors: list[str] = []
    residual_errors: list[str] = []

    try:
        _assert_deadline(started_monotonic)
        _expect_aws_role_absent(iam_aws, role_name)
        _expect_gcp_service_account_absent(
            iam_gcp,
            gcp["gcp_project_id"],
            service_account_email,
        )

        exchange_stage = "provision_gcp_identity"
        created = _gcp_execute(
            iam_gcp.projects().serviceAccounts().create(
                name=f"projects/{gcp['gcp_project_id']}",
                body={
                    "accountId": account_id,
                    "serviceAccount": {
                        "displayName": "Twin2MultiCloud Phase 8 GCP to AWS probe",
                        "description": "Ephemeral identity-only thesis evaluation probe",
                    },
                },
            )
        )
        account_created = True
        unique_id = str(created.get("uniqueId") or "")
        if not unique_id.isdigit():
            raise ProbeBlocked("GCP_SERVICE_ACCOUNT_ID_UNAVAILABLE")
        _add_service_account_oidc_token_creator(
            iam_gcp, service_account_name, token_creator_member
        )
        binding_created = True
        exchange_stage = "await_gcp_token_permission"
        _wait_for_service_account_token_permission(
            iam_gcp,
            service_account_name,
            started_monotonic,
        )

        exchange_stage = "provision_aws_trust"
        trust_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": "sts:AssumeRoleWithWebIdentity",
                    "Principal": {"Federated": "accounts.google.com"},
                    "Condition": {
                        "StringEquals": {
                            "accounts.google.com:aud": unique_id,
                            "accounts.google.com:oaud": audience,
                            "accounts.google.com:sub": unique_id,
                        }
                    },
                }
            ],
        }
        iam_aws.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=_canonical_json(trust_policy),
            Description="Ephemeral identity-only thesis evaluation probe",
            MaxSessionDuration=3600,
            Tags=[
                {"Key": "Twin2MultiCloudPhase", "Value": "8"},
                {"Key": "Twin2MultiCloudRun", "Value": APPROVED_RUN_ID},
            ],
        )
        role_created = True
        role_arn = str(iam_aws.get_role(RoleName=role_name)["Role"]["Arn"])

        exchange_stage = "issue_gcp_id_token"
        token = _generate_gcp_id_token(
            iam_credentials,
            service_account_email,
            audience,
            started_monotonic,
        )

        exchange_stage = "exchange_gcp_token_for_aws_session"
        last_error: Exception | None = None
        for attempt in range(AWS_PROPAGATION_ATTEMPTS):
            _assert_deadline(started_monotonic)
            try:
                assumed = sts.assume_role_with_web_identity(
                    RoleArn=role_arn,
                    RoleSessionName="t2mc-p8-gcp-aws",
                    WebIdentityToken=token,
                    DurationSeconds=900,
                )
                temporary = assumed.get("Credentials") or {}
                probe_session = boto3.Session(
                    aws_access_key_id=temporary["AccessKeyId"],
                    aws_secret_access_key=temporary["SecretAccessKey"],
                    aws_session_token=temporary["SessionToken"],
                    region_name=aws["aws_region"],
                )
                probe_session.client(
                    "sts",
                    region_name=aws["aws_region"],
                    endpoint_url=f"https://sts.{aws['aws_region']}.amazonaws.com",
                ).get_caller_identity()
                last_error = None
                break
            except ClientError as exc:
                last_error = exc
                if attempt + 1 < AWS_PROPAGATION_ATTEMPTS:
                    time.sleep(AWS_PROPAGATION_DELAY_SECONDS)
        if last_error is not None:
            raise last_error
        exchange_completed_at = now()
        exchange_stage = "completed"
        result_code = "PROBE_PASSED"
    except Exception as exc:  # provider boundary, redacted below
        exchange_error_code = _safe_error_code(exc)
        result_code = f"PROBE_BLOCKED_{exchange_error_code}"
    finally:
        if role_created:
            try:
                _delete_aws_role(iam_aws, role_name)
            except Exception as exc:
                cleanup_errors.append(_safe_error_code(exc))
        if binding_created:
            try:
                _remove_service_account_oidc_token_creator(
                    iam_gcp, service_account_name, token_creator_member
                )
            except Exception as exc:
                cleanup_errors.append(_safe_error_code(exc))
        if account_created:
            try:
                _delete_gcp_service_account(iam_gcp, service_account_name)
            except Exception as exc:
                cleanup_errors.append(_safe_error_code(exc))

        for attempt in range(6):
            residual_errors = []
            try:
                _expect_aws_role_absent(iam_aws, role_name)
            except Exception as exc:
                residual_errors.append(_safe_error_code(exc))
            try:
                _expect_gcp_service_account_absent(
                    iam_gcp,
                    gcp["gcp_project_id"],
                    service_account_email,
                )
            except Exception as exc:
                residual_errors.append(_safe_error_code(exc))
            if not residual_errors or attempt == 5:
                break
            time.sleep(5)

    cleanup_completed_at = now()
    cleanup_status = "clean" if not cleanup_errors else "failed"
    residual_status = (
        "accepted_gcp_soft_delete_tombstone_only"
        if account_created and not residual_errors
        else "clean"
        if not residual_errors
        else "active_residual_detected"
    )
    if cleanup_errors or residual_errors:
        result_code = "PROBE_BLOCKED_CLEANUP_OR_RESIDUAL_FAILED"
    record: dict[str, Any] = {
        "schema_version": "six-layer-directed-federation-probe-result.v1",
        "run_id": APPROVED_RUN_ID,
        "plan_record_digest": APPROVED_PLAN_DIGEST,
        "probe_id": probe,
        "started_at": started_at,
        "exchange_completed_at": exchange_completed_at,
        "exchange_status": "passed" if exchange_completed_at else "blocked",
        "exchange_stage": exchange_stage,
        "exchange_error_code": exchange_error_code,
        "cleanup_completed_at": cleanup_completed_at,
        "result_code": result_code,
        "cleanup_status": cleanup_status,
        "residual_status": residual_status,
        "direct_cost_cap_usd": "0.000000",
        "credential_values_included": False,
        "provider_scope_values_included": False,
        "resource_identifiers_included": False,
    }
    record["record_digest"] = _digest(record)
    return record


def _run_gcp_to_azure(
    gcp: dict[str, Any],
    gcp_key: dict[str, Any],
    azure: dict[str, Any],
    *,
    now: Callable[[], str] = _utc_now,
) -> dict[str, Any]:
    started_monotonic = time.monotonic()
    started_at = now()
    probe = "federation-gcp-to-azure"
    account_id = GCP_TO_AZURE_NAMES["gcp_service_account"]
    service_account_email = (
        f"{account_id}@{gcp['gcp_project_id']}.iam.gserviceaccount.com"
    )
    service_account_name = (
        f"projects/{gcp['gcp_project_id']}/serviceAccounts/"
        f"{service_account_email}"
    )
    token_creator_member = f"serviceAccount:{gcp_key['client_email']}"
    resource_group_name = GCP_TO_AZURE_NAMES["azure_resource_group"]
    identity_name = GCP_TO_AZURE_NAMES["azure_managed_identity"]
    federated_credential_name = GCP_TO_AZURE_NAMES[
        "azure_federated_credential"
    ]
    subscription_id = azure["azure_subscription_id"]
    scope = f"/subscriptions/{subscription_id}/resourceGroups/{resource_group_name}"
    role_definition_id = (
        f"/subscriptions/{subscription_id}/providers/Microsoft.Authorization/"
        f"roleDefinitions/{AZURE_READER_ROLE_DEFINITION_ID}"
    )

    google_credentials = _gcp_credentials(gcp_key)
    iam_gcp = build_google_api(
        "iam", "v1", credentials=google_credentials, cache_discovery=False
    )
    iam_credentials = build_google_api(
        "iamcredentials", "v1", credentials=google_credentials, cache_discovery=False
    )
    azure_credential = _azure_credentials(azure)
    resource_client = ResourceManagementClient(azure_credential, subscription_id)
    identity_client = ManagedServiceIdentityClient(azure_credential, subscription_id)
    authorization_client = AuthorizationManagementClient(
        azure_credential,
        subscription_id,
    )

    account_created = False
    binding_created = False
    resource_group_created = False
    identity_created = False
    federated_credential_created = False
    role_assignment_created = False
    principal_id: str | None = None
    role_assignment_name: str | None = None
    exchange_completed_at: str | None = None
    exchange_error_code: str | None = None
    exchange_stage = "preflight"
    result_code = "PROBE_BLOCKED"
    cleanup_errors: list[str] = []
    residual_errors: list[str] = []

    try:
        _assert_deadline(started_monotonic)
        _expect_gcp_service_account_absent(
            iam_gcp,
            gcp["gcp_project_id"],
            service_account_email,
        )
        _expect_azure_resource_group_absent(resource_client, resource_group_name)

        exchange_stage = "provision_gcp_identity"
        created = _gcp_execute(
            iam_gcp.projects().serviceAccounts().create(
                name=f"projects/{gcp['gcp_project_id']}",
                body={
                    "accountId": account_id,
                    "serviceAccount": {
                        "displayName": "Twin2MultiCloud Phase 8 GCP to Azure probe",
                        "description": "Ephemeral identity-only thesis evaluation probe",
                    },
                },
            )
        )
        account_created = True
        unique_id = str(created.get("uniqueId") or "")
        if not unique_id.isdigit():
            raise ProbeBlocked("GCP_SERVICE_ACCOUNT_ID_UNAVAILABLE")
        _add_service_account_oidc_token_creator(
            iam_gcp,
            service_account_name,
            token_creator_member,
        )
        binding_created = True
        exchange_stage = "await_gcp_token_permission"
        _wait_for_service_account_token_permission(
            iam_gcp,
            service_account_name,
            started_monotonic,
        )

        exchange_stage = "create_azure_resource_group"
        resource_client.resource_groups.create_or_update(
            resource_group_name,
            {
                "location": AZURE_REGION,
                "tags": {
                    "Twin2MultiCloudPhase": "8",
                    "Twin2MultiCloudRun": APPROVED_RUN_ID,
                },
            },
        )
        resource_group_created = True
        exchange_stage = "create_azure_managed_identity"
        identity = identity_client.user_assigned_identities.create_or_update(
            resource_group_name,
            identity_name,
            {
                "location": AZURE_REGION,
                "tags": {
                    "Twin2MultiCloudPhase": "8",
                    "Twin2MultiCloudRun": APPROVED_RUN_ID,
                },
            },
        )
        identity_created = True
        principal_id = str(identity.principal_id or "")
        client_id = str(identity.client_id or "")
        if not principal_id or not client_id:
            raise ProbeBlocked("AZURE_MANAGED_IDENTITY_IDS_UNAVAILABLE")
        exchange_stage = "create_azure_federated_credential"
        identity_client.federated_identity_credentials.create_or_update(
            resource_group_name,
            identity_name,
            federated_credential_name,
            {
                "issuer": "https://accounts.google.com",
                "subject": unique_id,
                "audiences": [AZURE_FEDERATION_AUDIENCE],
            },
        )
        federated_credential_created = True
        role_assignment_name = str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"{scope}:{principal_id}:{AZURE_READER_ROLE_DEFINITION_ID}",
            )
        )
        exchange_stage = "create_azure_reader_assignment"
        authorization_client.role_assignments.create(
            scope,
            role_assignment_name,
            {
                "role_definition_id": role_definition_id,
                "principal_id": principal_id,
                "principal_type": "ServicePrincipal",
            },
        )
        role_assignment_created = True

        exchange_stage = "issue_gcp_id_token"
        token = _generate_gcp_id_token(
            iam_credentials,
            service_account_email,
            AZURE_FEDERATION_AUDIENCE,
            started_monotonic,
        )

        exchange_stage = "exchange_gcp_token_for_azure_session"
        last_error: Exception | None = None
        for attempt in range(AZURE_PROPAGATION_ATTEMPTS):
            _assert_deadline(started_monotonic)
            federated_credential = ClientAssertionCredential(
                tenant_id=azure["azure_tenant_id"],
                client_id=client_id,
                func=lambda: token,
            )
            try:
                federated_credential.get_token(
                    "https://management.azure.com/.default"
                )
                ManagedServiceIdentityClient(
                    federated_credential,
                    subscription_id,
                ).user_assigned_identities.get(
                    resource_group_name,
                    identity_name,
                )
                last_error = None
                break
            except (ClientAuthenticationError, HttpResponseError) as exc:
                last_error = exc
                if attempt + 1 < AZURE_PROPAGATION_ATTEMPTS:
                    time.sleep(AZURE_PROPAGATION_DELAY_SECONDS)
            finally:
                federated_credential.close()
        if last_error is not None:
            raise last_error
        exchange_completed_at = now()
        exchange_stage = "completed"
        result_code = "PROBE_PASSED"
    except Exception as exc:  # provider boundary, redacted below
        exchange_error_code = _safe_error_code(exc)
        result_code = f"PROBE_BLOCKED_{exchange_error_code}"
    finally:
        if role_assignment_created and role_assignment_name:
            try:
                authorization_client.role_assignments.delete(
                    scope,
                    role_assignment_name,
                )
            except Exception as exc:
                cleanup_errors.append(_safe_error_code(exc))
        if federated_credential_created:
            try:
                identity_client.federated_identity_credentials.delete(
                    resource_group_name,
                    identity_name,
                    federated_credential_name,
                )
            except Exception as exc:
                cleanup_errors.append(_safe_error_code(exc))
        if identity_created:
            try:
                identity_client.user_assigned_identities.delete(
                    resource_group_name,
                    identity_name,
                )
            except Exception as exc:
                cleanup_errors.append(_safe_error_code(exc))
        if resource_group_created:
            try:
                resource_client.resource_groups.begin_delete(
                    resource_group_name
                ).result(timeout=180)
            except Exception as exc:
                cleanup_errors.append(_safe_error_code(exc))
        if binding_created:
            try:
                _remove_service_account_oidc_token_creator(
                    iam_gcp,
                    service_account_name,
                    token_creator_member,
                )
            except Exception as exc:
                cleanup_errors.append(_safe_error_code(exc))
        if account_created:
            try:
                _delete_gcp_service_account(iam_gcp, service_account_name)
            except Exception as exc:
                cleanup_errors.append(_safe_error_code(exc))

        for attempt in range(12):
            residual_errors = []
            try:
                _expect_azure_resource_group_absent(
                    resource_client,
                    resource_group_name,
                )
            except Exception as exc:
                residual_errors.append(_safe_error_code(exc))
            if principal_id:
                try:
                    _expect_azure_service_principal_absent(
                        azure_credential,
                        principal_id,
                    )
                except Exception as exc:
                    residual_errors.append(_safe_error_code(exc))
            try:
                _expect_gcp_service_account_absent(
                    iam_gcp,
                    gcp["gcp_project_id"],
                    service_account_email,
                )
            except Exception as exc:
                residual_errors.append(_safe_error_code(exc))
            if not residual_errors or attempt == 11:
                break
            time.sleep(5)

    azure_credential.close()
    cleanup_completed_at = now()
    cleanup_status = "clean" if not cleanup_errors else "failed"
    residual_status = (
        "accepted_gcp_soft_delete_tombstone_only"
        if account_created and not residual_errors
        else "clean"
        if not residual_errors
        else "active_residual_detected"
    )
    if cleanup_errors or residual_errors:
        result_code = "PROBE_BLOCKED_CLEANUP_OR_RESIDUAL_FAILED"
    record: dict[str, Any] = {
        "schema_version": "six-layer-directed-federation-probe-result.v1",
        "run_id": APPROVED_RUN_ID,
        "plan_record_digest": APPROVED_PLAN_DIGEST,
        "probe_id": probe,
        "started_at": started_at,
        "exchange_completed_at": exchange_completed_at,
        "exchange_status": "passed" if exchange_completed_at else "blocked",
        "exchange_stage": exchange_stage,
        "exchange_error_code": exchange_error_code,
        "cleanup_completed_at": cleanup_completed_at,
        "result_code": result_code,
        "cleanup_status": cleanup_status,
        "residual_status": residual_status,
        "direct_cost_cap_usd": "0.000000",
        "credential_values_included": False,
        "provider_scope_values_included": False,
        "resource_identifiers_included": False,
    }
    record["record_digest"] = _digest(record)
    return record


def _run_aws_to_azure(
    aws: dict[str, Any],
    azure: dict[str, Any],
    *,
    now: Callable[[], str] = _utc_now,
) -> dict[str, Any]:
    if aws["aws_region"] != AWS_REGION:
        raise ProbeBlocked("AWS_REGION_OUTSIDE_APPROVED_SCOPE")

    started_monotonic = time.monotonic()
    started_at = now()
    probe = "federation-aws-to-azure"
    role_name = AWS_TO_AZURE_NAMES["aws_role"]
    inline_policy_name = AWS_TO_AZURE_NAMES["aws_inline_policy"]
    resource_group_name = AWS_TO_AZURE_NAMES["azure_resource_group"]
    identity_name = AWS_TO_AZURE_NAMES["azure_managed_identity"]
    federated_credential_name = AWS_TO_AZURE_NAMES[
        "azure_federated_credential"
    ]
    source_session_name = "t2mc-p8-aws-azure"
    subscription_id = azure["azure_subscription_id"]
    scope = f"/subscriptions/{subscription_id}/resourceGroups/{resource_group_name}"
    role_definition_id = (
        f"/subscriptions/{subscription_id}/providers/Microsoft.Authorization/"
        f"roleDefinitions/{AZURE_READER_ROLE_DEFINITION_ID}"
    )

    aws_session = _aws_session(aws)
    iam_aws = aws_session.client("iam")
    sts_aws = _aws_regional_sts(aws_session, aws["aws_region"])
    azure_credential = _azure_credentials(azure)
    resource_client = ResourceManagementClient(azure_credential, subscription_id)
    identity_client = ManagedServiceIdentityClient(azure_credential, subscription_id)
    authorization_client = AuthorizationManagementClient(
        azure_credential,
        subscription_id,
    )

    role_created = False
    resource_group_created = False
    identity_created = False
    federated_credential_created = False
    role_assignment_created = False
    principal_id: str | None = None
    role_assignment_name: str | None = None
    exchange_completed_at: str | None = None
    exchange_error_code: str | None = None
    exchange_stage = "preflight"
    result_code = "PROBE_BLOCKED"
    cleanup_errors: list[str] = []
    residual_errors: list[str] = []

    try:
        _assert_deadline(started_monotonic)
        _expect_aws_role_absent(iam_aws, role_name)
        _expect_azure_resource_group_absent(resource_client, resource_group_name)
        issuer = _aws_outbound_issuer(iam_aws)
        caller = sts_aws.get_caller_identity()
        caller_arn = str(caller.get("Arn") or "")
        if ":iam::" not in caller_arn or ":user/" not in caller_arn:
            raise ProbeBlocked("AWS_DEPLOYMENT_PRINCIPAL_NOT_IAM_USER")

        exchange_stage = "create_aws_source_role"
        trust_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": "sts:AssumeRole",
                    "Principal": {"AWS": caller_arn},
                }
            ],
        }
        iam_aws.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=_canonical_json(trust_policy),
            Description="Ephemeral identity-only thesis evaluation probe",
            MaxSessionDuration=3600,
            Tags=[
                {"Key": "Twin2MultiCloudPhase", "Value": "8"},
                {"Key": "Twin2MultiCloudRun", "Value": APPROVED_RUN_ID},
            ],
        )
        role_created = True
        token_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": "sts:GetWebIdentityToken",
                    "Resource": "*",
                    "Condition": {
                        "ForAllValues:StringEquals": {
                            "sts:IdentityTokenAudience": AZURE_FEDERATION_AUDIENCE,
                        },
                        "NumericLessThanEquals": {
                            "sts:DurationSeconds": 300,
                        },
                    },
                }
            ],
        }
        iam_aws.put_role_policy(
            RoleName=role_name,
            PolicyName=inline_policy_name,
            PolicyDocument=_canonical_json(token_policy),
        )
        role_arn = _aws_role_subject(
            str(iam_aws.get_role(RoleName=role_name)["Role"]["Arn"]),
            role_name,
        )

        exchange_stage = "assume_aws_source_role"
        assumed: dict[str, Any] | None = None
        last_aws_error: ClientError | None = None
        for attempt in range(AWS_PROPAGATION_ATTEMPTS):
            _assert_deadline(started_monotonic)
            try:
                assumed = sts_aws.assume_role(
                    RoleArn=role_arn,
                    RoleSessionName=source_session_name,
                    DurationSeconds=900,
                )
                last_aws_error = None
                break
            except ClientError as exc:
                last_aws_error = exc
                if attempt + 1 < AWS_PROPAGATION_ATTEMPTS:
                    time.sleep(AWS_PROPAGATION_DELAY_SECONDS)
        if last_aws_error is not None:
            raise last_aws_error
        if assumed is None:
            raise ProbeBlocked("AWS_SOURCE_SESSION_UNAVAILABLE")
        temporary = assumed.get("Credentials") or {}
        source_session = boto3.Session(
            aws_access_key_id=temporary["AccessKeyId"],
            aws_secret_access_key=temporary["SecretAccessKey"],
            aws_session_token=temporary["SessionToken"],
            region_name=aws["aws_region"],
        )

        exchange_stage = "issue_aws_web_identity_token"
        token_response = _aws_regional_sts(
            source_session,
            aws["aws_region"],
        ).get_web_identity_token(
            Audience=[AZURE_FEDERATION_AUDIENCE],
            DurationSeconds=300,
            SigningAlgorithm="RS256",
        )
        token = token_response.get("WebIdentityToken")
        if not isinstance(token, str):
            raise ProbeBlocked("AWS_IDENTITY_TOKEN_UNAVAILABLE")
        claims = _jwt_claims(token)
        expected_subject = role_arn
        audience = claims.get("aud")
        audience_values = audience if isinstance(audience, list) else [audience]
        if (
            claims.get("sub") != expected_subject
            or str(claims.get("iss") or "").rstrip("/") != issuer
            or AZURE_FEDERATION_AUDIENCE not in audience_values
        ):
            raise ProbeBlocked("AWS_IDENTITY_TOKEN_CLAIMS_INVALID")

        exchange_stage = "create_azure_resource_group"
        resource_client.resource_groups.create_or_update(
            resource_group_name,
            {
                "location": AZURE_REGION,
                "tags": {
                    "Twin2MultiCloudPhase": "8",
                    "Twin2MultiCloudRun": APPROVED_RUN_ID,
                },
            },
        )
        resource_group_created = True
        exchange_stage = "create_azure_managed_identity"
        identity = identity_client.user_assigned_identities.create_or_update(
            resource_group_name,
            identity_name,
            {
                "location": AZURE_REGION,
                "tags": {
                    "Twin2MultiCloudPhase": "8",
                    "Twin2MultiCloudRun": APPROVED_RUN_ID,
                },
            },
        )
        identity_created = True
        principal_id = str(identity.principal_id or "")
        client_id = str(identity.client_id or "")
        if not principal_id or not client_id:
            raise ProbeBlocked("AZURE_MANAGED_IDENTITY_IDS_UNAVAILABLE")
        exchange_stage = "create_azure_federated_credential"
        identity_client.federated_identity_credentials.create_or_update(
            resource_group_name,
            identity_name,
            federated_credential_name,
            {
                "issuer": issuer,
                "subject": expected_subject,
                "audiences": [AZURE_FEDERATION_AUDIENCE],
            },
        )
        federated_credential_created = True
        role_assignment_name = str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"{scope}:{principal_id}:{AZURE_READER_ROLE_DEFINITION_ID}",
            )
        )
        exchange_stage = "create_azure_reader_assignment"
        authorization_client.role_assignments.create(
            scope,
            role_assignment_name,
            {
                "role_definition_id": role_definition_id,
                "principal_id": principal_id,
                "principal_type": "ServicePrincipal",
            },
        )
        role_assignment_created = True

        exchange_stage = "exchange_aws_token_for_azure_session"
        last_azure_error: Exception | None = None
        for attempt in range(AZURE_PROPAGATION_ATTEMPTS):
            _assert_deadline(started_monotonic)
            federated_credential = ClientAssertionCredential(
                tenant_id=azure["azure_tenant_id"],
                client_id=client_id,
                func=lambda: token,
            )
            try:
                federated_credential.get_token(
                    "https://management.azure.com/.default"
                )
                ManagedServiceIdentityClient(
                    federated_credential,
                    subscription_id,
                ).user_assigned_identities.get(
                    resource_group_name,
                    identity_name,
                )
                last_azure_error = None
                break
            except (ClientAuthenticationError, HttpResponseError) as exc:
                last_azure_error = exc
                if attempt + 1 < AZURE_PROPAGATION_ATTEMPTS:
                    time.sleep(AZURE_PROPAGATION_DELAY_SECONDS)
            finally:
                federated_credential.close()
        if last_azure_error is not None:
            raise last_azure_error
        exchange_completed_at = now()
        exchange_stage = "completed"
        result_code = "PROBE_PASSED"
    except Exception as exc:  # provider boundary, redacted below
        exchange_error_code = _safe_error_code(exc)
        result_code = f"PROBE_BLOCKED_{exchange_error_code}"
    finally:
        if role_assignment_created and role_assignment_name:
            try:
                authorization_client.role_assignments.delete(
                    scope,
                    role_assignment_name,
                )
            except Exception as exc:
                cleanup_errors.append(_safe_error_code(exc))
        if federated_credential_created:
            try:
                identity_client.federated_identity_credentials.delete(
                    resource_group_name,
                    identity_name,
                    federated_credential_name,
                )
            except Exception as exc:
                cleanup_errors.append(_safe_error_code(exc))
        if identity_created:
            try:
                identity_client.user_assigned_identities.delete(
                    resource_group_name,
                    identity_name,
                )
            except Exception as exc:
                cleanup_errors.append(_safe_error_code(exc))
        if resource_group_created:
            try:
                resource_client.resource_groups.begin_delete(
                    resource_group_name
                ).result(timeout=180)
            except Exception as exc:
                cleanup_errors.append(_safe_error_code(exc))
        if role_created:
            try:
                _delete_aws_role(iam_aws, role_name)
            except Exception as exc:
                cleanup_errors.append(_safe_error_code(exc))

        for attempt in range(12):
            residual_errors = []
            try:
                _expect_aws_role_absent(iam_aws, role_name)
            except Exception as exc:
                residual_errors.append(_safe_error_code(exc))
            try:
                _expect_azure_resource_group_absent(
                    resource_client,
                    resource_group_name,
                )
            except Exception as exc:
                residual_errors.append(_safe_error_code(exc))
            if principal_id:
                try:
                    _expect_azure_service_principal_absent(
                        azure_credential,
                        principal_id,
                    )
                except Exception as exc:
                    residual_errors.append(_safe_error_code(exc))
            if not residual_errors or attempt == 11:
                break
            time.sleep(5)

    azure_credential.close()
    cleanup_completed_at = now()
    cleanup_status = "clean" if not cleanup_errors else "failed"
    residual_status = "clean" if not residual_errors else "active_residual_detected"
    if cleanup_errors or residual_errors:
        result_code = "PROBE_BLOCKED_CLEANUP_OR_RESIDUAL_FAILED"
    record: dict[str, Any] = {
        "schema_version": "six-layer-directed-federation-probe-result.v1",
        "run_id": APPROVED_RUN_ID,
        "plan_record_digest": APPROVED_PLAN_DIGEST,
        "probe_id": probe,
        "started_at": started_at,
        "exchange_completed_at": exchange_completed_at,
        "exchange_status": "passed" if exchange_completed_at else "blocked",
        "exchange_stage": exchange_stage,
        "exchange_error_code": exchange_error_code,
        "cleanup_completed_at": cleanup_completed_at,
        "result_code": result_code,
        "cleanup_status": cleanup_status,
        "residual_status": residual_status,
        "direct_cost_cap_usd": "0.000000",
        "credential_values_included": False,
        "provider_scope_values_included": False,
        "resource_identifiers_included": False,
    }
    record["record_digest"] = _digest(record)
    return record


def _run_aws_to_gcp(
    aws: dict[str, Any],
    gcp: dict[str, Any],
    gcp_key: dict[str, Any],
    *,
    now: Callable[[], str] = _utc_now,
) -> dict[str, Any]:
    if aws["aws_region"] != AWS_REGION:
        raise ProbeBlocked("AWS_REGION_OUTSIDE_APPROVED_SCOPE")

    started_monotonic = time.monotonic()
    started_at = now()
    probe = "federation-aws-to-gcp"
    role_name = AWS_TO_GCP_NAMES["aws_role"]
    service_account_id = AWS_TO_GCP_NAMES["gcp_service_account"]
    pool_id = AWS_TO_GCP_NAMES["gcp_workload_identity_pool"]
    provider_id = AWS_TO_GCP_NAMES["gcp_workload_identity_provider"]
    service_account_email = (
        f"{service_account_id}@{gcp['gcp_project_id']}.iam.gserviceaccount.com"
    )
    service_account_name = (
        f"projects/{gcp['gcp_project_id']}/serviceAccounts/"
        f"{service_account_email}"
    )

    aws_session = _aws_session(aws)
    iam_aws = aws_session.client("iam")
    sts_aws = _aws_regional_sts(aws_session, aws["aws_region"])
    google_credentials = _gcp_credentials(gcp_key)
    iam_gcp = build_google_api(
        "iam", "v1", credentials=google_credentials, cache_discovery=False
    )
    resource_manager = build_google_api(
        "cloudresourcemanager",
        "v1",
        credentials=google_credentials,
        cache_discovery=False,
    )
    project = _gcp_execute(
        resource_manager.projects().get(projectId=gcp["gcp_project_id"])
    )
    project_number = str(project.get("projectNumber") or "")
    if not project_number.isdigit():
        raise ProbeBlocked("GCP_PROJECT_NUMBER_UNAVAILABLE")
    pool_parent = f"projects/{project_number}/locations/global"
    pool_name = f"{pool_parent}/workloadIdentityPools/{pool_id}"
    provider_name = f"{pool_name}/providers/{provider_id}"
    pools = iam_gcp.projects().locations().workloadIdentityPools()
    providers = pools.providers()
    member = _aws_to_gcp_principal_set(project_number, pool_id, role_name)

    role_created = False
    service_account_created = False
    pool_created = False
    provider_created = False
    binding_created = False
    exchange_completed_at: str | None = None
    exchange_error_code: str | None = None
    exchange_stage = "preflight"
    result_code = "PROBE_BLOCKED"
    cleanup_errors: list[str] = []
    residual_errors: list[str] = []

    try:
        _assert_deadline(started_monotonic)
        _expect_aws_role_absent(iam_aws, role_name)
        _expect_gcp_service_account_absent(
            iam_gcp,
            gcp["gcp_project_id"],
            service_account_email,
        )
        _expect_gcp_workload_identity_pool_absent(
            pools,
            pool_parent,
            pool_id,
        )

        exchange_stage = "create_aws_source_role"
        caller = sts_aws.get_caller_identity()
        caller_arn = str(caller.get("Arn") or "")
        aws_account_id = str(caller.get("Account") or "")
        if ":iam::" not in caller_arn or ":user/" not in caller_arn:
            raise ProbeBlocked("AWS_DEPLOYMENT_PRINCIPAL_NOT_IAM_USER")
        provider_body = _aws_to_gcp_provider_body(aws_account_id, role_name)
        trust_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": "sts:AssumeRole",
                    "Principal": {"AWS": caller_arn},
                }
            ],
        }
        created_role = iam_aws.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=_canonical_json(trust_policy),
            Description="Ephemeral identity-only thesis evaluation probe",
            MaxSessionDuration=3600,
            Tags=[
                {"Key": "Twin2MultiCloudPhase", "Value": "8"},
                {"Key": "Twin2MultiCloudRun", "Value": APPROVED_RUN_ID},
            ],
        )
        role_created = True
        role_arn = _aws_role_subject(
            str((created_role.get("Role") or {}).get("Arn") or ""),
            role_name,
        )

        exchange_stage = "create_gcp_service_account"
        _gcp_execute(
            iam_gcp.projects().serviceAccounts().create(
                name=f"projects/{gcp['gcp_project_id']}",
                body={
                    "accountId": service_account_id,
                    "serviceAccount": {
                        "displayName": "Twin2MultiCloud AWS to GCP probe",
                        "description": (
                            "Ephemeral identity-only thesis evaluation probe"
                        ),
                    },
                },
            )
        )
        service_account_created = True

        exchange_stage = "create_gcp_workload_identity_pool"
        pool_operation = _gcp_execute(
            pools.create(
                parent=pool_parent,
                workloadIdentityPoolId=pool_id,
                body={
                    "displayName": "Twin2MultiCloud AWS to GCP",
                    "description": (
                        "Ephemeral identity-only thesis evaluation probe"
                    ),
                    "disabled": False,
                },
            )
        )
        pool_created = True
        _wait_for_gcp_operation(
            pools.operations(),
            pool_operation,
            started_monotonic,
        )

        exchange_stage = "create_gcp_aws_provider"
        provider_operation = _gcp_execute(
            providers.create(
                parent=pool_name,
                workloadIdentityPoolProviderId=provider_id,
                body=provider_body,
            )
        )
        provider_created = True
        _wait_for_gcp_operation(
            providers.operations(),
            provider_operation,
            started_monotonic,
        )

        exchange_stage = "bind_gcp_service_account"
        _add_service_account_workload_identity_user(
            iam_gcp,
            service_account_name,
            member,
        )
        binding_created = True

        exchange_stage = "assume_aws_source_role"
        assumed: dict[str, Any] | None = None
        last_aws_error: ClientError | None = None
        for attempt in range(AWS_PROPAGATION_ATTEMPTS):
            _assert_deadline(started_monotonic)
            try:
                assumed = sts_aws.assume_role(
                    RoleArn=role_arn,
                    RoleSessionName="t2mc-p8-aws-gcp",
                    DurationSeconds=900,
                )
                last_aws_error = None
                break
            except ClientError as exc:
                last_aws_error = exc
                if attempt + 1 < AWS_PROPAGATION_ATTEMPTS:
                    time.sleep(AWS_PROPAGATION_DELAY_SECONDS)
        if last_aws_error is not None:
            raise last_aws_error
        if assumed is None:
            raise ProbeBlocked("AWS_SOURCE_SESSION_UNAVAILABLE")
        temporary = dict(assumed.get("Credentials") or {})
        for key in ("AccessKeyId", "SecretAccessKey", "SessionToken"):
            if not isinstance(temporary.get(key), str):
                raise ProbeBlocked("AWS_SOURCE_CREDENTIALS_UNAVAILABLE")

        exchange_stage = "exchange_aws_subject_for_gcp_service_account"
        audience = f"//iam.googleapis.com/{provider_name}"
        impersonation_url = (
            "https://iamcredentials.googleapis.com/v1/projects/-/"
            f"serviceAccounts/{service_account_email}:generateAccessToken"
        )
        last_gcp_error: Exception | None = None
        for attempt in range(GCP_PERMISSION_PROPAGATION_ATTEMPTS):
            _assert_deadline(started_monotonic)
            federated = google_auth_aws.Credentials(
                audience=audience,
                subject_token_type=(
                    "urn:ietf:params:aws:token-type:aws4_request"
                ),
                token_url="https://sts.googleapis.com/v1/token",
                service_account_impersonation_url=impersonation_url,
                scopes=["https://www.googleapis.com/auth/cloud-platform"],
                aws_security_credentials_supplier=(
                    _StaticAwsCredentialsSupplier(
                        temporary,
                        aws["aws_region"],
                    )
                ),
            )
            try:
                federated.refresh(GoogleAuthRequest())
                if not isinstance(federated.token, str):
                    raise ProbeBlocked("GCP_ACCESS_TOKEN_UNAVAILABLE")
                last_gcp_error = None
                break
            except Exception as exc:
                last_gcp_error = exc
                if attempt + 1 < GCP_PERMISSION_PROPAGATION_ATTEMPTS:
                    time.sleep(GCP_PERMISSION_PROPAGATION_DELAY_SECONDS)
        if last_gcp_error is not None:
            raise last_gcp_error
        exchange_completed_at = now()
        exchange_stage = "completed"
        result_code = "PROBE_PASSED"
    except Exception as exc:  # provider boundary, redacted below
        exchange_error_code = _safe_error_code(exc)
        result_code = f"PROBE_BLOCKED_{exchange_error_code}"
    finally:
        if binding_created:
            try:
                _remove_service_account_workload_identity_user(
                    iam_gcp,
                    service_account_name,
                    member,
                )
            except Exception as exc:
                cleanup_errors.append(_safe_error_code(exc))
        if provider_created:
            try:
                operation = _gcp_execute(providers.delete(name=provider_name))
                _wait_for_gcp_operation(
                    providers.operations(),
                    operation,
                    started_monotonic,
                )
            except Exception as exc:
                cleanup_errors.append(_safe_error_code(exc))
        if pool_created:
            try:
                operation = _gcp_execute(pools.delete(name=pool_name))
                _wait_for_gcp_operation(
                    pools.operations(),
                    operation,
                    started_monotonic,
                )
            except Exception as exc:
                cleanup_errors.append(_safe_error_code(exc))
        if service_account_created:
            try:
                _delete_gcp_service_account(iam_gcp, service_account_name)
            except Exception as exc:
                cleanup_errors.append(_safe_error_code(exc))
        if role_created:
            try:
                _delete_aws_role(iam_aws, role_name)
            except Exception as exc:
                cleanup_errors.append(_safe_error_code(exc))

        for attempt in range(12):
            residual_errors = []
            try:
                _expect_aws_role_absent(iam_aws, role_name)
            except Exception as exc:
                residual_errors.append(_safe_error_code(exc))
            try:
                _expect_gcp_service_account_absent(
                    iam_gcp,
                    gcp["gcp_project_id"],
                    service_account_email,
                )
            except Exception as exc:
                residual_errors.append(_safe_error_code(exc))
            try:
                _expect_gcp_workload_identity_pool_absent(
                    pools,
                    pool_parent,
                    pool_id,
                )
            except Exception as exc:
                residual_errors.append(_safe_error_code(exc))
            if not residual_errors or attempt == 11:
                break
            time.sleep(5)

    cleanup_completed_at = now()
    cleanup_status = "clean" if not cleanup_errors else "failed"
    residual_status = "clean" if not residual_errors else "active_residual_detected"
    if cleanup_errors or residual_errors:
        result_code = "PROBE_BLOCKED_CLEANUP_OR_RESIDUAL_FAILED"
    record: dict[str, Any] = {
        "schema_version": "six-layer-directed-federation-probe-result.v1",
        "run_id": APPROVED_RUN_ID,
        "plan_record_digest": APPROVED_PLAN_DIGEST,
        "probe_id": probe,
        "started_at": started_at,
        "exchange_completed_at": exchange_completed_at,
        "exchange_status": "passed" if exchange_completed_at else "blocked",
        "exchange_stage": exchange_stage,
        "exchange_error_code": exchange_error_code,
        "cleanup_completed_at": cleanup_completed_at,
        "result_code": result_code,
        "cleanup_status": cleanup_status,
        "residual_status": residual_status,
        "accepted_inactive_tombstone_classes": [
            "gcp.service_account",
            "gcp.workload_identity_pool",
            "gcp.workload_identity_pool_provider",
        ],
        "direct_cost_cap_usd": "0.000000",
        "credential_values_included": False,
        "provider_scope_values_included": False,
        "resource_identifiers_included": False,
    }
    record["record_digest"] = _digest(record)
    return record


def execute(
    probe_id: str,
    provider_config_path: Path,
    gcp_credentials_path: Path,
) -> dict[str, Any]:
    if probe_id not in ENABLED_PROBES:
        raise ProbeBlocked("PROBE_NOT_IMPLEMENTED")
    credentials = _load_credentials(provider_config_path, gcp_credentials_path)
    aws, gcp, gcp_key, azure = credentials
    if probe_id == "federation-gcp-to-aws":
        record = _run_gcp_to_aws(aws, gcp, gcp_key)
    elif probe_id == "federation-gcp-to-azure":
        record = _run_gcp_to_azure(gcp, gcp_key, azure)
    elif probe_id == "federation-aws-to-azure":
        record = _run_aws_to_azure(aws, azure)
    elif probe_id == "federation-aws-to-gcp":
        record = _run_aws_to_gcp(aws, gcp, gcp_key)
    else:  # pragma: no cover - guarded above
        raise ProbeBlocked("PROBE_NOT_IMPLEMENTED")
    _assert_no_sensitive_values(record, credentials)
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe", required=True, choices=sorted(ENABLED_PROBES))
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--approved-plan-digest", required=True)
    parser.add_argument("--credentials", type=Path, required=True)
    parser.add_argument("--gcp-credentials", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    if not args.execute:
        raise ProbeBlocked("EXECUTE_FLAG_REQUIRED")
    if args.run_id != APPROVED_RUN_ID:
        raise ProbeBlocked("RUN_ID_NOT_APPROVED")
    if args.approved_plan_digest != APPROVED_PLAN_DIGEST:
        raise ProbeBlocked("PLAN_DIGEST_NOT_APPROVED")
    if args.output.exists():
        raise FileExistsError("result output already exists")
    plan = _load_object(PLAN_PATH)
    if plan.get("record_digest") != APPROVED_PLAN_DIGEST:
        raise ProbeBlocked("TRACKED_PLAN_DIGEST_DRIFT")

    try:
        record = execute(
            args.probe,
            args.credentials.resolve(),
            args.gcp_credentials.resolve(),
        )
    except Exception as exc:
        print(f"{args.probe}: PROBE_BLOCKED_{_safe_error_code(exc)}")
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"{record['probe_id']}: {record['result_code']}; "
        f"cleanup={record['cleanup_status']}; residual={record['residual_status']}"
    )
    return 0 if record["result_code"] == "PROBE_PASSED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
