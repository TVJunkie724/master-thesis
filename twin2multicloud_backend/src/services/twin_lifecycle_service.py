"""Twin read and lifecycle use cases."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path

from sqlalchemy.orm import Session

from src.config import settings
from src.models.twin import DigitalTwin, TwinState
from src.repositories.twin_repository import TwinRepository
from src.services.service_errors import ConflictError, EntityNotFoundError, ValidationError

ConfiguredTransitionValidator = Callable[[DigitalTwin, Session], Awaitable[None]]


class TwinReadService:
    """Read-side twin workflows."""

    def __init__(self, twin_repository: TwinRepository):
        self.twin_repository = twin_repository

    def list_twins(self, user_id: str) -> list[DigitalTwin]:
        """Return active twins for a user."""
        return self.twin_repository.list_active_for_user(user_id)

    def get_twin(self, twin_id: str, user_id: str) -> DigitalTwin:
        """Return an active twin owned by a user."""
        twin = self.twin_repository.get_active_for_user(twin_id, user_id)
        if not twin:
            raise EntityNotFoundError("Twin not found")
        return twin


class TwinLifecycleService:
    """Write-side twin lifecycle workflows."""

    BLOCKED_RENAME_STATES = {TwinState.DEPLOYED, TwinState.DEPLOYING, TwinState.DESTROYING}

    def __init__(self, db: Session, twin_repository: TwinRepository):
        self.db = db
        self.twin_repository = twin_repository

    def create_twin(self, name: str, user_id: str) -> DigitalTwin:
        """Create a draft twin after enforcing the per-user active-name rule."""
        existing = self.twin_repository.find_active_by_name(user_id, name)
        if existing:
            raise ConflictError(f"A twin with the name '{name}' already exists")

        twin = DigitalTwin(
            name=name,
            user_id=user_id,
            state=TwinState.DRAFT,
        )
        self.twin_repository.add(twin)
        self.db.commit()
        self.twin_repository.refresh(twin)
        return twin

    async def update_twin(
        self,
        twin_id: str,
        user_id: str,
        *,
        name: str | None,
        state: TwinState | None,
        configured_validator: ConfiguredTransitionValidator,
    ) -> DigitalTwin:
        """Update twin name and/or state while preserving current state rules."""
        twin = self._require_twin(twin_id, user_id)

        if name is not None and name != twin.name:
            self._validate_rename(twin, user_id, name)
            twin.name = name

        if state is not None and state == TwinState.CONFIGURED:
            await configured_validator(twin, self.db)

        if state is not None:
            twin.state = state

        self.db.commit()
        self.twin_repository.refresh(twin)
        return twin

    def delete_twin(self, twin_id: str, user_id: str) -> dict[str, str]:
        """Soft-delete a twin and clean up its uploaded scene asset if present."""
        twin = self._require_twin(twin_id, user_id)

        glb_path = Path(settings.UPLOAD_DIR) / twin_id / "scene.glb"
        glb_path.unlink(missing_ok=True)
        try:
            (Path(settings.UPLOAD_DIR) / twin_id).rmdir()
        except OSError:
            pass

        twin.state = TwinState.INACTIVE
        twin.name = f"_deleted_{twin_id}_{twin.name}"
        self.db.commit()
        return {"message": "Twin deleted"}

    def _require_twin(self, twin_id: str, user_id: str) -> DigitalTwin:
        twin = self.twin_repository.get_active_for_user(twin_id, user_id)
        if not twin:
            raise EntityNotFoundError("Twin not found")
        return twin

    def _validate_rename(self, twin: DigitalTwin, user_id: str, name: str) -> None:
        if twin.state in self.BLOCKED_RENAME_STATES:
            raise ValidationError(f"Cannot rename twin in '{twin.state.value}' state")

        existing = self.twin_repository.find_active_by_name(
            user_id=user_id,
            name=name,
            exclude_twin_id=twin.id,
        )
        if existing:
            raise ConflictError(f"A twin with the name '{name}' already exists")
