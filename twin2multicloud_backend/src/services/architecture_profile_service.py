"""Read the one canonical Six-layer architecture contract and Twin pins."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from src.models.architecture_profile import TwinArchitectureSelection
from src.repositories.architecture_repository import ArchitectureRepository
from src.schemas.architecture_profile import (
    ArchitectureExtensionSlotSummary,
    ArchitectureProfileDetailResponse,
    ArchitectureProfileSummaryResponse,
    ArchitectureProviderSummary,
    ArchitectureResponsibilitySummary,
    ArchitectureVisualization,
    ArchitectureVisualizationEdge,
    ArchitectureVisualizationNode,
    PinnedArchitectureReference,
    TwinArchitectureSelectionResponse,
)
from src.services.architecture_contract_service import ArchitectureContractService
from src.services.architecture_errors import architecture_error


DEFINITIONS_ROOT = (
    Path(__file__).resolve().parents[1]
    / "contracts"
    / "generated"
    / "architecture-profiles"
    / "definitions"
)
CANONICAL_ARCHITECTURE_ID = "six-layer-eventing"
CANONICAL_ARCHITECTURE_VERSION = "1"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("Architecture contract definition is unavailable") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("Architecture contract definition must be an object")
    return payload


def _provider_documents() -> tuple[dict[str, Any], ...]:
    root = (
        DEFINITIONS_ROOT
        / "provider-implementations"
        / CANONICAL_ARCHITECTURE_ID
        / CANONICAL_ARCHITECTURE_VERSION
    )
    return tuple(_read_json(path) for path in sorted(root.glob("*/*.json")))


def _catalog_documents() -> tuple[dict[str, Any], ...]:
    return tuple(
        _read_json(path)
        for path in sorted(
            (DEFINITIONS_ROOT / "component-catalogs").glob("*/*/catalog.json")
        )
    )


class ArchitectureProfileService:
    """Compatibility-named service for the fixed architecture contract.

    The persisted record pins the canonical contract digest to a Twin. It is
    not a user-selectable profile and has no registration or change workflow.
    """

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
        if profile_id != CANONICAL_ARCHITECTURE_ID:
            raise architecture_error(
                "ARCH_PROFILE_NOT_FOUND",
                "The canonical architecture contract was not found.",
            )
        if profile_version != CANONICAL_ARCHITECTURE_VERSION:
            raise architecture_error(
                "ARCH_PROFILE_VERSION_UNSUPPORTED",
                "The canonical architecture contract version is not available.",
            )

        path = (
            DEFINITIONS_ROOT
            / "profiles"
            / CANONICAL_ARCHITECTURE_ID
            / CANONICAL_ARCHITECTURE_VERSION
            / "profile.json"
        )
        profile = _read_json(path)
        providers = _provider_documents()
        catalogs = _catalog_documents()
        ArchitectureContractService.read_bundle((profile, *providers, *catalogs))
        if require_active and profile.get("lifecycle_status") != "active":
            raise architecture_error(
                "ARCH_PROFILE_NOT_ACTIVE",
                "The canonical architecture contract is not active.",
            )
        return profile

    @staticmethod
    def default_reference() -> PinnedArchitectureReference:
        profile = ArchitectureProfileService.get_definition(
            CANONICAL_ARCHITECTURE_ID,
            CANONICAL_ARCHITECTURE_VERSION,
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
        """Create the immutable canonical-contract pin for a new Twin."""
        reference = reference or ArchitectureProfileService.default_reference()
        if (
            reference.id != CANONICAL_ARCHITECTURE_ID
            or reference.version != CANONICAL_ARCHITECTURE_VERSION
        ):
            raise architecture_error(
                "ARCH_PROFILE_NOT_FOUND",
                "Only the canonical Six-layer architecture can be pinned.",
            )
        return TwinArchitectureSelection(
            twin_id=twin_id,
            user_id=user_id,
            profile_id=reference.id,
            profile_version=reference.version,
            profile_digest=reference.digest,
            revision=1,
            selected_by_user_id=user_id,
        )

    def get_profile(self) -> ArchitectureProfileDetailResponse:
        profile = self.get_definition(
            CANONICAL_ARCHITECTURE_ID,
            CANONICAL_ARCHITECTURE_VERSION,
        )
        summary = self._summary(profile)
        nodes = [
            ArchitectureVisualizationNode(
                id=component["component_id"],
                label=component["component_id"]
                .removeprefix("component.")
                .replace("-", " ")
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

    def get_selection(
        self,
        *,
        twin_id: str,
        user_id: str,
    ) -> TwinArchitectureSelectionResponse:
        self._require_db()
        if self.repository.get_twin(twin_id, user_id) is None:
            raise architecture_error(
                "ARCH_PROFILE_NOT_FOUND",
                "The Twin architecture contract was not found.",
            )
        selection = self.repository.get_selection(twin_id, user_id)
        if selection is None:
            raise RuntimeError("Twin architecture contract pin is missing")
        return TwinArchitectureSelectionResponse.model_validate(selection)

    @staticmethod
    def _summary(profile: dict[str, Any]) -> ArchitectureProfileSummaryResponse:
        providers = [
            ArchitectureProviderSummary(
                provider=document["provider"],
                supported=document["supported"],
                profile_id=document["implementation_profile_id"],
                profile_version=document["implementation_profile_version"],
                reason_codes=[
                    reason["reason_code"]
                    for reason in document["unsupported_reasons"]
                ],
            )
            for document in _provider_documents()
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
                    key=lambda value: (value["slot_id"], int(value["slot_version"])),
                )
            ],
        )

    def _require_db(self) -> None:
        if self.db is None or self.repository is None:
            raise RuntimeError("ArchitectureProfileService requires a database")
