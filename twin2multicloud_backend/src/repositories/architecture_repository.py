"""Thin persistence queries for architecture selections and resolutions."""

from __future__ import annotations

from sqlalchemy.orm import Session, joinedload

from src.models.architecture_profile import (
    ResolvedTwinArchitectureRecord,
    TwinArchitectureSelection,
)
from src.models.cost_calculation import CostCalculationRun
from src.models.twin import DigitalTwin, TwinState


class ArchitectureRepository:
    """Owner-scoped architecture persistence adapter."""

    def __init__(self, db: Session):
        self.db = db

    def get_twin(self, twin_id: str, user_id: str) -> DigitalTwin | None:
        return (
            self.db.query(DigitalTwin)
            .filter(
                DigitalTwin.id == twin_id,
                DigitalTwin.user_id == user_id,
                DigitalTwin.state != TwinState.INACTIVE,
            )
            .one_or_none()
        )

    def get_selection(
        self,
        twin_id: str,
        user_id: str,
    ) -> TwinArchitectureSelection | None:
        return (
            self.db.query(TwinArchitectureSelection)
            .filter(
                TwinArchitectureSelection.twin_id == twin_id,
                TwinArchitectureSelection.user_id == user_id,
            )
            .one_or_none()
        )

    def selected_run(
        self,
        twin_id: str,
        user_id: str,
    ) -> CostCalculationRun | None:
        return (
            self.db.query(CostCalculationRun)
            .filter(
                CostCalculationRun.twin_id == twin_id,
                CostCalculationRun.user_id == user_id,
                CostCalculationRun.selected_for_deployment_at.is_not(None),
            )
            .one_or_none()
        )

    def get_resolution_for_run(
        self,
        calculation_run_id: str,
        user_id: str,
    ) -> ResolvedTwinArchitectureRecord | None:
        return (
            self.db.query(ResolvedTwinArchitectureRecord)
            .options(
                joinedload(ResolvedTwinArchitectureRecord.components),
                joinedload(ResolvedTwinArchitectureRecord.edges),
            )
            .filter(
                ResolvedTwinArchitectureRecord.calculation_run_id
                == calculation_run_id,
                ResolvedTwinArchitectureRecord.user_id == user_id,
            )
            .one_or_none()
        )

    def get_resolution_for_selected_run(
        self,
        twin_id: str,
        user_id: str,
    ) -> ResolvedTwinArchitectureRecord | None:
        run = self.selected_run(twin_id, user_id)
        if run is None:
            return None
        return self.get_resolution_for_run(run.id, user_id)
