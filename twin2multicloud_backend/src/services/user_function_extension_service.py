"""Owner-scoped immutable user-function artifact and binding use cases."""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from src.models.twin import TwinState
from src.models.user_function_extension import (
    TwinExtensionBinding,
    UserFunctionArtifact,
    UserFunctionArtifactDependency,
    UserFunctionArtifactFile,
    UserFunctionAuditEvent,
)
from src.repositories.twin_repository import TwinRepository
from src.schemas.user_function_extension import (
    ExtensionSlotListResponse,
    ExtensionSlotResponse,
    TwinExtensionBindingListResponse,
    TwinExtensionBindingResponse,
    TwinExtensionBindingUpdate,
    UserFunctionArtifactListResponse,
    UserFunctionArtifactResponse,
    UserFunctionValidationResponse,
)
from src.services.twin_immutability import is_twin_definition_immutable

CONTRACT_ROOT = (
    Path(__file__).resolve().parents[1]
    / "contracts"
    / "generated"
    / "user-function-extension"
    / "v1"
)
MUTATION_REGRESS_STATES = {
    TwinState.CONFIGURED,
    TwinState.ERROR,
    TwinState.DESTROYED,
}


def _load_runtime() -> ModuleType:
    module_name = "_management_user_function_extension_runtime"
    existing = sys.modules.get(module_name)
    if existing is not None:
        return existing
    path = CONTRACT_ROOT / "runtime.py"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load generated extension contract: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


runtime = _load_runtime()
ExtensionContractError = runtime.ExtensionContractError


class UserFunctionExtensionService:
    """Transactions for extension validation, persistence, and binding."""

    def __init__(self, db: Session, twin_repository: TwinRepository | None = None):
        self.db = db
        self.twins = twin_repository or TwinRepository(db)

    def list_slots(self) -> ExtensionSlotListResponse:
        slots = []
        for slot in runtime.load_registry()["slots"]:
            slots.append(
                ExtensionSlotResponse(
                    schema_version=slot["schema_version"],
                    slot_id=slot["slot_id"],
                    slot_version=slot["slot_version"],
                    display_name=slot["display_name"],
                    entrypoint=slot["entrypoint"],
                    runtime_id=slot["runtime_contract"]["runtime_ids"][0],
                    configuration_schema=slot["configuration_schema"],
                    resource_limits=slot["resource_limits"],
                    permission_capabilities=slot["permission_capabilities"],
                    secret_policy=slot["secret_policy"],
                )
            )
        return ExtensionSlotListResponse(slots=slots)

    def record_upload(
        self,
        *,
        user_id: str,
        outcome: str,
        correlation_id: str,
        error_code: str | None = None,
    ) -> None:
        """Record a source-free multipart acceptance or rejection event."""

        self._audit(
            user_id=user_id,
            action="artifact.upload",
            outcome=outcome,
            correlation_id=correlation_id,
            error_code=error_code,
        )
        self.db.commit()

    def validate(
        self,
        *,
        user_id: str,
        metadata_bytes: bytes,
        archive_bytes: bytes,
        correlation_id: str,
    ) -> UserFunctionValidationResponse:
        try:
            result = self._validate(
                user_id=user_id,
                metadata_bytes=metadata_bytes,
                archive_bytes=archive_bytes,
            )
        except ExtensionContractError as exc:
            self._audit(
                user_id=user_id,
                action="artifact.validate",
                outcome="rejected",
                correlation_id=correlation_id,
                error_code=exc.code,
            )
            self.db.commit()
            raise self._correlated(exc, correlation_id) from exc
        self._audit(
            user_id=user_id,
            action="artifact.validate",
            outcome="succeeded",
            correlation_id=correlation_id,
            slot_id=result.manifest["slot_id"],
        )
        self.db.commit()
        return UserFunctionValidationResponse(
            artifact_digest=result.manifest["artifact_digest"],
            slot_id=result.manifest["slot_id"],
            slot_version=result.manifest["slot_version"],
            runtime_id=result.manifest["runtime_id"],
            source_files=list(result.files),
            dependencies=[item["name"] for item in result.manifest["dependencies"]],
            checks=list(result.manifest["validation"]["checks"]),
        )

    def create(
        self,
        *,
        user_id: str,
        metadata_bytes: bytes,
        archive_bytes: bytes,
        correlation_id: str,
    ) -> UserFunctionArtifactResponse:
        try:
            result = self._validate(
                user_id=user_id,
                metadata_bytes=metadata_bytes,
                archive_bytes=archive_bytes,
            )
        except ExtensionContractError as exc:
            self._audit(
                user_id=user_id,
                action="artifact.create",
                outcome="rejected",
                correlation_id=correlation_id,
                error_code=exc.code,
            )
            self.db.commit()
            raise self._correlated(exc, correlation_id) from exc
        existing = (
            self.db.query(UserFunctionArtifact)
            .filter(
                UserFunctionArtifact.user_id == user_id,
                UserFunctionArtifact.artifact_digest
                == result.manifest["artifact_digest"],
            )
            .one_or_none()
        )
        if existing is not None:
            self._audit(
                user_id=user_id,
                action="artifact.create",
                outcome="idempotent",
                correlation_id=correlation_id,
                artifact_id=existing.id,
                slot_id=existing.slot_id,
            )
            self.db.commit()
            return self._artifact_response(existing)

        manifest = dict(result.manifest)
        artifact = UserFunctionArtifact(
            id=manifest["artifact_id"],
            user_id=user_id,
            schema_version=manifest["schema_version"],
            artifact_state="valid",
            artifact_digest=manifest["artifact_digest"],
            slot_id=manifest["slot_id"],
            slot_version=manifest["slot_version"],
            runtime_id=manifest["runtime_id"],
            manifest_json=runtime.canonical_json(manifest),
            configuration_json=runtime.canonical_json(manifest["configuration"]),
            declared_capabilities_json=runtime.canonical_json(
                manifest["declared_capabilities"]
            ),
            validator_version=manifest["validation"]["validator_version"],
            created_by=user_id,
            created_at=_parse_datetime(manifest["created_at"]),
        )
        source_metadata = {
            item["relative_path"]: item for item in manifest["source"]["files"]
        }
        artifact.files = [
            UserFunctionArtifactFile(
                relative_path=path,
                content_text=content,
                content_digest=source_metadata[path]["content_digest"],
                size_bytes=source_metadata[path]["size_bytes"],
            )
            for path, content in result.files.items()
        ]
        artifact.dependencies = [
            UserFunctionArtifactDependency(
                name=item["name"],
                version=item["version"],
                hashes_json=runtime.canonical_json(item["hashes"]),
                policy_result=item["policy_result"],
            )
            for item in manifest["dependencies"]
        ]
        self.db.add(artifact)
        self._audit(
            user_id=user_id,
            action="artifact.create",
            outcome="succeeded",
            correlation_id=correlation_id,
            artifact_id=artifact.id,
            slot_id=artifact.slot_id,
        )
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            existing = (
                self.db.query(UserFunctionArtifact)
                .filter(
                    UserFunctionArtifact.user_id == user_id,
                    UserFunctionArtifact.artifact_digest
                    == result.manifest["artifact_digest"],
                )
                .one_or_none()
            )
            if existing is None:
                raise
            self._audit(
                user_id=user_id,
                action="artifact.create",
                outcome="idempotent",
                correlation_id=correlation_id,
                artifact_id=existing.id,
                slot_id=existing.slot_id,
            )
            self.db.commit()
            return self._artifact_response(existing)
        except SQLAlchemyError:
            self.db.rollback()
            raise
        self.db.refresh(artifact)
        return self._artifact_response(artifact)

    def import_legacy(
        self,
        *,
        user_id: str,
        legacy_artifact_id: str,
        metadata_bytes: bytes,
        archive_bytes: bytes,
        correlation_id: str,
    ) -> UserFunctionArtifactResponse:
        """Explicitly validate replacement source for an owner-scoped legacy row."""

        legacy = self._require_artifact(user_id, legacy_artifact_id)
        if legacy.artifact_state != "legacy_unvalidated":
            raise ExtensionContractError(
                "EXTENSION_BINDING_UNRESOLVED",
                "legacy_artifact_id",
                "Only a legacy unvalidated artifact can be imported.",
                correlation_id=correlation_id,
            )
        try:
            created = self.create(
                user_id=user_id,
                metadata_bytes=metadata_bytes,
                archive_bytes=archive_bytes,
                correlation_id=correlation_id,
            )
        except ExtensionContractError as exc:
            self._audit(
                user_id=user_id,
                action="artifact.legacy.import",
                outcome="rejected",
                correlation_id=correlation_id,
                artifact_id=legacy.id,
                slot_id=legacy.slot_id,
                error_code=exc.code,
            )
            self.db.commit()
            raise
        self._audit(
            user_id=user_id,
            action="artifact.legacy.import",
            outcome="succeeded",
            correlation_id=correlation_id,
            artifact_id=created.artifact_id,
            slot_id=created.slot_id,
        )
        self.db.commit()
        return created

    def list_artifacts(
        self,
        user_id: str,
        *,
        limit: int,
        offset: int,
    ) -> UserFunctionArtifactListResponse:
        query = self.db.query(UserFunctionArtifact).filter(
            UserFunctionArtifact.user_id == user_id
        )
        total = query.count()
        items = (
            query.order_by(
                UserFunctionArtifact.created_at.desc(),
                UserFunctionArtifact.id.desc(),
            )
            .offset(offset)
            .limit(limit)
            .all()
        )
        return UserFunctionArtifactListResponse(
            items=[self._artifact_response(item) for item in items],
            total=total,
            limit=limit,
            offset=offset,
        )

    def get_artifact(
        self,
        user_id: str,
        artifact_id: str,
    ) -> UserFunctionArtifactResponse:
        return self._artifact_response(self._require_artifact(user_id, artifact_id))

    def get_source_zip(
        self,
        *,
        user_id: str,
        artifact_id: str,
        correlation_id: str,
    ) -> bytes:
        try:
            return self._get_source_zip(
                user_id=user_id,
                artifact_id=artifact_id,
                correlation_id=correlation_id,
            )
        except ExtensionContractError as exc:
            self.db.rollback()
            self._audit(
                user_id=user_id,
                action="artifact.source.download",
                outcome="rejected",
                correlation_id=correlation_id,
                artifact_id=artifact_id,
                error_code=exc.code,
            )
            self.db.commit()
            raise self._correlated(exc, correlation_id) from exc

    def _get_source_zip(
        self,
        *,
        user_id: str,
        artifact_id: str,
        correlation_id: str,
    ) -> bytes:
        artifact = self._require_artifact(user_id, artifact_id)
        files = {item.relative_path: item.content_text for item in artifact.files}
        payload = runtime.deterministic_source_zip(files)
        self._audit(
            user_id=user_id,
            action="artifact.source.download",
            outcome="succeeded",
            correlation_id=correlation_id,
            artifact_id=artifact.id,
            slot_id=artifact.slot_id,
        )
        self.db.commit()
        return payload

    def record_source_download_attempt(
        self,
        *,
        user_id: str,
        artifact_id: str,
        outcome: str,
        correlation_id: str,
        error_code: str,
    ) -> None:
        self._audit(
            user_id=user_id,
            action="artifact.source.download",
            outcome=outcome,
            correlation_id=correlation_id,
            artifact_id=artifact_id,
            error_code=error_code,
        )
        self.db.commit()

    def list_bindings(
        self,
        *,
        user_id: str,
        twin_id: str,
    ) -> TwinExtensionBindingListResponse:
        self._require_twin(user_id, twin_id)
        bindings = (
            self.db.query(TwinExtensionBinding)
            .filter(
                TwinExtensionBinding.user_id == user_id,
                TwinExtensionBinding.twin_id == twin_id,
                TwinExtensionBinding.active.is_(True),
            )
            .order_by(
                TwinExtensionBinding.slot_id,
                TwinExtensionBinding.slot_version,
            )
            .all()
        )
        return TwinExtensionBindingListResponse(
            items=[self._binding_response(binding) for binding in bindings]
        )

    def bind(
        self,
        *,
        user_id: str,
        twin_id: str,
        slot_id: str,
        update: TwinExtensionBindingUpdate,
        correlation_id: str,
    ) -> TwinExtensionBindingResponse:
        try:
            return self._bind(
                user_id=user_id,
                twin_id=twin_id,
                slot_id=slot_id,
                update=update,
                correlation_id=correlation_id,
            )
        except ExtensionContractError as exc:
            self.db.rollback()
            self._audit(
                user_id=user_id,
                action="binding.bind",
                outcome="rejected",
                correlation_id=correlation_id,
                twin_id=twin_id,
                slot_id=slot_id,
                error_code=exc.code,
            )
            self.db.commit()
            raise self._correlated(exc, correlation_id) from exc
        except IntegrityError as exc:
            self.db.rollback()
            self._audit(
                user_id=user_id,
                action="binding.bind",
                outcome="rejected",
                correlation_id=correlation_id,
                twin_id=twin_id,
                slot_id=slot_id,
                error_code="EXTENSION_BINDING_UNRESOLVED",
            )
            self.db.commit()
            raise ExtensionContractError(
                "EXTENSION_BINDING_UNRESOLVED",
                "expected_revision",
                "The extension binding changed concurrently. Reload it and retry.",
                correlation_id=correlation_id,
            ) from exc

    def _bind(
        self,
        *,
        user_id: str,
        twin_id: str,
        slot_id: str,
        update: TwinExtensionBindingUpdate,
        correlation_id: str,
    ) -> TwinExtensionBindingResponse:
        twin = self._require_mutable_twin(user_id, twin_id)
        artifact = self._require_artifact(user_id, update.artifact_id)
        if artifact.artifact_state != "valid":
            raise ExtensionContractError(
                "EXTENSION_BINDING_UNRESOLVED",
                "artifact_id",
                "Legacy or unvalidated artifacts cannot be bound.",
                correlation_id=correlation_id,
            )
        if (
            artifact.slot_id != slot_id
            or artifact.slot_version != update.slot_version
        ):
            raise ExtensionContractError(
                "EXTENSION_BINDING_UNRESOLVED",
                "artifact_id",
                "The artifact does not match the requested slot.",
                correlation_id=correlation_id,
            )
        runtime.get_slot(slot_id, update.slot_version)
        current = self._active_binding(twin_id, slot_id, update.slot_version)
        if current is not None:
            if update.expected_revision is not None and current.revision != update.expected_revision:
                raise ExtensionContractError(
                    "EXTENSION_BINDING_UNRESOLVED",
                    "expected_revision",
                    "The extension binding revision is stale.",
                    correlation_id=correlation_id,
                )
            if current.artifact_id == artifact.id:
                self._audit(
                    user_id=user_id,
                    action="binding.bind",
                    outcome="idempotent",
                    correlation_id=correlation_id,
                    artifact_id=artifact.id,
                    twin_id=twin_id,
                    slot_id=slot_id,
                )
                self.db.commit()
                return self._binding_response(current)
            current.active = False
            current.unbound_at = _now()
            next_revision = current.revision + 1
            self.db.flush()
        else:
            if update.expected_revision is not None:
                raise ExtensionContractError(
                    "EXTENSION_BINDING_UNRESOLVED",
                    "expected_revision",
                    "No active extension binding exists for this revision.",
                    correlation_id=correlation_id,
                )
            next_revision = 1
        binding = TwinExtensionBinding(
            user_id=user_id,
            twin_id=twin_id,
            slot_id=slot_id,
            slot_version=update.slot_version,
            artifact_id=artifact.id,
            artifact=artifact,
            binding_digest=runtime.binding_digest(
                twin_id=twin_id,
                slot_id=slot_id,
                slot_version=update.slot_version,
                artifact_id=artifact.id,
                artifact_digest=artifact.artifact_digest,
            ),
            active=True,
            revision=next_revision,
        )
        self.db.add(binding)
        self._regress_twin(twin)
        self._audit(
            user_id=user_id,
            action="binding.bind",
            outcome="succeeded",
            correlation_id=correlation_id,
            artifact_id=artifact.id,
            twin_id=twin_id,
            slot_id=slot_id,
        )
        self.db.commit()
        self.db.refresh(binding)
        return self._binding_response(binding)

    def unbind(
        self,
        *,
        user_id: str,
        twin_id: str,
        slot_id: str,
        slot_version: str,
        expected_revision: int | None,
        correlation_id: str,
    ) -> None:
        try:
            self._unbind(
                user_id=user_id,
                twin_id=twin_id,
                slot_id=slot_id,
                slot_version=slot_version,
                expected_revision=expected_revision,
                correlation_id=correlation_id,
            )
        except ExtensionContractError as exc:
            self.db.rollback()
            self._audit(
                user_id=user_id,
                action="binding.unbind",
                outcome="rejected",
                correlation_id=correlation_id,
                twin_id=twin_id,
                slot_id=slot_id,
                error_code=exc.code,
            )
            self.db.commit()
            raise self._correlated(exc, correlation_id) from exc

    def _unbind(
        self,
        *,
        user_id: str,
        twin_id: str,
        slot_id: str,
        slot_version: str,
        expected_revision: int | None,
        correlation_id: str,
    ) -> None:
        twin = self._require_mutable_twin(user_id, twin_id)
        current = self._active_binding(twin_id, slot_id, slot_version)
        if current is None:
            raise ExtensionContractError(
                "EXTENSION_BINDING_UNRESOLVED",
                "slot_id",
                "No active extension binding exists.",
                correlation_id=correlation_id,
            )
        if expected_revision is not None and current.revision != expected_revision:
            raise ExtensionContractError(
                "EXTENSION_BINDING_UNRESOLVED",
                "expected_revision",
                "The extension binding revision is stale.",
                correlation_id=correlation_id,
            )
        current.active = False
        current.unbound_at = _now()
        self._regress_twin(twin)
        self._audit(
            user_id=user_id,
            action="binding.unbind",
            outcome="succeeded",
            correlation_id=correlation_id,
            artifact_id=current.artifact_id,
            twin_id=twin_id,
            slot_id=slot_id,
        )
        self.db.commit()

    def _validate(
        self,
        *,
        user_id: str,
        metadata_bytes: bytes,
        archive_bytes: bytes,
    ):
        metadata = runtime.load_json_bytes(metadata_bytes, field="metadata")
        return runtime.validate_source_archive(
            metadata=metadata,
            archive_bytes=archive_bytes,
            created_by=user_id,
        )

    def _require_artifact(
        self,
        user_id: str,
        artifact_id: str,
    ) -> UserFunctionArtifact:
        artifact = (
            self.db.query(UserFunctionArtifact)
            .filter(
                UserFunctionArtifact.id == artifact_id,
                UserFunctionArtifact.user_id == user_id,
            )
            .one_or_none()
        )
        if artifact is None:
            raise ExtensionContractError(
                "EXTENSION_BINDING_UNRESOLVED",
                "artifact_id",
                "The user-function artifact was not found.",
            )
        return artifact

    def _require_twin(self, user_id: str, twin_id: str):
        twin = self.twins.get_active_for_user(twin_id, user_id)
        if twin is None:
            raise ExtensionContractError(
                "EXTENSION_BINDING_UNRESOLVED",
                "twin_id",
                "The Digital Twin was not found.",
            )
        return twin

    def _require_mutable_twin(self, user_id: str, twin_id: str):
        twin = self._require_twin(user_id, twin_id)
        if is_twin_definition_immutable(twin):
            raise ExtensionContractError(
                "EXTENSION_BINDING_UNRESOLVED",
                "twin_id",
                "A deployed Twin's function bindings are immutable; duplicate the Twin to change them.",
            )
        return twin

    def _active_binding(
        self,
        twin_id: str,
        slot_id: str,
        slot_version: str,
    ) -> TwinExtensionBinding | None:
        return (
            self.db.query(TwinExtensionBinding)
            .filter(
                TwinExtensionBinding.twin_id == twin_id,
                TwinExtensionBinding.slot_id == slot_id,
                TwinExtensionBinding.slot_version == slot_version,
                TwinExtensionBinding.active.is_(True),
            )
            .one_or_none()
        )

    @staticmethod
    def _regress_twin(twin) -> None:
        if twin.state in MUTATION_REGRESS_STATES:
            twin.state = TwinState.DRAFT

    def _artifact_response(
        self,
        artifact: UserFunctionArtifact,
    ) -> UserFunctionArtifactResponse:
        return UserFunctionArtifactResponse(
            schema_version=artifact.schema_version,
            artifact_id=artifact.id,
            artifact_state=artifact.artifact_state,
            artifact_digest=artifact.artifact_digest,
            slot_id=artifact.slot_id,
            slot_version=artifact.slot_version,
            runtime_id=artifact.runtime_id,
            configuration=json.loads(artifact.configuration_json),
            declared_capabilities=json.loads(
                artifact.declared_capabilities_json
            ),
            validator_version=artifact.validator_version,
            source_files=[item.relative_path for item in artifact.files],
            dependency_count=len(artifact.dependencies),
            created_at=artifact.created_at,
        )

    @staticmethod
    def _binding_response(
        binding: TwinExtensionBinding,
    ) -> TwinExtensionBindingResponse:
        return TwinExtensionBindingResponse(
            binding_id=binding.id,
            twin_id=binding.twin_id,
            slot_id=binding.slot_id,
            slot_version=binding.slot_version,
            artifact_id=binding.artifact_id,
            artifact_digest=binding.artifact.artifact_digest,
            binding_digest=binding.binding_digest,
            active=bool(binding.active),
            revision=binding.revision,
            created_at=binding.created_at,
            unbound_at=binding.unbound_at,
        )

    def _audit(
        self,
        *,
        user_id: str,
        action: str,
        outcome: str,
        correlation_id: str,
        artifact_id: str | None = None,
        twin_id: str | None = None,
        slot_id: str | None = None,
        error_code: str | None = None,
    ) -> None:
        self.db.add(
            UserFunctionAuditEvent(
                user_id=user_id,
                action=action,
                outcome=outcome,
                artifact_id=artifact_id,
                twin_id=twin_id,
                slot_id=slot_id,
                correlation_id=correlation_id,
                error_code=error_code,
            )
        )

    @staticmethod
    def _correlated(
        exc: ExtensionContractError,
        correlation_id: str,
    ) -> ExtensionContractError:
        return ExtensionContractError(
            exc.code,
            exc.field,
            exc.safe_message,
            correlation_id=correlation_id,
        )


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _now() -> datetime:
    return datetime.now(timezone.utc)
