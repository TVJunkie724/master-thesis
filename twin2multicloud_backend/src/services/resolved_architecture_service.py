"""Validation, immutable persistence, projection, and reads for resolved architectures."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from decimal import Decimal, InvalidOperation
import hashlib
import hmac
import json
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.models.architecture_profile import (
    ArchitectureAuditEvent,
    ResolvedArchitectureComponentAssignment,
    ResolvedArchitectureEdge,
    ResolvedTwinArchitectureRecord,
)
from src.models.cost_calculation import CostCalculationRun
from src.models.user_function_extension import TwinExtensionBinding
from src.repositories.architecture_repository import ArchitectureRepository
from src.schemas.architecture_profile import ResolvedArchitectureReadResponse
from src.security.request_context import current_request_id
from src.services.architecture_contract_service import (
    ArchitectureContractService,
    ContractError,
    canonical_json,
)
from src.services.architecture_errors import (
    ArchitectureDomainError,
    architecture_error,
)
from src.services.architecture_profile_service import (
    ArchitectureProfileService,
    _catalog_documents,
    _provider_documents,
)


SCHEMA_VERSION = "resolved-twin-architecture.v1"
READY = "ready"
LEGACY_NOT_RESOLVABLE = "legacy_not_resolvable"
BASELINE_PROFILE = ("five-layer-baseline", "1")
COMPONENT_TO_FIXED_FIELD = {
    "component.ingestion": "cheapest_l1",
    "component.processing": "cheapest_l2",
    "component.hot-storage": "cheapest_l3_hot",
    "component.cool-storage": "cheapest_l3_cool",
    "component.archive-storage": "cheapest_l3_archive",
    "component.twin-state": "cheapest_l4",
    "component.visualization": "cheapest_l5",
}
LEGACY_PROVIDER_LABELS = {
    "aws": "AWS",
    "azure": "Azure",
    "gcp": "GCP",
}
ARCHITECTURE_METRICS: Counter[tuple[str, str]] = Counter()


def _json(value: object) -> str:
    return canonical_json(value)


def _loaded(value: str) -> Any:
    return json.loads(value)


def _metric(outcome: str, profile_version: str) -> None:
    ARCHITECTURE_METRICS[(outcome, profile_version)] += 1


def _contract_error(exc: Exception) -> ArchitectureDomainError:
    code = getattr(exc, "code", "")
    path = str(getattr(exc, "path", ""))
    if code == "ARCH_DIGEST_MISMATCH":
        mapped = "ARCH_RESOLUTION_DIGEST_MISMATCH"
    elif (
        code == "ARCH_SCHEMA_INVALID"
        and path.startswith("functional_completeness")
    ):
        mapped = "ARCH_RESOLUTION_INCOMPLETE"
    elif code in {
        "ARCH_REFERENCE_UNRESOLVED",
        "ARCH_DEPLOYMENT_SPEC_INCOMPATIBLE",
        "ARCH_COMPONENT_UNAVAILABLE",
        "ARCH_EDGE_UNAVAILABLE",
        "ARCH_EXTENSION_BINDING_INVALID",
        "ARCH_BUNDLE_INCOMPATIBLE",
    }:
        mapped = "ARCH_RESOLUTION_REFERENCE_MISMATCH"
    elif code in {"ARCH_CAPABILITY_INCOMPLETE", "ARCH_FUNCTIONAL_INCOMPLETE"}:
        mapped = "ARCH_RESOLUTION_INCOMPLETE"
    else:
        mapped = "ARCH_RESOLUTION_INVALID"
    return architecture_error(
        mapped,
        "The resolved architecture contract is invalid.",
        field=path or None,
    )


class ResolvedArchitectureService:
    """Persist only server-validated, immutable architecture resolutions."""

    def __init__(
        self,
        db: Session,
        repository: ArchitectureRepository | None = None,
    ) -> None:
        self.db = db
        self.repository = repository or ArchitectureRepository(db)

    def persist(
        self,
        *,
        run: CostCalculationRun,
        raw_architecture: Mapping[str, Any],
        origin: str = "native_v1",
        linked_documents: Iterable[Mapping[str, Any]] | None = None,
        apply_legacy_projection: bool = True,
    ) -> ResolvedTwinArchitectureRecord:
        """Validate and stage one resolution and all projections atomically."""

        if origin not in {"native_v1", "reconstructed_v1"}:
            raise architecture_error(
                "ARCH_RESOLUTION_INVALID",
                "The resolved architecture origin is invalid.",
            )
        try:
            with self.db.no_autoflush:
                duplicate = run.resolved_architecture is not None
                if not duplicate and run in self.db:
                    duplicate = (
                        self.db.query(ResolvedTwinArchitectureRecord)
                        .filter(
                            ResolvedTwinArchitectureRecord.calculation_run_id
                            == run.id
                        )
                        .first()
                        is not None
                    )
                if duplicate:
                    self._record_failure(
                        run,
                        code="ARCH_RESOLUTION_DUPLICATE",
                        action="resolution.persistence",
                    )
                    raise architecture_error(
                        "ARCH_RESOLUTION_DUPLICATE",
                        "The calculation run already owns a resolved architecture.",
                    )
                architecture = self.validate(
                    run=run,
                    raw_architecture=raw_architecture,
                    linked_documents=linked_documents,
                )
                record = self._build_record(run, architecture, origin=origin)
                self.db.add(record)
                run.architecture_compatibility_status = READY
                run.resolved_architecture_version = architecture[
                    "schema_version"
                ]
                run.resolved_architecture_digest = architecture[
                    "content_digest"
                ]
                if apply_legacy_projection:
                    self.apply_fixed_projection(run, architecture)
            self.db.flush()
        except ArchitectureDomainError as exc:
            profile_version = "unknown"
            if isinstance(raw_architecture, Mapping):
                profile_ref = raw_architecture.get(
                    "architecture_profile_ref"
                )
                if isinstance(profile_ref, Mapping):
                    profile_version = str(
                        profile_ref.get("version") or "unknown"
                    )
            _metric(exc.code, profile_version)
            raise
        except IntegrityError as exc:
            raise architecture_error(
                "ARCH_RESOLUTION_DUPLICATE",
                "The calculation run already owns a resolved architecture.",
            ) from exc
        self._audit(
            run,
            architecture=architecture,
            action=(
                "resolution.reconstruction"
                if origin == "reconstructed_v1"
                else "resolution.persistence"
            ),
            outcome="succeeded",
        )
        _metric("persisted", architecture["architecture_profile_ref"]["version"])
        return record

    def validate(
        self,
        *,
        run: CostCalculationRun,
        raw_architecture: Mapping[str, Any],
        linked_documents: Iterable[Mapping[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Return a canonical validated resolution bound to Management state."""

        if not isinstance(raw_architecture, Mapping):
            raise architecture_error(
                "ARCH_RESOLUTION_INVALID",
                "The resolved architecture contract is missing.",
            )
        profile_ref = raw_architecture.get("architecture_profile_ref")
        if not isinstance(profile_ref, Mapping):
            raise architecture_error(
                "ARCH_RESOLUTION_INVALID",
                "The resolved architecture profile reference is missing.",
            )
        profile_id = str(profile_ref.get("id") or "")
        profile_version = str(profile_ref.get("version") or "")
        profile = ArchitectureProfileService.get_definition(
            profile_id,
            profile_version,
        )
        documents = tuple(
            linked_documents
            or (
                profile,
                *_provider_documents(profile_id, profile_version),
                *_catalog_documents(),
            )
        )
        try:
            validated_bundle = ArchitectureContractService.read_bundle(
                (*documents, raw_architecture)
            )
        except (ContractError, ValueError, TypeError) as exc:
            raise _contract_error(exc) from exc
        architecture = validated_bundle[-1].as_dict()
        self._validate_management_references(run, architecture, profile)
        self._validate_deployment_component_references(run, architecture)
        self._validate_extension_bindings(run, architecture)
        self._validate_child_references(architecture)
        return architecture

    def get_for_selected_twin(
        self,
        *,
        twin_id: str,
        user_id: str,
    ) -> ResolvedArchitectureReadResponse:
        if self.repository.get_twin(twin_id, user_id) is None:
            raise architecture_error(
                "ARCH_RESOLUTION_NOT_SELECTED",
                "No resolved architecture is selected for this Twin.",
            )
        run = self.repository.selected_run(twin_id, user_id)
        if run is None:
            raise architecture_error(
                "ARCH_RESOLUTION_NOT_SELECTED",
                "No resolved architecture is selected for this Twin.",
            )
        return self._read_response(run, user_id)

    def get_for_run(
        self,
        *,
        calculation_run_id: str,
        user_id: str,
    ) -> ResolvedArchitectureReadResponse:
        run = (
            self.db.query(CostCalculationRun)
            .filter(
                CostCalculationRun.id == calculation_run_id,
                CostCalculationRun.user_id == user_id,
            )
            .one_or_none()
        )
        if run is None:
            raise architecture_error(
                "ARCH_RESOLUTION_NOT_SELECTED",
                "The resolved architecture was not found.",
            )
        return self._read_response(
            run,
            user_id,
            require_current_profile=False,
        )

    def require_selectable(self, run: CostCalculationRun) -> None:
        """Enforce the run/specification/resolution readiness invariant."""

        self._require_resolution(
            run,
            require_current_profile=True,
        )

    def _require_resolution(
        self,
        run: CostCalculationRun,
        *,
        require_current_profile: bool,
    ) -> ResolvedTwinArchitectureRecord:
        if run.architecture_compatibility_status != READY:
            raise architecture_error(
                "ARCH_LEGACY_NOT_RESOLVABLE",
                "This calculation run has no deployment-ready architecture.",
            )
        resolution = self.repository.get_resolution_for_run(run.id, run.user_id)
        if resolution is None:
            raise architecture_error(
                "ARCH_RESOLUTION_INCOMPLETE",
                "The calculation run has no complete resolved architecture.",
            )
        if (
            resolution.functional_completeness_status != "complete"
            or resolution.twin_id != run.twin_id
            or resolution.user_id != run.user_id
            or resolution.schema_version
            != run.resolved_architecture_version
            or not hmac.compare_digest(
                run.resolved_architecture_digest or "",
                resolution.content_digest,
            )
            or not hmac.compare_digest(
                run.deployment_specification_digest or "",
                resolution.deployment_specification_digest,
            )
            or resolution.deployment_specification_version
            != run.deployment_specification_version
        ):
            raise architecture_error(
                "ARCH_RESOLUTION_REFERENCE_MISMATCH",
                "The selected run architecture references do not match.",
            )
        if require_current_profile:
            selection = self.repository.get_selection(
                run.twin_id,
                run.user_id,
            )
            if selection is None or (
                resolution.profile_id,
                resolution.profile_version,
                resolution.profile_digest,
            ) != (
                selection.profile_id,
                selection.profile_version,
                selection.profile_digest,
            ):
                raise architecture_error(
                    "ARCH_RESOLUTION_REFERENCE_MISMATCH",
                    "The calculation run does not match the selected profile.",
                )
        return resolution

    def apply_fixed_projection(
        self,
        run: CostCalculationRun,
        architecture: Mapping[str, Any],
    ) -> dict[str, str]:
        """Derive the seven legacy provider fields from component assignments."""

        profile_ref = architecture["architecture_profile_ref"]
        if (profile_ref["id"], profile_ref["version"]) != BASELINE_PROFILE:
            raise architecture_error(
                "ARCH_LEGACY_PROJECTION_UNSUPPORTED",
                "This architecture profile has no fixed-field projection.",
            )
        config = run.optimizer_config
        if config is None:
            raise architecture_error(
                "ARCH_RESOLUTION_REFERENCE_MISMATCH",
                "The calculation run optimizer configuration is missing.",
            )
        assignments = {
            item["logical_component_id"]: item["provider"]
            for item in architecture["component_assignments"]
        }
        if set(assignments) != set(COMPONENT_TO_FIXED_FIELD):
            raise architecture_error(
                "ARCH_RESOLUTION_INCOMPLETE",
                "The baseline component projection is incomplete.",
            )
        projected = {
            field: LEGACY_PROVIDER_LABELS[assignments[component]]
            for component, field in COMPONENT_TO_FIXED_FIELD.items()
        }
        for field, provider in projected.items():
            setattr(config, field, provider)
        self.assert_fixed_projection_round_trip(config, architecture)
        return projected

    @staticmethod
    def assert_fixed_projection_round_trip(
        config,
        architecture: Mapping[str, Any],
    ) -> None:
        expected = {
            COMPONENT_TO_FIXED_FIELD[item["logical_component_id"]]: item[
                "provider"
            ]
            for item in architecture["component_assignments"]
        }
        actual = {
            field: str(getattr(config, field) or "").strip().lower()
            for field in COMPONENT_TO_FIXED_FIELD.values()
        }
        if actual != expected:
            raise architecture_error(
                "ARCH_RESOLUTION_REFERENCE_MISMATCH",
                "The fixed-field architecture projection is inconsistent.",
            )

    @staticmethod
    def reproduce_components(
        record: ResolvedTwinArchitectureRecord,
    ) -> list[dict[str, Any]]:
        return [
            {
                "assignment_id": item.assignment_id,
                "responsibility_id": item.responsibility_id,
                "logical_component_id": item.logical_component_id,
                "provider": item.provider,
                "provider_implementation_profile_ref": {
                    "id": item.provider_profile_id,
                    "version": item.provider_profile_version,
                    "digest": item.provider_profile_digest,
                },
                "deployment_component_id": item.deployment_component_id,
                "deployment_component_version": item.deployment_component_version,
                "service_id": item.service_id,
                "region": item.region,
                "capability_evidence": _loaded(item.capability_refs_json),
                "pricing_model_refs": _loaded(item.pricing_refs_json),
                "formula_refs": _loaded(item.formula_refs_json),
                "deployment_specification_component_ids": _loaded(
                    item.deployment_specification_component_ids_json
                ),
                "cost_contribution": {
                    "currency": record.currency,
                    "monthly_amount": item.cost_contribution,
                },
                "required": True,
            }
            for item in sorted(record.components, key=lambda row: row.ordinal)
        ]

    @staticmethod
    def reproduce_edges(
        record: ResolvedTwinArchitectureRecord,
    ) -> list[dict[str, Any]]:
        edges: list[dict[str, Any]] = []
        for item in sorted(record.edges, key=lambda row: row.ordinal):
            bindings = _loaded(item.binding_refs_json)
            edges.append(
                {
                    "resolved_edge_id": item.resolved_edge_id,
                    "edge_id": item.logical_edge_id,
                    "source_assignment_id": item.source_assignment_id,
                    "source_port_id": item.source_port_id,
                    "destination_assignment_id": item.destination_assignment_id,
                    "destination_port_id": item.destination_port_id,
                    "edge_implementation_id": item.edge_implementation_id,
                    "mechanism": item.mechanism,
                    "delivery_semantics": _loaded(item.delivery_semantics_json),
                    "transfer_route_class": item.transfer_route_id,
                    "transfer_evidence_refs": _loaded(item.evidence_refs_json),
                    "formula_refs": _loaded(item.formula_refs_json),
                    "cost_contribution": {
                        "currency": record.currency,
                        "monthly_amount": item.cost_contribution,
                    },
                    "trust_contract_ref": _loaded(item.trust_ref_json),
                    "observability_contract_ref": _loaded(
                        item.observability_ref_json
                    ),
                    "deployment_input_binding_ids": bindings["input"],
                    "deployment_output_binding_ids": bindings["output"],
                }
            )
        return edges

    def assert_projection_reproduction(
        self,
        record: ResolvedTwinArchitectureRecord,
    ) -> None:
        architecture = _loaded(record.canonical_json)
        if (
            self.reproduce_components(record)
            != architecture["component_assignments"]
            or self.reproduce_edges(record) != architecture["resolved_edges"]
        ):
            raise architecture_error(
                "ARCH_RESOLUTION_REFERENCE_MISMATCH",
                "Resolved architecture projections differ from canonical JSON.",
            )

    def _validate_management_references(
        self,
        run: CostCalculationRun,
        architecture: Mapping[str, Any],
        profile: Mapping[str, Any],
    ) -> None:
        selection = self.repository.get_selection(run.twin_id, run.user_id)
        if selection is None:
            raise architecture_error(
                "ARCH_RESOLUTION_REFERENCE_MISMATCH",
                "The Twin architecture selection is missing.",
            )
        expected_profile = {
            "id": selection.profile_id,
            "version": selection.profile_version,
            "digest": selection.profile_digest,
        }
        if (
            architecture["calculation_run_id"] != run.id
            or architecture["architecture_profile_ref"] != expected_profile
            or architecture["architecture_profile_ref"]["digest"]
            != profile["content_digest"]
        ):
            raise architecture_error(
                "ARCH_RESOLUTION_REFERENCE_MISMATCH",
                "The resolution run or profile reference does not match.",
            )
        deployment_ref = architecture["deployment_specification_ref"]
        if (
            deployment_ref["calculation_run_id"] != run.id
            or deployment_ref["schema_version"]
            != run.deployment_specification_version
            or deployment_ref["digest"] != run.deployment_specification_digest
        ):
            raise architecture_error(
                "ARCH_RESOLUTION_REFERENCE_MISMATCH",
                "The resolution deployment specification reference does not match.",
            )
        workload_ref = architecture["workload_contract_ref"]
        if workload_ref != profile["workload_contract_ref"]:
            raise architecture_error(
                "ARCH_RESOLUTION_REFERENCE_MISMATCH",
                "The resolution workload reference does not match the profile.",
            )
        try:
            result = json.loads(run.result_summary_json or "")
        except json.JSONDecodeError as exc:
            raise architecture_error(
                "ARCH_RESOLUTION_REFERENCE_MISMATCH",
                "The calculation result metadata is unavailable.",
            ) from exc
        bundle = architecture["optimization_bundle_ref"]
        expected_bundle = {
            field: profile["optimization_bundle"][field]
            for field in (
                "optimization_strategy_id",
                "optimization_strategy_version",
                "calculation_strategy_id",
                "calculation_strategy_version",
                "formula_set_id",
                "formula_set_version",
                "scoring_strategy_id",
                "scoring_strategy_version",
                "compatibility_digest",
            )
        }
        result_profile = result.get("optimizationProfile")
        result_strategy = result.get("calculationStrategy")
        if (
            bundle != expected_bundle
            or not isinstance(result_profile, dict)
            or not isinstance(result_strategy, dict)
            or bundle["optimization_strategy_id"]
            != result.get("optimization_profile_id")
            or bundle["calculation_strategy_id"]
            != result.get("calculation_strategy_id")
            or bundle["formula_set_id"]
            != result_strategy.get("formula_set_id")
            or bundle["scoring_strategy_id"]
            != result_profile.get("scoring_strategy_id")
        ):
            raise architecture_error(
                "ARCH_RESOLUTION_REFERENCE_MISMATCH",
                "The resolution optimization bundle does not match the run.",
            )
        used_providers = {
            item["provider"] for item in architecture["component_assignments"]
        }
        evidence_providers = {
            item["provider"] for item in architecture["pricing_evidence_refs"]
        }
        if used_providers != evidence_providers:
            raise architecture_error(
                "ARCH_RESOLUTION_REFERENCE_MISMATCH",
                "The resolution pricing evidence provider set does not match.",
            )
        completeness = architecture["functional_completeness"]
        if completeness.get("status") != "complete":
            raise architecture_error(
                "ARCH_RESOLUTION_INCOMPLETE",
                "The resolved architecture is not functionally complete.",
            )
        if run.total_monthly_cost is not None:
            try:
                run_total = Decimal(str(run.total_monthly_cost))
                architecture_total = Decimal(
                    architecture["cost_summary"]["monthly_total"]
                )
            except (InvalidOperation, KeyError, TypeError) as exc:
                raise architecture_error(
                    "ARCH_RESOLUTION_INVALID",
                    "The resolved architecture cost is invalid.",
                ) from exc
            if run_total != architecture_total:
                raise architecture_error(
                    "ARCH_RESOLUTION_REFERENCE_MISMATCH",
                    "The resolved architecture cost does not match the run.",
                )
        if architecture["cost_summary"]["currency"] != run.currency:
            raise architecture_error(
                "ARCH_RESOLUTION_REFERENCE_MISMATCH",
                "The resolved architecture currency does not match the run.",
            )

    def _validate_extension_bindings(
        self,
        run: CostCalculationRun,
        architecture: Mapping[str, Any],
    ) -> None:
        queried_bindings = (
            self.db.query(TwinExtensionBinding)
            .filter(
                TwinExtensionBinding.twin_id == run.twin_id,
                TwinExtensionBinding.user_id == run.user_id,
                TwinExtensionBinding.active.is_(True),
            )
            .all()
        )
        active = [binding for binding in queried_bindings if binding.active]
        active_by_identity = {
            (item.slot_id, item.slot_version, item.artifact_id): item
            for item in active
        }
        resolved = architecture["extension_bindings"]
        resolved_identities = {
            (item["slot_id"], item["slot_version"], item["artifact_id"])
            for item in resolved
        }
        if resolved_identities != set(active_by_identity):
            raise architecture_error(
                "ARCH_RESOLUTION_REFERENCE_MISMATCH",
                "The resolution extension binding set is not current.",
            )
        for item in resolved:
            binding = active_by_identity[
                (item["slot_id"], item["slot_version"], item["artifact_id"])
            ]
            artifact = binding.artifact
            if (
                artifact is None
                or artifact.artifact_state != "valid"
                or artifact.artifact_digest != item["artifact_digest"]
                or artifact.validator_version
                != item["validation_contract_version"]
            ):
                raise architecture_error(
                    "ARCH_RESOLUTION_REFERENCE_MISMATCH",
                    "The resolution contains an unresolved extension binding.",
                )
            try:
                configuration = json.loads(artifact.configuration_json)
            except json.JSONDecodeError as exc:
                raise architecture_error(
                    "ARCH_RESOLUTION_REFERENCE_MISMATCH",
                    "The extension configuration is not canonical.",
                ) from exc
            expected_digest = "sha256:" + hashlib.sha256(
                canonical_json(configuration).encode("utf-8")
            ).hexdigest()
            if not hmac.compare_digest(
                expected_digest,
                item["configuration_digest"],
            ):
                raise architecture_error(
                    "ARCH_RESOLUTION_REFERENCE_MISMATCH",
                    "The extension configuration reference does not match.",
                )

    @staticmethod
    def _validate_deployment_component_references(
        run: CostCalculationRun,
        architecture: Mapping[str, Any],
    ) -> None:
        try:
            specification = json.loads(
                run.deployment_specification_json or ""
            )
        except json.JSONDecodeError as exc:
            raise architecture_error(
                "ARCH_RESOLUTION_REFERENCE_MISMATCH",
                "The run deployment specification is unavailable.",
            ) from exc
        raw_components = specification.get("components")
        if not isinstance(raw_components, list):
            raise architecture_error(
                "ARCH_RESOLUTION_REFERENCE_MISMATCH",
                "The run deployment component set is unavailable.",
            )
        specification_components = {
            item.get("component_id"): item
            for item in raw_components
            if isinstance(item, dict)
            and isinstance(item.get("component_id"), str)
        }
        assigned_ids: set[str] = set()
        for assignment in architecture["component_assignments"]:
            for component_id in assignment[
                "deployment_specification_component_ids"
            ]:
                component = specification_components.get(component_id)
                if (
                    component is None
                    or component.get("provider") != assignment["provider"]
                ):
                    raise architecture_error(
                        "ARCH_RESOLUTION_REFERENCE_MISMATCH",
                        "Architecture and deployment component references differ.",
                    )
                assigned_ids.add(component_id)
        non_auxiliary = {
            component_id
            for component_id, component in specification_components.items()
            if component.get("slot_id")
            not in {"transition_runtime", "cross_cloud_glue"}
        }
        if assigned_ids != non_auxiliary:
            raise architecture_error(
                "ARCH_RESOLUTION_REFERENCE_MISMATCH",
                "Architecture and deployment component sets differ.",
            )

    @staticmethod
    def _validate_child_references(architecture: Mapping[str, Any]) -> None:
        assignments = {
            item["assignment_id"] for item in architecture["component_assignments"]
        }
        for edge in architecture["resolved_edges"]:
            if (
                edge["source_assignment_id"] not in assignments
                or edge["destination_assignment_id"] not in assignments
            ):
                raise architecture_error(
                    "ARCH_RESOLUTION_REFERENCE_MISMATCH",
                    "A resolved edge references an unknown assignment.",
                )

    def _build_record(
        self,
        run: CostCalculationRun,
        architecture: dict[str, Any],
        *,
        origin: str,
    ) -> ResolvedTwinArchitectureRecord:
        profile = architecture["architecture_profile_ref"]
        bundle = architecture["optimization_bundle_ref"]
        workload = architecture["workload_contract_ref"]
        deployment = architecture["deployment_specification_ref"]
        record = ResolvedTwinArchitectureRecord(
            id=architecture["resolution_id"],
            calculation_run_id=run.id,
            twin_id=run.twin_id,
            user_id=run.user_id,
            schema_version=architecture["schema_version"],
            profile_id=profile["id"],
            profile_version=profile["version"],
            profile_digest=profile["digest"],
            optimization_bundle_digest=bundle["compatibility_digest"],
            workload_contract_id=workload["id"],
            workload_contract_version=workload["version"],
            workload_digest=workload["digest"],
            deployment_specification_version=deployment["schema_version"],
            deployment_specification_digest=deployment["digest"],
            total_monthly_cost=architecture["cost_summary"]["monthly_total"],
            currency=architecture["cost_summary"]["currency"],
            functional_completeness_status=architecture[
                "functional_completeness"
            ]["status"],
            canonical_json=_json(architecture),
            content_digest=architecture["content_digest"],
            origin=origin,
        )
        record.components = [
            self._component_row(record.id, item, ordinal)
            for ordinal, item in enumerate(
                architecture["component_assignments"]
            )
        ]
        record.edges = [
            self._edge_row(record.id, item, ordinal)
            for ordinal, item in enumerate(architecture["resolved_edges"])
        ]
        return record

    @staticmethod
    def _component_row(
        resolution_id: str,
        item: Mapping[str, Any],
        ordinal: int,
    ) -> ResolvedArchitectureComponentAssignment:
        provider_ref = item["provider_implementation_profile_ref"]
        return ResolvedArchitectureComponentAssignment(
            resolved_architecture_id=resolution_id,
            assignment_id=item["assignment_id"],
            responsibility_id=item["responsibility_id"],
            logical_component_id=item["logical_component_id"],
            provider=item["provider"],
            deployment_component_id=item["deployment_component_id"],
            deployment_component_version=item["deployment_component_version"],
            service_id=item["service_id"],
            provider_profile_id=provider_ref["id"],
            provider_profile_version=provider_ref["version"],
            provider_profile_digest=provider_ref["digest"],
            region=item["region"],
            deployment_specification_component_ids_json=_json(
                item["deployment_specification_component_ids"]
            ),
            cost_contribution=item["cost_contribution"]["monthly_amount"],
            capability_refs_json=_json(item["capability_evidence"]),
            pricing_refs_json=_json(item["pricing_model_refs"]),
            formula_refs_json=_json(item["formula_refs"]),
            evidence_refs_json=_json(item["capability_evidence"]),
            ordinal=ordinal,
        )

    @staticmethod
    def _edge_row(
        resolution_id: str,
        item: Mapping[str, Any],
        ordinal: int,
    ) -> ResolvedArchitectureEdge:
        return ResolvedArchitectureEdge(
            resolved_architecture_id=resolution_id,
            resolved_edge_id=item["resolved_edge_id"],
            logical_edge_id=item["edge_id"],
            source_assignment_id=item["source_assignment_id"],
            source_port_id=item["source_port_id"],
            destination_assignment_id=item["destination_assignment_id"],
            destination_port_id=item["destination_port_id"],
            edge_implementation_id=item["edge_implementation_id"],
            mechanism=item["mechanism"],
            transfer_route_id=item["transfer_route_class"],
            cost_contribution=item["cost_contribution"]["monthly_amount"],
            delivery_semantics_json=_json(item["delivery_semantics"]),
            binding_refs_json=_json(
                {
                    "input": item["deployment_input_binding_ids"],
                    "output": item["deployment_output_binding_ids"],
                }
            ),
            trust_ref_json=_json(item["trust_contract_ref"]),
            observability_ref_json=_json(
                item["observability_contract_ref"]
            ),
            formula_refs_json=_json(item["formula_refs"]),
            evidence_refs_json=_json(item["transfer_evidence_refs"]),
            ordinal=ordinal,
        )

    def _read_response(
        self,
        run: CostCalculationRun,
        user_id: str,
        *,
        require_current_profile: bool = True,
    ) -> ResolvedArchitectureReadResponse:
        if run.architecture_compatibility_status != READY:
            raise architecture_error(
                "ARCH_LEGACY_NOT_RESOLVABLE",
                "This legacy run has no resolvable architecture.",
            )
        record = self._require_resolution(
            run,
            require_current_profile=require_current_profile,
        )
        if record.user_id != user_id:
            raise architecture_error(
                "ARCH_RESOLUTION_NOT_SELECTED",
                "The resolved architecture was not found.",
            )
        self.assert_projection_reproduction(record)
        return ResolvedArchitectureReadResponse(
            twin_id=run.twin_id,
            calculation_run_id=run.id,
            selected_for_deployment_at=run.selected_for_deployment_at,
            architecture_compatibility_status=run.architecture_compatibility_status,
            origin=record.origin,
            architecture=_loaded(record.canonical_json),
        )

    def _audit(
        self,
        run: CostCalculationRun,
        *,
        architecture: Mapping[str, Any],
        action: str,
        outcome: str,
        result_code: str | None = None,
    ) -> None:
        profile = architecture.get("architecture_profile_ref", {})
        self.db.add(
            ArchitectureAuditEvent(
                user_id=run.user_id,
                action=action,
                outcome=outcome,
                profile_id=profile.get("id"),
                profile_version=profile.get("version"),
                profile_digest=profile.get("digest"),
                twin_id=run.twin_id,
                calculation_run_id=run.id,
                resolution_digest=architecture.get("content_digest"),
                result_code=result_code,
                correlation_id=current_request_id(),
            )
        )

    def _record_failure(
        self,
        run: CostCalculationRun,
        *,
        code: str,
        action: str,
    ) -> None:
        self.db.add(
            ArchitectureAuditEvent(
                user_id=run.user_id,
                action=action,
                outcome="rejected",
                twin_id=run.twin_id,
                calculation_run_id=run.id,
                result_code=code,
                correlation_id=current_request_id(),
            )
        )
