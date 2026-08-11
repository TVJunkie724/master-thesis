"""Profile catalog and transactional selection coverage."""

from __future__ import annotations

import copy
import json
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import sessionmaker

from src.models.architecture_profile import TwinArchitectureSelection
from src.models.cloud_connection import CloudConnection
from src.models.cost_calculation import CostCalculationRun
from src.models.deployment_preflight import DeploymentPreflightCache
from src.models.optimizer_config import OptimizerConfiguration
from src.models.twin import DigitalTwin, TwinState
from src.models.user_function_extension import (
    TwinExtensionBinding,
    UserFunctionArtifact,
)
from src.schemas.architecture_profile import PinnedArchitectureReference
from src.services.architecture_errors import ArchitectureDomainError
from src.services.architecture_contract_service import calculate_digest
from src.services.architecture_profile_service import ArchitectureProfileService
from src.services.architecture_profile_service import (
    RUNTIME_SELECTABLE_PROFILE_REFS,
)


@pytest.fixture(autouse=True)
def _activate_profiles_used_by_transaction_tests(monkeypatch):
    """Add historical synthetic profiles used only by mutation tests."""
    monkeypatch.setattr(
        "src.services.architecture_profile_service.RUNTIME_SELECTABLE_PROFILE_REFS",
        frozenset(
            {
                ("five-layer-baseline", "1"),
                ("minimal-profile", "1"),
                ("concurrent-profile", "1"),
            }
        ),
    )


def _user(db_session):
    from src.models.user import User

    user = User(id="architecture-owner", email="owner@example.test")
    db_session.add(user)
    db_session.flush()
    return user


def _twin_with_selection(db_session):
    user = _user(db_session)
    twin = DigitalTwin(
        id="architecture-twin",
        user_id=user.id,
        name="Architecture Twin",
        state=TwinState.CONFIGURED,
    )
    db_session.add(twin)
    db_session.flush()
    historical = ArchitectureProfileService.get_definition(
        "five-layer-baseline",
        "1",
        require_active=False,
    )
    db_session.add(
        ArchitectureProfileService.build_default_selection(
            twin_id=twin.id,
            user_id=user.id,
            reference=PinnedArchitectureReference(
                id=historical["profile_id"],
                version=historical["profile_version"],
                digest=historical["content_digest"],
            ),
        )
    )
    db_session.commit()
    return user, twin


def test_catalog_excludes_historical_profile_until_runtime_activation(
    monkeypatch,
):
    monkeypatch.setattr(
        "src.services.architecture_profile_service.RUNTIME_SELECTABLE_PROFILE_REFS",
        frozenset(),
    )
    service = ArchitectureProfileService()

    profiles = service.list_profiles()

    assert profiles == []
    with pytest.raises(ArchitectureDomainError) as historical:
        service.get_profile("five-layer-baseline", "1")
    assert historical.value.code == "ARCH_PROFILE_NOT_ACTIVE"


def test_runtime_activated_catalog_returns_safe_detail(monkeypatch):
    assert RUNTIME_SELECTABLE_PROFILE_REFS == frozenset({("five-layer-baseline", "2")})
    monkeypatch.setattr(
        "src.services.architecture_profile_service.RUNTIME_SELECTABLE_PROFILE_REFS",
        RUNTIME_SELECTABLE_PROFILE_REFS,
    )
    service = ArchitectureProfileService()

    profiles = service.list_profiles()
    detail = service.get_profile("five-layer-baseline", "2")

    assert [(item.profile_id, item.profile_version) for item in profiles] == [
        ("five-layer-baseline", "2")
    ]
    assert detail.lifecycle_status == "active"
    assert len(detail.responsibilities) == 5
    assert len(detail.logical_components) == 7
    assert len(detail.logical_edges) == 8
    assert len(detail.visualization.nodes) == 7
    serialized = detail.model_dump_json()
    assert "terraform_binding" not in serialized
    assert "package_artifact" not in serialized


def test_new_default_selection_pins_five_layer_v2():
    selection = ArchitectureProfileService.build_default_selection(
        twin_id="new-twin",
        user_id="owner",
    )

    assert selection.profile_id == "five-layer-baseline"
    assert selection.profile_version == "2"
    assert (
        selection.profile_digest
        == (
            ArchitectureProfileService.get_definition(
                "five-layer-baseline",
                "2",
            )["content_digest"]
        )
    )


def test_invalid_profile_identity_is_rejected_before_repository_access():
    with pytest.raises(ArchitectureDomainError) as invalid_id:
        ArchitectureProfileService.get_definition("../profiles", "1")
    with pytest.raises(ArchitectureDomainError) as invalid_version:
        ArchitectureProfileService.get_definition("five-layer-baseline", "0")

    assert invalid_id.value.code == "ARCH_PROFILE_NOT_FOUND"
    assert invalid_version.value.code == "ARCH_PROFILE_VERSION_UNSUPPORTED"


def test_unknown_and_inactive_profiles_fail_with_stable_codes(
    tmp_path,
    monkeypatch,
):
    with pytest.raises(ArchitectureDomainError) as unknown:
        ArchitectureProfileService.get_definition("unknown-profile", "1")
    assert unknown.value.code == "ARCH_PROFILE_NOT_FOUND"

    baseline = ArchitectureProfileService.get_definition(
        "five-layer-baseline",
        "1",
    )
    inactive = copy.deepcopy(baseline)
    inactive["lifecycle_status"] = "deprecated"
    inactive["content_digest"] = calculate_digest(inactive)
    root = tmp_path / "definitions"
    path = root / "profiles" / "five-layer-baseline" / "1" / "profile.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(inactive), encoding="utf-8")
    monkeypatch.setattr(
        "src.services.architecture_profile_service.DEFINITIONS_ROOT",
        root,
    )

    with pytest.raises(ArchitectureDomainError) as rejected:
        ArchitectureProfileService.get_definition(
            "five-layer-baseline",
            "1",
        )
    assert rejected.value.code == "ARCH_PROFILE_NOT_ACTIVE"


def test_active_profile_catalog_bound_fails_closed(
    tmp_path,
    monkeypatch,
):
    baseline = ArchitectureProfileService.get_definition(
        "five-layer-baseline",
        "1",
    )
    root = tmp_path / "definitions"
    profiles = {}
    for index in range(33):
        profile = copy.deepcopy(baseline)
        profile_id = f"profile-{index:02d}"
        profile["profile_id"] = profile_id
        profiles[(profile_id, "1")] = profile
        path = root / "profiles" / profile_id / "1" / "profile.json"
        path.parent.mkdir(parents=True)
        path.write_text(
            json.dumps(
                {
                    "profile_id": profile_id,
                    "profile_version": "1",
                    "lifecycle_status": "active",
                }
            ),
            encoding="utf-8",
        )

    monkeypatch.setattr(
        "src.services.architecture_profile_service.DEFINITIONS_ROOT",
        root,
    )
    monkeypatch.setattr(
        "src.services.architecture_profile_service.RUNTIME_SELECTABLE_PROFILE_REFS",
        frozenset(profiles),
    )
    monkeypatch.setattr(
        ArchitectureProfileService,
        "get_definition",
        staticmethod(
            lambda profile_id, profile_version, require_active=True: profiles[
                (profile_id, profile_version)
            ]
        ),
    )

    with pytest.raises(RuntimeError, match="32-version bound"):
        ArchitectureProfileService().list_profiles()


def test_same_profile_preview_and_selection_are_idempotent(db_session):
    user, twin = _twin_with_selection(db_session)
    service = ArchitectureProfileService(db_session)

    preview = service.preview_change(
        twin_id=twin.id,
        user_id=user.id,
        profile_id="five-layer-baseline",
        profile_version="1",
        expected_revision=1,
    )
    selected = service.select_profile(
        twin_id=twin.id,
        user_id=user.id,
        profile_id="five-layer-baseline",
        profile_version="1",
        expected_revision=1,
        invalidation_digest=preview.invalidation_digest,
    )

    assert preview.incompatible_workload_fields == []
    assert preview.incompatible_extension_bindings == []
    assert preview.selected_calculation_run_id is None
    assert selected.revision == 1
    assert selected.deployment_readiness_state == "unchanged"


def test_inactive_current_profile_can_be_changed_to_active_target(
    db_session,
    monkeypatch,
):
    user, twin = _twin_with_selection(db_session)
    selection = db_session.query(TwinArchitectureSelection).one()
    selection.profile_id = "retired-profile"
    selection.profile_digest = "sha256:" + ("a" * 64)
    db_session.commit()
    baseline = ArchitectureProfileService.get_definition(
        "five-layer-baseline",
        "1",
    )
    retired = copy.deepcopy(baseline)
    retired.update(
        {
            "profile_id": "retired-profile",
            "lifecycle_status": "deprecated",
            "content_digest": selection.profile_digest,
        }
    )
    original_get = ArchitectureProfileService.get_definition

    def fake_get(profile_id, profile_version, *, require_active=True):
        if profile_id == "retired-profile":
            if require_active:
                raise AssertionError("Current selections must remain readable")
            return retired
        return original_get(
            profile_id,
            profile_version,
            require_active=require_active,
        )

    monkeypatch.setattr(
        ArchitectureProfileService,
        "get_definition",
        staticmethod(fake_get),
    )
    service = ArchitectureProfileService(db_session)

    preview = service.preview_change(
        twin_id=twin.id,
        user_id=user.id,
        profile_id="five-layer-baseline",
        profile_version="1",
        expected_revision=1,
    )
    result = service.select_profile(
        twin_id=twin.id,
        user_id=user.id,
        profile_id="five-layer-baseline",
        profile_version="1",
        expected_revision=1,
        invalidation_digest=preview.invalidation_digest,
    )

    assert result.selection.profile_id == "five-layer-baseline"
    assert result.revision == 2


def test_profile_change_invalidates_only_previewed_twin_state(
    db_session,
    monkeypatch,
):
    user, twin = _twin_with_selection(db_session)
    baseline = ArchitectureProfileService.get_definition(
        "five-layer-baseline",
        "1",
    )
    target = copy.deepcopy(baseline)
    target.update(
        {
            "profile_id": "minimal-profile",
            "content_digest": "sha256:" + ("b" * 64),
            "responsibilities": [],
            "extension_slots": [],
        }
    )
    original_get = ArchitectureProfileService.get_definition

    def fake_get(profile_id, profile_version, *, require_active=True):
        if profile_id == "minimal-profile":
            return target
        return original_get(
            profile_id,
            profile_version,
            require_active=require_active,
        )

    monkeypatch.setattr(
        ArchitectureProfileService,
        "get_definition",
        staticmethod(fake_get),
    )

    config = OptimizerConfiguration(
        id="optimizer-config",
        twin_id=twin.id,
        params=json.dumps(
            {
                "numberOfDevices": 100,
                "deviceSendingIntervalInMinutes": 1,
                "eventsPerMessage": 1,
                "dashboardRefreshesPerHour": 2,
                "apiCallsPerDashboardRefresh": 3,
                "dashboardActiveHoursPerDay": 4,
                "amountOfActiveEditors": 1,
                "amountOfActiveViewers": 5,
                "preserved": "yes",
            }
        ),
    )
    artifact = UserFunctionArtifact(
        id="artifact.processor",
        user_id=user.id,
        schema_version="user-function-artifact.v1",
        artifact_state="valid",
        artifact_digest="sha256:" + ("1" * 64),
        slot_id="processor.telemetry",
        slot_version="1",
        runtime_id="python311",
        configuration_json="{}",
        declared_capabilities_json="[]",
        validator_version="1",
        created_by=user.id,
    )
    binding = TwinExtensionBinding(
        id="binding.processor",
        user_id=user.id,
        twin_id=twin.id,
        slot_id="processor.telemetry",
        slot_version="1",
        artifact_id=artifact.id,
        binding_digest="sha256:" + ("2" * 64),
        active=True,
        revision=1,
    )
    run = CostCalculationRun(
        id="018f0f5e-7b5e-7b2d-9f0b-7f66c2a88a01",
        twin_id=twin.id,
        user_id=user.id,
        optimizer_config_id=config.id,
        params_json="{}",
        status="succeeded",
        currency="USD",
        optimization_profile_id="cost_minimization_v1",
        scoring_strategy_id="min_total_cost_v1",
        selected_for_deployment_at=__import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ),
    )
    readiness = DeploymentPreflightCache(
        id="preflight",
        twin_id=twin.id,
        provider="aws",
        cloud_connection_id="connection",
        connection_payload_fingerprint="fingerprint",
        expected_permission_set_version="1",
        ready=True,
        summary="ready",
        checks_json="[]",
    )
    connection = CloudConnection(
        id="connection",
        user_id=user.id,
        provider="aws",
        display_name="Preserved",
        cloud_scope="{}",
        auth_type="access_key",
        encrypted_payload="encrypted",
        payload_fingerprint="fingerprint",
    )
    db_session.add_all([config, artifact, binding, run, readiness, connection])
    db_session.commit()
    readiness_id = readiness.id

    service = ArchitectureProfileService(db_session)
    preview = service.preview_change(
        twin_id=twin.id,
        user_id=user.id,
        profile_id="minimal-profile",
        profile_version="1",
        expected_revision=1,
    )

    assert [item.field_id for item in preview.incompatible_workload_fields] == [
        "workload.logical-query-count",
        "workload.telemetry-update-count",
    ]
    assert [item.slot_id for item in preview.incompatible_extension_bindings] == [
        "processor.telemetry"
    ]
    assert preview.selected_calculation_run_id == run.id
    assert preview.deployment_readiness_sections == ["deployment_preflight"]

    result = service.select_profile(
        twin_id=twin.id,
        user_id=user.id,
        profile_id="minimal-profile",
        profile_version="1",
        expected_revision=1,
        invalidation_digest=preview.invalidation_digest,
    )
    db_session.refresh(twin)
    db_session.refresh(run)
    db_session.refresh(binding)
    db_session.refresh(config)

    assert result.revision == 2
    assert result.invalidated_calculation_run_id == run.id
    assert result.unbound_extension_slot_ids == ["processor.telemetry"]
    assert twin.state == TwinState.DRAFT
    assert run.selected_for_deployment_at is None
    assert binding.active is False
    assert json.loads(config.params) == {"preserved": "yes"}
    assert db_session.get(UserFunctionArtifact, artifact.id) is not None
    assert db_session.get(CloudConnection, connection.id) is not None
    assert db_session.get(DeploymentPreflightCache, readiness_id) is None


def test_stale_revision_and_digest_do_not_mutate_selection(db_session):
    user, twin = _twin_with_selection(db_session)
    service = ArchitectureProfileService(db_session)

    with pytest.raises(ArchitectureDomainError) as stale_revision:
        service.preview_change(
            twin_id=twin.id,
            user_id=user.id,
            profile_id="five-layer-baseline",
            profile_version="1",
            expected_revision=2,
        )
    assert stale_revision.value.code == "ARCH_SELECTION_REVISION_CONFLICT"

    with pytest.raises(ArchitectureDomainError) as stale_digest:
        service.select_profile(
            twin_id=twin.id,
            user_id=user.id,
            profile_id="five-layer-baseline",
            profile_version="1",
            expected_revision=1,
            invalidation_digest="sha256:" + ("0" * 64),
        )
    assert stale_digest.value.code == "ARCH_SELECTION_INVALIDATION_STALE"
    assert (
        service.get_selection(
            twin_id=twin.id,
            user_id=user.id,
        ).revision
        == 1
    )


def test_malformed_workload_state_fails_closed_before_invalidation():
    twin = SimpleNamespace(optimizer_config=SimpleNamespace(params="{not-json"))

    with pytest.raises(ArchitectureDomainError) as rejected:
        ArchitectureProfileService._clear_workload_fields(
            twin,
            ["workload.telemetry-update-count"],
        )

    assert rejected.value.code == "ARCH_SELECTION_FORBIDDEN"
    assert twin.optimizer_config.params == "{not-json"


@pytest.mark.parametrize(
    ("params", "field_id"),
    (
        ('{"unknown":1}', "workload.future-field"),
        ('{"preserved":NaN}', "workload.telemetry-update-count"),
    ),
)
def test_unmapped_or_noncanonical_workload_state_fails_closed(
    params,
    field_id,
):
    twin = SimpleNamespace(optimizer_config=SimpleNamespace(params=params))

    with pytest.raises(ArchitectureDomainError) as rejected:
        ArchitectureProfileService._clear_workload_fields(
            twin,
            [field_id],
        )

    assert rejected.value.code == "ARCH_SELECTION_FORBIDDEN"
    assert twin.optimizer_config.params == params


def test_concurrent_profile_change_uses_database_optimistic_lock(
    db_session,
    monkeypatch,
):
    user, twin = _twin_with_selection(db_session)
    baseline = ArchitectureProfileService.get_definition(
        "five-layer-baseline",
        "1",
    )
    target = copy.deepcopy(baseline)
    target.update(
        {
            "profile_id": "concurrent-profile",
            "content_digest": "sha256:" + ("c" * 64),
        }
    )
    original_get = ArchitectureProfileService.get_definition

    def fake_get(profile_id, profile_version, *, require_active=True):
        if profile_id == "concurrent-profile":
            return target
        return original_get(
            profile_id,
            profile_version,
            require_active=require_active,
        )

    monkeypatch.setattr(
        ArchitectureProfileService,
        "get_definition",
        staticmethod(fake_get),
    )
    session_factory = sessionmaker(bind=db_session.get_bind())
    first_session = session_factory()
    second_session = session_factory()
    try:
        first = ArchitectureProfileService(first_session)
        second = ArchitectureProfileService(second_session)
        first_preview = first.preview_change(
            twin_id=twin.id,
            user_id=user.id,
            profile_id="concurrent-profile",
            profile_version="1",
            expected_revision=1,
        )
        second_preview = second.preview_change(
            twin_id=twin.id,
            user_id=user.id,
            profile_id="concurrent-profile",
            profile_version="1",
            expected_revision=1,
        )

        first.select_profile(
            twin_id=twin.id,
            user_id=user.id,
            profile_id="concurrent-profile",
            profile_version="1",
            expected_revision=1,
            invalidation_digest=first_preview.invalidation_digest,
        )
        with pytest.raises(ArchitectureDomainError) as conflict:
            second.select_profile(
                twin_id=twin.id,
                user_id=user.id,
                profile_id="concurrent-profile",
                profile_version="1",
                expected_revision=1,
                invalidation_digest=second_preview.invalidation_digest,
            )
        assert conflict.value.code == "ARCH_SELECTION_REVISION_CONFLICT"
    finally:
        first_session.close()
        second_session.close()

    db_session.expire_all()
    selection = db_session.query(TwinArchitectureSelection).one()
    assert selection.profile_id == "concurrent-profile"
    assert selection.revision == 2
