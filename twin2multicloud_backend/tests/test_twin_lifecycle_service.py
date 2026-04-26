from datetime import datetime, timezone

import pytest

from src.models.twin import DigitalTwin, TwinState
from src.services.errors import InvalidTwinStateTransition, OperationAlreadyInProgress
from src.services.twin_lifecycle_service import TwinLifecycleService


def _twin(state: TwinState = TwinState.DRAFT) -> DigitalTwin:
    return DigitalTwin(id="twin-1", name="Factory Twin", user_id="user-1", state=state)


def test_rename_updates_allowed_state():
    twin = _twin(TwinState.DRAFT)

    TwinLifecycleService().rename(twin, "Renamed Twin")

    assert twin.name == "Renamed Twin"


@pytest.mark.parametrize("state", [TwinState.DEPLOYED, TwinState.DEPLOYING, TwinState.DESTROYING])
def test_rename_blocks_deployment_owned_states(state):
    twin = _twin(state)

    with pytest.raises(InvalidTwinStateTransition) as exc_info:
        TwinLifecycleService().rename(twin, "Renamed Twin")

    assert exc_info.value.message == f"Cannot rename twin in '{state.value}' state"
    assert twin.name == "Factory Twin"


@pytest.mark.parametrize("state", [TwinState.CONFIGURED, TwinState.DESTROYED, TwinState.ERROR])
def test_start_deploy_allows_configured_destroyed_and_error(state):
    twin = _twin(state)
    twin.last_error = "old error"

    TwinLifecycleService().start_deploy(twin)

    assert twin.state == TwinState.DEPLOYING
    assert twin.last_error is None


@pytest.mark.parametrize("state", [TwinState.DRAFT, TwinState.DEPLOYED, TwinState.DESTROYING, TwinState.INACTIVE])
def test_start_deploy_rejects_invalid_states(state):
    twin = _twin(state)

    with pytest.raises(InvalidTwinStateTransition) as exc_info:
        TwinLifecycleService().start_deploy(twin)

    assert exc_info.value.message == (
        f"Cannot deploy twin in '{state.value}' state. Must be configured, destroyed, or error."
    )
    assert twin.state == state


def test_start_deploy_reports_operation_in_progress():
    twin = _twin(TwinState.DEPLOYING)

    with pytest.raises(OperationAlreadyInProgress) as exc_info:
        TwinLifecycleService().start_deploy(twin)

    assert exc_info.value.message == "Deployment already in progress"


def test_deploy_completion_and_failure_mutate_state_and_error_fields():
    service = TwinLifecycleService()
    deployed_at = datetime(2026, 4, 26, 10, 0, tzinfo=timezone.utc)
    twin = _twin(TwinState.DEPLOYING)

    service.complete_deploy(twin, deployed_at=deployed_at)

    assert twin.state == TwinState.DEPLOYED
    assert twin.deployed_at == deployed_at
    assert twin.last_error is None

    service.fail_deploy(twin, "terraform failed")

    assert twin.state == TwinState.ERROR
    assert twin.last_error == "terraform failed"


@pytest.mark.parametrize("state", [TwinState.DEPLOYED, TwinState.ERROR])
def test_start_destroy_allows_deployed_and_error(state):
    twin = _twin(state)
    twin.last_error = "old error"

    TwinLifecycleService().start_destroy(twin)

    assert twin.state == TwinState.DESTROYING
    assert twin.last_error is None


@pytest.mark.parametrize("state", [TwinState.DRAFT, TwinState.CONFIGURED, TwinState.DEPLOYING, TwinState.DESTROYED, TwinState.INACTIVE])
def test_start_destroy_rejects_invalid_states(state):
    twin = _twin(state)

    with pytest.raises(InvalidTwinStateTransition) as exc_info:
        TwinLifecycleService().start_destroy(twin)

    assert exc_info.value.message == (
        f"Cannot destroy twin in '{state.value}' state. Must be deployed or error."
    )
    assert twin.state == state


def test_start_destroy_reports_operation_in_progress():
    twin = _twin(TwinState.DESTROYING)

    with pytest.raises(OperationAlreadyInProgress) as exc_info:
        TwinLifecycleService().start_destroy(twin)

    assert exc_info.value.message == "Destroy operation already in progress"


def test_destroy_completion_and_failure_mutate_state_and_error_fields():
    service = TwinLifecycleService()
    destroyed_at = datetime(2026, 4, 26, 11, 0, tzinfo=timezone.utc)
    twin = _twin(TwinState.DESTROYING)

    service.complete_destroy(twin, destroyed_at=destroyed_at)

    assert twin.state == TwinState.DESTROYED
    assert twin.destroyed_at == destroyed_at
    assert twin.last_error is None

    service.fail_destroy(twin, "destroy failed")

    assert twin.state == TwinState.ERROR
    assert twin.last_error == "destroy failed"


def test_deploy_and_destroy_rollbacks_restore_previous_state():
    service = TwinLifecycleService()
    twin = _twin(TwinState.DEPLOYING)

    service.rollback_deploy_start(twin, previous_state=TwinState.DESTROYED)
    assert twin.state == TwinState.DESTROYED

    twin.state = TwinState.DESTROYING
    service.rollback_destroy_start(twin, previous_state=TwinState.ERROR)
    assert twin.state == TwinState.ERROR
