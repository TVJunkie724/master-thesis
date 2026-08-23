"""Owner-scoped guided cloud-bootstrap lifecycle."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
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
    CloudBootstrapConnectionSummary,
    CloudBootstrapCredentialOrigin,
    CloudBootstrapDisposalStatus,
    CloudBootstrapEntryPoint,
    CloudBootstrapExecuteRequest,
    CloudBootstrapFinding,
    CloudBootstrapGuidePackReference,
    CloudBootstrapGuideResponse,
    CloudBootstrapInstruction,
    CloudBootstrapPackReference,
    CloudBootstrapSessionCreateRequest,
    CloudBootstrapSessionListResponse,
    CloudBootstrapSessionResponse,
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
    CloudBootstrapAdapterError,
    DeterministicFakeCloudBootstrapAdapter,
    DisabledCloudBootstrapAdapter,
)
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
                "Confirm the billing-enabled project or the bootstrap project, organization/folder, and billing account shown above.",
                "Every displayed ID and the target region are known.",
                "https://cloud.google.com/resource-manager/docs/cloud-platform-resource-hierarchy",
            ),
            (
                "create_temporary_service_account",
                "Create temporary bootstrap service account",
                "Bind bootstrap.gcp.admin-v2 and create one JSON key only when organization policy permits it.",
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
    def __init__(self, db: Session):
        self._db = db
        self._repo = CloudBootstrapRepository(db)
        self._connections = CloudConnectionService(db)
        self._adapter = (
            DeterministicFakeCloudBootstrapAdapter()
            if settings.CLOUD_BOOTSTRAP_ADAPTER_MODE == "deterministic_fake"
            else DisabledCloudBootstrapAdapter()
        )

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
        authority = self._pack_reference(normalized, authority=True, detailed=True)
        deployment = self._pack_reference(normalized, authority=False, detailed=True)
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
        payload = {
            "schema_version": "cloud-bootstrap-guide.v1",
            "provider": normalized,
            "execution_mode": settings.CLOUD_BOOTSTRAP_ADAPTER_MODE,
            "target": target,
            "bootstrap_authority_pack": authority,
            "generated_deployment_pack": deployment,
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
            if active.target_json != _canonical_json(target_data):
                raise self._conflict(
                    "An active session already owns this provider scope with different credential context."
                )
            return self.to_response(active)

        session = CloudBootstrapSession(
            id=str(uuid.uuid4()),
            user_id=user_id,
            provider=request.provider,
            target_scope_digest=target_digest,
            target_json=_canonical_json(target_data),
            entry_point=request.entry_point.value,
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
    ) -> CloudBootstrapSessionResponse:
        session = self._owned_session(user_id, session_id)
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
            session.lease_started_at = None
            session.finding_json = (
                _canonical_json(self._manual_revocation_finding(session.provider))
                if result.disposal_status
                == CloudBootstrapDisposalStatus.MANUAL_REVOCATION_REQUIRED
                else None
            )
            session.state = (
                CloudBootstrapState.MANUAL_REVOCATION_REQUIRED.value
                if result.disposal_status
                == CloudBootstrapDisposalStatus.MANUAL_REVOCATION_REQUIRED
                else CloudBootstrapState.READY.value
            )
            session.revision += 1
            session.updated_at = datetime.now(timezone.utc)
            CredentialSecurityAuditService.append(
                self._db,
                audit.model_copy(update={"resource_id": session.id}),
            )
            self._db.commit()
        except StaleDataError:
            self._db.rollback()
            current = self._owned_session(user_id, session_id)
            if current.state == CloudBootstrapState.CANCELLED.value:
                return self.to_response(current)
            return self._record_execute_failure(
                current,
                CloudBootstrapAdapterError(
                    "BOOTSTRAP_SESSION_CONFLICT",
                    "The bootstrap session changed while the command was running.",
                ),
                audit,
            )
        except (SQLAlchemyError, ValueError) as exc:
            self._db.rollback()
            session = self._owned_session(user_id, session_id)
            return self._record_execute_failure(
                session,
                CloudBootstrapAdapterError(
                    "BOOTSTRAP_CONNECTION_VALIDATION_FAILED",
                    "The generated deployment connection could not be validated and persisted.",
                ),
                audit,
                cause=exc,
            )
        return self.to_response(self._owned_session(user_id, session_id))

    def acknowledge_manual_revocation(
        self,
        user_id: str,
        session_id: str,
        expected_revision: int,
        audit: CredentialSecurityEventDraft,
    ) -> CloudBootstrapSessionResponse:
        session = self._owned_session(user_id, session_id)
        self._require_revision(session, expected_revision)
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
        if authority:
            pack_id = document["contract_id"]
            version = pack_id.rsplit("-v", maxsplit=1)[-1]
            repository_name = {
                "aws": "aws_bootstrap_admin_v2.json",
                "azure": "azure_bootstrap_admin_v2.json",
                "gcp": "gcp_bootstrap_admin_v2.json",
            }[provider]
            scope = document["scope_summary"]
            limitations = document["limitations"]
        else:
            version = document["permission_set_version"]
            pack_id = f"{provider}.{version}"
            repository_name = f"{provider}_thesis_demo_v2.json"
            scope = document["assignment"]
            limitations = document["known_gaps"]
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
                        "3-cloud-deployer/docs/references/permission_sets/"
                        f"{repository_name}"
                    ),
                }
            )
            return CloudBootstrapGuidePackReference(**fields)
        return CloudBootstrapPackReference(**fields)

    def _record_execute_failure(
        self,
        session: CloudBootstrapSession,
        error: CloudBootstrapAdapterError,
        audit: CredentialSecurityEventDraft,
        *,
        cause: Exception | None = None,
    ) -> CloudBootstrapSessionResponse:
        del cause
        session.state = CloudBootstrapState.CREDENTIAL_REENTRY_REQUIRED.value
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
                action="Review the safe finding and explicitly re-enter the credential.",
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

    def _reconcile_stale_leases(self, user_id: str) -> None:
        cutoff = datetime.now(timezone.utc) - timedelta(
            seconds=settings.CLOUD_BOOTSTRAP_LEASE_TIMEOUT_SECONDS
        )
        stale = self._repo.list_stale_leases(user_id, cutoff)
        if not stale:
            return
        for session in stale:
            if session.connection_id is None:
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
    def _command_permissions(session: CloudBootstrapSession) -> list[str]:
        state = CloudBootstrapState(session.state)
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
            return ["recheck", "cancel"]
        if state == CloudBootstrapState.MANUAL_REVOCATION_REQUIRED:
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
