"""Contract tests for wizard Step 3 deployer configuration persistence."""

from tests.conftest import create_test_twin


def test_payload_only_deployer_config_round_trips(authenticated_client):
    client, headers = authenticated_client
    twin_id = create_test_twin(client, headers)

    response = client.put(
        f"/twins/{twin_id}/deployer/config",
        json={
            "payloads_json": '{"device-1":{"temperature":21}}',
            "payloads_validated": True,
        },
        headers=headers,
    )

    assert response.status_code == 200

    loaded = client.get(f"/twins/{twin_id}/deployer/config", headers=headers)
    assert loaded.status_code == 200
    data = loaded.json()
    assert data["payloads_json"] == '{"device-1":{"temperature":21}}'
    assert data["payloads_validated"] is True


def test_function_only_deployer_config_round_trips(authenticated_client):
    client, headers = authenticated_client
    twin_id = create_test_twin(client, headers)

    response = client.put(
        f"/twins/{twin_id}/deployer/config",
        json={
            "processor_contents": {"device-1": "def process(event): return event"},
            "processor_requirements": {"device-1": "requests==2.32.3"},
            "processor_validated": {"device-1": True},
            "event_action_contents": {"overheat": "def handle(event): return event"},
            "event_action_requirements": {"overheat": "pydantic==2.11.0"},
            "event_action_validated": {"overheat": True},
        },
        headers=headers,
    )

    assert response.status_code == 200

    loaded = client.get(f"/twins/{twin_id}/deployer/config", headers=headers)
    data = loaded.json()
    assert data["processor_contents"] == {
        "device-1": "def process(event): return event"
    }
    assert data["processor_requirements"] == {"device-1": "requests==2.32.3"}
    assert data["processor_validated"] == {"device-1": True}
    assert data["event_action_contents"] == {
        "overheat": "def handle(event): return event"
    }
    assert data["event_action_requirements"] == {"overheat": "pydantic==2.11.0"}
    assert data["event_action_validated"] == {"overheat": True}


def test_workflow_and_feedback_deployer_config_round_trips(authenticated_client):
    client, headers = authenticated_client
    twin_id = create_test_twin(client, headers)

    response = client.put(
        f"/twins/{twin_id}/deployer/config",
        json={
            "event_feedback_content": "def feedback(event): return event",
            "event_feedback_requirements": "requests==2.32.3",
            "event_feedback_validated": True,
            "state_machine_content": '{"StartAt":"Done","States":{"Done":{"Type":"Succeed"}}}',
            "state_machine_validated": True,
        },
        headers=headers,
    )

    assert response.status_code == 200

    loaded = client.get(f"/twins/{twin_id}/deployer/config", headers=headers)
    data = loaded.json()
    assert data["event_feedback_content"] == "def feedback(event): return event"
    assert data["event_feedback_requirements"] == "requests==2.32.3"
    assert data["event_feedback_validated"] is True
    assert data["state_machine_content"] == (
        '{"StartAt":"Done","States":{"Done":{"Type":"Succeed"}}}'
    )
    assert data["state_machine_validated"] is True


def test_l4_l5_deployer_config_round_trips(authenticated_client):
    client, headers = authenticated_client
    twin_id = create_test_twin(client, headers)

    response = client.put(
        f"/twins/{twin_id}/deployer/config",
        json={
            "hierarchy_content": '{"entities":[]}',
            "hierarchy_validated": True,
            "scene_glb_uploaded": True,
            "scene_config_content": '{"scene":"factory"}',
            "scene_config_validated": True,
            "user_config_content": '{"users":[]}',
            "user_config_validated": True,
        },
        headers=headers,
    )

    assert response.status_code == 200

    loaded = client.get(f"/twins/{twin_id}/deployer/config", headers=headers)
    data = loaded.json()
    assert data["hierarchy_content"] == '{"entities":[]}'
    assert data["hierarchy_validated"] is True
    assert data["scene_glb_uploaded"] is True
    assert data["scene_config_content"] == '{"scene":"factory"}'
    assert data["scene_config_validated"] is True
    assert data["user_config_content"] == '{"users":[]}'
    assert data["user_config_validated"] is True


def test_deployer_config_read_model_includes_hydration_metadata(authenticated_client):
    client, headers = authenticated_client
    twin_id = create_test_twin(client, headers)

    response = client.put(
        f"/twins/{twin_id}/deployer/config",
        json={
            "deployer_digital_twin_name": "factory",
            "config_json_validated": True,
            "payloads_json": '{"device-1":{"temperature":21}}',
            "payloads_validated": True,
            "processor_contents": {"device-1": "def process(event): return event"},
            "state_machine_content": '{"StartAt":"Done","States":{"Done":{"Type":"Succeed"}}}',
            "hierarchy_content": '{"entities":[]}',
            "scene_config_content": '{"scene":"factory"}',
        },
        headers=headers,
    )

    assert response.status_code == 200

    data = response.json()
    assert data["twin_state"] == "draft"
    assert data["has_config_artifacts"] is True
    assert data["has_l1_payloads"] is True
    assert data["has_l2_artifacts"] is True
    assert data["has_l4_l5_artifacts"] is True
    assert data["validation_summary"] == {
        "config": True,
        "events": False,
        "iot_devices": False,
        "payloads": True,
        "event_feedback": False,
        "state_machine": False,
        "hierarchy": False,
        "scene_config": False,
        "user_config": False,
    }


def test_deployer_config_omitted_fields_remain_unchanged(authenticated_client):
    client, headers = authenticated_client
    twin_id = create_test_twin(client, headers)
    client.put(
        f"/twins/{twin_id}/deployer/config",
        json={
            "payloads_json": '{"device-1":{"temperature":21}}',
            "payloads_validated": True,
        },
        headers=headers,
    )

    response = client.put(
        f"/twins/{twin_id}/deployer/config",
        json={"config_events_json": "[]"},
        headers=headers,
    )

    assert response.status_code == 200

    loaded = client.get(f"/twins/{twin_id}/deployer/config", headers=headers)
    data = loaded.json()
    assert data["config_events_json"] == "[]"
    assert data["payloads_json"] == '{"device-1":{"temperature":21}}'
    assert data["payloads_validated"] is True


def test_deployer_config_explicit_null_clears_values(authenticated_client):
    client, headers = authenticated_client
    twin_id = create_test_twin(client, headers)
    client.put(
        f"/twins/{twin_id}/deployer/config",
        json={
            "deployer_digital_twin_name": "factory",
            "payloads_json": '{"device-1":{"temperature":21}}',
            "payloads_validated": True,
            "processor_contents": {"device-1": "def process(event): return event"},
            "processor_validated": {"device-1": True},
            "event_feedback_content": "def feedback(event): return event",
            "event_feedback_validated": True,
            "scene_glb_uploaded": True,
        },
        headers=headers,
    )

    response = client.put(
        f"/twins/{twin_id}/deployer/config",
        json={
            "deployer_digital_twin_name": None,
            "payloads_json": None,
            "payloads_validated": None,
            "processor_contents": None,
            "processor_validated": None,
            "event_feedback_content": None,
            "event_feedback_validated": None,
            "scene_glb_uploaded": None,
        },
        headers=headers,
    )

    assert response.status_code == 200

    loaded = client.get(f"/twins/{twin_id}/deployer/config", headers=headers)
    data = loaded.json()
    assert data["deployer_digital_twin_name"] is None
    assert data["payloads_json"] is None
    assert data["payloads_validated"] is False
    assert data["processor_contents"] is None
    assert data["processor_validated"] is None
    assert data["event_feedback_content"] is None
    assert data["event_feedback_validated"] is False
    assert data["scene_glb_uploaded"] is False
