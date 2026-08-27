"""Single source of truth for the PoC's immutable deployed-Twin rule."""

from __future__ import annotations

from src.models.twin import DigitalTwin, TwinState
from src.services.service_errors import ValidationError

IMMUTABLE_TWIN_DETAIL = (
    "A Twin definition is immutable after its first successful deployment. "
    "Duplicate it under a new name to make changes."
)

_DEPLOYMENT_OWNED_STATES = {
    TwinState.DEPLOYING,
    TwinState.DEPLOYED,
    TwinState.DESTROYING,
}


def is_twin_definition_immutable(twin: DigitalTwin) -> bool:
    """Return whether user-authored definition changes must be rejected."""
    return twin.deployed_at is not None or twin.state in _DEPLOYMENT_OWNED_STATES


def require_mutable_twin_definition(twin: DigitalTwin) -> None:
    """Fail closed when a write would alter a deployed Twin definition."""
    if is_twin_definition_immutable(twin):
        raise ValidationError(IMMUTABLE_TWIN_DETAIL)
