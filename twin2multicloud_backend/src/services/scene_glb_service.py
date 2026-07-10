"""Scene GLB file storage use cases."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from src.config import settings
from src.models.deployer_config import DeployerConfiguration
from src.repositories.twin_repository import TwinRepository
from src.services.service_errors import EntityNotFoundError, StorageError, ValidationError


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
        self.max_size_mb = max_size_mb if max_size_mb is not None else settings.MAX_GLB_SIZE_MB

    def upload_scene_glb(self, twin_id: str, user_id: str, content: bytes) -> dict[str, float | str]:
        """Persist a scene.glb file and mark the twin's deployer config as uploaded."""
        twin = self._require_twin(twin_id, user_id)
        max_size = self.max_size_mb * 1024 * 1024
        if len(content) > max_size:
            raise ValidationError(f"File exceeds {self.max_size_mb}MB limit")

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
