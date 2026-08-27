"""Validation and current-source persistence for bounded Twin user functions."""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType

from sqlalchemy.orm import Session

from src.models.twin import TwinState
from src.models.user_function_extension import (
    TwinUserFunction,
    TwinUserFunctionDependency,
    TwinUserFunctionFile,
)
from src.repositories.twin_repository import TwinRepository
from src.schemas.user_function_extension import (
    ExtensionSlotListResponse,
    ExtensionSlotResponse,
    TwinUserFunctionListResponse,
    TwinUserFunctionResponse,
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
    """Keep one validated source per Twin and reviewed extension slot."""

    def __init__(self, db: Session, twin_repository: TwinRepository | None = None):
        self.db = db
        self.twins = twin_repository or TwinRepository(db)

    def list_slots(self) -> ExtensionSlotListResponse:
        return ExtensionSlotListResponse(
            slots=[
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
                for slot in runtime.load_registry()["slots"]
            ]
        )

    def validate(
        self,
        *,
        user_id: str,
        twin_id: str,
        slot_id: str,
        metadata_bytes: bytes,
        archive_bytes: bytes,
    ) -> UserFunctionValidationResponse:
        self._require_twin(user_id, twin_id)
        result = self._validate(
            user_id=user_id,
            slot_id=slot_id,
            metadata_bytes=metadata_bytes,
            archive_bytes=archive_bytes,
        )
        return UserFunctionValidationResponse(
            artifact_digest=result.manifest["artifact_digest"],
            slot_id=result.manifest["slot_id"],
            slot_version=result.manifest["slot_version"],
            runtime_id=result.manifest["runtime_id"],
            source_files=list(result.files),
            dependencies=[item["name"] for item in result.manifest["dependencies"]],
            checks=list(result.manifest["validation"]["checks"]),
        )

    def save(
        self,
        *,
        user_id: str,
        twin_id: str,
        slot_id: str,
        metadata_bytes: bytes,
        archive_bytes: bytes,
    ) -> TwinUserFunctionResponse:
        twin = self._require_mutable_twin(user_id, twin_id)
        metadata = runtime.load_json_bytes(metadata_bytes, field="metadata")
        slot_version = str(metadata.get("slot_version", ""))
        current = self._current(twin_id, slot_id, slot_version)
        result = self._validate(
            user_id=user_id,
            slot_id=slot_id,
            metadata_bytes=metadata_bytes,
            archive_bytes=archive_bytes,
            artifact_id=current.id if current is not None else None,
            created_at=(
                current.created_at.isoformat() if current is not None else None
            ),
        )
        manifest = dict(result.manifest)
        user_function = current or TwinUserFunction(
            id=manifest["artifact_id"],
            twin_id=twin_id,
            slot_id=manifest["slot_id"],
            slot_version=manifest["slot_version"],
        )
        if current is None:
            self.db.add(user_function)
        else:
            user_function.files.clear()
            user_function.dependencies.clear()
            self.db.flush()

        user_function.artifact_digest = manifest["artifact_digest"]
        user_function.runtime_id = manifest["runtime_id"]
        user_function.manifest_json = runtime.canonical_json(manifest)
        user_function.configuration_json = runtime.canonical_json(
            manifest["configuration"]
        )
        user_function.declared_capabilities_json = runtime.canonical_json(
            manifest["declared_capabilities"]
        )
        user_function.validator_version = manifest["validation"]["validator_version"]
        user_function.updated_at = _now()
        source_metadata = {
            item["relative_path"]: item for item in manifest["source"]["files"]
        }
        user_function.files = [
            TwinUserFunctionFile(
                relative_path=path,
                content_text=content,
                content_digest=source_metadata[path]["content_digest"],
                size_bytes=source_metadata[path]["size_bytes"],
            )
            for path, content in result.files.items()
        ]
        user_function.dependencies = [
            TwinUserFunctionDependency(
                name=item["name"],
                version=item["version"],
                hashes_json=runtime.canonical_json(item["hashes"]),
                policy_result=item["policy_result"],
            )
            for item in manifest["dependencies"]
        ]
        self._regress_twin(twin)
        self.db.commit()
        self.db.refresh(user_function)
        return self._response(user_function)

    def list_for_twin(
        self,
        *,
        user_id: str,
        twin_id: str,
    ) -> TwinUserFunctionListResponse:
        self._require_twin(user_id, twin_id)
        items = (
            self.db.query(TwinUserFunction)
            .filter(TwinUserFunction.twin_id == twin_id)
            .order_by(TwinUserFunction.slot_id, TwinUserFunction.slot_version)
            .all()
        )
        return TwinUserFunctionListResponse(
            items=[self._response(item) for item in items]
        )

    def delete(
        self,
        *,
        user_id: str,
        twin_id: str,
        slot_id: str,
        slot_version: str,
    ) -> None:
        twin = self._require_mutable_twin(user_id, twin_id)
        current = self._current(twin_id, slot_id, slot_version)
        if current is None:
            raise ExtensionContractError(
                "EXTENSION_BINDING_UNRESOLVED",
                "slot_id",
                "No user function is configured for this Twin slot.",
            )
        self.db.delete(current)
        self._regress_twin(twin)
        self.db.commit()

    def _validate(
        self,
        *,
        user_id: str,
        slot_id: str,
        metadata_bytes: bytes,
        archive_bytes: bytes,
        artifact_id: str | None = None,
        created_at: str | None = None,
    ):
        metadata = runtime.load_json_bytes(metadata_bytes, field="metadata")
        if metadata.get("slot_id") != slot_id:
            raise ExtensionContractError(
                "EXTENSION_SCHEMA_INVALID",
                "slot_id",
                "The uploaded function does not match the requested Twin slot.",
            )
        return runtime.validate_source_archive(
            metadata=metadata,
            archive_bytes=archive_bytes,
            created_by=user_id,
            artifact_id=artifact_id,
            created_at=created_at,
        )

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
                "A deployed Twin's user functions are immutable; duplicate the Twin to change them.",
            )
        return twin

    def _current(
        self,
        twin_id: str,
        slot_id: str,
        slot_version: str,
    ) -> TwinUserFunction | None:
        return (
            self.db.query(TwinUserFunction)
            .filter(
                TwinUserFunction.twin_id == twin_id,
                TwinUserFunction.slot_id == slot_id,
                TwinUserFunction.slot_version == slot_version,
            )
            .one_or_none()
        )

    @staticmethod
    def _regress_twin(twin) -> None:
        if twin.state in MUTATION_REGRESS_STATES:
            twin.state = TwinState.DRAFT

    @staticmethod
    def _response(user_function: TwinUserFunction) -> TwinUserFunctionResponse:
        return TwinUserFunctionResponse(
            function_id=user_function.id,
            twin_id=user_function.twin_id,
            artifact_digest=user_function.artifact_digest,
            slot_id=user_function.slot_id,
            slot_version=user_function.slot_version,
            runtime_id=user_function.runtime_id,
            configuration=json.loads(user_function.configuration_json),
            declared_capabilities=json.loads(user_function.declared_capabilities_json),
            validator_version=user_function.validator_version,
            source_files=[item.relative_path for item in user_function.files],
            dependencies=[item.name for item in user_function.dependencies],
            created_at=user_function.created_at,
            updated_at=user_function.updated_at,
        )


def _now() -> datetime:
    return datetime.now(timezone.utc)
