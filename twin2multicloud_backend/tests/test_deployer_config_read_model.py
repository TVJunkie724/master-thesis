import json

from src.models.deployer_config import DeployerConfiguration
from src.models.twin import DigitalTwin, TwinState
from src.models.user import User


def _current_user(db_session) -> User:
    user = db_session.query(User).first()
    assert user is not None
    return user


def _create_twin(db_session, user_id: str, *, name: str = "Read Model Twin") -> DigitalTwin:
    twin = DigitalTwin(name=name, user_id=user_id, state=TwinState.DRAFT)
    db_session.add(twin)
    db_session.commit()
    db_session.refresh(twin)
    return twin


def _section(body: dict, section_id: str) -> dict:
    return next(section for section in body["sections"] if section["section_id"] == section_id)


def _artifact(section: dict, artifact_id: str) -> dict:
    return next(
        artifact
        for artifact in section["artifacts"]
        if artifact["artifact_id"] == artifact_id
    )


def test_deployer_config_read_model_creates_empty_default(
    authenticated_client,
    db_session,
):
    client, headers = authenticated_client
    twin = _create_twin(db_session, _current_user(db_session).id)

    response = client.get(
        f"/twins/{twin.id}/deployer/config/read-model",
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == "deployer-config-read-model.v1"
    assert body["twin_id"] == twin.id
    assert body["twin_state"] == "draft"
    assert [section["section_id"] for section in body["sections"]] == [
        "configuration",
        "payloads",
        "user_logic",
        "digital_twin_assets",
    ]
    assert db_session.query(DeployerConfiguration).filter_by(twin_id=twin.id).one()


def test_deployer_config_read_model_maps_sections_and_artifacts(
    authenticated_client,
    db_session,
):
    client, headers = authenticated_client
    twin = _create_twin(db_session, _current_user(db_session).id)
    config = DeployerConfiguration(
        twin_id=twin.id,
        deployer_digital_twin_name="factory-twin",
        config_events_json='{"events":[]}',
        config_iot_devices_json='{"devices":[]}',
        config_json_validated=True,
        config_events_validated=False,
        config_iot_devices_validated=True,
        payloads_json='{"payloads":[]}',
        payloads_validated=True,
        processor_contents=json.dumps({"device-a": "print('ok')"}),
        processor_validated=json.dumps({"device-a": True}),
        processor_requirements=json.dumps({"device-a": "requests==2.32.0"}),
        event_action_contents=json.dumps({"notify": "def handler(): pass"}),
        event_action_validated=json.dumps({"notify": False}),
        state_machine_content="StartAt: Done",
        state_machine_validated=True,
        hierarchy_content='{"root":"factory"}',
        hierarchy_validated=True,
        scene_glb_uploaded=True,
        scene_config_content='{"scene":"main"}',
        scene_config_validated=True,
        user_config_content='{"users":[]}',
        user_config_validated=True,
    )
    db_session.add(config)
    db_session.commit()

    response = client.get(
        f"/twins/{twin.id}/deployer/config/read-model",
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    configuration = _section(body, "configuration")
    assert configuration["has_content"] is True
    assert configuration["validated"] is False
    assert configuration["invalid_artifacts"] == ["config_events_json"]
    assert _artifact(configuration, "deployer_digital_twin_name")["required"] is True

    user_logic = _section(body, "user_logic")
    processor = _artifact(user_logic, "processor:device-a")
    assert processor["content"] == "print('ok')"
    assert processor["requirements"] == "requests==2.32.0"
    assert processor["validated"] is True
    event_action = _artifact(user_logic, "event_action:notify")
    assert event_action["validated"] is False
    assert "event_action:notify" in user_logic["invalid_artifacts"]

    assets = _section(body, "digital_twin_assets")
    assert _artifact(assets, "scene_glb")["has_content"] is True
    assert body["validation_summary"]["processor:device-a"] is True
    assert body["validation_summary"]["event_action:notify"] is False


def test_deployer_config_read_model_reports_invalid_legacy_json(
    authenticated_client,
    db_session,
):
    client, headers = authenticated_client
    twin = _create_twin(db_session, _current_user(db_session).id)
    db_session.add(
        DeployerConfiguration(
            twin_id=twin.id,
            processor_contents="{not-json",
            event_action_contents=json.dumps(["not", "an", "object"]),
        )
    )
    db_session.commit()

    response = client.get(
        f"/twins/{twin.id}/deployer/config/read-model",
        headers=headers,
    )

    assert response.status_code == 200
    warnings = response.json()["warnings"]
    assert any("processor_contents contains invalid JSON" in item for item in warnings)
    assert any("event_action_contents is not an object" in item for item in warnings)
    assert _section(response.json(), "user_logic")["artifacts"][0]["artifact_id"] == "event_feedback"


def test_deployer_config_read_model_is_owner_scoped(
    authenticated_client,
    db_session,
):
    client, headers = authenticated_client
    twin = _create_twin(db_session, "other-user", name="Other Read Model Twin")

    response = client.get(
        f"/twins/{twin.id}/deployer/config/read-model",
        headers=headers,
    )

    assert response.status_code == 404
