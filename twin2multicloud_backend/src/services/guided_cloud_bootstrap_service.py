"""Owner-scoped guided cloud-bootstrap lifecycle."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import secrets
from typing import Any, cast
import uuid

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from src.config import settings
from src.models.cloud_bootstrap_session import CloudBootstrapSession
from src.models.twin import DigitalTwin, TwinState
from src.repositories.architecture_repository import ArchitectureRepository
from src.repositories.cloud_bootstrap_repository import CloudBootstrapRepository
from src.security.request_context import current_request_id
from src.schemas.cloud_bootstrap import (
    AWSBootstrapCredential,
    AWSBootstrapTarget,
    AzureBootstrapCredential,
    AzureBootstrapTarget,
    CloudBootstrapCredential,
    CloudBootstrapConnectionSummary,
    CloudBootstrapApiBaseline,
    CloudBootstrapCredentialOrigin,
    CloudBootstrapDisposalStatus,
    CloudBootstrapEntryPoint,
    CloudBootstrapExecutionKind,
    CloudBootstrapExecuteRequest,
    CloudBootstrapFinding,
    CloudBootstrapGuidePackReference,
    CloudBootstrapGuideResponse,
    CloudBootstrapInstruction,
    CloudBootstrapPackReference,
    CloudBootstrapSessionCreateRequest,
    CloudBootstrapSessionListResponse,
    CloudBootstrapSessionResponse,
    CloudBootstrapSetupCleanupRequest,
    CloudBootstrapSetupCleanupResponse,
    CloudBootstrapSetupReceiptResponse,
    CloudBootstrapState,
    CloudBootstrapTarget,
    GCPBootstrapCredential,
    GCPExistingProjectBootstrapTarget,
    GCPOrganizationBootstrapTarget,
)
from src.schemas.cloud_connection import CloudProvider
from src.schemas.credential_security_event import (
    CredentialSecurityAction,
    CredentialSecurityEventDraft,
    CredentialSecurityOutcome,
)
from src.services.cloud_bootstrap_adapters import (
    CloudBootstrapAdapter,
    CloudBootstrapAdapterError,
    CloudBootstrapAdapterResult,
    CloudBootstrapRollbackReceipt,
    DeterministicFakeCloudBootstrapAdapter,
    DisabledCloudBootstrapAdapter,
    SupervisedLiveCloudBootstrapAdapter,
    UnconfiguredSupervisedLiveCloudBootstrapAdapter,
    bootstrap_run_id,
)
from src.services.aws_cloud_bootstrap_driver import AWSCloudBootstrapDriver
from src.services.azure_cloud_bootstrap_driver import AzureCloudBootstrapDriver
from src.services.gcp_cloud_bootstrap_driver import GCPCloudBootstrapDriver
from src.services.cloud_bootstrap_errors import CloudBootstrapDomainError
from src.services.cloud_connection_service import CloudConnectionService
from src.services.credential_security_audit_service import (
    CredentialSecurityAuditService,
)
from src.services.provider_contract import normalize_provider_id


CONTRACT_ROOT = (
    Path(__file__).resolve().parents[1]
    / "contracts"
    / "generated"
    / "cloud-bootstrap"
    / "v1"
)


PROVIDER_GUIDANCE: dict[str, dict[str, Any]] = {
    "aws": {
        "credential_fields": [
            ("access_key_id", "Access key ID", "identifier", True, "identifier"),
            ("secret_access_key", "Secret access key", "secret", True, "secret"),
            ("session_token", "Session token", "secret", False, "secret"),
        ],
        "steps": [
            (
                "select_account",
                "Select the AWS account",
                "Sign in as a non-root administrator and select the target account.",
                "The twelve-digit account ID and target region are known.",
                "https://docs.aws.amazon.com/IAM/latest/UserGuide/introduction_identity-management.html",
            ),
            (
                "create_temporary_authority",
                "Create temporary bootstrap authority",
                "Create a dedicated temporary IAM credential or obtain a short STS session that matches bootstrap.aws.admin-v2.",
                "The access key material is copied once and any STS expiry is recorded.",
                "https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_access-keys.html",
            ),
        ],
    },
    "azure": {
        "credential_fields": [
            ("tenant_id", "Tenant ID", "identifier", True, "identifier"),
            ("subscription_id", "Subscription ID", "identifier", True, "identifier"),
            ("client_id", "Client ID", "identifier", True, "identifier"),
            ("client_secret", "Client secret", "secret", True, "secret"),
        ],
        "steps": [
            (
                "select_tenant_subscription",
                "Select tenant and subscription",
                "Sign in to the correct Entra tenant and select the target subscription.",
                "Tenant, subscription, and region match the displayed target.",
                "https://learn.microsoft.com/en-us/azure/role-based-access-control/scope-overview",
            ),
            (
                "create_temporary_application",
                "Create temporary bootstrap application",
                "Create a dedicated bootstrap application/service principal with bootstrap.azure.admin-v2 directory and subscription authority.",
                "Client ID, one short-lived secret, and its safe key ID are available.",
                "https://learn.microsoft.com/en-us/entra/identity-platform/howto-create-service-principal-portal",
            ),
        ],
    },
    "gcp": {
        "credential_fields": [
            (
                "service_account_json",
                "Service-account JSON",
                "json",
                True,
                "private_key_document",
            ),
        ],
        "steps": [
            (
                "select_gcp_scope",
                "Select the GCP scope",
                "Confirm the existing billing-enabled project shown above; the first supervised PoC gate does not admit organization/project-creation mode.",
                "The existing project ID and target region are known.",
                "https://cloud.google.com/resource-manager/docs/cloud-platform-resource-hierarchy",
            ),
            (
                "enable_bootstrap_prerequisites",
                "Enable bootstrap prerequisite APIs",
                "Ensure Service Usage, IAM, and Cloud Resource Manager are available before creating the temporary bootstrap identity.",
                "The three prerequisite APIs are enabled; no Twin workload has been created.",
                "https://docs.cloud.google.com/service-usage/docs/enable-disable",
            ),
            (
                "create_temporary_service_account",
                "Create temporary bootstrap service account",
                "Bind bootstrap.gcp.admin-v3 and create one JSON key only when organization policy permits it.",
                "One service-account JSON document is downloaded and no key policy was weakened.",
                "https://cloud.google.com/iam/docs/keys-create-delete",
            ),
        ],
    },
}


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: Any) -> str:
    return (
        f"sha256:{hashlib.sha256(_canonical_json(value).encode('utf-8')).hexdigest()}"
    )


class GuidedCloudBootstrapService:
    def __init__(
        self,
        db: Session,
        *,
        adapter: CloudBootstrapAdapter | None = None,
    ):
        self._db = db
        self._repo = CloudBootstrapRepository(db)
        self._connections = CloudConnectionService(db)
        self._adapter = adapter or self._adapter_for_mode(
            settings.CLOUD_BOOTSTRAP_ADAPTER_MODE
        )

    @staticmethod
    def _adapter_for_mode(mode: str):
        if mode == "deterministic_fake":
            return DeterministicFakeCloudBootstrapAdapter()
        if mode == "supervised_live":
            drivers = {}
            if "aws" in settings.cloud_bootstrap_supervised_providers:
                drivers["aws"] = AWSCloudBootstrapDriver()
            if "azure" in settings.cloud_bootstrap_supervised_providers:
                drivers["azure"] = AzureCloudBootstrapDriver()
            if "gcp" in settings.cloud_bootstrap_supervised_providers:
                drivers["gcp"] = GCPCloudBootstrapDriver()
            return (
                SupervisedLiveCloudBootstrapAdapter(drivers)
                if drivers
                else UnconfiguredSupervisedLiveCloudBootstrapAdapter()
            )
        return DisabledCloudBootstrapAdapter()

    def guide(
        self,
        provider: str,
        target: CloudBootstrapTarget,
    ) -> CloudBootstrapGuideResponse:
        normalized = cast(CloudProvider, normalize_provider_id(provider))
        if normalized not in {"aws", "azure", "gcp"} or target.provider != normalized:
            raise CloudBootstrapDomainError(
                "BOOTSTRAP_AUTHORITY_PACK_MISMATCH",
                "The provider path does not match the requested target.",
            )
        if normalized == "gcp" and isinstance(target, GCPOrganizationBootstrapTarget):
            raise CloudBootstrapDomainError(
                "BOOTSTRAP_SCOPE_UNSUPPORTED",
                "The active GCP bootstrap v3 gate supports an existing project only; organization/project-creation mode requires a separate reviewed ownership contract.",
                http_status=409,
            )
        authority = self._pack_reference(normalized, authority=True, detailed=True)
        deployment = self._pack_reference(normalized, authority=False, detailed=True)
        api_baseline = self._api_baseline_reference(normalized)
        guidance = PROVIDER_GUIDANCE[normalized]
        blockers: list[CloudBootstrapFinding] = []
        if settings.CLOUD_BOOTSTRAP_ADAPTER_MODE == "disabled":
            blockers.append(
                CloudBootstrapFinding(
                    code="BOOTSTRAP_IDENTITY_CREATION_FAILED",
                    title="Guided execution is disabled",
                    message="This runtime exposes the reviewed guide but has no live provider adapter enabled.",
                    blocking=True,
                    action="Use the advanced manual bootstrap fallback or enable a reviewed adapter.",
                )
            )
        elif (
            settings.CLOUD_BOOTSTRAP_ADAPTER_MODE == "supervised_live"
            and not self._adapter.supports_provider(normalized)
        ):
            blockers.append(
                CloudBootstrapFinding(
                    code="BOOTSTRAP_IDENTITY_CREATION_FAILED",
                    title="Supervised provider adapter is not configured",
                    message="The live execution contract is recognized, but this build has no reviewed adapter enabled for the selected provider.",
                    blocking=True,
                    action="Keep using the offline simulation until this provider adapter is installed and explicitly enabled.",
                )
            )
        payload = {
            "schema_version": "cloud-bootstrap-guide.v1",
            "provider": normalized,
            "execution_mode": settings.CLOUD_BOOTSTRAP_ADAPTER_MODE,
            "target": target,
            "bootstrap_authority_pack": authority,
            "generated_deployment_pack": deployment,
            "api_baseline": api_baseline,
            "credential_fields": [
                {
                    "id": field_id,
                    "label": label,
                    "input_type": input_type,
                    "required": required,
                    "redaction_rule": redaction,
                }
                for field_id, label, input_type, required, redaction in guidance[
                    "credential_fields"
                ]
            ],
            "credential_origins": (
                "dedicated_disposable",
                "existing_user_owned",
            ),
            "preparation_steps": [
                CloudBootstrapInstruction(
                    id=step_id,
                    title=title,
                    description=description,
                    expected_outcome=outcome,
                    official_url=url,
                )
                for step_id, title, description, outcome, url in guidance["steps"]
            ],
            "known_blockers": blockers,
            "legacy_fallback_available": True,
        }
        guide_digest = _digest(json.loads(_canonical_json(self._jsonable(payload))))
        return CloudBootstrapGuideResponse(
            guide_digest=guide_digest,
            **payload,
        )

    def create_session(
        self,
        user_id: str,
        request: CloudBootstrapSessionCreateRequest,
        audit: CredentialSecurityEventDraft,
    ) -> CloudBootstrapSessionResponse:
        self._reconcile_stale_leases(user_id)
        guide = self.guide(request.provider, request.target)
        self._validate_guide_references(request, guide)
        self._validate_entry_point(user_id, request)
        if (
            request.execution_kind
            == CloudBootstrapExecutionKind.SETUP_ONLY_VALIDATION
            and not settings.CLOUD_BOOTSTRAP_SETUP_GATE_ENABLED
        ):
            raise CloudBootstrapDomainError(
                "BOOTSTRAP_SETUP_GATE_DISABLED",
                "The thesis-only setup validation gate is disabled in this runtime.",
                http_status=409,
            )
        target_data = request.target.model_dump(mode="json", exclude_none=True)
        target_digest = _digest(self._scope_target_data(request.target))
        request_digest = _digest(request.model_dump(mode="json"))
        existing = self._repo.get_by_create_idempotency(
            user_id, request.idempotency_key
        )
        if existing is not None:
            if existing.create_request_digest != request_digest:
                raise self._conflict(
                    "The session idempotency key was reused for another request."
                )
            return self.to_response(existing)
        active = self._repo.get_active_for_scope(
            user_id, request.provider, target_digest
        )
        if active is not None:
            if (
                active.target_json != _canonical_json(target_data)
                or active.execution_kind != request.execution_kind.value
            ):
                raise self._conflict(
                    "An active session already owns this provider scope with a different execution contract."
                )
            return self.to_response(active)

        session = CloudBootstrapSession(
            id=str(uuid.uuid4()),
            user_id=user_id,
            provider=request.provider,
            target_scope_digest=target_digest,
            target_json=_canonical_json(target_data),
            entry_point=request.entry_point.value,
            execution_kind=request.execution_kind.value,
            twin_id=request.twin_id,
            display_name=request.display_name,
            revision=1,
            state=CloudBootstrapState.DRAFT.value,
            guide_digest=guide.guide_digest,
            bootstrap_authority_pack_id=guide.bootstrap_authority_pack.id,
            bootstrap_authority_pack_version=guide.bootstrap_authority_pack.version,
            bootstrap_authority_pack_digest=guide.bootstrap_authority_pack.digest,
            generated_deployment_pack_id=guide.generated_deployment_pack.id,
            generated_deployment_pack_version=guide.generated_deployment_pack.version,
            generated_deployment_pack_digest=guide.generated_deployment_pack.digest,
            create_idempotency_key=request.idempotency_key,
            create_request_digest=request_digest,
        )
        self._repo.add(session)
        CredentialSecurityAuditService.append(
            self._db,
            audit.model_copy(update={"resource_id": session.id}),
        )
        try:
            self._db.commit()
        except IntegrityError as exc:
            self._db.rollback()
            active = self._repo.get_active_for_scope(
                user_id, request.provider, target_digest
            )
            if active is not None:
                return self.to_response(active)
            raise self._conflict(
                "Another bootstrap session was created concurrently."
            ) from exc
        self._db.refresh(session)
        return self.to_response(session)

    def list_sessions(
        self,
        user_id: str,
        *,
        provider: str | None,
        active: bool | None,
    ) -> CloudBootstrapSessionListResponse:
        self._reconcile_stale_leases(user_id)
        normalized = None
        if provider is not None:
            normalized = normalize_provider_id(provider)
            if normalized not in {"aws", "azure", "gcp"}:
                raise CloudBootstrapDomainError(
                    "BOOTSTRAP_AUTHORITY_PACK_MISMATCH",
                    "Unsupported bootstrap provider.",
                )
        return CloudBootstrapSessionListResponse(
            items=[
                self.to_response(item)
                for item in self._repo.list_for_owner(
                    user_id,
                    provider=normalized,
                    active=active,
                )
            ]
        )

    def get_session(
        self, user_id: str, session_id: str
    ) -> CloudBootstrapSessionResponse:
        self._reconcile_stale_leases(user_id)
        return self.to_response(self._owned_session(user_id, session_id))

    def execute(
        self,
        user_id: str,
        session_id: str,
        request: CloudBootstrapExecuteRequest,
        audit: CredentialSecurityEventDraft,
        *,
        setup_confirmation: str | None = None,
    ) -> CloudBootstrapSessionResponse:
        session = self._owned_session(user_id, session_id)
        setup_only = self._is_setup_only(session)
        if setup_only:
            self._require_setup_confirmation(session, setup_confirmation)
        if session.execute_idempotency_key == request.idempotency_key:
            return self.to_response(session)
        if session.state not in {
            CloudBootstrapState.DRAFT.value,
            CloudBootstrapState.CREDENTIAL_REENTRY_REQUIRED.value,
        }:
            raise self._conflict(
                "The bootstrap session cannot accept another credential."
            )
        self._require_revision(session, request.expected_revision)
        if request.credential.provider != session.provider:
            raise CloudBootstrapDomainError(
                "BOOTSTRAP_CREDENTIAL_INVALID",
                "The submitted credential provider does not match the session.",
            )
        session.execute_idempotency_key = request.idempotency_key
        session.credential_origin = request.credential_origin.value
        session.safe_credential_identifier = self._safe_identifier(request)
        session.state = CloudBootstrapState.BOOTSTRAP_RUNNING.value
        session.lease_started_at = datetime.now(timezone.utc)
        session.finding_json = None
        session.revision += 1
        session.updated_at = datetime.now(timezone.utc)
        try:
            self._db.commit()
        except StaleDataError as exc:
            self._db.rollback()
            raise self._conflict(
                "The bootstrap session changed before execution started."
            ) from exc
        self._db.refresh(session)

        target = self._parse_target(session.target_json)
        try:
            result = self._adapter.execute(
                session_id=session.id,
                display_name=session.display_name,
                target=target,
                credential_origin=request.credential_origin,
                credential=request.credential,
            )
        except CloudBootstrapAdapterError as exc:
            return self._record_execute_failure(session, exc, audit)

        try:
            connection = self._connections.stage_deployment_connection(
                user_id,
                result.connection,
                audit.model_copy(
                    update={
                        "action": CredentialSecurityAction.CONNECTION_CREATE,
                        "resource_type": "cloud_connection",
                        "purpose": "deployment",
                    }
                ),
            )
            self._connections.stage_validation_result(
                connection,
                {
                    "valid": True,
                    "optimizer": {"valid": True},
                    "deployer": {"valid": True},
                },
            )
            session.connection_id = connection.id
            session.disposal_status = result.disposal_status.value
            session.credential_expires_at = result.credential_expires_at
            session.safe_credential_identifier = result.safe_credential_identifier
            if setup_only:
                if result.rollback_receipt is None:
                    raise ValueError(
                        "Setup-only validation requires a provider cleanup receipt"
                    )
                session.provider_cleanup_receipt_json = self._receipt_json(
                    result.rollback_receipt
                )
                session.setup_generated_access_clean = False
                session.setup_local_connection_clean = False
            session.lease_started_at = None
            session.finding_json = (
                _canonical_json(self._manual_revocation_finding(session.provider))
                if not result.bootstrap_finalization_required
                and result.disposal_status
                == CloudBootstrapDisposalStatus.MANUAL_REVOCATION_REQUIRED
                else None
            )
            if setup_only or result.bootstrap_finalization_required:
                session.state = CloudBootstrapState.GENERATED_CONNECTION_READY.value
            elif (
                result.disposal_status
                == CloudBootstrapDisposalStatus.MANUAL_REVOCATION_REQUIRED
            ):
                session.state = CloudBootstrapState.MANUAL_REVOCATION_REQUIRED.value
            else:
                session.state = CloudBootstrapState.READY.value
            session.revision += 1
            session.updated_at = datetime.now(timezone.utc)
            if setup_only or not result.bootstrap_finalization_required:
                CredentialSecurityAuditService.append(
                    self._db,
                    audit.model_copy(update={"resource_id": session.id}),
                )
            self._db.commit()
        except StaleDataError:
            self._db.rollback()
            cleanup_error = self._rollback_generated_connection(
                result,
                target,
                request.credential,
            )
            current = self._owned_session(user_id, session_id)
            if (
                current.state == CloudBootstrapState.CANCELLED.value
                and cleanup_error is None
            ):
                return self.to_response(current)
            return self._record_execute_failure(
                current,
                cleanup_error
                or CloudBootstrapAdapterError(
                    "BOOTSTRAP_SESSION_CONFLICT",
                    "The bootstrap session changed while the command was running.",
                ),
                audit,
            )
        except (SQLAlchemyError, ValueError) as exc:
            self._db.rollback()
            cleanup_error = self._rollback_generated_connection(
                result,
                target,
                request.credential,
            )
            session = self._owned_session(user_id, session_id)
            return self._record_execute_failure(
                session,
                cleanup_error
                or CloudBootstrapAdapterError(
                    "BOOTSTRAP_CONNECTION_VALIDATION_FAILED",
                    "The generated deployment connection could not be validated and persisted.",
                ),
                audit,
                cause=exc,
            )
        if setup_only:
            return self.to_response(self._owned_session(user_id, session_id))
        if result.bootstrap_finalization_required:
            return self._finalize_bootstrap_authority(
                user_id,
                session_id,
                result,
                target,
                request,
                audit,
            )
        return self.to_response(self._owned_session(user_id, session_id))

    def get_setup_receipt(
        self,
        user_id: str,
        session_id: str,
        confirmation: str | None,
    ) -> CloudBootstrapSetupReceiptResponse:
        session = self._owned_session(user_id, session_id)
        self._require_setup_confirmation(session, confirmation)
        receipt = self._stored_receipt(session)
        if receipt is None:
            raise self._conflict(
                "The setup-only session has no resumable provider cleanup receipt."
            )
        return CloudBootstrapSetupReceiptResponse(
            session_id=session.id,
            provider=receipt.provider,
            run_id=receipt.run_id,
            resource_ids=dict(receipt.resource_ids),
            connection_id=session.connection_id,
        )

    def cleanup_setup_session(
        self,
        user_id: str,
        session_id: str,
        request: CloudBootstrapSetupCleanupRequest,
        confirmation: str | None,
        audit: CredentialSecurityEventDraft,
    ) -> CloudBootstrapSetupCleanupResponse:
        session = self._owned_session(user_id, session_id)
        self._require_setup_confirmation(session, confirmation)
        self._require_revision(session, request.expected_revision)
        if request.credential.provider != session.provider:
            raise CloudBootstrapDomainError(
                "BOOTSTRAP_CREDENTIAL_INVALID",
                "The cleanup credential provider does not match the setup session.",
            )
        if session.state not in {
            CloudBootstrapState.GENERATED_CONNECTION_READY.value,
            CloudBootstrapState.MANUAL_REVOCATION_REQUIRED.value,
        }:
            raise self._conflict(
                "The setup-only session is not awaiting mandatory cleanup."
            )
        receipt = self._stored_receipt(session)
        if receipt is None or session.credential_origin is None:
            raise self._conflict(
                "The setup-only cleanup receipt is missing; manual reconciliation is required."
            )
        target = self._parse_target(session.target_json)
        session.state = CloudBootstrapState.DISPOSAL_RUNNING.value
        session.lease_started_at = datetime.now(timezone.utc)
        session.revision += 1
        session.updated_at = datetime.now(timezone.utc)
        self._db.commit()

        try:
            self._adapter.cleanup_generated_access(
                receipt=receipt,
                target=target,
                credential=request.credential,
            )
        except CloudBootstrapAdapterError:
            return self._record_setup_cleanup_failure(
                session_id,
                receipt,
                audit,
                generated_access_clean=False,
                local_connection_clean=False,
            )

        session = self._owned_session(user_id, session_id)
        local_connection_clean = session.connection_id is None
        if session.connection_id is not None:
            connection = self._connections.get_connection(
                session.connection_id, user_id
            )
            if connection is None:
                session.connection_id = None
                local_connection_clean = True
            elif self._connections.count_twin_bindings(connection.id) > 0:
                return self._record_setup_cleanup_failure(
                    session_id,
                    receipt,
                    audit,
                    generated_access_clean=True,
                    local_connection_clean=False,
                )
            else:
                try:
                    CredentialSecurityAuditService.append(
                        self._db,
                        audit.model_copy(
                            update={
                                "action": CredentialSecurityAction.CONNECTION_DELETE,
                                "resource_type": "cloud_connection",
                                "resource_id": connection.id,
                                "purpose": "deployment",
                            }
                        ),
                    )
                    session.connection_id = None
                    self._db.delete(connection)
                    self._db.commit()
                    local_connection_clean = True
                except SQLAlchemyError:
                    self._db.rollback()
                    return self._record_setup_cleanup_failure(
                        session_id,
                        receipt,
                        audit,
                        generated_access_clean=True,
                        local_connection_clean=False,
                    )

        origin = CloudBootstrapCredentialOrigin(session.credential_origin)
        try:
            finalization = self._adapter.finalize_bootstrap_receipt(
                receipt=receipt,
                target=target,
                credential_origin=origin,
                credential=request.credential,
            )
        except CloudBootstrapAdapterError:
            return self._record_setup_cleanup_failure(
                session_id,
                receipt,
                audit,
                generated_access_clean=True,
                local_connection_clean=local_connection_clean,
            )

        acceptable_disposal = (
            {
                CloudBootstrapDisposalStatus.NOT_RETAINED_USER_MANAGED,
            }
            if origin == CloudBootstrapCredentialOrigin.EXISTING_USER_OWNED
            else {
                CloudBootstrapDisposalStatus.REVOKED,
                CloudBootstrapDisposalStatus.EXPIRES_AT_PROVIDER,
            }
        )
        if (
            finalization.disposal_status not in acceptable_disposal
            or (
                finalization.disposal_status
                == CloudBootstrapDisposalStatus.EXPIRES_AT_PROVIDER
            )
            != (finalization.credential_expires_at is not None)
        ):
            return self._record_setup_cleanup_failure(
                session_id,
                receipt,
                audit,
                generated_access_clean=True,
                local_connection_clean=local_connection_clean,
            )

        session = self._owned_session(user_id, session_id)
        session.state = CloudBootstrapState.CANCELLED.value
        session.lease_started_at = None
        session.disposal_status = finalization.disposal_status.value
        session.credential_expires_at = finalization.credential_expires_at
        session.finding_json = None
        session.provider_cleanup_receipt_json = None
        session.setup_generated_access_clean = True
        session.setup_local_connection_clean = True
        session.revision += 1
        session.updated_at = datetime.now(timezone.utc)
        CredentialSecurityAuditService.append(
            self._db,
            audit.model_copy(update={"resource_id": session.id}),
        )
        self._db.commit()
        return CloudBootstrapSetupCleanupResponse(
            session_id=session.id,
            provider=receipt.provider,
            run_id=receipt.run_id,
            generated_access_clean=True,
            local_connection_clean=True,
            bootstrap_authority_disposal_status=finalization.disposal_status,
            cleanup_complete=True,
            manual_action_required=False,
        )

    def _finalize_bootstrap_authority(
        self,
        user_id: str,
        session_id: str,
        result: CloudBootstrapAdapterResult,
        target: CloudBootstrapTarget,
        request: CloudBootstrapExecuteRequest,
        audit: CredentialSecurityEventDraft,
    ) -> CloudBootstrapSessionResponse:
        session = self._owned_session(user_id, session_id)
        session.state = CloudBootstrapState.DISPOSAL_RUNNING.value
        session.lease_started_at = datetime.now(timezone.utc)
        session.revision += 1
        session.updated_at = datetime.now(timezone.utc)
        try:
            self._db.commit()
        except SQLAlchemyError:
            self._db.rollback()
            session = self._owned_session(user_id, session_id)
            session.state = CloudBootstrapState.MANUAL_REVOCATION_REQUIRED.value
            session.disposal_status = (
                CloudBootstrapDisposalStatus.MANUAL_REVOCATION_REQUIRED.value
            )
            session.lease_started_at = None
            session.finding_json = _canonical_json(
                self._manual_revocation_finding(session.provider)
            )
            session.revision += 1
            session.updated_at = datetime.now(timezone.utc)
            CredentialSecurityAuditService.append(
                self._db,
                audit.model_copy(update={"resource_id": session.id}),
            )
            self._db.commit()
            self._db.refresh(session)
            return self.to_response(session)

        try:
            finalization = self._adapter.finalize_bootstrap(
                result=result,
                target=target,
                credential_origin=request.credential_origin,
                credential=request.credential,
            )
        except CloudBootstrapAdapterError:
            finalization = None

        session = self._owned_session(user_id, session_id)
        session.lease_started_at = None
        session.revision += 1
        session.updated_at = datetime.now(timezone.utc)
        if (
            finalization is None
            or finalization.disposal_status
            == CloudBootstrapDisposalStatus.MANUAL_REVOCATION_REQUIRED
        ):
            session.disposal_status = (
                CloudBootstrapDisposalStatus.MANUAL_REVOCATION_REQUIRED.value
            )
            session.credential_expires_at = None
            session.state = CloudBootstrapState.MANUAL_REVOCATION_REQUIRED.value
            session.finding_json = _canonical_json(
                self._manual_revocation_finding(session.provider)
            )
        else:
            session.disposal_status = finalization.disposal_status.value
            session.credential_expires_at = finalization.credential_expires_at
            session.state = CloudBootstrapState.READY.value
            session.finding_json = None
        CredentialSecurityAuditService.append(
            self._db,
            audit.model_copy(update={"resource_id": session.id}),
        )
        self._db.commit()
        self._db.refresh(session)
        return self.to_response(session)

    def acknowledge_manual_revocation(
        self,
        user_id: str,
        session_id: str,
        expected_revision: int,
        audit: CredentialSecurityEventDraft,
        setup_confirmation: str | None = None,
    ) -> CloudBootstrapSessionResponse:
        session = self._owned_session(user_id, session_id)
        self._require_revision(session, expected_revision)
        if self._is_setup_only(session):
            self._require_setup_confirmation(session, setup_confirmation)
            if session.state != CloudBootstrapState.MANUAL_REVOCATION_REQUIRED.value:
                raise self._conflict(
                    "This setup-only session has no manual revocation to acknowledge."
                )
            if not (
                session.provider_cleanup_receipt_json
                and session.connection_id is None
                and session.setup_generated_access_clean
                and session.setup_local_connection_clean
            ):
                raise self._conflict(
                    "Provider-generated access and the local connection must be clean before manual bootstrap revocation can be acknowledged."
                )
            session.disposal_status = CloudBootstrapDisposalStatus.REVOKED.value
            session.credential_expires_at = None
            session.state = CloudBootstrapState.CANCELLED.value
            session.finding_json = None
            session.provider_cleanup_receipt_json = None
            session.revision += 1
            session.updated_at = datetime.now(timezone.utc)
            CredentialSecurityAuditService.append(
                self._db,
                audit.model_copy(update={"resource_id": session.id}),
            )
            self._db.commit()
            self._db.refresh(session)
            return self.to_response(session)
        if session.state != CloudBootstrapState.MANUAL_REVOCATION_REQUIRED.value:
            raise self._conflict(
                "This session has no manual revocation to acknowledge."
            )
        session.disposal_status = CloudBootstrapDisposalStatus.REVOKED.value
        session.state = CloudBootstrapState.READY.value
        session.finding_json = None
        session.revision += 1
        session.updated_at = datetime.now(timezone.utc)
        CredentialSecurityAuditService.append(
            self._db,
            audit.model_copy(update={"resource_id": session.id}),
        )
        self._db.commit()
        self._db.refresh(session)
        return self.to_response(session)

    def cancel(
        self,
        user_id: str,
        session_id: str,
        expected_revision: int,
        audit: CredentialSecurityEventDraft,
    ) -> CloudBootstrapSessionResponse:
        session = self._owned_session(user_id, session_id)
        if self._is_setup_only(session) and session.provider_cleanup_receipt_json:
            raise self._conflict(
                "A setup-only session with provider cleanup evidence cannot be cancelled."
            )
        if session.connection_id is not None:
            return self.to_response(session)
        self._require_revision(session, expected_revision)
        if session.state in {
            CloudBootstrapState.CANCELLED.value,
            CloudBootstrapState.FAILED.value,
            CloudBootstrapState.EXPIRED.value,
        }:
            return self.to_response(session)
        session.state = CloudBootstrapState.CANCELLED.value
        session.revision += 1
        session.updated_at = datetime.now(timezone.utc)
        CredentialSecurityAuditService.append(
            self._db,
            audit.model_copy(update={"resource_id": session.id}),
        )
        self._db.commit()
        self._db.refresh(session)
        return self.to_response(session)

    def to_response(
        self, session: CloudBootstrapSession
    ) -> CloudBootstrapSessionResponse:
        target = self._parse_target(session.target_json)
        finding = None
        if session.finding_json:
            finding = CloudBootstrapFinding.model_validate(
                json.loads(session.finding_json)
            )
        connection = None
        if session.connection is not None:
            connection = CloudBootstrapConnectionSummary(
                id=session.connection.id,
                provider=session.connection.provider,
                purpose="deployment",
                display_name=session.connection.display_name,
                cloud_scope=json.loads(session.connection.cloud_scope),
                permission_set_version=session.connection.permission_set_version,
                validation_status=session.connection.validation_status,
            )
        return CloudBootstrapSessionResponse(
            id=session.id,
            provider=cast(CloudProvider, session.provider),
            target=target,
            entry_point=CloudBootstrapEntryPoint(session.entry_point),
            twin_id=session.twin_id,
            display_name=session.display_name,
            revision=session.revision,
            state=CloudBootstrapState(session.state),
            guide_digest=session.guide_digest,
            bootstrap_authority_pack=CloudBootstrapPackReference(
                id=session.bootstrap_authority_pack_id,
                version=session.bootstrap_authority_pack_version,
                digest=session.bootstrap_authority_pack_digest,
            ),
            generated_deployment_pack=CloudBootstrapPackReference(
                id=session.generated_deployment_pack_id,
                version=session.generated_deployment_pack_version,
                digest=session.generated_deployment_pack_digest,
            ),
            credential_origin=(
                CloudBootstrapCredentialOrigin(session.credential_origin)
                if session.credential_origin
                else None
            ),
            disposal_status=(
                CloudBootstrapDisposalStatus(session.disposal_status)
                if session.disposal_status
                else None
            ),
            credential_expires_at=session.credential_expires_at,
            safe_credential_identifier=session.safe_credential_identifier,
            finding=finding,
            connection=connection,
            command_permissions=self._command_permissions(session),
            created_at=session.created_at,
            updated_at=session.updated_at,
        )

    def _validate_guide_references(
        self,
        request: CloudBootstrapSessionCreateRequest,
        guide: CloudBootstrapGuideResponse,
    ) -> None:
        if request.guide_digest != guide.guide_digest:
            raise CloudBootstrapDomainError(
                "BOOTSTRAP_AUTHORITY_PACK_MISMATCH",
                "The bootstrap guide changed; reload it before continuing.",
                http_status=409,
            )
        if (
            request.bootstrap_authority_pack_digest
            != guide.bootstrap_authority_pack.digest
        ):
            raise CloudBootstrapDomainError(
                "BOOTSTRAP_AUTHORITY_PACK_MISMATCH",
                "The bootstrap authority pack changed; reload the guide.",
                http_status=409,
            )
        if (
            request.generated_deployment_pack_digest
            != guide.generated_deployment_pack.digest
        ):
            raise CloudBootstrapDomainError(
                "BOOTSTRAP_GENERATED_DEPLOYMENT_PACK_MISMATCH",
                "The generated deployment pack changed; reload the guide.",
                http_status=409,
            )

    def _validate_entry_point(
        self,
        user_id: str,
        request: CloudBootstrapSessionCreateRequest,
    ) -> None:
        if request.entry_point != CloudBootstrapEntryPoint.TWIN_PREPARE:
            return
        twin = (
            self._db.query(DigitalTwin)
            .filter(
                DigitalTwin.id == request.twin_id,
                DigitalTwin.user_id == user_id,
                DigitalTwin.state != TwinState.INACTIVE,
            )
            .one_or_none()
        )
        if twin is None:
            raise CloudBootstrapDomainError(
                "BOOTSTRAP_SESSION_CONFLICT",
                "The Twin draft is not available to this owner.",
                http_status=404,
            )
        resolution = ArchitectureRepository(self._db).get_resolution_for_selected_run(
            cast(str, request.twin_id), user_id
        )
        if resolution is None or request.provider not in {
            assignment.provider for assignment in resolution.components
        }:
            raise CloudBootstrapDomainError(
                "BOOTSTRAP_SESSION_CONFLICT",
                "The selected immutable architecture does not require this provider.",
                http_status=409,
            )

    def _pack_reference(
        self,
        provider: CloudProvider,
        *,
        authority: bool,
        detailed: bool,
    ) -> CloudBootstrapPackReference:
        category = "authority-packs" if authority else "deployment-packs"
        path = CONTRACT_ROOT / category / f"{provider}.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        digest = _digest(document)
        artifact_path: str
        if authority:
            pack_id = document["contract_id"]
            version = pack_id.rsplit("-v", maxsplit=1)[-1]
            repository_name = {
                "aws": "aws_bootstrap_admin_v2.json",
                "azure": "azure_bootstrap_admin_v2.json",
                "gcp": "gcp_bootstrap_admin_v3.json",
            }[provider]
            scope = document["scope_summary"]
            limitations = document["limitations"]
            artifact_path = (
                f"3-cloud-deployer/docs/references/permission_sets/{repository_name}"
            )
        else:
            version = document["permission_set_version"]
            pack_id = f"{provider}.{version}"
            repository_name = f"{provider}_thesis_demo_v2.json"
            scope = document["assignment"]
            limitations = document["known_gaps"]
            artifact_path = (
                f"3-cloud-deployer/docs/references/permission_sets/{repository_name}"
            )
            if provider in {"aws", "azure", "gcp"}:
                binding_path = (
                    CONTRACT_ROOT / "deployment-identity-bindings" / f"{provider}.json"
                )
                binding = json.loads(binding_path.read_text(encoding="utf-8"))
                if (
                    binding.get("provider") != provider
                    or binding.get("permission_set_version") != version
                    or binding.get("base_pack_digest") != digest
                    or not isinstance(binding.get("self_check_permissions"), list)
                    or not binding["self_check_permissions"]
                    or len(binding["self_check_permissions"])
                    != len(set(binding["self_check_permissions"]))
                    or (
                        provider == "gcp"
                        and not set(binding["self_check_permissions"]).issubset(
                            document.get("custom_role_inputs", [])
                        )
                    )
                ):
                    raise CloudBootstrapDomainError(
                        "BOOTSTRAP_AUTHORITY_PACK_MISMATCH",
                        "The deployment identity binding does not match the active permission pack.",
                    )
                expected_identity = {
                    "aws": ("iam_user", "access_key", "customer_managed_policy"),
                    "azure": (
                        "service_principal",
                        "client_secret",
                        "custom_role_assignment",
                    ),
                    "gcp": (
                        "service_account",
                        "service_account_key",
                        "project_custom_role_binding",
                    ),
                }[provider]
                if (
                    binding.get("identity_kind"),
                    binding.get("connection_auth_type"),
                    binding.get("policy_attachment_kind"),
                ) != expected_identity:
                    raise CloudBootstrapDomainError(
                        "BOOTSTRAP_AUTHORITY_PACK_MISMATCH",
                        "The deployment identity binding does not match the implemented CloudConnection path.",
                    )
                digest = _digest(
                    {"permission_set": document, "identity_binding": binding}
                )
                pack_id = binding["binding_id"]
                scope = binding["scope_summary"]
                limitations = [*binding["limitations"], *limitations]
                artifact_path = (
                    "contracts/cloud-bootstrap/v1/deployment-identity-bindings/"
                    f"{provider}.json"
                )
        fields: dict[str, Any] = {
            "id": pack_id,
            "version": version,
            "digest": digest,
        }
        if detailed:
            fields.update(
                {
                    "scope_summary": scope,
                    "limitations": limitations,
                    "artifact_url": (
                        "https://github.com/TVJunkie724/master-thesis/blob/master/"
                        f"{artifact_path}"
                    ),
                }
            )
            return CloudBootstrapGuidePackReference(**fields)
        return CloudBootstrapPackReference(**fields)

    @staticmethod
    def _api_baseline_reference(
        provider: CloudProvider,
    ) -> CloudBootstrapApiBaseline | None:
        if provider != "gcp":
            return None
        path = CONTRACT_ROOT / "gcp-phase8-api-baseline.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        services = document.get("services") if isinstance(document, dict) else None
        prerequisites = (
            document.get("bootstrap_prerequisite_services")
            if isinstance(document, dict)
            else None
        )
        if (
            not isinstance(document, dict)
            or document.get("schema_version") != "gcp-phase8-api-baseline.v1"
            or document.get("baseline_id") != "gcp.phase8-api-baseline.v1"
            or document.get("provider") != "gcp"
            or document.get("status") != "frozen_offline_contract"
            or document.get("profiles")
            != ["five-layer-baseline@2", "six-layer-eventing@1"]
            or document.get("owner") != "bootstrap.gcp.admin-v3"
            or document.get("target_mode") != "existing_project"
            or document.get("region") != "europe-west1"
            or not isinstance(services, list)
            or not 1 <= len(services) <= 20
            or any(not isinstance(service, str) for service in services)
            or services != sorted(set(services))
            or not isinstance(prerequisites, list)
            or prerequisites
            != [
                "cloudresourcemanager.googleapis.com",
                "iam.googleapis.com",
                "serviceusage.googleapis.com",
            ]
            or document.get("retain_enabled") is not True
        ):
            raise CloudBootstrapDomainError(
                "BOOTSTRAP_AUTHORITY_PACK_MISMATCH",
                "The GCP API baseline does not match the active bootstrap boundary.",
            )
        return CloudBootstrapApiBaseline(
            id=document["baseline_id"],
            digest=_digest(document),
            services=document["services"],
            retain_enabled=document["retain_enabled"],
            mutation_summary=document["mutation_summary"],
            limitations=document["limitations"],
            artifact_url=(
                "https://github.com/TVJunkie724/master-thesis/blob/master/"
                "contracts/cloud-bootstrap/v1/gcp-phase8-api-baseline.json"
            ),
        )

    def _record_execute_failure(
        self,
        session: CloudBootstrapSession,
        error: CloudBootstrapAdapterError,
        audit: CredentialSecurityEventDraft,
        *,
        cause: Exception | None = None,
    ) -> CloudBootstrapSessionResponse:
        del cause
        cleanup_failed = error.code == "BOOTSTRAP_CLEANUP_FAILED"
        session.state = (
            CloudBootstrapState.FAILED.value
            if cleanup_failed
            else CloudBootstrapState.CREDENTIAL_REENTRY_REQUIRED.value
        )
        session.disposal_status = (
            CloudBootstrapDisposalStatus.RELEASED_AFTER_FAILURE.value
        )
        session.lease_started_at = None
        session.finding_json = _canonical_json(
            CloudBootstrapFinding(
                code=error.code,
                title="Bootstrap could not complete",
                message=error.message,
                blocking=True,
                action=(
                    "Remove the gate-owned provider resources identified by the setup run before starting a new session."
                    if cleanup_failed
                    else "Review the safe finding and explicitly re-enter the credential."
                ),
            ).model_dump(mode="json")
        )
        session.revision += 1
        session.updated_at = datetime.now(timezone.utc)
        CredentialSecurityAuditService.append(
            self._db,
            audit.model_copy(
                update={
                    "outcome": CredentialSecurityOutcome.REJECTED,
                    "resource_id": session.id,
                    "http_status": 422,
                }
            ),
        )
        self._db.commit()
        self._db.refresh(session)
        return self.to_response(session)

    def _rollback_generated_connection(
        self,
        result: CloudBootstrapAdapterResult,
        target: CloudBootstrapTarget,
        credential: CloudBootstrapCredential,
    ) -> CloudBootstrapAdapterError | None:
        try:
            self._adapter.rollback(
                result=result,
                target=target,
                credential=credential,
            )
        except CloudBootstrapAdapterError:
            receipt = result.rollback_receipt
            run_id = receipt.run_id if receipt is not None else "unknown"
            return CloudBootstrapAdapterError(
                "BOOTSTRAP_CLEANUP_FAILED",
                f"Generated provider access for setup run {run_id} requires manual cleanup.",
            )
        return None

    def _reconcile_stale_leases(self, user_id: str) -> None:
        cutoff = datetime.now(timezone.utc) - timedelta(
            seconds=settings.CLOUD_BOOTSTRAP_LEASE_TIMEOUT_SECONDS
        )
        stale = self._repo.list_stale_leases(user_id, cutoff)
        if not stale:
            return
        for session in stale:
            if self._is_setup_only(session) and session.provider_cleanup_receipt_json:
                session.state = CloudBootstrapState.MANUAL_REVOCATION_REQUIRED.value
                session.disposal_status = (
                    CloudBootstrapDisposalStatus.MANUAL_REVOCATION_REQUIRED.value
                )
                session.finding_json = _canonical_json(
                    self._setup_cleanup_finding(session.provider)
                )
            elif session.connection_id is None:
                session.state = CloudBootstrapState.CREDENTIAL_REENTRY_REQUIRED.value
                session.disposal_status = (
                    CloudBootstrapDisposalStatus.RELEASED_AFTER_FAILURE.value
                )
                session.finding_json = _canonical_json(
                    CloudBootstrapFinding(
                        code="BOOTSTRAP_CREDENTIAL_REENTRY_REQUIRED",
                        title="Credential re-entry required",
                        message="The prior request ended before a generated connection was validated.",
                        blocking=True,
                        action="Review the target and explicitly submit a new credential.",
                    ).model_dump(mode="json")
                )
            elif session.credential_origin == (
                CloudBootstrapCredentialOrigin.EXISTING_USER_OWNED.value
            ):
                session.state = CloudBootstrapState.READY.value
                session.disposal_status = (
                    CloudBootstrapDisposalStatus.NOT_RETAINED_USER_MANAGED.value
                )
                session.finding_json = None
            elif session.disposal_status in {
                CloudBootstrapDisposalStatus.REVOKED.value,
                CloudBootstrapDisposalStatus.EXPIRES_AT_PROVIDER.value,
            }:
                session.state = CloudBootstrapState.READY.value
                session.finding_json = None
            else:
                session.state = CloudBootstrapState.MANUAL_REVOCATION_REQUIRED.value
                session.disposal_status = (
                    CloudBootstrapDisposalStatus.MANUAL_REVOCATION_REQUIRED.value
                )
                session.finding_json = _canonical_json(
                    self._manual_revocation_finding(session.provider)
                )
            session.lease_started_at = None
            session.revision += 1
            session.updated_at = datetime.now(timezone.utc)
            CredentialSecurityAuditService.append(
                self._db,
                CredentialSecurityEventDraft(
                    user_id=user_id,
                    action=CredentialSecurityAction.BOOTSTRAP_EXECUTE,
                    outcome=(
                        CredentialSecurityOutcome.SUCCEEDED
                        if session.connection_id is not None
                        else CredentialSecurityOutcome.REJECTED
                    ),
                    resource_type="cloud_bootstrap",
                    resource_id=session.id,
                    provider=session.provider,
                    purpose="bootstrap",
                    http_status=200,
                    request_id=current_request_id(),
                ),
            )
        self._db.commit()

    def _record_setup_cleanup_failure(
        self,
        session_id: str,
        receipt: CloudBootstrapRollbackReceipt,
        audit: CredentialSecurityEventDraft,
        *,
        generated_access_clean: bool,
        local_connection_clean: bool,
    ) -> CloudBootstrapSetupCleanupResponse:
        session = (
            self._db.query(CloudBootstrapSession)
            .filter(CloudBootstrapSession.id == session_id)
            .one()
        )
        session.state = CloudBootstrapState.MANUAL_REVOCATION_REQUIRED.value
        session.disposal_status = (
            CloudBootstrapDisposalStatus.MANUAL_REVOCATION_REQUIRED.value
        )
        session.lease_started_at = None
        session.finding_json = _canonical_json(
            self._setup_cleanup_finding(session.provider)
        )
        session.setup_generated_access_clean = generated_access_clean
        session.setup_local_connection_clean = local_connection_clean
        session.revision += 1
        session.updated_at = datetime.now(timezone.utc)
        CredentialSecurityAuditService.append(
            self._db,
            audit.model_copy(
                update={
                    "outcome": CredentialSecurityOutcome.REJECTED,
                    "resource_id": session.id,
                    "http_status": 409,
                }
            ),
        )
        self._db.commit()
        return CloudBootstrapSetupCleanupResponse(
            session_id=session.id,
            provider=receipt.provider,
            run_id=receipt.run_id,
            generated_access_clean=generated_access_clean,
            local_connection_clean=local_connection_clean,
            bootstrap_authority_disposal_status=(
                CloudBootstrapDisposalStatus.MANUAL_REVOCATION_REQUIRED
            ),
            cleanup_complete=False,
            manual_action_required=True,
        )

    @staticmethod
    def _receipt_json(receipt: CloudBootstrapRollbackReceipt) -> str:
        return _canonical_json(
            {
                "provider": receipt.provider,
                "run_id": receipt.run_id,
                "resource_ids": [list(item) for item in receipt.resource_ids],
            }
        )

    @staticmethod
    def _stored_receipt(
        session: CloudBootstrapSession,
    ) -> CloudBootstrapRollbackReceipt | None:
        if not session.provider_cleanup_receipt_json:
            return None
        try:
            document = json.loads(session.provider_cleanup_receipt_json)
            if set(document) != {"provider", "run_id", "resource_ids"}:
                raise ValueError("Unexpected receipt fields")
            resource_ids = tuple(
                (str(item[0]), str(item[1]))
                for item in document["resource_ids"]
                if isinstance(item, list) and len(item) == 2
            )
            if len(resource_ids) != len(document["resource_ids"]):
                raise ValueError("Invalid receipt resource identifier")
            receipt = CloudBootstrapRollbackReceipt(
                provider=cast(CloudProvider, document["provider"]),
                run_id=str(document["run_id"]),
                resource_ids=resource_ids,
            )
            if (
                receipt.provider != session.provider
                or receipt.run_id != bootstrap_run_id(session.id)
            ):
                raise ValueError("Receipt scope does not match setup session")
            return receipt
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise CloudBootstrapDomainError(
                "BOOTSTRAP_CLEANUP_FAILED",
                "The stored setup-only cleanup receipt is invalid; manual reconciliation is required.",
                http_status=409,
            ) from exc

    @staticmethod
    def _is_setup_only(session: CloudBootstrapSession) -> bool:
        return (
            session.execution_kind
            == CloudBootstrapExecutionKind.SETUP_ONLY_VALIDATION.value
        )

    def _require_setup_confirmation(
        self,
        session: CloudBootstrapSession,
        confirmation: str | None,
    ) -> None:
        if not self._is_setup_only(session):
            raise self._conflict("This session is not a setup-only validation session.")
        if not settings.CLOUD_BOOTSTRAP_SETUP_GATE_ENABLED:
            raise CloudBootstrapDomainError(
                "BOOTSTRAP_SETUP_GATE_DISABLED",
                "The thesis-only setup validation gate is disabled in this runtime.",
                http_status=409,
            )
        expected = self._setup_confirmation(session)
        if confirmation is None or not secrets.compare_digest(confirmation, expected):
            raise CloudBootstrapDomainError(
                "BOOTSTRAP_SETUP_CONFIRMATION_INVALID",
                "The setup-only confirmation does not match this provider transaction.",
                http_status=409,
            )

    @staticmethod
    def _setup_confirmation(session: CloudBootstrapSession) -> str:
        return f"{bootstrap_run_id(session.id)}:{session.provider}:setup_only"

    def _owned_session(self, user_id: str, session_id: str) -> CloudBootstrapSession:
        session = self._repo.get_for_owner(session_id, user_id)
        if session is None:
            raise CloudBootstrapDomainError(
                "BOOTSTRAP_SESSION_CONFLICT",
                "The bootstrap session was not found.",
                http_status=404,
            )
        return session

    @staticmethod
    def _require_revision(session: CloudBootstrapSession, expected: int) -> None:
        if session.revision != expected:
            raise CloudBootstrapDomainError(
                "BOOTSTRAP_SESSION_CONFLICT",
                "The bootstrap session changed; reload it before continuing.",
                http_status=409,
            )

    @staticmethod
    def _conflict(message: str) -> CloudBootstrapDomainError:
        return CloudBootstrapDomainError(
            "BOOTSTRAP_SESSION_CONFLICT",
            message,
            http_status=409,
        )

    @staticmethod
    def _parse_target(raw: str) -> CloudBootstrapTarget:
        document = json.loads(raw)
        provider = document.get("provider")
        if provider == "aws":
            return AWSBootstrapTarget.model_validate(document)
        if provider == "azure":
            return AzureBootstrapTarget.model_validate(document)
        if document.get("mode") == "organization":
            return GCPOrganizationBootstrapTarget.model_validate(document)
        return GCPExistingProjectBootstrapTarget.model_validate(document)

    @staticmethod
    def _scope_target_data(target: CloudBootstrapTarget) -> dict[str, Any]:
        document = target.model_dump(mode="json", exclude_none=True)
        document.pop("session_expires_at", None)
        document.pop("bootstrap_credential_key_id", None)
        return document

    @staticmethod
    def _safe_identifier(request: CloudBootstrapExecuteRequest) -> str:
        credential = request.credential
        if isinstance(credential, AWSBootstrapCredential):
            return credential.access_key_id.get_secret_value()
        if isinstance(credential, AzureBootstrapCredential):
            return credential.client_id.get_secret_value()
        if isinstance(credential, GCPBootstrapCredential):
            return credential.private_key_id.get_secret_value()
        raise CloudBootstrapDomainError(
            "BOOTSTRAP_CREDENTIAL_INVALID",
            "The credential shape is unsupported.",
        )

    @staticmethod
    def _manual_revocation_finding(provider: str) -> dict[str, Any]:
        remediation_url = {
            "aws": "https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_access-keys.html",
            "azure": "https://learn.microsoft.com/en-us/entra/identity-platform/howto-create-service-principal-portal",
            "gcp": "https://cloud.google.com/iam/docs/keys-create-delete",
        }[provider]
        return CloudBootstrapFinding(
            code="BOOTSTRAP_MANUAL_REVOCATION_REQUIRED",
            title="Manual credential cleanup required",
            message=(
                "Provider-side deletion of the displayed temporary credential "
                "was not durably confirmed."
            ),
            blocking=True,
            action=(
                "Delete the displayed credential in the provider console, "
                "then acknowledge the cleanup."
            ),
            remediation_url=remediation_url,
        ).model_dump(mode="json", exclude_none=True)

    @staticmethod
    def _setup_cleanup_finding(provider: str) -> dict[str, Any]:
        return CloudBootstrapFinding(
            code="BOOTSTRAP_CLEANUP_FAILED",
            title="Setup-only cleanup requires reconciliation",
            message=(
                "The setup-only transaction did not complete mandatory cleanup. "
                "Keep the encrypted test connection and secret-free receipt until cleanup is retried or completed manually."
            ),
            blocking=True,
            action=(
                "Retry supervised cleanup with the same bootstrap authority, then verify provider resources before removing local evidence."
            ),
            remediation_url={
                "aws": "https://docs.aws.amazon.com/IAM/latest/UserGuide/id_users_remove.html",
                "azure": "https://learn.microsoft.com/en-us/entra/identity-platform/howto-remove-app",
                "gcp": "https://cloud.google.com/iam/docs/service-accounts-delete-undelete",
            }[provider],
        ).model_dump(mode="json", exclude_none=True)

    @staticmethod
    def _command_permissions(session: CloudBootstrapSession) -> list[str]:
        state = CloudBootstrapState(session.state)
        setup_only = GuidedCloudBootstrapService._is_setup_only(session)
        if state in {
            CloudBootstrapState.DRAFT,
            CloudBootstrapState.CREDENTIAL_REENTRY_REQUIRED,
        }:
            return ["execute", "cancel"]
        if state in {
            CloudBootstrapState.BOOTSTRAP_RUNNING,
            CloudBootstrapState.GENERATED_CONNECTION_READY,
            CloudBootstrapState.DISPOSAL_RUNNING,
        }:
            return ["recheck"] if setup_only else ["recheck", "cancel"]
        if state == CloudBootstrapState.MANUAL_REVOCATION_REQUIRED:
            if setup_only:
                return (
                    ["acknowledge_manual_revocation"]
                    if session.setup_generated_access_clean
                    and session.setup_local_connection_clean
                    and session.connection_id is None
                    else ["recheck"]
                )
            return ["acknowledge_manual_revocation"]
        if state in {
            CloudBootstrapState.FAILED,
            CloudBootstrapState.CANCELLED,
            CloudBootstrapState.EXPIRED,
        }:
            return ["start_new"]
        return []

    @staticmethod
    def _jsonable(value: Any) -> Any:
        if hasattr(value, "model_dump"):
            return value.model_dump(mode="json", exclude_none=True)
        if isinstance(value, dict):
            return {
                key: GuidedCloudBootstrapService._jsonable(item)
                for key, item in value.items()
            }
        if isinstance(value, (list, tuple)):
            return [GuidedCloudBootstrapService._jsonable(item) for item in value]
        return value
