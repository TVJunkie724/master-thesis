"""
Unit tests for the Deployer complete validation endpoint.

Tests D1-D13 from the implementation plan.
"""
import json

from fastapi.testclient import TestClient

import rest_api


client = TestClient(rest_api.app)


# Valid processor code for each provider
VALID_AWS_PROCESSOR = '''
def lambda_handler(event, context):
    return {"statusCode": 200}
'''

VALID_AZURE_PROCESSOR = '''
def main(req):
    return "OK"
'''

VALID_GCP_PROCESSOR = '''
def process(request):
    return "OK"
'''

# Valid config contents
VALID_CONFIG_EVENTS = '[{"condition": "temp > 30", "action": {"type": "lambda", "functionName": "alert-handler"}}]'
VALID_CONFIG_IOT_DEVICES = '[{"id": "device-1", "properties": ["temperature"]}]'
VALID_PAYLOADS = '[{"iotDeviceId": "device-1", "temperature": 25}]'
VALID_AWS_HIERARCHY = '[{"type": "entity", "id": "root", "children": [{"type": "component", "name": "sensor", "componentTypeId": "sensor-type", "properties": [{"name": "temp", "dataType": "DOUBLE"}]}]}]'


class TestDeployerCompleteValidation:
    """Tests for POST /validate/deployer-complete endpoint."""
    
    def test_D1_gcp_l4_l5_are_rejected_as_unavailable(self):
        """D1: GCP L4/L5 must fail before deployment side effects."""
        response = client.post("/validate/deployer-complete", json={
            "deployer_digital_twin_name": "my-twin",
            "config_events": VALID_CONFIG_EVENTS,
            "config_iot_devices": VALID_CONFIG_IOT_DEVICES,
            "payloads": VALID_PAYLOADS,
            "processors": {"device-1": VALID_AWS_PROCESSOR},
            "cheapest_path": {"L1": "aws", "L2": "aws", "L3_hot": "aws", "L4": "gcp", "L5": "gcp"},
            "optimizer_params": {"useEventChecking": False}
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        capability_errors = [
            error for error in data["errors"]
            if error["code"] == "CAPABILITY_UNAVAILABLE"
        ]
        assert {error["field"] for error in capability_errors} == {
            "cheapest_path.l4",
            "cheapest_path.l5",
        }
    
    def test_D2_empty_digital_twin_name(self):
        """D2: Empty digital_twin_name should return EMPTY_NAME error."""
        response = client.post("/validate/deployer-complete", json={
            "deployer_digital_twin_name": "",
            "config_events": VALID_CONFIG_EVENTS,
            "config_iot_devices": VALID_CONFIG_IOT_DEVICES,
            "payloads": VALID_PAYLOADS,
            "processors": {"device-1": VALID_AWS_PROCESSOR},
            "cheapest_path": {"L4": "gcp"}
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert any(e["code"] == "EMPTY_NAME" for e in data["errors"])
    
    def test_D3_invalid_name_special_chars(self):
        """D3: Name with special chars should return INVALID_NAME error."""
        response = client.post("/validate/deployer-complete", json={
            "deployer_digital_twin_name": "my twin!",
            "config_events": VALID_CONFIG_EVENTS,
            "config_iot_devices": VALID_CONFIG_IOT_DEVICES,
            "payloads": VALID_PAYLOADS,
            "processors": {"device-1": VALID_AWS_PROCESSOR},
            "cheapest_path": {"L4": "gcp"}
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert any(e["code"] == "INVALID_NAME" for e in data["errors"])
    
    def test_D4_missing_processor_for_device(self):
        """D4: Missing processor for a device should return MISSING_PROCESSOR error."""
        response = client.post("/validate/deployer-complete", json={
            "deployer_digital_twin_name": "my-twin",
            "config_events": VALID_CONFIG_EVENTS,
            "config_iot_devices": '[{"id": "device-1", "properties": []}, {"id": "device-2", "properties": []}]',
            "payloads": VALID_PAYLOADS,
            "processors": {"device-1": VALID_AWS_PROCESSOR},  # Missing device-2
            "cheapest_path": {"L4": "gcp"}
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert any(e["code"] == "MISSING_PROCESSOR" and "device-2" in e["field"] for e in data["errors"])
    
    def test_D5_l4_aws_no_hierarchy(self):
        """D5: L4=AWS without hierarchy should return MISSING_HIERARCHY error."""
        response = client.post("/validate/deployer-complete", json={
            "deployer_digital_twin_name": "my-twin",
            "config_events": VALID_CONFIG_EVENTS,
            "config_iot_devices": VALID_CONFIG_IOT_DEVICES,
            "payloads": VALID_PAYLOADS,
            "processors": {"device-1": VALID_AWS_PROCESSOR},
            "hierarchy": None,
            "cheapest_path": {"L4": "aws"}
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert any(e["code"] == "MISSING_HIERARCHY" for e in data["errors"])
    
    def test_D6_needs_3d_model_no_glb(self):
        """D6: L4=AWS, needs3DModel but no GLB should return MISSING_SCENE_GLB error."""
        response = client.post("/validate/deployer-complete", json={
            "deployer_digital_twin_name": "my-twin",
            "config_events": VALID_CONFIG_EVENTS,
            "config_iot_devices": VALID_CONFIG_IOT_DEVICES,
            "payloads": VALID_PAYLOADS,
            "processors": {"device-1": VALID_AWS_PROCESSOR},
            "hierarchy": VALID_AWS_HIERARCHY,
            "scene_config": '{"specVersion": "1.0"}',
            "scene_glb_uploaded": False,
            "cheapest_path": {"L4": "aws"},
            "optimizer_params": {"needs3DModel": True}
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert any(e["code"] == "MISSING_SCENE_GLB" for e in data["errors"])
    
    def test_D7_l4_gcp_needs_3d_is_explicitly_unavailable(self):
        """D7: GCP L4 remains unavailable even without a scene payload."""
        response = client.post("/validate/deployer-complete", json={
            "deployer_digital_twin_name": "my-twin",
            "config_events": VALID_CONFIG_EVENTS,
            "config_iot_devices": VALID_CONFIG_IOT_DEVICES,
            "payloads": VALID_PAYLOADS,
            "processors": {"device-1": VALID_AWS_PROCESSOR},
            "cheapest_path": {"L2": "aws", "L4": "gcp", "L5": "gcp"},
            "optimizer_params": {"needs3DModel": True}
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert any(
            error["code"] == "CAPABILITY_UNAVAILABLE"
            and error["field"] == "cheapest_path.l4"
            for error in data["errors"]
        )
    
    def test_D8_return_feedback_missing(self):
        """D8: returnFeedbackToDevice=true but missing event_feedback should error."""
        response = client.post("/validate/deployer-complete", json={
            "deployer_digital_twin_name": "my-twin",
            "config_events": VALID_CONFIG_EVENTS,
            "config_iot_devices": VALID_CONFIG_IOT_DEVICES,
            "payloads": VALID_PAYLOADS,
            "processors": {"device-1": VALID_AWS_PROCESSOR},
            "event_feedback": None,
            "cheapest_path": {"L4": "gcp"},
            "optimizer_params": {"returnFeedbackToDevice": True}
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert any(e["code"] == "MISSING_EVENT_FEEDBACK" for e in data["errors"])
    
    def test_D9_use_event_checking_partial_actions(self):
        """D9: useEventChecking with partial actions should error for missing ones."""
        events_with_two_actions = '[{"condition": "x", "action": {"functionName": "action1"}}, {"condition": "y", "action": {"functionName": "action2"}}]'
        response = client.post("/validate/deployer-complete", json={
            "deployer_digital_twin_name": "my-twin",
            "config_events": events_with_two_actions,
            "config_iot_devices": VALID_CONFIG_IOT_DEVICES,
            "payloads": VALID_PAYLOADS,
            "processors": {"device-1": VALID_AWS_PROCESSOR},
            "event_actions": {"action1": VALID_AWS_PROCESSOR},  # Missing action2
            "cheapest_path": {"L4": "gcp"},
            "optimizer_params": {"useEventChecking": True}
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert any(e["code"] == "MISSING_EVENT_ACTION" and "action2" in e["field"] for e in data["errors"])
    
    def test_D10_multiple_errors_aggregated(self):
        """D10: Multiple errors should all be returned."""
        response = client.post("/validate/deployer-complete", json={
            "deployer_digital_twin_name": "",  # Error 1
            "config_events": None,             # Error 2
            "config_iot_devices": None,        # Error 3
            "payloads": None,                  # Error 4
            "cheapest_path": {"L4": "gcp"}
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert len(data["errors"]) >= 4
    
    def test_D11_device_not_in_payloads(self):
        """D11: Device in config_iot but missing from payloads - cross-reference check."""
        response = client.post("/validate/deployer-complete", json={
            "deployer_digital_twin_name": "my-twin",
            "config_events": VALID_CONFIG_EVENTS,
            "config_iot_devices": '[{"id": "device-1"}, {"id": "device-2"}]',
            "payloads": '[{"iotDeviceId": "device-1", "temperature": 25}]',
            "processors": {
                "device-1": VALID_AWS_PROCESSOR,
                "device-2": VALID_AWS_PROCESSOR,
            },
            "cheapest_path": {"L2": "aws", "L4": "gcp"},
        })

        assert response.status_code == 200
        assert any(
            error["code"] == "MISSING_DEVICE_PAYLOAD"
            and error["field"] == "payload:device-2"
            for error in response.json()["errors"]
        )
    
    def test_D12_action_name_mismatch(self):
        """D12: Action functionName not in event_actions keys - should error."""
        response = client.post("/validate/deployer-complete", json={
            "deployer_digital_twin_name": "my-twin",
            "config_events": '[{"condition": "x", "action": {"functionName": "expected-action"}}]',
            "config_iot_devices": VALID_CONFIG_IOT_DEVICES,
            "payloads": VALID_PAYLOADS,
            "processors": {"device-1": VALID_AWS_PROCESSOR},
            "event_actions": {"wrong-action": VALID_AWS_PROCESSOR},  # Wrong key
            "cheapest_path": {"L4": "gcp"},
            "optimizer_params": {"useEventChecking": True}
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert any(e["code"] == "MISSING_EVENT_ACTION" and "expected-action" in e["field"] for e in data["errors"])
    
    def test_D13_scene_entity_not_in_hierarchy(self):
        """D13: Scene references entity not in hierarchy - cross-reference check."""
        hierarchy = '{"twins": [{"$dtId": "room-1", "$metadata": {"$model": "dtmi:test;1"}}]}'
        scene = json.dumps({
            "configuration": {
                "scenes": [{
                    "id": "scene-1",
                    "elements": [{
                        "id": "missing-element",
                        "primaryTwinID": "room-99",
                        "type": "TwinToObjectMapping",
                    }],
                }],
            },
        })
        response = client.post("/validate/deployer-complete", json={
            "deployer_digital_twin_name": "my-twin",
            "config_events": VALID_CONFIG_EVENTS,
            "config_iot_devices": VALID_CONFIG_IOT_DEVICES,
            "payloads": VALID_PAYLOADS,
            "processors": {"device-1": VALID_AZURE_PROCESSOR},
            "hierarchy": hierarchy,
            "scene_config": scene,
            "scene_glb_uploaded": True,
            "cheapest_path": {"L2": "azure", "L4": "azure"},
            "optimizer_params": {"needs3DModel": True},
        })

        assert response.status_code == 200
        assert any(
            error["code"] == "INVALID_SCENE_CONFIG"
            and "room-99" in error["message"]
            for error in response.json()["errors"]
        )

    def test_unknown_payload_device_is_rejected(self):
        response = client.post("/validate/deployer-complete", json={
            "deployer_digital_twin_name": "my-twin",
            "config_events": VALID_CONFIG_EVENTS,
            "config_iot_devices": VALID_CONFIG_IOT_DEVICES,
            "payloads": '[{"iotDeviceId": "unknown-device"}]',
            "processors": {"device-1": VALID_AWS_PROCESSOR},
            "cheapest_path": {"L2": "aws", "L4": "gcp"},
        })

        assert response.status_code == 200
        codes = {error["code"] for error in response.json()["errors"]}
        assert {"UNKNOWN_PAYLOAD_DEVICE", "MISSING_DEVICE_PAYLOAD"} <= codes

    def test_cheapest_path_requires_object_contract(self):
        response = client.post("/validate/deployer-complete", json={
            "cheapest_path": ["L1_AWS", "L2_AZURE"],
        })

        assert response.status_code == 422
    
    def test_trigger_notification_missing_state_machine(self):
        """triggerNotificationWorkflow=true but missing state_machine should error."""
        response = client.post("/validate/deployer-complete", json={
            "deployer_digital_twin_name": "my-twin",
            "config_events": VALID_CONFIG_EVENTS,
            "config_iot_devices": VALID_CONFIG_IOT_DEVICES,
            "payloads": VALID_PAYLOADS,
            "processors": {"device-1": VALID_AWS_PROCESSOR},
            "state_machine": None,
            "cheapest_path": {"L4": "gcp"},
            "optimizer_params": {"triggerNotificationWorkflow": True}
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert any(e["code"] == "MISSING_STATE_MACHINE" for e in data["errors"])
    
    def test_l5_aws_missing_user_config(self):
        """L5=AWS but missing user_config should error."""
        response = client.post("/validate/deployer-complete", json={
            "deployer_digital_twin_name": "my-twin",
            "config_events": VALID_CONFIG_EVENTS,
            "config_iot_devices": VALID_CONFIG_IOT_DEVICES,
            "payloads": VALID_PAYLOADS,
            "processors": {"device-1": VALID_AWS_PROCESSOR},
            "user_config": None,
            "cheapest_path": {"L4": "gcp", "L5": "aws"}
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert any(e["code"] == "MISSING_USER_CONFIG" for e in data["errors"])

    def test_missing_l2_does_not_fall_back_to_aws(self):
        response = client.post("/validate/deployer-complete", json={
            "deployer_digital_twin_name": "my-twin",
            "config_events": VALID_CONFIG_EVENTS,
            "config_iot_devices": VALID_CONFIG_IOT_DEVICES,
            "payloads": VALID_PAYLOADS,
            "processors": {"device-1": VALID_AWS_PROCESSOR},
            "cheapest_path": {"L4": "gcp", "L5": "gcp"},
        })

        assert any(
            error["code"] == "MISSING_PROVIDER"
            and error["field"] == "cheapest_path.L2"
            for error in response.json()["errors"]
        )

    def test_invalid_optimizer_flag_type_is_not_truthy(self):
        response = client.post("/validate/deployer-complete", json={
            "deployer_digital_twin_name": "my-twin",
            "config_events": VALID_CONFIG_EVENTS,
            "config_iot_devices": VALID_CONFIG_IOT_DEVICES,
            "payloads": VALID_PAYLOADS,
            "processors": {"device-1": VALID_AWS_PROCESSOR},
            "cheapest_path": {"L2": "aws", "L4": "gcp", "L5": "gcp"},
            "optimizer_params": {"needs3DModel": "false"},
        })

        codes = {error["code"] for error in response.json()["errors"]}
        assert "INVALID_OPTIMIZER_FLAG" in codes
        assert "MISSING_SCENE_CONFIG" not in codes

    def test_orphan_processor_and_action_are_rejected(self):
        response = client.post("/validate/deployer-complete", json={
            "deployer_digital_twin_name": "my-twin",
            "config_events": VALID_CONFIG_EVENTS,
            "config_iot_devices": VALID_CONFIG_IOT_DEVICES,
            "payloads": VALID_PAYLOADS,
            "processors": {
                "device-1": VALID_AWS_PROCESSOR,
                "removed-device": VALID_AWS_PROCESSOR,
            },
            "event_actions": {
                "alert-handler": VALID_AWS_PROCESSOR,
                "removed-action": VALID_AWS_PROCESSOR,
            },
            "cheapest_path": {"L2": "aws", "L4": "gcp", "L5": "gcp"},
            "optimizer_params": {"useEventChecking": True},
        })

        codes = {error["code"] for error in response.json()["errors"]}
        assert {"UNEXPECTED_PROCESSOR", "UNEXPECTED_EVENT_ACTION"} <= codes

    def test_azure_user_config_is_validated_beyond_presence(self):
        response = client.post("/validate/deployer-complete", json={
            "deployer_digital_twin_name": "my-twin",
            "config_events": VALID_CONFIG_EVENTS,
            "config_iot_devices": VALID_CONFIG_IOT_DEVICES,
            "payloads": VALID_PAYLOADS,
            "processors": {"device-1": VALID_AZURE_PROCESSOR},
            "user_config": '{"admin_email":"user@example.com"}',
            "cheapest_path": {"L2": "azure", "L4": "gcp", "L5": "azure"},
        })

        assert any(
            error["code"] == "INVALID_USER_CONFIG"
            for error in response.json()["errors"]
        )

    def test_unknown_request_fields_are_rejected(self):
        response = client.post(
            "/validate/deployer-complete",
            json={"legacy_credentials": {"secret": "must-not-be-accepted"}},
        )

        assert response.status_code == 422

    def test_device_config_requires_array_contract(self):
        response = client.post("/validate/deployer-complete", json={
            "deployer_digital_twin_name": "my-twin",
            "config_events": VALID_CONFIG_EVENTS,
            "config_iot_devices": '{"id":"device-1","properties":[]}',
            "payloads": "[]",
            "cheapest_path": {"L2": "aws", "L4": "gcp", "L5": "gcp"},
        })

        assert any(
            error["code"] == "INVALID_CONFIG_IOT_DEVICES"
            and "JSON array" in error["message"]
            for error in response.json()["errors"]
        )

    def test_payload_device_id_requires_string_contract(self):
        response = client.post("/validate/deployer-complete", json={
            "deployer_digital_twin_name": "my-twin",
            "config_events": VALID_CONFIG_EVENTS,
            "config_iot_devices": VALID_CONFIG_IOT_DEVICES,
            "payloads": '[{"iotDeviceId":42}]',
            "processors": {"device-1": VALID_AWS_PROCESSOR},
            "cheapest_path": {"L2": "aws", "L4": "gcp", "L5": "gcp"},
        })

        assert any(
            error["code"] == "INVALID_PAYLOADS"
            for error in response.json()["errors"]
        )

    def test_lowercase_path_and_valid_aws_user_config_are_accepted(self):
        response = client.post("/validate/deployer-complete", json={
            "deployer_digital_twin_name": "my-twin",
            "config_events": VALID_CONFIG_EVENTS,
            "config_iot_devices": VALID_CONFIG_IOT_DEVICES,
            "payloads": VALID_PAYLOADS,
            "processors": {"device-1": VALID_AWS_PROCESSOR},
            "user_config": '{"admin_email":"admin@example.com"}',
            "cheapest_path": {"l2": "aws", "l4": "none", "l5": "aws"},
        })

        assert response.status_code == 200
        assert response.json() == {"valid": True, "errors": []}

    def test_google_alias_uses_gcp_function_contract(self):
        response = client.post("/validate/deployer-complete", json={
            "deployer_digital_twin_name": "my-twin",
            "config_events": VALID_CONFIG_EVENTS,
            "config_iot_devices": VALID_CONFIG_IOT_DEVICES,
            "payloads": VALID_PAYLOADS,
            "processors": {"device-1": VALID_GCP_PROCESSOR},
            "cheapest_path": {"L2": "google", "L4": "none", "L5": "none"},
        })

        assert response.status_code == 200
        assert response.json() == {"valid": True, "errors": []}
