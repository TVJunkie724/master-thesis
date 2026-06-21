"""Twin read and lifecycle use cases."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from src.config import settings
from src.models.twin import DigitalTwin, TwinState
from src.repositories.twin_repository import TwinRepository
from src.services.errors import InvalidTwinStateTransition, OperationAlreadyInProgress
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
    """Write-side twin lifecycle workflows and pure transition helpers."""

    BLOCKED_RENAME_STATES = {TwinState.DEPLOYED, TwinState.DEPLOYING, TwinState.DESTROYING}
    DEPLOY_ALLOWED_STATES = {TwinState.CONFIGURED, TwinState.DESTROYED, TwinState.ERROR}
    DESTROY_ALLOWED_STATES = {TwinState.DEPLOYED, TwinState.ERROR}

    def __init__(
        self,
        db: Session | None = None,
        twin_repository: TwinRepository | None = None,
    ):
        self.db = db
        self.twin_repository = twin_repository

    def create_twin(self, name: str, user_id: str) -> DigitalTwin:
        """Create a draft twin after enforcing the per-user active-name rule."""
        self._require_dependencies()
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
        self._require_dependencies()
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
        self._require_dependencies()
        twin = self._require_twin(twin_id, user_id)

        glb_path = Path(settings.UPLOAD_DIR) / twin_id / "scene.glb"
        glb_path.unlink(missing_ok=True)
        try:
            (Path(settings.UPLOAD_DIR) / twin_id).rmdir()
        except OSError:
            pass

        self.twin_repository.soft_delete(twin)
        self.db.commit()
        return {"message": "Twin deleted"}

    def rename(self, twin: DigitalTwin, new_name: str) -> DigitalTwin:
        """Pure state helper for renaming already-loaded twins."""
        if new_name == twin.name:
            return twin
        if twin.state in self.BLOCKED_RENAME_STATES:
            raise InvalidTwinStateTransition(f"Cannot rename twin in '{twin.state.value}' state")
        twin.name = new_name
        return twin

    @staticmethod
    def mark_configured(twin: DigitalTwin) -> DigitalTwin:
        """Pure state helper for marking a twin configured."""
        twin.state = TwinState.CONFIGURED
        return twin

    def start_deploy(self, twin: DigitalTwin) -> DigitalTwin:
        """Pure state helper for starting deployment."""
        if twin.state == TwinState.DEPLOYING:
            raise OperationAlreadyInProgress("Deployment already in progress")
        if twin.state not in self.DEPLOY_ALLOWED_STATES:
            raise InvalidTwinStateTransition(
                f"Cannot deploy twin in '{twin.state.value}' state. Must be configured, destroyed, or error."
            )
        twin.state = TwinState.DEPLOYING
        twin.last_error = None
        return twin

    @staticmethod
    def rollback_deploy_start(
        twin: DigitalTwin,
        previous_state: TwinState = TwinState.CONFIGURED,
    ) -> DigitalTwin:
        """Pure state helper for rolling back a deployment start."""
        twin.state = previous_state
        return twin

    @staticmethod
    def complete_deploy(
        twin: DigitalTwin,
        deployed_at: datetime | None = None,
    ) -> DigitalTwin:
        """Pure state helper for successful deployment completion."""
        twin.state = TwinState.DEPLOYED
        twin.deployed_at = deployed_at or datetime.now(timezone.utc)
        twin.last_error = None
        return twin

    @staticmethod
    def fail_deploy(twin: DigitalTwin, error: str) -> DigitalTwin:
        """Pure state helper for failed deployment completion."""
        twin.state = TwinState.ERROR
        twin.last_error = error
        return twin

    def start_destroy(self, twin: DigitalTwin) -> DigitalTwin:
        """Pure state helper for starting destruction."""
        if twin.state == TwinState.DESTROYING:
            raise OperationAlreadyInProgress("Destroy operation already in progress")
        if twin.state not in self.DESTROY_ALLOWED_STATES:
            raise InvalidTwinStateTransition(
                f"Cannot destroy twin in '{twin.state.value}' state. Must be deployed or error."
            )
        twin.state = TwinState.DESTROYING
        twin.last_error = None
        return twin

    @staticmethod
    def rollback_destroy_start(
        twin: DigitalTwin,
        previous_state: TwinState = TwinState.DEPLOYED,
    ) -> DigitalTwin:
        """Pure state helper for rolling back a destroy start."""
        twin.state = previous_state
        return twin

    @staticmethod
    def complete_destroy(
        twin: DigitalTwin,
        destroyed_at: datetime | None = None,
    ) -> DigitalTwin:
        """Pure state helper for successful destroy completion."""
        twin.state = TwinState.DESTROYED
        twin.destroyed_at = destroyed_at or datetime.now(timezone.utc)
        twin.last_error = None
        return twin

    @staticmethod
    def fail_destroy(twin: DigitalTwin, error: str) -> DigitalTwin:
        """Pure state helper for failed destroy completion."""
        twin.state = TwinState.ERROR
        twin.last_error = error
        return twin

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

    def _require_dependencies(self) -> None:
        if self.db is None or self.twin_repository is None:
            raise RuntimeError("TwinLifecycleService requires db and twin_repository for persistence workflows")
