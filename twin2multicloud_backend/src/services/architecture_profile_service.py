"""Repository-backed architecture profile reads and transactional selection."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from src.models.architecture_profile import (
    ArchitectureAuditEvent,
    TwinArchitectureSelection,
)
from src.models.deployment_preflight import DeploymentPreflightCache
from src.models.twin import TwinState
from src.models.user_function_extension import TwinExtensionBinding
from src.repositories.architecture_repository import ArchitectureRepository
from src.schemas.architecture_profile import (
    ArchitectureExtensionSlotSummary,
    ArchitectureProfileChangePreviewResponse,
    ArchitectureProfileDetailResponse,
    ArchitectureProfileSelectionResult,
    ArchitectureProfileSummaryResponse,
    ArchitectureProviderSummary,
    ArchitectureResponsibilitySummary,
    ArchitectureVisualization,
    ArchitectureVisualizationEdge,
    ArchitectureVisualizationNode,
    IncompatibleExtensionBinding,
    IncompatibleWorkloadField,
    PinnedArchitectureReference,
    TwinArchitectureSelectionResponse,
)
from src.security.request_context import current_request_id
from src.services.architecture_contract_service import (
    ArchitectureContractService,
    canonical_json,
)
from src.services.architecture_errors import architecture_error


DEFINITIONS_ROOT = (
    Path(__file__).resolve().parents[1]
    / "contracts"
    / "generated"
    / "architecture-profiles"
    / "definitions"
)
DEFAULT_PROFILE_ID = "six-layer-eventing"
DEFAULT_PROFILE_VERSION = "1"
# Six-layer is the sole profile owned by Management. Historical comparison
# architectures remain internal to the Optimizer and are not API profiles.
RUNTIME_SELECTABLE_PROFILE_REFS: frozenset[tuple[str, str]] = frozenset(
    {("six-layer-eventing", "1")}
)
MAX_ACTIVE_PROFILE_VERSIONS = 32
PROFILE_ID_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:[.-][a-z0-9]+)*$")
PROFILE_VERSION_PATTERN = re.compile(r"^[1-9][0-9]*$")
MUTATION_BLOCKED_STATES = {
    TwinState.DEPLOYED,
    TwinState.DEPLOYING,
    TwinState.DESTROYING,
}
MUTATION_REGRESS_STATES = {
    TwinState.CONFIGURED,
    TwinState.ERROR,
    TwinState.DESTROYED,
}
WORKLOAD_STORAGE_KEYS: dict[str, tuple[str, ...]] = {
    "workload.eventing-scenario": ("eventingScenarioId",),
    "workload.telemetry-update-count": (
        "numberOfDevices",
        "deviceSendingIntervalInMinutes",
        "eventsPerMessage",
    ),
    "workload.logical-query-count": (
        "dashboardRefreshesPerHour",
        "apiCallsPerDashboardRefresh",
        "dashboardActiveHoursPerDay",
        "amountOfActiveEditors",
        "amountOfActiveViewers",
    ),
}


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("Architecture profile definition is unavailable") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("Architecture profile definition must be an object")
    return payload


def _provider_documents(
    profile_id: str,
    profile_version: str,
) -> tuple[dict[str, Any], ...]:
    root = DEFINITIONS_ROOT / "provider-implementations" / profile_id / profile_version
    documents: list[dict[str, Any]] = []
    if root.exists():
        for path in sorted(root.glob("*/*.json")):
            documents.append(_read_json(path))
    return tuple(documents)


def _catalog_documents() -> tuple[dict[str, Any], ...]:
    return tuple(
        _read_json(path)
        for path in sorted(
            (DEFINITIONS_ROOT / "component-catalogs").glob("*/*/catalog.json")
        )
    )


class ArchitectureProfileService:
    """Read active definitions and own profile selection invalidation."""

    def __init__(
        self,
        db: Session | None = None,
        repository: ArchitectureRepository | None = None,
    ) -> None:
        self.db = db
        self.repository = repository or (
            ArchitectureRepository(db) if db is not None else None
        )

    @staticmethod
    def get_definition(
        profile_id: str,
        profile_version: str,
        *,
        require_active: bool = True,
    ) -> dict[str, Any]:
        if PROFILE_ID_PATTERN.fullmatch(profile_id) is None:
            raise architecture_error(
                "ARCH_PROFILE_NOT_FOUND",
                "The architecture profile was not found.",
            )
        if PROFILE_VERSION_PATTERN.fullmatch(profile_version) is None:
            raise architecture_error(
                "ARCH_PROFILE_VERSION_UNSUPPORTED",
                "The architecture profile version is not available.",
            )
        profile_root = DEFINITIONS_ROOT / "profiles" / profile_id
        if not profile_root.exists():
            raise architecture_error(
                "ARCH_PROFILE_NOT_FOUND",
                "The architecture profile was not found.",
            )
        path = profile_root / profile_version / "profile.json"
        if not path.exists():
            raise architecture_error(
                "ARCH_PROFILE_VERSION_UNSUPPORTED",
                "The architecture profile version is not available.",
            )
        profile = _read_json(path)
        providers = _provider_documents(profile_id, profile_version)
        catalogs = _catalog_documents()
        ArchitectureContractService.read_bundle((profile, *providers, *catalogs))
        if require_active and profile.get("lifecycle_status") != "active":
            raise architecture_error(
                "ARCH_PROFILE_NOT_ACTIVE",
                "The architecture profile version is not active.",
            )
        return profile

    @staticmethod
    def default_reference() -> PinnedArchitectureReference:
        """Return the pinned default reference for newly created Twins.

        This is not by itself proof that the profile is runtime-selectable;
        mutations still pass ``get_selectable_definition``.
        """
        profile = ArchitectureProfileService.get_definition(
            DEFAULT_PROFILE_ID,
            DEFAULT_PROFILE_VERSION,
            require_active=False,
        )
        return PinnedArchitectureReference(
            id=profile["profile_id"],
            version=profile["profile_version"],
            digest=profile["content_digest"],
        )

    @staticmethod
    def build_default_selection(
        *,
        twin_id: str,
        user_id: str,
        reference: PinnedArchitectureReference | None = None,
    ) -> TwinArchitectureSelection:
        reference = reference or ArchitectureProfileService.default_reference()
        return TwinArchitectureSelection(
            twin_id=twin_id,
            user_id=user_id,
            profile_id=reference.id,
            profile_version=reference.version,
            profile_digest=reference.digest,
            revision=1,
            selected_by_user_id=user_id,
        )

    def list_profiles(self) -> list[ArchitectureProfileSummaryResponse]:
        profiles: list[ArchitectureProfileSummaryResponse] = []
        root = DEFINITIONS_ROOT / "profiles"
        for path in sorted(root.glob("*/*/profile.json")):
            profile = _read_json(path)
            reference = (
                str(profile.get("profile_id")),
                str(profile.get("profile_version")),
            )
            if reference not in RUNTIME_SELECTABLE_PROFILE_REFS:
                continue
            validated = self.get_selectable_definition(
                reference[0],
                reference[1],
            )
            profiles.append(self._summary(validated))
        profiles.sort(key=lambda item: (item.profile_id, int(item.profile_version)))
        if len(profiles) > MAX_ACTIVE_PROFILE_VERSIONS:
            raise RuntimeError(
                "Architecture profile catalog exceeds the 32-version bound"
            )
        return profiles

    def get_profile(
        self,
        profile_id: str,
        profile_version: str,
    ) -> ArchitectureProfileDetailResponse:
        profile = self.get_selectable_definition(profile_id, profile_version)
        summary = self._summary(profile)
        nodes = [
            ArchitectureVisualizationNode(
                id=component["component_id"],
                label=component["component_id"]
                .removeprefix("component.")
                .replace(
                    "-",
                    " ",
                )
                .title(),
                responsibility_id=component["responsibility_id"],
            )
            for component in profile["components"]
        ]
        edges = [
            ArchitectureVisualizationEdge(
                id=edge["edge_id"],
                source=edge["source_component_id"],
                destination=edge["destination_component_id"],
            )
            for edge in profile["edges"]
        ]
        return ArchitectureProfileDetailResponse(
            **summary.model_dump(),
            logical_components=profile["components"],
            logical_edges=profile["edges"],
            visualization=ArchitectureVisualization(nodes=nodes, edges=edges),
        )

    @staticmethod
    def get_selectable_definition(
        profile_id: str,
        profile_version: str,
    ) -> dict[str, Any]:
        """Load a reviewed definition only when its runtime gate is active."""
        profile = ArchitectureProfileService.get_definition(
            profile_id,
            profile_version,
            require_active=False,
        )
        if (
            profile_id,
            profile_version,
        ) not in RUNTIME_SELECTABLE_PROFILE_REFS or profile.get(
            "lifecycle_status"
        ) != "active":
            raise architecture_error(
                "ARCH_PROFILE_NOT_ACTIVE",
                "The architecture profile version is not active.",
            )
        return profile

    def get_selection(
        self,
        *,
        twin_id: str,
        user_id: str,
    ) -> TwinArchitectureSelectionResponse:
        selection = self._require_selection(twin_id, user_id)
        return TwinArchitectureSelectionResponse.model_validate(selection)

    def preview_change(
        self,
        *,
        twin_id: str,
        user_id: str,
        profile_id: str,
        profile_version: str,
        expected_revision: int,
    ) -> ArchitectureProfileChangePreviewResponse:
        selection = self._require_selection(twin_id, user_id)
        if selection.revision != expected_revision:
            self._audit_rejection(
                selection,
                code="ARCH_SELECTION_REVISION_CONFLICT",
                action="profile.change.preview",
            )
            raise architecture_error(
                "ARCH_SELECTION_REVISION_CONFLICT",
                "The architecture selection revision is stale.",
            )
        target = self.get_selectable_definition(profile_id, profile_version)
        return self._build_preview(selection, target)

    def select_profile(
        self,
        *,
        twin_id: str,
        user_id: str,
        profile_id: str,
        profile_version: str,
        expected_revision: int,
        invalidation_digest: str,
    ) -> ArchitectureProfileSelectionResult:
        selection = self._require_selection(twin_id, user_id)
        twin = self.repository.get_twin(twin_id, user_id)
        if twin is None:
            raise architecture_error(
                "ARCH_SELECTION_FORBIDDEN",
                "The architecture selection cannot be changed.",
            )
        if twin.state in MUTATION_BLOCKED_STATES:
            self._audit_rejection(
                selection,
                code="ARCH_SELECTION_FORBIDDEN",
                action="profile.change",
            )
            raise architecture_error(
                "ARCH_SELECTION_FORBIDDEN",
                "The architecture selection cannot change during a deployment.",
            )
        if selection.revision != expected_revision:
            self._audit_rejection(
                selection,
                code="ARCH_SELECTION_REVISION_CONFLICT",
                action="profile.change",
            )
            raise architecture_error(
                "ARCH_SELECTION_REVISION_CONFLICT",
                "The architecture selection revision is stale.",
            )

        target = self.get_selectable_definition(profile_id, profile_version)
        preview = self._build_preview(selection, target)
        if preview.invalidation_digest != invalidation_digest:
            self._audit_rejection(
                selection,
                code="ARCH_SELECTION_INVALIDATION_STALE",
                action="profile.change",
            )
            raise architecture_error(
                "ARCH_SELECTION_INVALIDATION_STALE",
                "The profile-change preview is stale.",
            )

        same_profile = (
            selection.profile_id == target["profile_id"]
            and selection.profile_version == target["profile_version"]
            and selection.profile_digest == target["content_digest"]
        )
        if same_profile:
            self._audit(selection, action="profile.select", outcome="idempotent")
            self.db.commit()
            return ArchitectureProfileSelectionResult(
                selection=TwinArchitectureSelectionResponse.model_validate(selection),
                revision=selection.revision,
                invalidated_calculation_run_id=None,
                unbound_extension_slot_ids=[],
                cleared_workload_field_ids=[],
                deployment_readiness_state="unchanged",
            )

        now = datetime.now(timezone.utc)
        selected_run = self.repository.selected_run(twin_id, user_id)
        incompatible_workload_ids = [
            field.field_id for field in preview.incompatible_workload_fields
        ]
        cleared_ids = self._clear_workload_fields(
            twin,
            incompatible_workload_ids,
        )
        if selected_run is not None:
            selected_run.selected_for_deployment_at = None
            self._audit(
                selection,
                action="run.invalidation",
                outcome="succeeded",
                calculation_run_id=selected_run.id,
            )
        unbound_slots = self._apply_extension_unbinds(
            preview.incompatible_extension_bindings,
            twin_id=twin_id,
            now=now,
        )
        readiness_invalidated = bool(preview.deployment_readiness_sections)
        if readiness_invalidated:
            (
                self.db.query(DeploymentPreflightCache)
                .filter(DeploymentPreflightCache.twin_id == twin_id)
                .delete(synchronize_session="fetch")
            )
        if twin.state in MUTATION_REGRESS_STATES:
            twin.state = TwinState.DRAFT

        selection.profile_id = target["profile_id"]
        selection.profile_version = target["profile_version"]
        selection.profile_digest = target["content_digest"]
        selection.revision += 1
        selection.selected_at = now
        selection.updated_at = now
        selection.selected_by_user_id = user_id
        self._audit(selection, action="profile.change", outcome="succeeded")
        try:
            self.db.commit()
        except (IntegrityError, StaleDataError) as exc:
            self.db.rollback()
            raise architecture_error(
                "ARCH_SELECTION_REVISION_CONFLICT",
                "The architecture selection changed concurrently.",
            ) from exc
        self.db.refresh(selection)
        return ArchitectureProfileSelectionResult(
            selection=TwinArchitectureSelectionResponse.model_validate(selection),
            revision=selection.revision,
            invalidated_calculation_run_id=(
                selected_run.id if selected_run is not None else None
            ),
            unbound_extension_slot_ids=unbound_slots,
            cleared_workload_field_ids=cleared_ids,
            deployment_readiness_state=(
                "invalidated" if readiness_invalidated else "unchanged"
            ),
        )

    def _summary(
        self,
        profile: dict[str, Any],
    ) -> ArchitectureProfileSummaryResponse:
        providers = [
            ArchitectureProviderSummary(
                provider=document["provider"],
                supported=document["supported"],
                profile_id=document["implementation_profile_id"],
                profile_version=document["implementation_profile_version"],
                reason_codes=[
                    reason["reason_code"] for reason in document["unsupported_reasons"]
                ],
            )
            for document in _provider_documents(
                profile["profile_id"],
                profile["profile_version"],
            )
        ]
        providers.sort(key=lambda item: item.provider)
        responsibilities = [
            ArchitectureResponsibilitySummary(
                responsibility_id=item["responsibility_id"],
                display_name=item["display_name"],
                required=item["required"],
                capability_ids=sorted(item["capability_requirements"]),
                workload_field_ids=sorted(item["workload_field_refs"]),
            )
            for item in sorted(
                profile["responsibilities"],
                key=lambda value: value["evaluation_order"],
            )
        ]
        return ArchitectureProfileSummaryResponse(
            profile_id=profile["profile_id"],
            profile_version=profile["profile_version"],
            profile_digest=profile["content_digest"],
            display_name=profile["display_name"],
            description=profile["description"],
            lifecycle_status="active",
            responsibilities=responsibilities,
            capability_ids=sorted(
                {
                    capability
                    for item in responsibilities
                    for capability in item.capability_ids
                }
            ),
            workload_contract_ref=PinnedArchitectureReference(
                **profile["workload_contract_ref"]
            ),
            available_providers=[item for item in providers if item.supported],
            unsupported_providers=[item for item in providers if not item.supported],
            extension_slots=[
                ArchitectureExtensionSlotSummary(
                    slot_id=item["slot_id"],
                    slot_version=item["slot_version"],
                    logical_component_id=item["component_id"],
                )
                for item in sorted(
                    profile["extension_slots"],
                    key=lambda value: (
                        value["slot_id"],
                        int(value["slot_version"]),
                    ),
                )
            ],
        )

    def _require_selection(
        self,
        twin_id: str,
        user_id: str,
    ) -> TwinArchitectureSelection:
        self._require_db()
        if self.repository.get_twin(twin_id, user_id) is None:
            raise architecture_error(
                "ARCH_PROFILE_NOT_FOUND",
                "The architecture profile selection was not found.",
            )
        selection = self.repository.get_selection(twin_id, user_id)
        if selection is None:
            raise RuntimeError("Twin architecture selection invariant is missing")
        return selection

    def _build_preview(
        self,
        selection: TwinArchitectureSelection,
        target: dict[str, Any],
    ) -> ArchitectureProfileChangePreviewResponse:
        current = self.get_definition(
            selection.profile_id,
            selection.profile_version,
            require_active=False,
        )
        same_profile = (
            selection.profile_id == target["profile_id"]
            and selection.profile_version == target["profile_version"]
            and selection.profile_digest == target["content_digest"]
        )
        incompatible_workload: list[IncompatibleWorkloadField] = []
        incompatible_bindings: list[IncompatibleExtensionBinding] = []
        selected_run_id: str | None = None
        readiness_sections: list[str] = []
        if not same_profile:
            target_fields = self._workload_fields(target)
            incompatible_workload = [
                IncompatibleWorkloadField(
                    field_id=field_id,
                    display_label=field_id.removeprefix("workload.")
                    .replace("-", " ")
                    .title(),
                )
                for field_id in sorted(self._workload_fields(current) - target_fields)
            ]
            target_slots = {
                (item["slot_id"], item["slot_version"])
                for item in target["extension_slots"]
            }
            queried_bindings = (
                self.db.query(TwinExtensionBinding)
                .filter(
                    TwinExtensionBinding.twin_id == selection.twin_id,
                    TwinExtensionBinding.user_id == selection.user_id,
                    TwinExtensionBinding.active.is_(True),
                )
                .all()
            )
            bindings = [binding for binding in queried_bindings if binding.active]
            incompatible_bindings = [
                IncompatibleExtensionBinding(
                    slot_id=binding.slot_id,
                    slot_version=binding.slot_version,
                    artifact_id=binding.artifact_id,
                )
                for binding in sorted(
                    bindings,
                    key=lambda item: (
                        item.slot_id,
                        int(item.slot_version),
                        item.artifact_id,
                    ),
                )
                if (binding.slot_id, binding.slot_version) not in target_slots
            ]
            selected_run = self.repository.selected_run(
                selection.twin_id,
                selection.user_id,
            )
            selected_run_id = selected_run.id if selected_run is not None else None
            has_readiness = (
                self.db.query(DeploymentPreflightCache)
                .filter(DeploymentPreflightCache.twin_id == selection.twin_id)
                .count()
                > 0
            )
            readiness_sections = ["deployment_preflight"] if has_readiness else []

        digest_payload = {
            "current_revision": selection.revision,
            "target_profile_digest": target["content_digest"],
            "invalidation": {
                "workload_field_ids": [item.field_id for item in incompatible_workload],
                "extension_bindings": [
                    item.model_dump() for item in incompatible_bindings
                ],
                "selected_calculation_run_id": selected_run_id,
                "deployment_readiness_sections": readiness_sections,
            },
        }
        invalidation_digest = (
            "sha256:"
            + hashlib.sha256(canonical_json(digest_payload).encode("utf-8")).hexdigest()
        )
        return ArchitectureProfileChangePreviewResponse(
            current=PinnedArchitectureReference(
                id=selection.profile_id,
                version=selection.profile_version,
                digest=selection.profile_digest,
            ),
            target=PinnedArchitectureReference(
                id=target["profile_id"],
                version=target["profile_version"],
                digest=target["content_digest"],
            ),
            expected_revision=selection.revision,
            incompatible_workload_fields=incompatible_workload,
            incompatible_extension_bindings=incompatible_bindings,
            selected_calculation_run_id=selected_run_id,
            deployment_readiness_sections=readiness_sections,
            invalidation_digest=invalidation_digest,
        )

    @staticmethod
    def _workload_fields(profile: dict[str, Any]) -> set[str]:
        return {
            field_id
            for responsibility in profile["responsibilities"]
            for field_id in responsibility["workload_field_refs"]
        }

    @staticmethod
    def _clear_workload_fields(twin, field_ids: list[str]) -> list[str]:
        config = twin.optimizer_config
        if config is None or not config.params:
            return []
        try:
            params = json.loads(config.params)
        except json.JSONDecodeError as exc:
            raise architecture_error(
                "ARCH_SELECTION_FORBIDDEN",
                "The stored workload state cannot be safely invalidated.",
            ) from exc
        if not isinstance(params, dict):
            raise architecture_error(
                "ARCH_SELECTION_FORBIDDEN",
                "The stored workload state cannot be safely invalidated.",
            )
        if any(field_id not in WORKLOAD_STORAGE_KEYS for field_id in field_ids):
            raise architecture_error(
                "ARCH_SELECTION_FORBIDDEN",
                "The stored workload state cannot be safely invalidated.",
            )
        cleared: list[str] = []
        for field_id in field_ids:
            removed = False
            for storage_key in WORKLOAD_STORAGE_KEYS[field_id]:
                if storage_key in params:
                    params.pop(storage_key)
                    removed = True
            if removed:
                cleared.append(field_id)
        try:
            canonical_params = json.dumps(
                params,
                ensure_ascii=True,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        except (TypeError, ValueError) as exc:
            raise architecture_error(
                "ARCH_SELECTION_FORBIDDEN",
                "The stored workload state cannot be safely invalidated.",
            ) from exc
        config.params = canonical_params
        return cleared

    def _apply_extension_unbinds(
        self,
        bindings: list[IncompatibleExtensionBinding],
        *,
        twin_id: str,
        now: datetime,
    ) -> list[str]:
        unbound: list[str] = []
        for item in bindings:
            row = (
                self.db.query(TwinExtensionBinding)
                .filter(
                    TwinExtensionBinding.twin_id == twin_id,
                    TwinExtensionBinding.slot_id == item.slot_id,
                    TwinExtensionBinding.slot_version == item.slot_version,
                    TwinExtensionBinding.artifact_id == item.artifact_id,
                    TwinExtensionBinding.active.is_(True),
                )
                .one_or_none()
            )
            if row is not None:
                row.active = False
                row.unbound_at = now
                unbound.append(row.slot_id)
        return sorted(set(unbound))

    def _audit(
        self,
        selection: TwinArchitectureSelection,
        *,
        action: str,
        outcome: str,
        result_code: str | None = None,
        calculation_run_id: str | None = None,
    ) -> None:
        self.db.add(
            ArchitectureAuditEvent(
                user_id=selection.user_id,
                action=action,
                outcome=outcome,
                profile_id=selection.profile_id,
                profile_version=selection.profile_version,
                profile_digest=selection.profile_digest,
                twin_id=selection.twin_id,
                calculation_run_id=calculation_run_id,
                result_code=result_code,
                correlation_id=current_request_id(),
            )
        )

    def _audit_rejection(
        self,
        selection: TwinArchitectureSelection,
        *,
        code: str,
        action: str,
    ) -> None:
        self._audit(
            selection,
            action=action,
            outcome="rejected",
            result_code=code,
        )
        self.db.commit()

    def _require_db(self) -> None:
        if self.db is None or self.repository is None:
            raise RuntimeError("ArchitectureProfileService requires a database")
