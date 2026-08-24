"""Guided bootstrap provider adapter boundary and deterministic offline PoC."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import secrets
from typing import Mapping, Protocol, cast
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
from src.schemas.cloud_connection import CloudConnectionCreate, CloudProvider
from src.schemas.twin_config import AWSCredentials, AzureCredentials, GCPCredentials
from src.services.deployment_policy_materializer import (
    PolicyMaterializationError,
    load_gcp_phase8_api_baseline,
    materialize_aws_deployment_bundle,
    materialize_azure_custom_role,
    materialize_gcp_custom_role,
)


GCP_OAUTH_ENDPOINT = "https://oauth2.googleapis.com/token"
ROLLBACK_RESOURCE_KEYS = {
    "aws": frozenset({"access_key_id", "policy_arn", "user_name"}),
    "azure": frozenset(
        {
            "application_object_id",
            "credential_key_id",
            "role_assignment_id",
            "role_definition_id",
            "service_principal_object_id",
        }
    ),
    "gcp": frozenset({"key_id", "role_name", "service_account_email"}),
}


def bootstrap_run_id(session_id: str) -> str:
    """Return the one deterministic setup-run identifier for a session."""

    return f"twin2mc-e2e-{hashlib.sha256(session_id.encode('utf-8')).hexdigest()[:12]}"


class CloudBootstrapAdapterError(RuntimeError):
    """Safe provider-adapter failure without raw provider payloads."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class CloudBootstrapRollbackReceipt:
    """Secret-free provider resource identifiers needed for compensating cleanup."""

    provider: CloudProvider
    run_id: str
    resource_ids: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        identifiers = dict(self.resource_ids)
        if (
            not self.run_id.startswith("twin2mc-e2e-")
            or not identifiers
            or len(identifiers) != len(self.resource_ids)
            or not set(identifiers).issubset(ROLLBACK_RESOURCE_KEYS[self.provider])
            or any(
                not value or len(value) > 512 or "\n" in value or "\r" in value
                for value in identifiers.values()
            )
        ):
            raise ValueError("Invalid secret-free bootstrap rollback receipt.")


@dataclass(frozen=True)
class SupervisedLiveBootstrapPlan:
    """Immutable, secret-free provider input for one setup-only transaction."""

    provider: CloudProvider
    run_id: str
    deployment_document_json: str
    gcp_api_baseline_json: str | None = None

    def deployment_document(self) -> dict:
        return json.loads(self.deployment_document_json)

    def gcp_api_baseline(self) -> dict | None:
        return (
            json.loads(self.gcp_api_baseline_json)
            if self.gcp_api_baseline_json is not None
            else None
        )


@dataclass(frozen=True)
class CloudBootstrapAdapterResult:
    connection: CloudConnectionCreate
    safe_credential_identifier: str
    disposal_status: CloudBootstrapDisposalStatus
    credential_expires_at: datetime | None = None
    generated_credential_validated: bool = True
    rollback_receipt: CloudBootstrapRollbackReceipt | None = None
    bootstrap_finalization_required: bool = False


@dataclass(frozen=True)
class CloudBootstrapFinalizationResult:
    disposal_status: CloudBootstrapDisposalStatus
    credential_expires_at: datetime | None = None


class CloudBootstrapAdapter(Protocol):
    def supports_provider(self, provider: CloudProvider) -> bool: ...

    def execute(
        self,
        *,
        session_id: str,
        display_name: str,
        target: CloudBootstrapTarget,
        credential_origin: CloudBootstrapCredentialOrigin,
        credential: CloudBootstrapCredential,
    ) -> CloudBootstrapAdapterResult: ...

    def rollback(
        self,
        *,
        result: CloudBootstrapAdapterResult,
        target: CloudBootstrapTarget,
        credential: CloudBootstrapCredential,
    ) -> None: ...

    def finalize_bootstrap(
        self,
        *,
        result: CloudBootstrapAdapterResult,
        target: CloudBootstrapTarget,
        credential_origin: CloudBootstrapCredentialOrigin,
        credential: CloudBootstrapCredential,
    ) -> CloudBootstrapFinalizationResult: ...

    def cleanup_generated_access(
        self,
        *,
        receipt: CloudBootstrapRollbackReceipt,
        target: CloudBootstrapTarget,
        credential: CloudBootstrapCredential,
    ) -> None: ...

    def finalize_bootstrap_receipt(
        self,
        *,
        receipt: CloudBootstrapRollbackReceipt,
        target: CloudBootstrapTarget,
        credential_origin: CloudBootstrapCredentialOrigin,
        credential: CloudBootstrapCredential,
    ) -> CloudBootstrapFinalizationResult: ...


class SupervisedLiveProviderDriver(Protocol):
    """Provider boundary that self-compensates partial provision failures.

    ``provision`` must leave disposable bootstrap authority usable. Management
    invokes ``finalize_bootstrap`` only after the generated connection commits.
    """

    def provision(
        self,
        *,
        plan: SupervisedLiveBootstrapPlan,
        display_name: str,
        target: CloudBootstrapTarget,
        credential_origin: CloudBootstrapCredentialOrigin,
        credential: CloudBootstrapCredential,
    ) -> CloudBootstrapAdapterResult: ...

    def rollback(
        self,
        *,
        receipt: CloudBootstrapRollbackReceipt,
        target: CloudBootstrapTarget,
        credential: CloudBootstrapCredential,
    ) -> None: ...

    def finalize_bootstrap(
        self,
        *,
        receipt: CloudBootstrapRollbackReceipt,
        target: CloudBootstrapTarget,
        credential: CloudBootstrapCredential,
    ) -> CloudBootstrapFinalizationResult: ...


class DisabledCloudBootstrapAdapter:
    def supports_provider(self, provider: CloudProvider) -> bool:
        del provider
        return False

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

    def rollback(
        self,
        *,
        result: CloudBootstrapAdapterResult,
        target: CloudBootstrapTarget,
        credential: CloudBootstrapCredential,
    ) -> None:
        del result, target, credential

    def finalize_bootstrap(
        self,
        *,
        result: CloudBootstrapAdapterResult,
        target: CloudBootstrapTarget,
        credential_origin: CloudBootstrapCredentialOrigin,
        credential: CloudBootstrapCredential,
    ) -> CloudBootstrapFinalizationResult:
        del result, target, credential_origin, credential
        raise CloudBootstrapAdapterError(
            "BOOTSTRAP_IDENTITY_CREATION_FAILED",
            "Live provider bootstrap is disabled in this runtime.",
        )

    def cleanup_generated_access(
        self,
        *,
        receipt: CloudBootstrapRollbackReceipt,
        target: CloudBootstrapTarget,
        credential: CloudBootstrapCredential,
    ) -> None:
        del receipt, target, credential
        raise CloudBootstrapAdapterError(
            "BOOTSTRAP_CLEANUP_FAILED",
            "Generated provider access requires manual cleanup because live bootstrap is disabled.",
        )

    def finalize_bootstrap_receipt(
        self,
        *,
        receipt: CloudBootstrapRollbackReceipt,
        target: CloudBootstrapTarget,
        credential_origin: CloudBootstrapCredentialOrigin,
        credential: CloudBootstrapCredential,
    ) -> CloudBootstrapFinalizationResult:
        del receipt, target, credential_origin, credential
        raise CloudBootstrapAdapterError(
            "BOOTSTRAP_CLEANUP_FAILED",
            "The temporary bootstrap authority requires manual provider cleanup because live bootstrap is disabled.",
        )


class UnconfiguredSupervisedLiveCloudBootstrapAdapter:
    """Fail closed until reviewed provider implementations are wired in."""

    def supports_provider(self, provider: CloudProvider) -> bool:
        del provider
        return False

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
            "Supervised live bootstrap has no reviewed provider adapter configured.",
        )

    def rollback(
        self,
        *,
        result: CloudBootstrapAdapterResult,
        target: CloudBootstrapTarget,
        credential: CloudBootstrapCredential,
    ) -> None:
        del result, target, credential

    def finalize_bootstrap(
        self,
        *,
        result: CloudBootstrapAdapterResult,
        target: CloudBootstrapTarget,
        credential_origin: CloudBootstrapCredentialOrigin,
        credential: CloudBootstrapCredential,
    ) -> CloudBootstrapFinalizationResult:
        del result, target, credential_origin, credential
        raise CloudBootstrapAdapterError(
            "BOOTSTRAP_IDENTITY_CREATION_FAILED",
            "Supervised live bootstrap has no reviewed provider adapter configured.",
        )

    def cleanup_generated_access(
        self,
        *,
        receipt: CloudBootstrapRollbackReceipt,
        target: CloudBootstrapTarget,
        credential: CloudBootstrapCredential,
    ) -> None:
        del receipt, target, credential
        raise CloudBootstrapAdapterError(
            "BOOTSTRAP_CLEANUP_FAILED",
            "Generated provider access requires manual cleanup because its adapter is unavailable.",
        )

    def finalize_bootstrap_receipt(
        self,
        *,
        receipt: CloudBootstrapRollbackReceipt,
        target: CloudBootstrapTarget,
        credential_origin: CloudBootstrapCredentialOrigin,
        credential: CloudBootstrapCredential,
    ) -> CloudBootstrapFinalizationResult:
        del receipt, target, credential_origin, credential
        raise CloudBootstrapAdapterError(
            "BOOTSTRAP_CLEANUP_FAILED",
            "The temporary bootstrap authority requires manual provider cleanup because its adapter is unavailable.",
        )


class SupervisedLiveCloudBootstrapAdapter:
    """SDK-independent setup-only orchestration over reviewed provider drivers."""

    def __init__(self, drivers: Mapping[CloudProvider, SupervisedLiveProviderDriver]):
        self._drivers = dict(drivers)

    def supports_provider(self, provider: CloudProvider) -> bool:
        return provider in self._drivers

    def execute(
        self,
        *,
        session_id: str,
        display_name: str,
        target: CloudBootstrapTarget,
        credential_origin: CloudBootstrapCredentialOrigin,
        credential: CloudBootstrapCredential,
    ) -> CloudBootstrapAdapterResult:
        self._validate_input_shape(target, credential)
        provider = cast(CloudProvider, target.provider)
        driver = self._drivers.get(provider)
        if driver is None:
            raise CloudBootstrapAdapterError(
                "BOOTSTRAP_IDENTITY_CREATION_FAILED",
                "The selected provider has no reviewed supervised adapter configured.",
            )
        try:
            plan = self._plan(session_id, target)
            result = driver.provision(
                plan=plan,
                display_name=display_name,
                target=target,
                credential_origin=credential_origin,
                credential=credential,
            )
        except CloudBootstrapAdapterError:
            raise
        except (PolicyMaterializationError, ValueError) as exc:
            raise CloudBootstrapAdapterError(
                "BOOTSTRAP_AUTHORITY_PACK_MISMATCH",
                "The reviewed provider policy could not be materialized safely.",
            ) from exc
        except Exception as exc:
            raise CloudBootstrapAdapterError(
                "BOOTSTRAP_IDENTITY_CREATION_FAILED",
                "The supervised provider transaction failed without exposing provider details.",
            ) from exc

        try:
            self._validate_result(
                result,
                plan,
                display_name,
                target,
                credential_origin,
            )
        except CloudBootstrapAdapterError as validation_error:
            try:
                self.rollback(result=result, target=target, credential=credential)
            except CloudBootstrapAdapterError as cleanup_error:
                raise cleanup_error from validation_error
            raise
        return result

    def finalize_bootstrap(
        self,
        *,
        result: CloudBootstrapAdapterResult,
        target: CloudBootstrapTarget,
        credential_origin: CloudBootstrapCredentialOrigin,
        credential: CloudBootstrapCredential,
    ) -> CloudBootstrapFinalizationResult:
        if not result.bootstrap_finalization_required:
            return CloudBootstrapFinalizationResult(
                disposal_status=result.disposal_status,
                credential_expires_at=result.credential_expires_at,
            )
        receipt = result.rollback_receipt
        if receipt is None:
            raise CloudBootstrapAdapterError(
                "BOOTSTRAP_CLEANUP_FAILED",
                "The temporary bootstrap authority requires manual provider cleanup.",
            )
        return self.finalize_bootstrap_receipt(
            receipt=receipt,
            target=target,
            credential_origin=credential_origin,
            credential=credential,
        )

    def finalize_bootstrap_receipt(
        self,
        *,
        receipt: CloudBootstrapRollbackReceipt,
        target: CloudBootstrapTarget,
        credential_origin: CloudBootstrapCredentialOrigin,
        credential: CloudBootstrapCredential,
    ) -> CloudBootstrapFinalizationResult:
        if credential_origin == CloudBootstrapCredentialOrigin.EXISTING_USER_OWNED:
            return CloudBootstrapFinalizationResult(
                disposal_status=(
                    CloudBootstrapDisposalStatus.NOT_RETAINED_USER_MANAGED
                ),
            )
        if credential_origin != CloudBootstrapCredentialOrigin.DEDICATED_DISPOSABLE:
            raise CloudBootstrapAdapterError(
                "BOOTSTRAP_CLEANUP_FAILED",
                "The bootstrap credential origin cannot be finalized safely.",
            )
        if target.provider != receipt.provider or credential.provider != receipt.provider:
            raise CloudBootstrapAdapterError(
                "BOOTSTRAP_CLEANUP_FAILED",
                "The temporary bootstrap authority requires manual cleanup because its scope is inconsistent.",
            )
        driver = self._drivers.get(receipt.provider)
        if driver is None:
            raise CloudBootstrapAdapterError(
                "BOOTSTRAP_CLEANUP_FAILED",
                "The temporary bootstrap authority requires manual cleanup because its adapter is unavailable.",
            )
        try:
            finalization = driver.finalize_bootstrap(
                receipt=receipt,
                target=target,
                credential=credential,
            )
        except Exception as exc:
            raise CloudBootstrapAdapterError(
                "BOOTSTRAP_CLEANUP_FAILED",
                "The temporary bootstrap authority could not be revoked automatically; manual cleanup is required.",
            ) from exc
        if finalization.disposal_status not in {
            CloudBootstrapDisposalStatus.REVOKED,
            CloudBootstrapDisposalStatus.EXPIRES_AT_PROVIDER,
            CloudBootstrapDisposalStatus.MANUAL_REVOCATION_REQUIRED,
        } or (
            finalization.disposal_status
            == CloudBootstrapDisposalStatus.EXPIRES_AT_PROVIDER
        ) != (finalization.credential_expires_at is not None):
            raise CloudBootstrapAdapterError(
                "BOOTSTRAP_CLEANUP_FAILED",
                "The temporary bootstrap authority returned an invalid disposal result.",
            )
        return finalization

    def rollback(
        self,
        *,
        result: CloudBootstrapAdapterResult,
        target: CloudBootstrapTarget,
        credential: CloudBootstrapCredential,
    ) -> None:
        receipt = result.rollback_receipt
        if receipt is None:
            return
        self.cleanup_generated_access(
            receipt=receipt,
            target=target,
            credential=credential,
        )

    def cleanup_generated_access(
        self,
        *,
        receipt: CloudBootstrapRollbackReceipt,
        target: CloudBootstrapTarget,
        credential: CloudBootstrapCredential,
    ) -> None:
        if (
            target.provider != receipt.provider
            or credential.provider != receipt.provider
        ):
            raise CloudBootstrapAdapterError(
                "BOOTSTRAP_CLEANUP_FAILED",
                "Generated provider access requires manual cleanup because its rollback scope is inconsistent.",
            )
        driver = self._drivers.get(receipt.provider)
        if driver is None:
            raise CloudBootstrapAdapterError(
                "BOOTSTRAP_CLEANUP_FAILED",
                "Generated provider access requires manual cleanup because its adapter is unavailable.",
            )
        try:
            driver.rollback(
                receipt=receipt,
                target=target,
                credential=credential,
            )
        except Exception as exc:
            raise CloudBootstrapAdapterError(
                "BOOTSTRAP_CLEANUP_FAILED",
                "Generated provider access could not be cleaned up automatically; manual cleanup is required.",
            ) from exc

    @staticmethod
    def _plan(
        session_id: str,
        target: CloudBootstrapTarget,
    ) -> SupervisedLiveBootstrapPlan:
        run_id = bootstrap_run_id(session_id)
        baseline = None
        if isinstance(target, AWSBootstrapTarget):
            provider: CloudProvider = "aws"
            document = materialize_aws_deployment_bundle(
                account_id=target.account_id,
                run_id=run_id,
            )
        elif isinstance(target, AzureBootstrapTarget):
            provider = "azure"
            document = materialize_azure_custom_role(
                subscription_id=target.subscription_id,
                run_id=run_id,
            )
        elif isinstance(target, GCPExistingProjectBootstrapTarget):
            provider = "gcp"
            document = materialize_gcp_custom_role(
                project_id=target.project_id,
                run_id=run_id,
            )
            baseline = load_gcp_phase8_api_baseline()
        else:
            raise CloudBootstrapAdapterError(
                "BOOTSTRAP_SCOPE_UNSUPPORTED",
                "Supervised GCP setup supports an existing project only.",
            )
        return SupervisedLiveBootstrapPlan(
            provider=provider,
            run_id=run_id,
            deployment_document_json=json.dumps(
                document,
                sort_keys=True,
                separators=(",", ":"),
            ),
            gcp_api_baseline_json=(
                json.dumps(baseline, sort_keys=True, separators=(",", ":"))
                if baseline is not None
                else None
            ),
        )

    @staticmethod
    def _validate_input_shape(
        target: CloudBootstrapTarget,
        credential: CloudBootstrapCredential,
    ) -> None:
        valid = (
            (
                isinstance(target, AWSBootstrapTarget)
                and isinstance(credential, AWSBootstrapCredential)
            )
            or (
                isinstance(target, AzureBootstrapTarget)
                and isinstance(credential, AzureBootstrapCredential)
            )
            or (
                isinstance(target, GCPExistingProjectBootstrapTarget)
                and isinstance(credential, GCPBootstrapCredential)
            )
        )
        if not valid or target.provider != credential.provider:
            raise CloudBootstrapAdapterError(
                "BOOTSTRAP_CREDENTIAL_INVALID",
                "The provider credential does not match the selected supervised target.",
            )

    @staticmethod
    def _validate_result(
        result: CloudBootstrapAdapterResult,
        plan: SupervisedLiveBootstrapPlan,
        display_name: str,
        target: CloudBootstrapTarget,
        credential_origin: CloudBootstrapCredentialOrigin,
    ) -> None:
        expected_auth = {
            "aws": "access_key",
            "azure": "service_principal",
            "gcp": "service_account_key",
        }[plan.provider]
        connection = result.connection
        receipt = result.rollback_receipt
        scope = connection.cloud_scope
        if isinstance(target, AWSBootstrapTarget):
            expected_scope = {
                "account_id": target.account_id,
                "region": target.region,
            }
        elif isinstance(target, AzureBootstrapTarget):
            expected_scope = {
                "tenant_id": target.tenant_id,
                "subscription_id": target.subscription_id,
                "region": target.region,
            }
        else:
            expected_scope = target.model_dump(mode="json", exclude_none=True)
        expected_scope["bootstrap_mode"] = "supervised_live"
        expected_finalization = (
            credential_origin == CloudBootstrapCredentialOrigin.DEDICATED_DISPOSABLE
            and result.disposal_status
            == CloudBootstrapDisposalStatus.MANUAL_REVOCATION_REQUIRED
        )
        existing_owned = (
            credential_origin == CloudBootstrapCredentialOrigin.EXISTING_USER_OWNED
            and result.disposal_status
            == CloudBootstrapDisposalStatus.NOT_RETAINED_USER_MANAGED
            and not result.bootstrap_finalization_required
        )
        expiring = (
            credential_origin == CloudBootstrapCredentialOrigin.DEDICATED_DISPOSABLE
            and result.disposal_status
            == CloudBootstrapDisposalStatus.EXPIRES_AT_PROVIDER
            and result.credential_expires_at is not None
            and not result.bootstrap_finalization_required
        )
        if (
            connection.provider != plan.provider
            or connection.purpose != "deployment"
            or connection.display_name != display_name
            or connection.auth_type != expected_auth
            or connection.permission_set_version != "thesis-demo-v2"
            or scope != expected_scope
            or not result.generated_credential_validated
            or not result.safe_credential_identifier.strip()
            or len(result.safe_credential_identifier) > 256
            or "\n" in result.safe_credential_identifier
            or "\r" in result.safe_credential_identifier
            or receipt is None
            or receipt.provider != plan.provider
            or receipt.run_id != plan.run_id
            or result.disposal_status
            == CloudBootstrapDisposalStatus.RELEASED_AFTER_FAILURE
            or not (existing_owned or expiring or expected_finalization)
            or result.bootstrap_finalization_required != expected_finalization
        ):
            raise CloudBootstrapAdapterError(
                "BOOTSTRAP_CONNECTION_VALIDATION_FAILED",
                "The generated deployment credential did not satisfy the reviewed connection boundary.",
            )


class DeterministicFakeCloudBootstrapAdapter:
    """No-cloud adapter with real lifecycle semantics for thesis verification."""

    def supports_provider(self, provider: CloudProvider) -> bool:
        return provider in {"aws", "azure", "gcp"}

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
            return self._aws(
                session_id, display_name, target, credential_origin, credential
            )
        if target.provider == "azure":
            return self._azure(
                session_id, display_name, target, credential_origin, credential
            )
        return self._gcp(
            session_id, display_name, target, credential_origin, credential
        )

    def rollback(
        self,
        *,
        result: CloudBootstrapAdapterResult,
        target: CloudBootstrapTarget,
        credential: CloudBootstrapCredential,
    ) -> None:
        del result, target, credential

    def finalize_bootstrap(
        self,
        *,
        result: CloudBootstrapAdapterResult,
        target: CloudBootstrapTarget,
        credential_origin: CloudBootstrapCredentialOrigin,
        credential: CloudBootstrapCredential,
    ) -> CloudBootstrapFinalizationResult:
        del target, credential_origin, credential
        return CloudBootstrapFinalizationResult(
            disposal_status=result.disposal_status,
            credential_expires_at=result.credential_expires_at,
        )

    def cleanup_generated_access(
        self,
        *,
        receipt: CloudBootstrapRollbackReceipt,
        target: CloudBootstrapTarget,
        credential: CloudBootstrapCredential,
    ) -> None:
        if target.provider != receipt.provider or credential.provider != receipt.provider:
            raise CloudBootstrapAdapterError(
                "BOOTSTRAP_CLEANUP_FAILED",
                "The offline cleanup receipt does not match its provider scope.",
            )

    def finalize_bootstrap_receipt(
        self,
        *,
        receipt: CloudBootstrapRollbackReceipt,
        target: CloudBootstrapTarget,
        credential_origin: CloudBootstrapCredentialOrigin,
        credential: CloudBootstrapCredential,
    ) -> CloudBootstrapFinalizationResult:
        if target.provider != receipt.provider or credential.provider != receipt.provider:
            raise CloudBootstrapAdapterError(
                "BOOTSTRAP_CLEANUP_FAILED",
                "The offline bootstrap receipt does not match its provider scope.",
            )
        return CloudBootstrapFinalizationResult(
            disposal_status=(
                CloudBootstrapDisposalStatus.NOT_RETAINED_USER_MANAGED
                if credential_origin
                == CloudBootstrapCredentialOrigin.EXISTING_USER_OWNED
                else CloudBootstrapDisposalStatus.REVOKED
            )
        )

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
            expiry=target.session_expires_at
            if credential.session_token is not None
            else None,
        )
        return CloudBootstrapAdapterResult(
            connection=connection,
            safe_credential_identifier=access_key_id,
            disposal_status=disposal,
            credential_expires_at=expiry,
            rollback_receipt=CloudBootstrapRollbackReceipt(
                provider="aws",
                run_id=bootstrap_run_id(session_id),
                resource_ids=(("user_name", f"{bootstrap_run_id(session_id)}-deployer"),),
            ),
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
        safe_id = (
            target.bootstrap_credential_key_id
            or credential.client_id.get_secret_value()
        )
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
            rollback_receipt=CloudBootstrapRollbackReceipt(
                provider="azure",
                run_id=bootstrap_run_id(session_id),
                resource_ids=(("application_object_id", generated_client_id),),
            ),
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
            rollback_receipt=CloudBootstrapRollbackReceipt(
                provider="gcp",
                run_id=bootstrap_run_id(session_id),
                resource_ids=(("service_account_email", email),),
            ),
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
