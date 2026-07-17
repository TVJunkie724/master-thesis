"""Optimizer configuration persistence use cases."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from src.models.optimizer_config import OptimizerConfiguration
from src.repositories.twin_repository import TwinRepository
from src.schemas.optimizer_config import OptimizerConfigResponse, OptimizerParamsUpdate, OptimizerResultUpdate
from src.services.optimizer_config_projection import (
    cheapest_path_dict,
    optimizer_config_to_response,
    parse_iso_safe,
    set_cheapest_columns_from_payload,
    to_json,
)
from src.services.service_errors import EntityNotFoundError


class OptimizerConfigurationService:
    """Owns Step-2 optimizer persistence and response shaping."""

    def __init__(self, db: Session, twin_repository: TwinRepository):
        self.db = db
        self.twin_repository = twin_repository

    def get_config(self, twin_id: str, user_id: str) -> OptimizerConfigResponse:
        """Return the persisted optimizer config, creating an empty one when missing."""
        twin = self._require_twin(twin_id, user_id)
        config = self._ensure_config(twin_id, twin)
        return optimizer_config_to_response(config)

    def update_params(
        self,
        twin_id: str,
        user_id: str,
        update: OptimizerParamsUpdate,
    ) -> OptimizerConfigResponse:
        """Persist calculation parameters without running a calculation."""
        twin = self._require_twin(twin_id, user_id)
        config = self._ensure_config(twin_id, twin, commit=False)

        if update.params:
            config.params = to_json(update.params.to_persisted_payload())

        self.db.add(config)
        self.db.commit()
        self.db.refresh(config)
        return optimizer_config_to_response(config)

    def save_result(
        self,
        twin_id: str,
        user_id: str,
        update: OptimizerResultUpdate,
    ) -> OptimizerConfigResponse:
        """Persist full calculation result, pricing evidence, and cheapest path."""
        twin = self._require_twin(twin_id, user_id)
        config = self._ensure_config(twin_id, twin, commit=False)

        config.params = to_json(update.params.to_persisted_payload())
        config.result_json = to_json(update.result)
        set_cheapest_columns_from_payload(
            config,
            cheapest_path=update.cheapest_path,
            optimizer_result=update.result,
        )

        snapshots = update.pricing_snapshots or {}
        config.pricing_aws_snapshot = to_json(_dict_or_none(snapshots.get("aws")))
        config.pricing_azure_snapshot = to_json(_dict_or_none(snapshots.get("azure")))
        config.pricing_gcp_snapshot = to_json(_dict_or_none(snapshots.get("gcp")))

        timestamps = update.pricing_timestamps or {}
        config.pricing_aws_updated_at = parse_iso_safe(timestamps.get("aws"))
        config.pricing_azure_updated_at = parse_iso_safe(timestamps.get("azure"))
        config.pricing_gcp_updated_at = parse_iso_safe(timestamps.get("gcp"))
        config.calculated_at = datetime.now(timezone.utc)

        self.db.add(config)
        self.db.commit()
        self.db.refresh(config)
        return optimizer_config_to_response(config)

    def get_cheapest_path(self, twin_id: str, user_id: str) -> dict[str, str | None]:
        """Return cheapest provider selection for deployment logic."""
        twin = self._require_twin(twin_id, user_id)
        config = twin.optimizer_config
        if not config or not config.cheapest_l1:
            raise EntityNotFoundError("No optimizer result found. Run calculation first.")
        return cheapest_path_dict(config)

    def _require_twin(self, twin_id: str, user_id: str):
        twin = self.twin_repository.get_active_for_user(twin_id, user_id)
        if not twin:
            raise EntityNotFoundError("Twin not found")
        return twin

    def _ensure_config(self, twin_id: str, twin, *, commit: bool = True) -> OptimizerConfiguration:
        if twin.optimizer_config:
            return twin.optimizer_config

        config = OptimizerConfiguration(twin_id=twin_id)
        self.db.add(config)
        twin.optimizer_config = config
        if commit:
            self.db.commit()
            self.db.refresh(config)
        return config


def _dict_or_none(value: Any) -> dict[str, Any] | None:
    return value if isinstance(value, dict) else None
