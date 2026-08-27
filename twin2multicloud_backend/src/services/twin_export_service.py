"""Portable, credential-free Twin duplicate/import/export workflows."""

from __future__ import annotations

import hashlib
import io
import json
import shutil
import stat
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.orm import Session

from src.config import settings
from src.models.deployer_config import DeployerConfiguration
from src.models.optimizer_config import OptimizerConfiguration
from src.models.twin import DigitalTwin
from src.models.twin_config import TwinConfiguration
from src.repositories.twin_repository import TwinRepository
from src.schemas.twin_transfer import (
    PortableDeployerDefinition,
    PortableProviderSettings,
    PortableTwinDefinition,
    PortableTwinManifest,
)
from src.services.scene_glb_service import SceneGlbService
from src.services.service_errors import EntityNotFoundError, ValidationError
from src.services.twin_lifecycle_service import TwinLifecycleService

PORTABLE_SCHEMA_VERSION = "twin2multicloud-portable.v1"
MANIFEST_PATH = "manifest.json"
DEFINITION_PATH = "twin-definition.json"
SCENE_PATH = "assets/scene.glb"
ALLOWED_PATHS = frozenset({MANIFEST_PATH, DEFINITION_PATH, SCENE_PATH})
MAX_ARCHIVE_BYTES = 128 * 1024 * 1024
MAX_DEFINITION_BYTES = 8 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 3
MAX_COMPRESSION_RATIO = 100
FIXED_ZIP_TIMESTAMP = (2026, 1, 1, 0, 0, 0)

_DEPLOYER_TEXT_FIELDS = tuple(PortableDeployerDefinition.model_fields)


@dataclass(frozen=True)
class TwinExportArchive:
    """Prepared portable Twin archive for the HTTP adapter."""

    content: io.BytesIO
    filename: str
    media_type: str = "application/zip"


class TwinExportService:
    """Own the bounded portable Twin definition contract."""

    def __init__(
        self,
        db: Session,
        twin_repository: TwinRepository | None = None,
        *,
        upload_dir: Path | None = None,
    ):
        self.db = db
        self.twin_repository = twin_repository or TwinRepository(db)
        self.upload_dir = upload_dir or Path(settings.UPLOAD_DIR)
        self.lifecycle = TwinLifecycleService(
            db=db,
            twin_repository=self.twin_repository,
        )

    def export_twin(self, twin_id: str, user_id: str) -> TwinExportArchive:
        """Export authored inputs and an optional scene, never credentials or history."""
        twin = self._load_twin(twin_id, user_id)
        definition = self._definition_from_twin(twin)
        members = {
            DEFINITION_PATH: self._canonical_json(definition.model_dump(mode="json")),
        }
        scene = self._read_scene(twin)
        if scene is not None:
            members[SCENE_PATH] = scene
        manifest = PortableTwinManifest(
            schema_version=PORTABLE_SCHEMA_VERSION,
            files={path: self._digest(content) for path, content in sorted(members.items())},
        )

        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
            self._write_member(
                archive,
                MANIFEST_PATH,
                self._canonical_json(manifest.model_dump(mode="json")),
            )
            for path, content in sorted(members.items()):
                self._write_member(archive, path, content)
        output.seek(0)
        return TwinExportArchive(
            content=output,
            filename=f"{self._safe_filename(twin.name)}.twin.zip",
        )

    def duplicate_twin(
        self,
        source_twin_id: str,
        user_id: str,
        new_name: str,
    ) -> DigitalTwin:
        """Copy authored inputs into a new draft while retaining same-owner bindings."""
        source = self._load_twin(source_twin_id, user_id)
        definition = self._definition_from_twin(source)
        return self._create_from_definition(
            definition,
            user_id=user_id,
            new_name=new_name,
            scene=self._read_scene(source),
            connection_source=source.configuration,
        )

    def import_twin(
        self,
        archive_content: bytes,
        user_id: str,
        new_name: str,
    ) -> DigitalTwin:
        """Validate a portable archive and import it as a credential-unbound draft."""
        definition, scene = self._parse_archive(archive_content)
        return self._create_from_definition(
            definition,
            user_id=user_id,
            new_name=new_name,
            scene=scene,
            connection_source=None,
        )

    def _create_from_definition(
        self,
        definition: PortableTwinDefinition,
        *,
        user_id: str,
        new_name: str,
        scene: bytes | None,
        connection_source: TwinConfiguration | None,
    ) -> DigitalTwin:
        new_name = self._validated_name(new_name)
        created_scene: Path | None = None
        try:
            twin = self.lifecycle.create_twin(new_name, user_id, commit=False)
            settings_value = definition.provider_settings
            config = TwinConfiguration(
                twin_id=twin.id,
                debug_mode=definition.debug_mode,
                highest_step_reached=0,
                aws_region=settings_value.aws_region,
                aws_sso_region=settings_value.aws_sso_region,
                azure_region=settings_value.azure_region,
                azure_region_iothub=settings_value.azure_region_iothub,
                azure_region_digital_twin=settings_value.azure_region_digital_twin,
                gcp_project_id=settings_value.gcp_project_id,
                gcp_region=settings_value.gcp_region,
                aws_cloud_connection_id=(
                    connection_source.aws_cloud_connection_id
                    if connection_source is not None
                    else None
                ),
                azure_cloud_connection_id=(
                    connection_source.azure_cloud_connection_id
                    if connection_source is not None
                    else None
                ),
                gcp_cloud_connection_id=(
                    connection_source.gcp_cloud_connection_id
                    if connection_source is not None
                    else None
                ),
                aws_validated=False,
                azure_validated=False,
                gcp_validated=False,
            )
            self.db.add(config)
            twin.configuration = config

            if definition.optimizer_params is not None:
                optimizer = OptimizerConfiguration(
                    twin_id=twin.id,
                    params=json.dumps(
                        definition.optimizer_params,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                )
                self.db.add(optimizer)
                twin.optimizer_config = optimizer

            if definition.deployer is not None:
                values = definition.deployer.model_dump()
                deployer = DeployerConfiguration(twin_id=twin.id, **values)
                self.db.add(deployer)
                twin.deployer_config = deployer

            self.db.flush()
            if scene is not None:
                self._validate_scene_size(scene)
                target_dir = self.upload_dir / twin.id
                target_dir.mkdir(parents=True, exist_ok=False)
                created_scene = target_dir / "scene.glb"
                created_scene.write_bytes(scene)
                if twin.deployer_config is None:
                    twin.deployer_config = DeployerConfiguration(twin_id=twin.id)
                    self.db.add(twin.deployer_config)
                twin.deployer_config.scene_glb_uploaded = True

            self.db.commit()
            self.db.refresh(twin)
            return twin
        except Exception:  # noqa: BLE001 - transaction boundary must roll back every failure
            self.db.rollback()
            if created_scene is not None:
                created_scene.unlink(missing_ok=True)
                shutil.rmtree(created_scene.parent, ignore_errors=True)
            raise

    def _parse_archive(
        self,
        content: bytes,
    ) -> tuple[PortableTwinDefinition, bytes | None]:
        if not content or len(content) > MAX_ARCHIVE_BYTES:
            raise ValidationError("Portable Twin archive size is invalid")
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                infos = archive.infolist()
                names = [info.filename for info in infos]
                if not infos or len(infos) > MAX_ARCHIVE_MEMBERS:
                    raise ValidationError("Portable Twin archive has too many files")
                if len(names) != len(set(names)) or not set(names) <= ALLOWED_PATHS:
                    raise ValidationError("Portable Twin archive contains unsupported files")
                if MANIFEST_PATH not in names or DEFINITION_PATH not in names:
                    raise ValidationError("Portable Twin archive is incomplete")
                for info in infos:
                    self._validate_member(info)

                manifest_bytes = self._read_bounded(
                    archive,
                    MANIFEST_PATH,
                    MAX_DEFINITION_BYTES,
                )
                definition_bytes = self._read_bounded(
                    archive,
                    DEFINITION_PATH,
                    MAX_DEFINITION_BYTES,
                )
                manifest = PortableTwinManifest.model_validate_json(manifest_bytes)
                expected_member_names = set(names) - {MANIFEST_PATH}
                if set(manifest.files) != expected_member_names:
                    raise ValidationError("Portable Twin manifest does not match archive files")
                members = {DEFINITION_PATH: definition_bytes}
                scene = None
                if SCENE_PATH in expected_member_names:
                    scene = self._read_bounded(
                        archive,
                        SCENE_PATH,
                        settings.MAX_GLB_SIZE_MB * 1024 * 1024,
                    )
                    members[SCENE_PATH] = scene
                for path, member_content in members.items():
                    if manifest.files[path] != self._digest(member_content):
                        raise ValidationError(
                            f"Portable Twin archive digest mismatch for {path}"
                        )
                definition = PortableTwinDefinition.model_validate_json(
                    definition_bytes
                )
                return definition, scene
        except (zipfile.BadZipFile, PydanticValidationError, UnicodeDecodeError) as exc:
            raise ValidationError("Portable Twin archive contract is invalid") from exc

    def _definition_from_twin(self, twin: DigitalTwin) -> PortableTwinDefinition:
        config = twin.configuration
        optimizer_params = self._load_json_object(
            twin.optimizer_config.params if twin.optimizer_config else None,
            "optimizer params",
        )
        deployer = None
        if twin.deployer_config is not None:
            deployer = PortableDeployerDefinition(
                **{
                    field: getattr(twin.deployer_config, field)
                    for field in _DEPLOYER_TEXT_FIELDS
                }
            )
        return PortableTwinDefinition(
            schema_version="twin-definition.v1",
            source_name=twin.name,
            debug_mode=bool(config.debug_mode) if config else False,
            provider_settings=PortableProviderSettings(
                aws_region=(config.aws_region if config else None) or "eu-central-1",
                aws_sso_region=config.aws_sso_region if config else None,
                azure_region=(config.azure_region if config else None) or "westeurope",
                azure_region_iothub=(config.azure_region_iothub if config else None),
                azure_region_digital_twin=(
                    config.azure_region_digital_twin if config else None
                ),
                gcp_project_id=config.gcp_project_id if config else None,
                gcp_region=(config.gcp_region if config else None) or "europe-west1",
            ),
            optimizer_params=optimizer_params,
            deployer=deployer,
        )

    def _load_twin(self, twin_id: str, user_id: str) -> DigitalTwin:
        twin = self.twin_repository.get_with_configs_for_user(twin_id, user_id)
        if not twin:
            raise EntityNotFoundError("Twin not found")
        return twin

    def _read_scene(self, twin: DigitalTwin) -> bytes | None:
        if not twin.deployer_config or not twin.deployer_config.scene_glb_uploaded:
            return None
        path = self.upload_dir / twin.id / "scene.glb"
        if not path.is_file():
            raise ValidationError("Twin scene flag is set but scene.glb is missing")
        content = path.read_bytes()
        self._validate_scene_size(content)
        return content

    @staticmethod
    def _validate_scene_size(content: bytes) -> None:
        if not content or len(content) > settings.MAX_GLB_SIZE_MB * 1024 * 1024:
            raise ValidationError("Portable Twin scene exceeds the configured size limit")
        SceneGlbService._validate_glb(content)

    @staticmethod
    def _validated_name(value: str) -> str:
        name = str(value).strip()
        if not name or len(name) > 120:
            raise ValidationError("Twin name must contain between 1 and 120 characters")
        return name

    @staticmethod
    def _load_json_object(raw: str | None, label: str) -> dict[str, Any] | None:
        if raw is None:
            return None
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValidationError(f"Stored {label} are not valid JSON") from exc
        if not isinstance(value, dict):
            raise ValidationError(f"Stored {label} must be a JSON object")
        return value

    @staticmethod
    def _canonical_json(value: Any) -> bytes:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")

    @staticmethod
    def _digest(content: bytes) -> str:
        return f"sha256:{hashlib.sha256(content).hexdigest()}"

    @staticmethod
    def _write_member(archive: zipfile.ZipFile, path: str, content: bytes) -> None:
        info = zipfile.ZipInfo(path, FIXED_ZIP_TIMESTAMP)
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o600 << 16
        archive.writestr(info, content)

    @staticmethod
    def _validate_member(info: zipfile.ZipInfo) -> None:
        if info.is_dir() or info.flag_bits & 0x1:
            raise ValidationError("Portable Twin archive entries must be unencrypted files")
        if stat.S_ISLNK(info.external_attr >> 16):
            raise ValidationError("Portable Twin archive links are forbidden")
        if info.file_size < 0 or info.file_size > MAX_ARCHIVE_BYTES:
            raise ValidationError("Portable Twin archive entry is too large")
        if (
            info.compress_size > 0
            and info.file_size > max(1, info.compress_size) * MAX_COMPRESSION_RATIO
        ):
            raise ValidationError("Portable Twin archive compression ratio is unsafe")

    @staticmethod
    def _read_bounded(
        archive: zipfile.ZipFile,
        path: str,
        max_bytes: int,
    ) -> bytes:
        with archive.open(path) as stream:
            content = stream.read(max_bytes + 1)
        if len(content) > max_bytes:
            raise ValidationError(f"Portable Twin archive entry {path} is too large")
        return content

    @staticmethod
    def _safe_filename(name: str) -> str:
        safe = "".join(
            character.lower() if character.isalnum() else "-" for character in name
        )
        safe = "-".join(part for part in safe.split("-") if part)
        return safe[:80] or "twin"
