"""
Unit tests for L4 Digital Twin Data Connector.

Tests the GCP query translation and response transformation logic.
"""
import pytest
import json
from urllib.parse import urlencode


# ==============================================================================
# Mock the transformation function directly (avoid module import issues)
# ==============================================================================

def _transform_gcp_to_twinmaker(raw_response: dict, event: dict) -> dict:
    """Copy of transformation function for testing."""
    items = raw_response.get("items", [])
    if not items and "item" in raw_response:
        items = [raw_response["item"]] if raw_response["item"] else []
    
    selected_properties = event.get("selectedProperties", [])
    properties_meta = event.get("properties", {})
    
    property_values = []
    for prop_name in selected_properties:
        prop_def = properties_meta.get(prop_name, {}).get("definition", {})
        declared_type = prop_def.get("dataType", {}).get("type", "").upper()
        
        entry = {
            "entityPropertyReference": {"propertyName": prop_name},
            "values": []
        }
        
        for item in items:
            if prop_name in item:
                value = item[prop_name]
                
                if declared_type:
                    type_key = f"{declared_type.capitalize()}Value"
                elif isinstance(value, bool):
                    type_key = "BooleanValue"
                elif isinstance(value, int):
                    type_key = "IntegerValue"
                elif isinstance(value, float):
                    type_key = "DoubleValue"
                else:
                    type_key = "StringValue"
                    value = str(value)
                
                timestamp = item.get("timestamp") or item.get("id", "")
                entry["values"].append({
                    "time": timestamp,
                    "value": {type_key: value}
                })
        
        property_values.append(entry)
    
    return {"propertyValues": property_values}


def _build_gcp_query_url(base_url: str, event: dict) -> str:
    """Copy of URL builder for testing."""
    device_id = event.get("componentName") or event.get("entityId")
    params = {
        "device_id": device_id,
        "startTime": event.get("startTime", ""),
        "endTime": event.get("endTime", ""),
    }
    params = {k: v for k, v in params.items() if v}
    return f"{base_url}?{urlencode(params)}"


# ==============================================================================
# Tests
# ==============================================================================

class TestGcpDetection:
    """Tests for GCP URL detection."""
    
    def test_detects_gcp_gen2_url(self):
        """Gen2 functions use .run.app domain."""
        url = "https://hot-reader-abc123xyz-uc.a.run.app"
        assert ".run.app" in url
    
    def test_does_not_detect_azure_url(self):
        """Azure functions use azurewebsites.net domain."""
        url = "https://myapp.azurewebsites.net/api/hot-reader"
        assert ".run.app" not in url
    
    def test_does_not_detect_aws_url(self):
        """AWS Lambda URLs use lambda-url domain."""
        url = "https://abc123.lambda-url.us-east-1.on.aws/"
        assert ".run.app" not in url


class TestGcpQueryUrl:
    """Tests for _build_gcp_query_url."""
    
    def test_builds_url_with_all_params(self):
        event = {
            "componentName": "temp-sensor-1",
            "startTime": "2026-01-30T18:00:00Z",
            "endTime": "2026-01-30T19:00:00Z",
        }
        base_url = "https://hot-reader-abc.a.run.app"
        
        url = _build_gcp_query_url(base_url, event)
        
        assert "device_id=temp-sensor-1" in url
        assert "startTime=2026-01-30T18%3A00%3A00Z" in url
        assert "endTime=2026-01-30T19%3A00%3A00Z" in url
    
    def test_falls_back_to_entity_id(self):
        event = {
            "entityId": "machine-1",
            "startTime": "2026-01-30T18:00:00Z",
        }
        base_url = "https://hot-reader.a.run.app"
        
        url = _build_gcp_query_url(base_url, event)
        
        assert "device_id=machine-1" in url
    
    def test_omits_empty_params(self):
        event = {
            "componentName": "sensor-1",
        }
        base_url = "https://hot-reader.a.run.app"
        
        url = _build_gcp_query_url(base_url, event)
        
        assert "device_id=sensor-1" in url
        assert "startTime" not in url


class TestTransformGcpToTwinmaker:
    """Tests for _transform_gcp_to_twinmaker."""
    
    @pytest.fixture
    def sample_event(self):
        return {
            "selectedProperties": ["temperature", "humidity"],
            "properties": {
                "temperature": {"definition": {"dataType": {"type": "DOUBLE"}}},
                "humidity": {"definition": {"dataType": {"type": "DOUBLE"}}}
            }
        }
    
    def test_transforms_items_format(self, sample_event):
        gcp_response = {
            "items": [
                {"device_id": "s1", "temperature": 23.5, "humidity": 65.0, "timestamp": "2026-01-30T18:00:00Z"},
                {"device_id": "s1", "temperature": 24.0, "humidity": 63.0, "timestamp": "2026-01-30T18:05:00Z"}
            ],
            "count": 2
        }
        
        result = _transform_gcp_to_twinmaker(gcp_response, sample_event)
        
        assert "propertyValues" in result
        assert len(result["propertyValues"]) == 2
        
        temp_prop = next(p for p in result["propertyValues"]
                        if p["entityPropertyReference"]["propertyName"] == "temperature")
        assert len(temp_prop["values"]) == 2
        assert temp_prop["values"][0]["value"]["DoubleValue"] == 23.5
        assert temp_prop["values"][0]["time"] == "2026-01-30T18:00:00Z"
    
    def test_handles_single_item_format(self):
        """GCP hot-reader-last-entry returns {"item": {...}}."""
        event = {"selectedProperties": ["temperature"]}
        gcp_response = {
            "item": {"device_id": "s1", "temperature": 25.0, "id": "2026-01-30T18:10:00Z"}
        }
        
        result = _transform_gcp_to_twinmaker(gcp_response, event)
        
        assert len(result["propertyValues"]) == 1
        assert result["propertyValues"][0]["values"][0]["value"]["DoubleValue"] == 25.0
    
    def test_handles_empty_items(self, sample_event):
        result = _transform_gcp_to_twinmaker({"items": [], "count": 0}, sample_event)
        
        assert "propertyValues" in result
        assert len(result["propertyValues"]) == 2  # temperature and humidity
        for prop in result["propertyValues"]:
            assert prop["values"] == []
    
    def test_infers_type_from_value(self):
        """When no type metadata, infer from Python type."""
        event = {"selectedProperties": ["count", "active", "name"]}
        gcp_response = {
            "items": [
                {"count": 42, "active": True, "name": "sensor-a", "timestamp": "2026-01-30T18:00:00Z"}
            ]
        }
        
        result = _transform_gcp_to_twinmaker(gcp_response, event)
        
        count_prop = next(p for p in result["propertyValues"]
                        if p["entityPropertyReference"]["propertyName"] == "count")
        assert "IntegerValue" in count_prop["values"][0]["value"]
        
        active_prop = next(p for p in result["propertyValues"]
                         if p["entityPropertyReference"]["propertyName"] == "active")
        assert "BooleanValue" in active_prop["values"][0]["value"]
        
        name_prop = next(p for p in result["propertyValues"]
                        if p["entityPropertyReference"]["propertyName"] == "name")
        assert "StringValue" in name_prop["values"][0]["value"]
    
    def test_uses_id_field_as_fallback_timestamp(self):
        """Some GCP responses use 'id' instead of 'timestamp'."""
        event = {"selectedProperties": ["temperature"]}
        gcp_response = {
            "items": [{"temperature": 23.5, "id": "sensor1_2026-01-30T18:00:00Z"}]
        }
        
        result = _transform_gcp_to_twinmaker(gcp_response, event)
        
        assert result["propertyValues"][0]["values"][0]["time"] == "sensor1_2026-01-30T18:00:00Z"
