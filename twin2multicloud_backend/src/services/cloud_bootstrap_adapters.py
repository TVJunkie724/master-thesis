"""Guided bootstrap provider adapter boundary and deterministic offline PoC."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import secrets
import uuid

from src.schemas.cloud_bootstrap import (
    AWSBootstrapCredential,
    AWSBootstrapTarget,
    AzureBootstrapCredential,
    AzureBootstrapTarget,
    CloudBootstrapCredential,
    CloudBootstrapCredentialOrigin,
    CloudBootstrapDisposalStatus,
    CloudBootstrapTarget,
    GCPBootstrapCredential,
    GCPExistingProjectBootstrapTarget,
    GCPOrganizationBootstrapTarget,
)
from src.schemas.cloud_connection import CloudConnectionCreate
from src.schemas.twin_config import AWSCredentials, AzureCredentials, GCPCredentials


GCP_OAUTH_ENDPOINT = "https://oauth2.googleapis.com/token"


class CloudBootstrapAdapterError(RuntimeError):
    """Safe provider-adapter failure without raw provider payloads."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class CloudBootstrapAdapterResult:
    connection: CloudConnectionCreate
    safe_credential_identifier: str
    disposal_status: CloudBootstrapDisposalStatus
    credential_expires_at: datetime | None = None


class DisabledCloudBootstrapAdapter:
    def execute(
        self,
        *,
        session_id: str,
        display_name: str,
        target: CloudBootstrapTarget,
        credential_origin: CloudBootstrapCredentialOrigin,
        credential: CloudBootstrapCredential,
    ) -> CloudBootstrapAdapterResult:
        del session_id, display_name, target, credential_origin, credential
        raise CloudBootstrapAdapterError(
            "BOOTSTRAP_IDENTITY_CREATION_FAILED",
            "Live provider bootstrap is disabled in this runtime.",
        )


class DeterministicFakeCloudBootstrapAdapter:
    """No-cloud adapter with real lifecycle semantics for thesis verification."""

    def execute(
        self,
        *,
        session_id: str,
        display_name: str,
        target: CloudBootstrapTarget,
        credential_origin: CloudBootstrapCredentialOrigin,
        credential: CloudBootstrapCredential,
    ) -> CloudBootstrapAdapterResult:
        if target.provider != credential.provider:
            raise CloudBootstrapAdapterError(
                "BOOTSTRAP_CREDENTIAL_INVALID",
                "The submitted credential provider does not match the target.",
            )
        if target.provider == "aws":
            return self._aws(session_id, display_name, target, credential_origin, credential)
        if target.provider == "azure":
            return self._azure(session_id, display_name, target, credential_origin, credential)
        return self._gcp(session_id, display_name, target, credential_origin, credential)

    def _aws(
        self,
        session_id: str,
        display_name: str,
        target: CloudBootstrapTarget,
        origin: CloudBootstrapCredentialOrigin,
        credential: CloudBootstrapCredential,
    ) -> CloudBootstrapAdapterResult:
        if not isinstance(target, AWSBootstrapTarget) or not isinstance(
            credential, AWSBootstrapCredential
        ):
            raise self._invalid_shape()
        access_key_id = credential.access_key_id.get_secret_value()
        if not access_key_id.startswith(("AKIA", "ASIA")):
            raise CloudBootstrapAdapterError(
                "BOOTSTRAP_CREDENTIAL_INVALID",
                "The AWS access-key identifier has an unsupported shape.",
            )
        if credential.session_token is not None and target.session_expires_at is None:
            raise CloudBootstrapAdapterError(
                "BOOTSTRAP_CREDENTIAL_INVALID",
                "An AWS session credential requires its provider-issued expiry.",
            )
        suffix = self._suffix(session_id)
        connection = CloudConnectionCreate(
            provider="aws",
            purpose="deployment",
            display_name=display_name,
            auth_type="access_key",
            permission_set_version="thesis-demo-v2",
            cloud_scope={
                "account_id": target.account_id,
                "region": target.region,
                "bootstrap_mode": "offline_fake",
            },
            aws=AWSCredentials(
                access_key_id=f"AKIA{suffix[:16].upper()}",
                secret_access_key=secrets.token_urlsafe(32),
                region=target.region,
            ),
        )
        disposal, expiry = self._disposal(
            origin,
            manual="MANUAL" in access_key_id.upper(),
            expiry=target.session_expires_at if credential.session_token is not None else None,
        )
        return CloudBootstrapAdapterResult(
            connection=connection,
            safe_credential_identifier=access_key_id,
            disposal_status=disposal,
            credential_expires_at=expiry,
        )

    def _azure(
        self,
        session_id: str,
        display_name: str,
        target: CloudBootstrapTarget,
        origin: CloudBootstrapCredentialOrigin,
        credential: CloudBootstrapCredential,
    ) -> CloudBootstrapAdapterResult:
        if not isinstance(target, AzureBootstrapTarget) or not isinstance(
            credential, AzureBootstrapCredential
        ):
            raise self._invalid_shape()
        tenant_id = credential.tenant_id.get_secret_value()
        subscription_id = credential.subscription_id.get_secret_value()
        if tenant_id != target.tenant_id or subscription_id != target.subscription_id:
            raise CloudBootstrapAdapterError(
                "BOOTSTRAP_CREDENTIAL_INVALID",
                "The Azure credential scope does not match the selected tenant and subscription.",
            )
        namespace = uuid.UUID("00000000-0000-4000-8000-000000000154")
        generated_client_id = str(uuid.uuid5(namespace, f"client:{session_id}"))
        connection = CloudConnectionCreate(
            provider="azure",
            purpose="deployment",
            display_name=display_name,
            auth_type="service_principal",
            permission_set_version="thesis-demo-v2",
            cloud_scope={
                "tenant_id": target.tenant_id,
                "subscription_id": target.subscription_id,
                "region": target.region,
                "bootstrap_mode": "offline_fake",
            },
            azure=AzureCredentials(
                subscription_id=target.subscription_id,
                client_id=generated_client_id,
                client_secret=secrets.token_urlsafe(32),
                tenant_id=target.tenant_id,
                region=target.region,
            ),
        )
        safe_id = target.bootstrap_credential_key_id or credential.client_id.get_secret_value()
        disposal, expiry = self._disposal(
            origin,
            manual=(
                target.bootstrap_credential_key_id is None
                or "manual" in safe_id.lower()
            ),
        )
        return CloudBootstrapAdapterResult(
            connection=connection,
            safe_credential_identifier=safe_id,
            disposal_status=disposal,
            credential_expires_at=expiry,
        )

    def _gcp(
        self,
        session_id: str,
        display_name: str,
        target: CloudBootstrapTarget,
        origin: CloudBootstrapCredentialOrigin,
        credential: CloudBootstrapCredential,
    ) -> CloudBootstrapAdapterResult:
        if not isinstance(
            target,
            (GCPExistingProjectBootstrapTarget, GCPOrganizationBootstrapTarget),
        ) or not isinstance(credential, GCPBootstrapCredential):
            raise self._invalid_shape()
        target_project = (
            target.project_id
            if isinstance(target, GCPExistingProjectBootstrapTarget)
            else target.bootstrap_project_id
        )
        if credential.project_id != target_project:
            raise CloudBootstrapAdapterError(
                "BOOTSTRAP_CREDENTIAL_INVALID",
                "The GCP credential project does not match the selected bootstrap project.",
            )
        suffix = self._suffix(session_id)[:12]
        email = f"twin2mc-{suffix}@{target_project}.iam.gserviceaccount.com"
        service_account = {
            "type": "service_account",
            "project_id": target_project,
            "private_key_id": self._suffix(f"key:{session_id}"),
            "private_key": f"offline-fake-{secrets.token_urlsafe(32)}",
            "client_email": email,
            "client_id": str(int(self._suffix(f"client:{session_id}")[:15], 16)),
            "token_uri": GCP_OAUTH_ENDPOINT,
        }
        cloud_scope = target.model_dump(mode="json")
        cloud_scope["bootstrap_mode"] = "offline_fake"
        connection = CloudConnectionCreate(
            provider="gcp",
            purpose="deployment",
            display_name=display_name,
            auth_type="service_account_key",
            permission_set_version="thesis-demo-v2",
            cloud_scope=cloud_scope,
            gcp=GCPCredentials(
                project_id=target_project,
                billing_account=(
                    target.billing_account_id
                    if isinstance(target, GCPOrganizationBootstrapTarget)
                    else None
                ),
                service_account_json=json.dumps(service_account, sort_keys=True),
                region=target.region,
            ),
        )
        key_id = credential.private_key_id.get_secret_value()
        disposal, expiry = self._disposal(
            origin,
            manual="manual" in key_id.lower(),
        )
        return CloudBootstrapAdapterResult(
            connection=connection,
            safe_credential_identifier=key_id,
            disposal_status=disposal,
            credential_expires_at=expiry,
        )

    @staticmethod
    def _suffix(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _disposal(
        origin: CloudBootstrapCredentialOrigin,
        *,
        manual: bool,
        expiry: datetime | None = None,
    ) -> tuple[CloudBootstrapDisposalStatus, datetime | None]:
        if origin == CloudBootstrapCredentialOrigin.EXISTING_USER_OWNED:
            return CloudBootstrapDisposalStatus.NOT_RETAINED_USER_MANAGED, None
        if expiry is not None:
            return CloudBootstrapDisposalStatus.EXPIRES_AT_PROVIDER, expiry
        if manual:
            return CloudBootstrapDisposalStatus.MANUAL_REVOCATION_REQUIRED, None
        return CloudBootstrapDisposalStatus.REVOKED, None

    @staticmethod
    def _invalid_shape() -> CloudBootstrapAdapterError:
        return CloudBootstrapAdapterError(
            "BOOTSTRAP_CREDENTIAL_INVALID",
            "The provider credential does not match the selected target.",
        )
