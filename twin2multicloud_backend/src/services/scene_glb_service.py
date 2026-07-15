"""Scene GLB file storage use cases."""

from __future__ import annotations

from pathlib import Path
import json
import struct

from sqlalchemy.orm import Session

from src.config import settings
from src.models.deployer_config import DeployerConfiguration
from src.repositories.twin_repository import TwinRepository
from src.services.service_errors import (
    EntityNotFoundError,
    StorageError,
    ValidationError,
)


class SceneGlbService:
    """Owns scene.glb file storage and deployer config flag persistence."""

    def __init__(
        self,
        db: Session,
        twin_repository: TwinRepository,
        upload_dir: Path | None = None,
        max_size_mb: int | None = None,
    ):
        self.db = db
        self.twin_repository = twin_repository
        self.upload_dir = upload_dir or Path(settings.UPLOAD_DIR)
        self.max_size_mb = (
            max_size_mb if max_size_mb is not None else settings.MAX_GLB_SIZE_MB
        )

    def upload_scene_glb(
        self, twin_id: str, user_id: str, content: bytes
    ) -> dict[str, float | str]:
        """Persist a scene.glb file and mark the twin's deployer config as uploaded."""
        twin = self._require_twin(twin_id, user_id)
        max_size = self.max_size_mb * 1024 * 1024
        if len(content) > max_size:
            raise ValidationError(f"File exceeds {self.max_size_mb}MB limit")
        self._validate_glb(content)

        upload_path = self.upload_dir / twin_id
        glb_path = upload_path / "scene.glb"

        try:
            upload_path.mkdir(parents=True, exist_ok=True)
            glb_path.write_bytes(content)

            config = twin.deployer_config
            if not config:
                config = DeployerConfiguration(twin_id=twin_id)
                self.db.add(config)
            config.scene_glb_uploaded = True
            self.db.commit()
        except Exception as exc:
            self.db.rollback()
            glb_path.unlink(missing_ok=True)
            raise StorageError("Failed to save GLB file") from exc

        return {
            "message": "GLB file uploaded successfully",
            "size_mb": round(len(content) / 1024 / 1024, 2),
        }

    @staticmethod
    def _validate_glb(content: bytes) -> None:
        """Validate the GLB 2.0 header and chunk table before persistence."""
        if len(content) < 20:
            raise ValidationError("File is not a valid GLB 2.0 container")
        magic, version, declared_length = struct.unpack_from("<4sII", content, 0)
        if magic != b"glTF" or version != 2 or declared_length != len(content):
            raise ValidationError("File is not a valid GLB 2.0 container")

        offset = 12
        chunk_index = 0
        binary_chunk_seen = False
        while offset < len(content):
            if len(content) - offset < 8:
                raise ValidationError("GLB contains a truncated chunk header")
            chunk_length, chunk_type = struct.unpack_from("<I4s", content, offset)
            offset += 8
            if chunk_length % 4 != 0 or chunk_length > len(content) - offset:
                raise ValidationError("GLB contains an invalid chunk length")
            chunk_content = content[offset : offset + chunk_length]
            if chunk_index == 0:
                if chunk_type != b"JSON":
                    raise ValidationError("GLB first chunk must contain JSON")
                try:
                    document = json.loads(
                        chunk_content.rstrip(b" \x00").decode("utf-8")
                    )
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise ValidationError("GLB contains invalid JSON metadata") from exc
                if not isinstance(document, dict):
                    raise ValidationError("GLB JSON metadata must be an object")
            elif chunk_type != b"BIN\x00" or binary_chunk_seen:
                raise ValidationError("GLB contains an unsupported chunk layout")
            else:
                binary_chunk_seen = True
            offset += chunk_length
            chunk_index += 1

        if offset != len(content) or chunk_index == 0:
            raise ValidationError("File is not a valid GLB 2.0 container")

    def delete_scene_glb(self, twin_id: str, user_id: str) -> dict[str, str]:
        """Delete the scene.glb file and clear the uploaded flag when a config exists."""
        twin = self._require_twin(twin_id, user_id)
        glb_path = self.upload_dir / twin_id / "scene.glb"

        try:
            glb_path.unlink(missing_ok=True)
            try:
                (self.upload_dir / twin_id).rmdir()
            except OSError:
                pass

            config = twin.deployer_config
            if config:
                config.scene_glb_uploaded = False
                self.db.commit()
        except Exception as exc:
            self.db.rollback()
            raise StorageError("Failed to delete GLB file") from exc

        return {"message": "GLB file deleted"}

    def _require_twin(self, twin_id: str, user_id: str):
        twin = self.twin_repository.get_for_user(twin_id, user_id)
        if not twin:
            raise EntityNotFoundError("Twin not found")
        return twin
