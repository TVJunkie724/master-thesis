"""Optimizer configuration persistence use cases."""

from __future__ import annotations

from sqlalchemy.orm import Session

from src.models.optimizer_config import OptimizerConfiguration
from src.repositories.twin_repository import TwinRepository
from src.schemas.optimizer_config import (
    CheapestPathResponse,
    OptimizerConfigResponse,
    OptimizerParamsUpdate,
)
from src.services.architecture_projection_service import provider_path
from src.services.optimizer_config_projection import (
    optimizer_config_to_response,
    to_json,
)
from src.services.service_errors import EntityNotFoundError
from src.services.twin_immutability import require_mutable_twin_definition


class OptimizerConfigurationService:
    """Owns Step-2 optimizer persistence and response shaping."""

    def __init__(
        self,
        db: Session,
        twin_repository: TwinRepository,
    ):
        self.db = db
        self.twin_repository = twin_repository

    def get_config(self, twin_id: str, user_id: str) -> OptimizerConfigResponse:
        """Return the persisted optimizer config, creating an empty one when missing."""
        twin = self._require_twin(twin_id, user_id)
        config = self._ensure_config(twin_id, twin)
        response = optimizer_config_to_response(config)
        path = provider_path(twin)
        if path:
            response.cheapest_path = CheapestPathResponse(**path)
        return response

    def update_params(
        self,
        twin_id: str,
        user_id: str,
        update: OptimizerParamsUpdate,
    ) -> OptimizerConfigResponse:
        """Persist calculation parameters without running a calculation."""
        twin = self._require_twin(twin_id, user_id)
        require_mutable_twin_definition(twin)
        config = self._ensure_config(twin_id, twin, commit=False)

        if update.params:
            config.params = to_json(update.params.to_persisted_payload())

        self.db.add(config)
        self.db.commit()
        self.db.refresh(config)
        return optimizer_config_to_response(config)

    def get_cheapest_path(self, twin_id: str, user_id: str) -> dict[str, str | None]:
        """Return the fixed-shape compatibility view of selected architecture."""
        twin = self._require_twin(twin_id, user_id)
        path = provider_path(twin)
        if not path:
            raise EntityNotFoundError(
                "No optimizer result found. Run calculation first."
            )
        return path

    def _require_twin(self, twin_id: str, user_id: str):
        twin = self.twin_repository.get_active_for_user(twin_id, user_id)
        if not twin:
            raise EntityNotFoundError("Twin not found")
        return twin

    def _ensure_config(
        self, twin_id: str, twin, *, commit: bool = True
    ) -> OptimizerConfiguration:
        if twin.optimizer_config:
            return twin.optimizer_config

        config = OptimizerConfiguration(twin_id=twin_id)
        self.db.add(config)
        twin.optimizer_config = config
        if commit:
            self.db.commit()
            self.db.refresh(config)
        return config
