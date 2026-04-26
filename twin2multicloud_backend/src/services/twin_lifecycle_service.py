"""State transition rules for DigitalTwin lifecycle operations."""

from datetime import datetime, timezone

from src.models.twin import DigitalTwin, TwinState
from src.services.errors import InvalidTwinStateTransition, OperationAlreadyInProgress


class TwinLifecycleService:
    """Owns legal DigitalTwin state transitions and lifecycle mutations."""

    _RENAME_BLOCKED_STATES = {
        TwinState.DEPLOYED,
        TwinState.DEPLOYING,
        TwinState.DESTROYING,
    }
    _DEPLOY_ALLOWED_STATES = {
        TwinState.CONFIGURED,
        TwinState.DESTROYED,
        TwinState.ERROR,
    }
    _DESTROY_ALLOWED_STATES = {
        TwinState.DEPLOYED,
        TwinState.ERROR,
    }

    def rename(self, twin: DigitalTwin, new_name: str) -> DigitalTwin:
        if new_name == twin.name:
            return twin
        if twin.state in self._RENAME_BLOCKED_STATES:
            raise InvalidTwinStateTransition(
                f"Cannot rename twin in '{twin.state.value}' state"
            )
        twin.name = new_name
        return twin

    def mark_configured(self, twin: DigitalTwin) -> DigitalTwin:
        twin.state = TwinState.CONFIGURED
        return twin

    def start_deploy(self, twin: DigitalTwin) -> DigitalTwin:
        if twin.state == TwinState.DEPLOYING:
            raise OperationAlreadyInProgress("Deployment already in progress")
        if twin.state not in self._DEPLOY_ALLOWED_STATES:
            raise InvalidTwinStateTransition(
                f"Cannot deploy twin in '{twin.state.value}' state. Must be configured, destroyed, or error."
            )
        twin.state = TwinState.DEPLOYING
        twin.last_error = None
        return twin

    def rollback_deploy_start(
        self,
        twin: DigitalTwin,
        previous_state: TwinState = TwinState.CONFIGURED,
    ) -> DigitalTwin:
        twin.state = previous_state
        return twin

    def complete_deploy(
        self,
        twin: DigitalTwin,
        deployed_at: datetime | None = None,
    ) -> DigitalTwin:
        twin.state = TwinState.DEPLOYED
        twin.deployed_at = deployed_at or datetime.now(timezone.utc)
        twin.last_error = None
        return twin

    def fail_deploy(self, twin: DigitalTwin, error: str) -> DigitalTwin:
        twin.state = TwinState.ERROR
        twin.last_error = error
        return twin

    def start_destroy(self, twin: DigitalTwin) -> DigitalTwin:
        if twin.state == TwinState.DESTROYING:
            raise OperationAlreadyInProgress("Destroy operation already in progress")
        if twin.state not in self._DESTROY_ALLOWED_STATES:
            raise InvalidTwinStateTransition(
                f"Cannot destroy twin in '{twin.state.value}' state. Must be deployed or error."
            )
        twin.state = TwinState.DESTROYING
        twin.last_error = None
        return twin

    def rollback_destroy_start(
        self,
        twin: DigitalTwin,
        previous_state: TwinState = TwinState.DEPLOYED,
    ) -> DigitalTwin:
        twin.state = previous_state
        return twin

    def complete_destroy(
        self,
        twin: DigitalTwin,
        destroyed_at: datetime | None = None,
    ) -> DigitalTwin:
        twin.state = TwinState.DESTROYED
        twin.destroyed_at = destroyed_at or datetime.now(timezone.utc)
        twin.last_error = None
        return twin

    def fail_destroy(self, twin: DigitalTwin, error: str) -> DigitalTwin:
        twin.state = TwinState.ERROR
        twin.last_error = error
        return twin
