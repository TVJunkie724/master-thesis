"""Fixed Six-layer architecture contract coverage."""

from __future__ import annotations

import copy
import json

import pytest

from src.models.twin import DigitalTwin, TwinState
from src.models.user import User
from src.schemas.architecture_profile import PinnedArchitectureReference
from src.services.architecture_contract_service import calculate_digest
from src.services.architecture_errors import ArchitectureDomainError
from src.services.architecture_profile_service import ArchitectureProfileService


def _twin_with_pin(db_session):
    user = User(id="architecture-owner", email="owner@example.test")
    twin = DigitalTwin(
        id="architecture-twin",
        user_id=user.id,
        name="Architecture Twin",
        state=TwinState.CONFIGURED,
    )
    db_session.add_all([user, twin])
    db_session.flush()
    db_session.add(
        ArchitectureProfileService.build_default_selection(
            twin_id=twin.id,
            user_id=user.id,
        )
    )
    db_session.commit()
    return user, twin


def test_canonical_contract_returns_safe_detail():
    detail = ArchitectureProfileService().get_profile()

    assert detail.profile_id == "six-layer-eventing"
    assert detail.profile_version == "1"
    assert detail.lifecycle_status == "active"
    assert len(detail.responsibilities) == 6
    assert len(detail.logical_components) == 8
    assert len(detail.logical_edges) == 9
    assert len(detail.visualization.nodes) == 8
    serialized = detail.model_dump_json()
    assert "terraform_binding" not in serialized
    assert "package_artifact" not in serialized


def test_default_pin_is_exact_and_rejects_alternatives():
    reference = ArchitectureProfileService.default_reference()
    pin = ArchitectureProfileService.build_default_selection(
        twin_id="new-twin",
        user_id="owner",
        reference=reference,
    )

    assert (pin.profile_id, pin.profile_version, pin.profile_digest) == (
        "six-layer-eventing",
        "1",
        reference.digest,
    )

    with pytest.raises(ArchitectureDomainError) as rejected:
        ArchitectureProfileService.build_default_selection(
            twin_id="new-twin",
            user_id="owner",
            reference=PinnedArchitectureReference(
                id="another-profile",
                version="1",
                digest="sha256:" + ("0" * 64),
            ),
        )
    assert rejected.value.code == "ARCH_PROFILE_NOT_FOUND"


@pytest.mark.parametrize(
    ("profile_id", "profile_version", "code"),
    (
        ("../profiles", "1", "ARCH_PROFILE_NOT_FOUND"),
        ("another-profile", "1", "ARCH_PROFILE_NOT_FOUND"),
        ("six-layer-eventing", "0", "ARCH_PROFILE_VERSION_UNSUPPORTED"),
        ("six-layer-eventing", "2", "ARCH_PROFILE_VERSION_UNSUPPORTED"),
    ),
)
def test_noncanonical_contract_identity_is_rejected(
    profile_id,
    profile_version,
    code,
):
    with pytest.raises(ArchitectureDomainError) as rejected:
        ArchitectureProfileService.get_definition(profile_id, profile_version)
    assert rejected.value.code == code


def test_inactive_canonical_contract_fails_closed(tmp_path, monkeypatch):
    baseline = ArchitectureProfileService.get_definition(
        "six-layer-eventing",
        "1",
    )
    inactive = copy.deepcopy(baseline)
    inactive["lifecycle_status"] = "deprecated"
    inactive["content_digest"] = calculate_digest(inactive)
    root = tmp_path / "definitions"
    path = root / "profiles" / "six-layer-eventing" / "1" / "profile.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(inactive), encoding="utf-8")
    monkeypatch.setattr(
        "src.services.architecture_profile_service.DEFINITIONS_ROOT",
        root,
    )

    with pytest.raises(ArchitectureDomainError) as rejected:
        ArchitectureProfileService.get_definition("six-layer-eventing", "1")
    assert rejected.value.code == "ARCH_PROFILE_NOT_ACTIVE"


def test_twin_pin_is_owner_scoped(db_session):
    user, twin = _twin_with_pin(db_session)
    service = ArchitectureProfileService(db_session)

    pin = service.get_selection(twin_id=twin.id, user_id=user.id)
    assert pin.profile_id == "six-layer-eventing"
    assert pin.profile_version == "1"

    with pytest.raises(ArchitectureDomainError) as hidden:
        service.get_selection(twin_id=twin.id, user_id="another-user")
    assert hidden.value.code == "ARCH_PROFILE_NOT_FOUND"
