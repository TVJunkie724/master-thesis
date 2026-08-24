"""GCP existing-project driver for the supervised setup-only transaction."""

from __future__ import annotations

import base64
from dataclasses import dataclass
import hmac
import json
import re
import time
from typing import Any, Callable, Protocol
from urllib.parse import quote

from jose import jwt

from src.schemas.cloud_bootstrap import (
    CloudBootstrapCredential,
    CloudBootstrapCredentialOrigin,
    CloudBootstrapDisposalStatus,
    CloudBootstrapTarget,
    GCPBootstrapCredential,
    GCPExistingProjectBootstrapTarget,
)
from src.schemas.cloud_connection import CloudConnectionCreate
from src.schemas.twin_config import GCPCredentials
from src.services.cloud_bootstrap_adapters import (
    CloudBootstrapAdapterError,
    CloudBootstrapAdapterResult,
    CloudBootstrapFinalizationResult,
    CloudBootstrapRollbackReceipt,
    SupervisedLiveBootstrapPlan,
)


OAUTH_ENDPOINT = "https://oauth2.googleapis.com/token"
OAUTH_SCOPE = "https://www.googleapis.com/auth/cloud-platform"
CRM_ROOT = "https://cloudresourcemanager.googleapis.com/v1"
IAM_ROOT = "https://iam.googleapis.com/v1"
SERVICE_USAGE_ROOT = "https://serviceusage.googleapis.com/v1"
BILLING_ROOT = "https://cloudbilling.googleapis.com/v1"
FROZEN_REGION = "europe-west1"
MANAGED_DESCRIPTION = "Gate-owned Twin2MultiCloud setup-only deployment identity"
ROLE_DESCRIPTION = "Gate-owned thesis-demo-v2 deployment role; offline-generated."
KEY_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,160}$")


class GCPResponse(Protocol):
    status_code: int

    def json(self) -> Any: ...


class GCPTransport(Protocol):
    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        data: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
    ) -> GCPResponse: ...


GCPTransportFactory = Callable[[dict[str, str]], GCPTransport]
GCPKeyPairVerifier = Callable[[str, str], bool]


def verify_private_key_matches_x509(
    private_key_pem: str,
    encoded_x509_pem: str,
) -> bool:
    """Prove that submitted private material matches one provider key ID."""

    from cryptography import x509
    from cryptography.exceptions import UnsupportedAlgorithm
    from cryptography.hazmat.primitives import serialization

    try:
        certificate_pem = base64.b64decode(
            encoded_x509_pem,
            validate=True,
        )
        certificate = x509.load_pem_x509_certificate(certificate_pem)
        private_key = serialization.load_pem_private_key(
            private_key_pem.encode("utf-8"),
            password=None,
        )
        provider_public = certificate.public_key().public_bytes(
            serialization.Encoding.DER,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        submitted_public = private_key.public_key().public_bytes(
            serialization.Encoding.DER,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    except (TypeError, UnsupportedAlgorithm, ValueError):
        return False
    return hmac.compare_digest(provider_public, submitted_public)


class _HttpxGCPTransport:
    """Explicit service-account transport; it never falls back to ADC."""

    def __init__(self, credential_info: dict[str, str]) -> None:
        import httpx

        self._info = dict(credential_info)
        self._client = httpx.Client(
            timeout=httpx.Timeout(30.0),
            follow_redirects=False,
            trust_env=False,
        )
        self._access_token: str | None = None
        self._expires_at = 0

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        data: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
    ):
        request_headers = dict(headers or {})
        request_headers["Authorization"] = f"Bearer {self._token()}"
        return self._client.request(
            method,
            url,
            headers=request_headers,
            params=params,
            data=data,
            json=json,
        )

    def _token(self) -> str:
        now = int(time.time())
        if self._access_token is not None and now < self._expires_at - 60:
            return self._access_token
        if self._info.get("token_uri") != OAUTH_ENDPOINT:
            raise ValueError("unsupported GCP OAuth endpoint")
        header = {
            "alg": "RS256",
            "kid": self._info["private_key_id"],
            "typ": "JWT",
        }
        claim = {
            "aud": OAUTH_ENDPOINT,
            "exp": now + 3600,
            "iat": now,
            "iss": self._info["client_email"],
            "scope": OAUTH_SCOPE,
        }
        assertion = jwt.encode(
            claim,
            self._info["private_key"],
            algorithm="RS256",
            headers=header,
        )
        response = self._client.post(
            OAUTH_ENDPOINT,
            data={
                "assertion": assertion,
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            },
        )
        if response.status_code != 200:
            raise ValueError("GCP OAuth rejected the service-account assertion")
        document = response.json()
        token = document.get("access_token") if isinstance(document, dict) else None
        expires_in = document.get("expires_in") if isinstance(document, dict) else None
        if not isinstance(token, str) or not token or not isinstance(expires_in, int):
            raise ValueError("GCP OAuth returned an incomplete token response")
        self._access_token = token
        self._expires_at = now + expires_in
        return token

    def close(self) -> None:
        self._client.close()


def default_gcp_transport_factory(credential_info: dict[str, str]) -> GCPTransport:
    return _HttpxGCPTransport(credential_info)


@dataclass(frozen=True)
class _GCPPlan:
    project_id: str
    project_number: str
    run_id: str
    service_account_email: str
    role_name: str
    role_document: dict[str, Any]
    services: tuple[str, ...]
    prerequisites: tuple[str, ...]


class GCPCloudBootstrapDriver:
    """Create and validate one gate-owned GCP deployment service account."""

    def __init__(
        self,
        *,
        transport_factory: GCPTransportFactory = default_gcp_transport_factory,
        sleeper: Callable[[float], None] = time.sleep,
        key_pair_verifier: GCPKeyPairVerifier = verify_private_key_matches_x509,
    ) -> None:
        self._transport_factory = transport_factory
        self._sleep = sleeper
        self._key_pair_verifier = key_pair_verifier

    def provision(
        self,
        *,
        plan: SupervisedLiveBootstrapPlan,
        display_name: str,
        target: CloudBootstrapTarget,
        credential_origin: CloudBootstrapCredentialOrigin,
        credential: CloudBootstrapCredential,
    ) -> CloudBootstrapAdapterResult:
        if (
            plan.provider != "gcp"
            or not isinstance(target, GCPExistingProjectBootstrapTarget)
            or not isinstance(credential, GCPBootstrapCredential)
        ):
            raise self._invalid_credential()
        info = self._credential_info(credential, target)
        bundle, baseline = self._validate_offline_plan(plan, target)
        transport = self._transport_factory(info)
        receipt: CloudBootstrapRollbackReceipt | None = None
        runtime: _GCPPlan | None = None
        try:
            project = self._validate_project(transport, target.project_id)
            project_number = self._required_numeric(project, "projectNumber")
            runtime = self._runtime_plan(
                plan,
                target,
                bundle,
                baseline,
                project_number,
            )
            self._verify_prerequisites(transport, runtime)
            self._enable_and_verify_billing(transport, runtime)
            self._enable_services(transport, runtime, runtime.services)
            self._verify_services(transport, runtime, runtime.services)

            account, account_created = self._get_or_create_service_account(
                transport,
                runtime,
            )
            if account_created:
                receipt = self._receipt(
                    runtime,
                    service_account_email=runtime.service_account_email,
                )
            self._validate_service_account(account, runtime)
            if account_created:
                visible_account = self._await_service_account(transport, runtime)
                self._validate_service_account(visible_account, runtime)
            if receipt is None:
                receipt = self._receipt(
                    runtime,
                    service_account_email=runtime.service_account_email,
                )

            role, role_created = self._get_or_create_role(transport, runtime)
            if role_created:
                receipt = self._receipt(
                    runtime,
                    role_name=runtime.role_name,
                    service_account_email=runtime.service_account_email,
                )
            self._validate_role(role, runtime)
            receipt = self._receipt(
                runtime,
                role_name=runtime.role_name,
                service_account_email=runtime.service_account_email,
            )
            self._ensure_project_binding(transport, runtime)
            generated = self._create_generated_key(transport, runtime)
            key_id = self._generated_key_id(generated, runtime)
            receipt = self._receipt(
                runtime,
                key_id=key_id,
                role_name=runtime.role_name,
                service_account_email=runtime.service_account_email,
            )
            generated_info = self._decode_generated_key(
                generated,
                runtime,
                expected_key_id=key_id,
                expected_client_id=str(account["oauth2ClientId"]),
            )
            self._verify_provider_key_pair(
                transport,
                runtime.project_id,
                runtime.service_account_email,
                key_id,
                generated_info["private_key"],
            )
            self._validate_generated_credential(runtime, generated_info)
        except Exception as exc:
            try:
                if receipt is not None and runtime is not None:
                    self._cleanup(transport, receipt, runtime)
            except Exception as cleanup_exc:
                raise CloudBootstrapAdapterError(
                    "BOOTSTRAP_CLEANUP_FAILED",
                    f"GCP setup run {plan.run_id} requires manual cleanup; the Phase 8 API baseline remains enabled.",
                ) from cleanup_exc
            if isinstance(exc, CloudBootstrapAdapterError):
                raise
            raise CloudBootstrapAdapterError(
                "BOOTSTRAP_IDENTITY_CREATION_FAILED",
                "GCP rejected the reviewed existing-project setup transaction; enabled Phase 8 APIs are retained.",
            ) from exc
        finally:
            self._close(transport)

        disposal, finalize = self._provisional_disposal(credential_origin)
        return CloudBootstrapAdapterResult(
            connection=CloudConnectionCreate(
                provider="gcp",
                purpose="deployment",
                display_name=display_name,
                auth_type="service_account_key",
                permission_set_version="thesis-demo-v2",
                cloud_scope={
                    "provider": "gcp",
                    "mode": "existing_project",
                    "project_id": target.project_id,
                    "region": target.region,
                    "bootstrap_mode": "supervised_live",
                },
                gcp=GCPCredentials(
                    project_id=target.project_id,
                    service_account_json=json.dumps(generated_info, sort_keys=True),
                    region=target.region,
                ),
            ),
            safe_credential_identifier=credential.private_key_id.get_secret_value(),
            disposal_status=disposal,
            generated_credential_validated=True,
            rollback_receipt=receipt,
            bootstrap_finalization_required=finalize,
        )

    def rollback(
        self,
        *,
        receipt: CloudBootstrapRollbackReceipt,
        target: CloudBootstrapTarget,
        credential: CloudBootstrapCredential,
    ) -> None:
        if (
            receipt.provider != "gcp"
            or not isinstance(target, GCPExistingProjectBootstrapTarget)
            or not isinstance(credential, GCPBootstrapCredential)
        ):
            raise self._invalid_credential()
        info = self._credential_info(credential, target)
        transport = self._transport_factory(info)
        try:
            project = self._validate_project(transport, target.project_id)
            runtime = self._runtime_from_receipt(
                receipt,
                target,
                self._required_numeric(project, "projectNumber"),
            )
            self._cleanup(transport, receipt, runtime)
        finally:
            self._close(transport)

    def finalize_bootstrap(
        self,
        *,
        receipt: CloudBootstrapRollbackReceipt,
        target: CloudBootstrapTarget,
        credential: CloudBootstrapCredential,
    ) -> CloudBootstrapFinalizationResult:
        if (
            receipt.provider != "gcp"
            or not isinstance(target, GCPExistingProjectBootstrapTarget)
            or not isinstance(credential, GCPBootstrapCredential)
        ):
            raise self._invalid_credential()
        info = self._credential_info(credential, target)
        transport = self._transport_factory(info)
        try:
            self._validate_project(transport, target.project_id)
            key_id = credential.private_key_id.get_secret_value()
            if not KEY_ID_PATTERN.fullmatch(key_id):
                raise self._invalid_credential()
            email = credential.client_email
            expected_name = self._key_name(target.project_id, email, key_id)
            keys = self._list_user_keys(transport, target.project_id, email)
            if expected_name not in {item.get("name") for item in keys}:
                raise CloudBootstrapAdapterError(
                    "BOOTSTRAP_CLEANUP_FAILED",
                    "GCP bootstrap-key ownership could not be proven for automatic deletion.",
                )
            self._verify_provider_key_pair(
                transport,
                target.project_id,
                email,
                key_id,
                credential.private_key.get_secret_value(),
            )
            self._delete(transport, f"{IAM_ROOT}/{expected_name}")
            return CloudBootstrapFinalizationResult(
                disposal_status=CloudBootstrapDisposalStatus.REVOKED,
            )
        finally:
            self._close(transport)

    @staticmethod
    def _credential_info(
        credential: GCPBootstrapCredential,
        target: GCPExistingProjectBootstrapTarget,
    ) -> dict[str, str]:
        token_uri = credential.token_uri or OAUTH_ENDPOINT
        account_id, separator, domain = credential.client_email.partition("@")
        private_key_id = credential.private_key_id.get_secret_value()
        client_id = credential.client_id.get_secret_value()
        if (
            credential.project_id != target.project_id
            or token_uri != OAUTH_ENDPOINT
            or separator != "@"
            or re.fullmatch(r"[a-z][a-z0-9-]{4,28}[a-z0-9]", account_id) is None
            or domain != f"{target.project_id}.iam.gserviceaccount.com"
            or KEY_ID_PATTERN.fullmatch(private_key_id) is None
            or not client_id.isdigit()
        ):
            raise GCPCloudBootstrapDriver._invalid_credential()
        return {
            "type": "service_account",
            "project_id": credential.project_id,
            "private_key_id": private_key_id,
            "private_key": credential.private_key.get_secret_value(),
            "client_email": credential.client_email,
            "client_id": client_id,
            "token_uri": token_uri,
        }

    @staticmethod
    def _validate_offline_plan(
        plan: SupervisedLiveBootstrapPlan,
        target: GCPExistingProjectBootstrapTarget,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        bundle = plan.deployment_document()
        baseline = plan.gcp_api_baseline()
        expected_email = f"{plan.run_id}@{target.project_id}.iam.gserviceaccount.com"
        expected_role = (
            f"projects/{target.project_id}/roles/{plan.run_id.replace('-', '_')}"
        )
        if (
            target.region != FROZEN_REGION
            or bundle.get("schema_version") != "gcp-deployment-identity-bundle.v1"
            or bundle.get("provider") != "gcp"
            or bundle.get("project_id") != target.project_id
            or bundle.get("region") != target.region
            or bundle.get("permission_set_version") != "thesis-demo-v2"
            or bundle.get("identity_binding_id")
            != "gcp.thesis-demo-v2.service-account-v1"
            or bundle.get("identity")
            != {"account_id": plan.run_id, "email": expected_email}
            or bundle.get("parent") != f"projects/{target.project_id}"
            or bundle.get("roleId") != plan.run_id.replace("-", "_")
            or bundle.get("role", {}).get("description") != ROLE_DESCRIPTION
            or bundle.get("role", {}).get("title") != f"Twin2MultiCloud {plan.run_id}"
            or bundle.get("role", {}).get("stage") != "GA"
            or not isinstance(bundle.get("role", {}).get("includedPermissions"), list)
            or not bundle.get("role", {}).get("includedPermissions")
            or len(bundle.get("role", {}).get("includedPermissions", []))
            != len(set(bundle.get("role", {}).get("includedPermissions", [])))
            or any(
                "*" in permission
                for permission in bundle.get("role", {}).get("includedPermissions", [])
            )
            or baseline is None
            or baseline.get("schema_version") != "gcp-phase8-api-baseline.v1"
            or baseline.get("baseline_id") != "gcp.phase8-api-baseline.v1"
            or baseline.get("owner") != "bootstrap.gcp.admin-v3"
            or baseline.get("target_mode") != "existing_project"
            or baseline.get("region") != target.region
            or baseline.get("retain_enabled") is not True
            or baseline.get("services") != sorted(baseline.get("services", []))
            or len(baseline.get("services", [])) != 19
            or not set(baseline.get("bootstrap_prerequisite_services", [])).issubset(
                baseline.get("services", [])
            )
            or expected_role
            != f"projects/{target.project_id}/roles/{bundle.get('roleId')}"
        ):
            raise CloudBootstrapAdapterError(
                "BOOTSTRAP_AUTHORITY_PACK_MISMATCH",
                "The GCP plan does not match the reviewed existing-project v2 contract.",
            )
        return bundle, baseline

    @staticmethod
    def _runtime_plan(
        plan: SupervisedLiveBootstrapPlan,
        target: GCPExistingProjectBootstrapTarget,
        bundle: dict[str, Any],
        baseline: dict[str, Any],
        project_number: str,
    ) -> _GCPPlan:
        return _GCPPlan(
            project_id=target.project_id,
            project_number=project_number,
            run_id=plan.run_id,
            service_account_email=(
                f"{plan.run_id}@{target.project_id}.iam.gserviceaccount.com"
            ),
            role_name=(f"projects/{target.project_id}/roles/{bundle['roleId']}"),
            role_document=dict(bundle["role"]),
            services=tuple(baseline["services"]),
            prerequisites=tuple(baseline["bootstrap_prerequisite_services"]),
        )

    @staticmethod
    def _runtime_from_receipt(
        receipt: CloudBootstrapRollbackReceipt,
        target: GCPExistingProjectBootstrapTarget,
        project_number: str,
    ) -> _GCPPlan:
        identifiers = dict(receipt.resource_ids)
        expected_email = f"{receipt.run_id}@{target.project_id}.iam.gserviceaccount.com"
        expected_role = (
            f"projects/{target.project_id}/roles/{receipt.run_id.replace('-', '_')}"
        )
        if (
            identifiers.get("service_account_email") != expected_email
            or (
                "role_name" in identifiers and identifiers["role_name"] != expected_role
            )
            or (
                "key_id" in identifiers
                and not KEY_ID_PATTERN.fullmatch(identifiers["key_id"])
            )
        ):
            raise CloudBootstrapAdapterError(
                "BOOTSTRAP_CLEANUP_FAILED",
                "The GCP rollback receipt does not match the selected project and setup run.",
            )
        return _GCPPlan(
            project_id=target.project_id,
            project_number=project_number,
            run_id=receipt.run_id,
            service_account_email=expected_email,
            role_name=expected_role,
            role_document={},
            services=(),
            prerequisites=(),
        )

    @staticmethod
    def _validate_project(transport: GCPTransport, project_id: str) -> dict[str, Any]:
        project = GCPCloudBootstrapDriver._json_request(
            transport,
            "GET",
            f"{CRM_ROOT}/projects/{quote(project_id, safe='')}",
        )
        if (
            project.get("projectId") != project_id
            or project.get("lifecycleState") != "ACTIVE"
        ):
            raise GCPCloudBootstrapDriver._invalid_credential()
        return project

    def _enable_and_verify_billing(
        self,
        transport: GCPTransport,
        runtime: _GCPPlan,
    ) -> None:
        billing_service = "cloudbilling.googleapis.com"
        self._enable_services(transport, runtime, (billing_service,))
        last_error: Exception | None = None
        for attempt in range(5):
            try:
                document = self._json_request(
                    transport,
                    "GET",
                    f"{BILLING_ROOT}/projects/{quote(runtime.project_id, safe='')}/billingInfo",
                )
                if (
                    document.get("projectId") != runtime.project_id
                    or document.get("name")
                    != f"projects/{runtime.project_id}/billingInfo"
                    or document.get("billingEnabled") is not True
                    or not isinstance(document.get("billingAccountName"), str)
                    or not document["billingAccountName"].startswith("billingAccounts/")
                ):
                    raise CloudBootstrapAdapterError(
                        "BOOTSTRAP_SCOPE_UNSUPPORTED",
                        "The selected GCP project is not linked to an active billing account.",
                    )
                return
            except CloudBootstrapAdapterError as exc:
                last_error = exc
                if exc.code == "BOOTSTRAP_SCOPE_UNSUPPORTED":
                    raise
                if attempt < 4:
                    self._sleep(2**attempt)
        raise CloudBootstrapAdapterError(
            "BOOTSTRAP_IDENTITY_CREATION_FAILED",
            "GCP Cloud Billing did not become readable after API enablement.",
        ) from last_error

    def _enable_services(
        self,
        transport: GCPTransport,
        runtime: _GCPPlan,
        services: tuple[str, ...],
    ) -> None:
        missing = tuple(
            service
            for service in services
            if not self._service_enabled(transport, runtime, service)
        )
        if not missing:
            return
        if len(missing) > 20:
            raise CloudBootstrapAdapterError(
                "BOOTSTRAP_AUTHORITY_PACK_MISMATCH",
                "The reviewed GCP API batch exceeds the provider limit.",
            )
        operation = self._json_request(
            transport,
            "POST",
            f"{SERVICE_USAGE_ROOT}/projects/{runtime.project_number}/services:batchEnable",
            body={"serviceIds": list(missing)},
        )
        name = self._required_string(operation, "name")
        if not name.startswith("operations/"):
            raise CloudBootstrapAdapterError(
                "BOOTSTRAP_IDENTITY_CREATION_FAILED",
                "GCP returned an invalid Service Usage operation.",
            )
        self._await_operation(transport, name)

    @staticmethod
    def _verify_prerequisites(
        transport: GCPTransport,
        runtime: _GCPPlan,
    ) -> None:
        missing = [
            service
            for service in runtime.prerequisites
            if not GCPCloudBootstrapDriver._service_enabled(transport, runtime, service)
        ]
        if missing:
            raise CloudBootstrapAdapterError(
                "BOOTSTRAP_SCOPE_UNSUPPORTED",
                "The GCP Service Usage, IAM, and Cloud Resource Manager prerequisite APIs must be enabled manually before guided setup.",
            )

    @staticmethod
    def _verify_services(
        transport: GCPTransport,
        runtime: _GCPPlan,
        services: tuple[str, ...],
    ) -> None:
        missing = [
            service
            for service in services
            if not GCPCloudBootstrapDriver._service_enabled(transport, runtime, service)
        ]
        if missing:
            raise CloudBootstrapAdapterError(
                "BOOTSTRAP_CONNECTION_VALIDATION_FAILED",
                "The required GCP API baseline is not fully enabled.",
            )

    @staticmethod
    def _service_enabled(
        transport: GCPTransport,
        runtime: _GCPPlan,
        service: str,
    ) -> bool:
        document = GCPCloudBootstrapDriver._json_request(
            transport,
            "GET",
            (
                f"{SERVICE_USAGE_ROOT}/projects/{runtime.project_number}/services/"
                f"{quote(service, safe='.')}"
            ),
        )
        return (
            document.get("name")
            == f"projects/{runtime.project_number}/services/{service}"
            and document.get("state") == "ENABLED"
        )

    def _await_operation(self, transport: GCPTransport, name: str) -> None:
        for attempt in range(10):
            operation = self._json_request(
                transport,
                "GET",
                f"{SERVICE_USAGE_ROOT}/{quote(name, safe='/')}",
            )
            if operation.get("done") is True:
                if operation.get("error"):
                    raise CloudBootstrapAdapterError(
                        "BOOTSTRAP_IDENTITY_CREATION_FAILED",
                        "GCP could not enable the reviewed API baseline.",
                    )
                return
            if attempt < 9:
                self._sleep(min(2**attempt, 10))
        raise CloudBootstrapAdapterError(
            "BOOTSTRAP_IDENTITY_CREATION_FAILED",
            "GCP API enablement did not complete within the setup-only wait window.",
        )

    @staticmethod
    def _get_or_create_service_account(
        transport: GCPTransport,
        runtime: _GCPPlan,
    ) -> tuple[dict[str, Any], bool]:
        account_url = GCPCloudBootstrapDriver._account_url(runtime)
        response = transport.request("GET", account_url)
        if response.status_code == 404:
            account = GCPCloudBootstrapDriver._json_request(
                transport,
                "POST",
                f"{IAM_ROOT}/projects/{runtime.project_id}/serviceAccounts",
                body={
                    "accountId": runtime.run_id,
                    "serviceAccount": {
                        "displayName": f"Twin2MultiCloud {runtime.run_id}",
                        "description": MANAGED_DESCRIPTION,
                    },
                },
                expected=(200,),
            )
            created = True
        else:
            account = GCPCloudBootstrapDriver._document(response, expected=(200,))
            created = False
        return account, created

    @staticmethod
    def _validate_service_account(
        account: dict[str, Any],
        runtime: _GCPPlan,
    ) -> None:
        if (
            account.get("name")
            != f"projects/{runtime.project_id}/serviceAccounts/{runtime.service_account_email}"
            or account.get("projectId") != runtime.project_id
            or account.get("email") != runtime.service_account_email
            or account.get("displayName") != f"Twin2MultiCloud {runtime.run_id}"
            or account.get("description") != MANAGED_DESCRIPTION
            or account.get("disabled") is True
            or not str(account.get("uniqueId", "")).isdigit()
            or not str(account.get("oauth2ClientId", "")).isdigit()
        ):
            raise CloudBootstrapAdapterError(
                "BOOTSTRAP_IDENTITY_CREATION_FAILED",
                "An existing GCP service account does not match the setup-run ownership boundary.",
            )

    def _await_service_account(
        self,
        transport: GCPTransport,
        runtime: _GCPPlan,
    ) -> dict[str, Any]:
        for attempt in range(7):
            response = transport.request("GET", self._account_url(runtime))
            if response.status_code != 404:
                return self._document(response, expected=(200,))
            if attempt < 6:
                self._sleep(min(2**attempt, 30))
        raise CloudBootstrapAdapterError(
            "BOOTSTRAP_IDENTITY_CREATION_FAILED",
            "The generated GCP service account did not become visible within the setup-only wait window.",
        )

    @staticmethod
    def _get_or_create_role(
        transport: GCPTransport,
        runtime: _GCPPlan,
    ) -> tuple[dict[str, Any], bool]:
        url = f"{IAM_ROOT}/{runtime.role_name}"
        response = transport.request("GET", url, params={"view": "FULL"})
        if response.status_code == 404:
            role = GCPCloudBootstrapDriver._json_request(
                transport,
                "POST",
                f"{IAM_ROOT}/projects/{runtime.project_id}/roles",
                body={
                    "roleId": runtime.run_id.replace("-", "_"),
                    "role": runtime.role_document,
                },
                expected=(200,),
            )
            created = True
        else:
            role = GCPCloudBootstrapDriver._document(response, expected=(200,))
            created = False
        return role, created

    @staticmethod
    def _validate_role(role: dict[str, Any], runtime: _GCPPlan) -> None:
        expected = runtime.role_document
        if (
            role.get("name") != runtime.role_name
            or role.get("title") != expected.get("title")
            or role.get("description") != expected.get("description")
            or role.get("stage") != expected.get("stage")
            or role.get("deleted") is True
            or sorted(role.get("includedPermissions", []))
            != sorted(expected.get("includedPermissions", []))
        ):
            raise CloudBootstrapAdapterError(
                "BOOTSTRAP_AUTHORITY_PACK_MISMATCH",
                "The GCP custom role does not match the reviewed v2 permission document.",
            )

    @staticmethod
    def _ensure_project_binding(transport: GCPTransport, runtime: _GCPPlan) -> None:
        policy = GCPCloudBootstrapDriver._get_project_policy(transport, runtime)
        member = f"serviceAccount:{runtime.service_account_email}"
        matching = [
            binding
            for binding in policy.get("bindings", [])
            if binding.get("role") == runtime.role_name
        ]
        if (
            any(
                binding.get("condition") is not None
                or set(binding.get("members", [])) - {member}
                for binding in matching
            )
            or len(matching) > 1
        ):
            raise CloudBootstrapAdapterError(
                "BOOTSTRAP_IDENTITY_CREATION_FAILED",
                "The gate-owned GCP role is bound outside the selected setup run.",
            )
        if matching and matching[0].get("members") == [member]:
            return
        bindings = list(policy.get("bindings", []))
        if matching:
            matching[0]["members"] = [member]
        else:
            bindings.append({"role": runtime.role_name, "members": [member]})
        policy["bindings"] = bindings
        GCPCloudBootstrapDriver._set_project_policy(transport, runtime, policy)

    @staticmethod
    def _create_generated_key(
        transport: GCPTransport,
        runtime: _GCPPlan,
    ) -> dict[str, Any]:
        existing_keys = GCPCloudBootstrapDriver._list_user_keys(
            transport,
            runtime.project_id,
            runtime.service_account_email,
        )
        if existing_keys:
            raise CloudBootstrapAdapterError(
                "BOOTSTRAP_CLEANUP_FAILED",
                "The gate-owned GCP service account contains an unrecorded user-managed key and requires manual reconciliation.",
            )
        response = transport.request(
            "POST",
            f"{GCPCloudBootstrapDriver._account_url(runtime)}/keys",
            json={
                "keyAlgorithm": "KEY_ALG_RSA_2048",
                "privateKeyType": "TYPE_GOOGLE_CREDENTIALS_FILE",
            },
        )
        if response.status_code == 403:
            raise CloudBootstrapAdapterError(
                "BOOTSTRAP_SCOPE_UNSUPPORTED",
                "GCP user-managed service-account key creation is blocked by the submitted authority or organization policy; guided setup will not weaken that policy.",
            )
        return GCPCloudBootstrapDriver._document(response, expected=(200,))

    @staticmethod
    def _generated_key_id(response: dict[str, Any], runtime: _GCPPlan) -> str:
        name = GCPCloudBootstrapDriver._required_string(response, "name")
        prefix = (
            f"projects/{runtime.project_id}/serviceAccounts/"
            f"{runtime.service_account_email}/keys/"
        )
        key_id = name.removeprefix(prefix)
        if (
            not name.startswith(prefix)
            or response.get("keyType") != "USER_MANAGED"
            or response.get("privateKeyType") != "TYPE_GOOGLE_CREDENTIALS_FILE"
            or response.get("keyAlgorithm") != "KEY_ALG_RSA_2048"
            or not KEY_ID_PATTERN.fullmatch(key_id)
        ):
            raise CloudBootstrapAdapterError(
                "BOOTSTRAP_IDENTITY_CREATION_FAILED",
                "GCP returned a generated key outside the setup-run identity boundary.",
            )
        return key_id

    @staticmethod
    def _decode_generated_key(
        response: dict[str, Any],
        runtime: _GCPPlan,
        *,
        expected_key_id: str,
        expected_client_id: str,
    ) -> dict[str, str]:
        encoded = GCPCloudBootstrapDriver._required_string(response, "privateKeyData")
        try:
            raw = base64.b64decode(encoded, validate=True).decode("utf-8")
            document = json.loads(raw)
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CloudBootstrapAdapterError(
                "BOOTSTRAP_IDENTITY_CREATION_FAILED",
                "GCP returned an invalid generated service-account key.",
            ) from exc
        required = {
            "type",
            "project_id",
            "private_key_id",
            "private_key",
            "client_email",
            "client_id",
            "token_uri",
        }
        if (
            not isinstance(document, dict)
            or not required.issubset(document)
            or any(
                not isinstance(document[key], str) or not document[key]
                for key in required
            )
            or document["type"] != "service_account"
            or document["project_id"] != runtime.project_id
            or document["private_key_id"] != expected_key_id
            or document["client_email"] != runtime.service_account_email
            or document["client_id"] != expected_client_id
            or document["token_uri"] != OAUTH_ENDPOINT
        ):
            raise CloudBootstrapAdapterError(
                "BOOTSTRAP_IDENTITY_CREATION_FAILED",
                "GCP returned a generated credential outside the setup-run identity boundary.",
            )
        return {str(key): str(value) for key, value in document.items()}

    def _validate_generated_credential(
        self,
        runtime: _GCPPlan,
        credential_info: dict[str, str],
    ) -> None:
        last_error: Exception | None = None
        for attempt in range(9):
            transport = self._transport_factory(credential_info)
            try:
                self._validate_project(transport, runtime.project_id)
                policy = self._get_project_policy(transport, runtime)
                member = f"serviceAccount:{runtime.service_account_email}"
                exact = [
                    item
                    for item in policy.get("bindings", [])
                    if item.get("role") == runtime.role_name
                    and item.get("members") == [member]
                    and item.get("condition") is None
                ]
                testable = {
                    "resourcemanager.projects.get",
                    "resourcemanager.projects.getIamPolicy",
                    "resourcemanager.projects.setIamPolicy",
                }
                checked = self._json_request(
                    transport,
                    "POST",
                    f"{CRM_ROOT}/projects/{runtime.project_id}:testIamPermissions",
                    body={"permissions": sorted(testable)},
                )
                granted = set(checked.get("permissions", []))
                self._verify_services(transport, runtime, runtime.services)
                if len(exact) != 1 or granted != testable:
                    raise self._invalid_credential()
                return
            except Exception as exc:
                last_error = exc
                if attempt < 8:
                    self._sleep(min(2**attempt, 30))
            finally:
                self._close(transport)
        raise CloudBootstrapAdapterError(
            "BOOTSTRAP_CONNECTION_VALIDATION_FAILED",
            "The generated GCP credential did not pass project, role-binding, permission, and API-baseline checks.",
        ) from last_error

    def _cleanup(
        self,
        transport: GCPTransport,
        receipt: CloudBootstrapRollbackReceipt,
        runtime: _GCPPlan,
    ) -> None:
        identifiers = dict(receipt.resource_ids)
        account_exists, role_active, binding_exists = (
            self._validate_cleanup_ownership(transport, runtime, identifiers)
        )
        key_id = identifiers.get("key_id")
        if key_id and account_exists:
            expected_name = self._key_name(
                runtime.project_id,
                runtime.service_account_email,
                key_id,
            )
            keys = self._list_user_keys(
                transport,
                runtime.project_id,
                runtime.service_account_email,
            )
            if expected_name not in {item.get("name") for item in keys}:
                raise CloudBootstrapAdapterError(
                    "BOOTSTRAP_CLEANUP_FAILED",
                    "The generated GCP key no longer matches the setup-run receipt.",
                )
            self._delete(transport, f"{IAM_ROOT}/{expected_name}")

        if identifiers.get("role_name") and binding_exists:
            self._remove_project_binding(transport, runtime)
        if identifiers.get("service_account_email") and account_exists:
            self._delete(transport, self._account_url(runtime))
        if identifiers.get("role_name") and role_active:
            response = transport.request("DELETE", f"{IAM_ROOT}/{runtime.role_name}")
            if response.status_code not in {200, 204, 404}:
                self._document(response, expected=(200, 204, 404))
            verify = transport.request(
                "GET",
                f"{IAM_ROOT}/{runtime.role_name}",
                params={"view": "FULL"},
            )
            if verify.status_code != 404:
                role = self._document(verify, expected=(200,))
                if role.get("deleted") is not True:
                    raise CloudBootstrapAdapterError(
                        "BOOTSTRAP_CLEANUP_FAILED",
                        "The gate-owned GCP custom role was not deactivated.",
                    )

    @staticmethod
    def _validate_cleanup_ownership(
        transport: GCPTransport,
        runtime: _GCPPlan,
        identifiers: dict[str, str],
    ) -> tuple[bool, bool, bool]:
        account_exists = False
        if identifiers.get("service_account_email"):
            response = transport.request(
                "GET", GCPCloudBootstrapDriver._account_url(runtime)
            )
            if response.status_code != 404:
                account = GCPCloudBootstrapDriver._document(
                    response, expected=(200,)
                )
                if (
                    account.get("email") != runtime.service_account_email
                    or account.get("displayName")
                    != f"Twin2MultiCloud {runtime.run_id}"
                    or account.get("description") != MANAGED_DESCRIPTION
                ):
                    raise CloudBootstrapAdapterError(
                        "BOOTSTRAP_CLEANUP_FAILED",
                        "GCP service-account ownership could not be proven for cleanup.",
                    )
                account_exists = True
                keys = GCPCloudBootstrapDriver._list_user_keys(
                    transport,
                    runtime.project_id,
                    runtime.service_account_email,
                )
                expected_key_id = identifiers.get("key_id")
                expected_keys = (
                    {
                        GCPCloudBootstrapDriver._key_name(
                            runtime.project_id,
                            runtime.service_account_email,
                            expected_key_id,
                        )
                    }
                    if expected_key_id is not None
                    else set()
                )
                if {key["name"] for key in keys} != expected_keys:
                    raise CloudBootstrapAdapterError(
                        "BOOTSTRAP_CLEANUP_FAILED",
                        "The GCP service-account key inventory does not match the setup-run receipt.",
                    )

        role_active = False
        binding_exists = False
        if identifiers.get("role_name"):
            response = transport.request(
                "GET",
                f"{IAM_ROOT}/{runtime.role_name}",
                params={"view": "FULL"},
            )
            if response.status_code != 404:
                role = GCPCloudBootstrapDriver._document(response, expected=(200,))
                if (
                    role.get("name") != runtime.role_name
                    or role.get("title") != f"Twin2MultiCloud {runtime.run_id}"
                    or role.get("description") != ROLE_DESCRIPTION
                ):
                    raise CloudBootstrapAdapterError(
                        "BOOTSTRAP_CLEANUP_FAILED",
                        "GCP custom-role ownership could not be proven for cleanup.",
                    )
                role_active = role.get("deleted") is not True
            policy = GCPCloudBootstrapDriver._get_project_policy(transport, runtime)
            member = f"serviceAccount:{runtime.service_account_email}"
            matching = [
                binding
                for binding in policy.get("bindings", [])
                if binding.get("role") == runtime.role_name
            ]
            if len(matching) > 1 or any(
                binding.get("members") != [member]
                or binding.get("condition") is not None
                for binding in matching
            ):
                raise CloudBootstrapAdapterError(
                    "BOOTSTRAP_CLEANUP_FAILED",
                    "The GCP deployment-role binding is not exclusively owned by the setup run.",
                )
            binding_exists = bool(matching)
        return account_exists, role_active, binding_exists

    @staticmethod
    def _remove_project_binding(transport: GCPTransport, runtime: _GCPPlan) -> None:
        policy = GCPCloudBootstrapDriver._get_project_policy(transport, runtime)
        policy["bindings"] = [
            binding
            for binding in policy.get("bindings", [])
            if binding.get("role") != runtime.role_name
        ]
        GCPCloudBootstrapDriver._set_project_policy(transport, runtime, policy)

    @staticmethod
    def _get_project_policy(
        transport: GCPTransport,
        runtime: _GCPPlan,
    ) -> dict[str, Any]:
        policy = GCPCloudBootstrapDriver._json_request(
            transport,
            "POST",
            f"{CRM_ROOT}/projects/{runtime.project_id}:getIamPolicy",
            body={"options": {"requestedPolicyVersion": 3}},
        )
        if (
            not isinstance(policy.get("bindings", []), list)
            or not isinstance(policy.get("etag"), str)
            or not policy.get("etag")
        ):
            raise CloudBootstrapAdapterError(
                "BOOTSTRAP_IDENTITY_CREATION_FAILED",
                "GCP returned an incomplete project IAM policy.",
            )
        return policy

    @staticmethod
    def _set_project_policy(
        transport: GCPTransport,
        runtime: _GCPPlan,
        policy: dict[str, Any],
    ) -> None:
        updated = GCPCloudBootstrapDriver._json_request(
            transport,
            "POST",
            f"{CRM_ROOT}/projects/{runtime.project_id}:setIamPolicy",
            body={"policy": policy, "updateMask": "bindings,etag,version"},
        )
        if not isinstance(updated.get("etag"), str) or not updated.get("etag"):
            raise CloudBootstrapAdapterError(
                "BOOTSTRAP_IDENTITY_CREATION_FAILED",
                "GCP did not confirm the project IAM policy update.",
            )

    @staticmethod
    def _list_user_keys(
        transport: GCPTransport,
        project_id: str,
        email: str,
    ) -> list[dict[str, Any]]:
        document = GCPCloudBootstrapDriver._json_request(
            transport,
            "GET",
            (
                f"{IAM_ROOT}/projects/{project_id}/serviceAccounts/"
                f"{quote(email, safe='')}/keys"
            ),
            params={"keyTypes": "USER_MANAGED"},
        )
        keys = document.get("keys", [])
        prefix = f"projects/{project_id}/serviceAccounts/{email}/keys/"
        if (
            not isinstance(keys, list)
            or any(
                not isinstance(item, dict)
                or item.get("keyType") != "USER_MANAGED"
                or not isinstance(item.get("name"), str)
                or not item["name"].startswith(prefix)
                or not KEY_ID_PATTERN.fullmatch(item["name"].removeprefix(prefix))
                for item in keys
            )
            or len({item["name"] for item in keys}) != len(keys)
        ):
            raise CloudBootstrapAdapterError(
                "BOOTSTRAP_IDENTITY_CREATION_FAILED",
                "GCP returned an incomplete service-account key inventory.",
            )
        return keys

    def _verify_provider_key_pair(
        self,
        transport: GCPTransport,
        project_id: str,
        email: str,
        key_id: str,
        private_key_pem: str,
    ) -> None:
        name = self._key_name(project_id, email, key_id)
        key = self._await_provider_key(transport, name)
        public_key_data = key.get("publicKeyData")
        if (
            key.get("name") != name
            or key.get("keyType") != "USER_MANAGED"
            or key.get("keyAlgorithm") != "KEY_ALG_RSA_2048"
            or not isinstance(public_key_data, str)
            or not public_key_data
            or not self._key_pair_verifier(private_key_pem, public_key_data)
        ):
            raise CloudBootstrapAdapterError(
                "BOOTSTRAP_CONNECTION_VALIDATION_FAILED",
                "The GCP private key does not cryptographically match the selected provider key ID.",
            )

    def _await_provider_key(
        self,
        transport: GCPTransport,
        name: str,
    ) -> dict[str, Any]:
        for attempt in range(7):
            response = transport.request(
                "GET",
                f"{IAM_ROOT}/{name}",
                params={"publicKeyType": "TYPE_X509_PEM_FILE"},
            )
            if response.status_code != 404:
                return self._document(response, expected=(200,))
            if attempt < 6:
                self._sleep(min(2**attempt, 30))
        raise CloudBootstrapAdapterError(
            "BOOTSTRAP_CONNECTION_VALIDATION_FAILED",
            "The selected GCP service-account key did not become visible within the setup-only wait window.",
        )

    @staticmethod
    def _account_url(runtime: _GCPPlan) -> str:
        return (
            f"{IAM_ROOT}/projects/{runtime.project_id}/serviceAccounts/"
            f"{quote(runtime.service_account_email, safe='')}"
        )

    @staticmethod
    def _key_name(project_id: str, email: str, key_id: str) -> str:
        return f"projects/{project_id}/serviceAccounts/{email}/keys/{key_id}"

    @staticmethod
    def _receipt(
        runtime: _GCPPlan,
        *,
        key_id: str | None = None,
        role_name: str | None = None,
        service_account_email: str,
    ) -> CloudBootstrapRollbackReceipt:
        values = {
            "key_id": key_id,
            "role_name": role_name,
            "service_account_email": service_account_email,
        }
        return CloudBootstrapRollbackReceipt(
            provider="gcp",
            run_id=runtime.run_id,
            resource_ids=tuple(
                (key, value) for key, value in values.items() if value is not None
            ),
        )

    @staticmethod
    def _json_request(
        transport: GCPTransport,
        method: str,
        url: str,
        *,
        body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        expected: tuple[int, ...] = (200,),
    ) -> dict[str, Any]:
        response = transport.request(method, url, json=body, params=params)
        return GCPCloudBootstrapDriver._document(response, expected=expected)

    @staticmethod
    def _document(
        response: GCPResponse,
        *,
        expected: tuple[int, ...],
    ) -> dict[str, Any]:
        if response.status_code not in expected:
            if response.status_code in {401, 403}:
                raise GCPCloudBootstrapDriver._invalid_credential()
            raise CloudBootstrapAdapterError(
                "BOOTSTRAP_IDENTITY_CREATION_FAILED",
                "GCP rejected the setup-only request.",
            )
        if response.status_code == 204:
            return {}
        try:
            document = response.json()
        except Exception as exc:
            raise CloudBootstrapAdapterError(
                "BOOTSTRAP_IDENTITY_CREATION_FAILED",
                "GCP returned an unreadable setup-only response.",
            ) from exc
        if not isinstance(document, dict):
            raise CloudBootstrapAdapterError(
                "BOOTSTRAP_IDENTITY_CREATION_FAILED",
                "GCP returned an incomplete setup-only response.",
            )
        return document

    @staticmethod
    def _delete(transport: GCPTransport, url: str) -> None:
        response = transport.request("DELETE", url)
        if response.status_code not in {200, 204, 404}:
            GCPCloudBootstrapDriver._document(response, expected=(200, 204, 404))

    @staticmethod
    def _required_string(document: dict[str, Any], key: str) -> str:
        value = document.get(key)
        if not isinstance(value, str) or not value:
            raise CloudBootstrapAdapterError(
                "BOOTSTRAP_IDENTITY_CREATION_FAILED",
                "GCP returned an incomplete setup-only response.",
            )
        return value

    @staticmethod
    def _required_numeric(document: dict[str, Any], key: str) -> str:
        value = str(document.get(key, ""))
        if not value.isdigit():
            raise CloudBootstrapAdapterError(
                "BOOTSTRAP_IDENTITY_CREATION_FAILED",
                "GCP returned an invalid project identifier.",
            )
        return value

    @staticmethod
    def _provisional_disposal(
        origin: CloudBootstrapCredentialOrigin,
    ) -> tuple[CloudBootstrapDisposalStatus, bool]:
        if origin == CloudBootstrapCredentialOrigin.EXISTING_USER_OWNED:
            return CloudBootstrapDisposalStatus.NOT_RETAINED_USER_MANAGED, False
        return CloudBootstrapDisposalStatus.MANUAL_REVOCATION_REQUIRED, True

    @staticmethod
    def _close(transport: GCPTransport) -> None:
        close = getattr(transport, "close", None)
        if callable(close):
            close()

    @staticmethod
    def _invalid_credential() -> CloudBootstrapAdapterError:
        return CloudBootstrapAdapterError(
            "BOOTSTRAP_CREDENTIAL_INVALID",
            "The GCP bootstrap credential does not match the selected existing project or supported service-account shape.",
        )
