"""Unit tests for AWS hierarchy validation.

Tests the validate_aws_hierarchy_content() function to ensure proper validation
of AWS TwinMaker hierarchy JSON files.
"""
import pytest
import logging
from src.validator import validate_aws_hierarchy_content


class TestAwsHierarchyValidation:
    """Test cases for validate_aws_hierarchy_content()."""
    
    def test_valid_hierarchy_passes(self):
        """Valid hierarchy with all required fields passes."""
        valid = [{
            "type": "entity",
            "id": "room-1",
            "children": [{
                "type": "component",
                "name": "sensor-1",
                "componentTypeId": "temperature-sensor",
                "properties": [{"name": "temp", "dataType": "DOUBLE"}],
                "constProperties": [{"name": "id", "dataType": "STRING", "value": "s1"}]
            }]
        }]
        validate_aws_hierarchy_content(valid)  # Should not raise
    
    def test_valid_hierarchy_minimal_passes(self):
        """Minimal valid hierarchy (component with just required fields) passes."""
        valid = [{
            "type": "entity",
            "id": "room-1",
            "children": [{
                "type": "component",
                "name": "sensor-1",
                "componentTypeId": "temperature-sensor"
                # No properties or constProperties - should pass with warning
            }]
        }]
        validate_aws_hierarchy_content(valid)  # Should not raise
    
    def test_missing_componentTypeId_raises_error(self):
        """Component without componentTypeId fails validation."""
        invalid = [{
            "type": "entity",
            "id": "room-1",
            "children": [{
                "type": "component",
                "name": "sensor-1"
                # Missing componentTypeId
            }]
        }]
        with pytest.raises(ValueError, match="missing required 'componentTypeId'"):
            validate_aws_hierarchy_content(invalid)
    
    def test_missing_component_name_raises_error(self):
        """Component without name fails validation."""
        invalid = [{
            "type": "entity",
            "id": "room-1",
            "children": [{
                "type": "component",
                "componentTypeId": "temp-sensor"
                # Missing name
            }]
        }]
        with pytest.raises(ValueError, match="missing required 'name' field"):
            validate_aws_hierarchy_content(invalid)
    
    def test_invalid_property_dataType_raises_error(self):
        """Property with invalid dataType fails validation."""
        invalid = [{
            "type": "entity",
            "id": "room-1",
            "children": [{
                "type": "component",
                "name": "sensor-1",
                "componentTypeId": "temp-sensor",
                "properties": [{"name": "temp", "dataType": "INVALID_TYPE"}]
            }]
        }]
        with pytest.raises(ValueError, match="invalid dataType"):
            validate_aws_hierarchy_content(invalid)
    
    def test_missing_property_name_raises_error(self):
        """Property without name fails validation."""
        invalid = [{
            "type": "entity",
            "id": "room-1",
            "children": [{
                "type": "component",
                "name": "sensor-1",
                "componentTypeId": "temp-sensor",
                "properties": [{"dataType": "DOUBLE"}]  # Missing name
            }]
        }]
        with pytest.raises(ValueError, match="missing 'name'"):
            validate_aws_hierarchy_content(invalid)
    
    def test_missing_property_dataType_raises_error(self):
        """Property without dataType fails validation."""
        invalid = [{
            "type": "entity",
            "id": "room-1",
            "children": [{
                "type": "component",
                "name": "sensor-1",
                "componentTypeId": "temp-sensor",
                "properties": [{"name": "temp"}]  # Missing dataType
            }]
        }]
        with pytest.raises(ValueError, match="missing 'dataType'"):
            validate_aws_hierarchy_content(invalid)
    
    def test_missing_constProperty_name_raises_error(self):
        """Const property without name fails validation."""
        invalid = [{
            "type": "entity",
            "id": "room-1",
            "children": [{
                "type": "component",
                "name": "sensor-1",
                "componentTypeId": "temp-sensor",
                "constProperties": [{"value": "123", "dataType": "STRING"}]  # Missing name
            }]
        }]
        with pytest.raises(ValueError, match="missing 'name'"):
            validate_aws_hierarchy_content(invalid)
    
    def test_missing_constProperty_value_raises_error(self):
        """Const property without value fails validation."""
        invalid = [{
            "type": "entity",
            "id": "room-1",
            "children": [{
                "type": "component",
                "name": "sensor-1",
                "componentTypeId": "temp-sensor",
                "constProperties": [{"name": "id", "dataType": "STRING"}]  # Missing value
            }]
        }]
        with pytest.raises(ValueError, match="missing 'value'"):
            validate_aws_hierarchy_content(invalid)
    
    def test_missing_constProperty_dataType_raises_error(self):
        """Const property without dataType fails validation."""
        invalid = [{
            "type": "entity",
            "id": "room-1",
            "children": [{
                "type": "component",
                "name": "sensor-1",
                "componentTypeId": "temp-sensor",
                "constProperties": [{"name": "id", "value": "123"}]  # Missing dataType
            }]
        }]
        with pytest.raises(ValueError, match="missing 'dataType'"):
            validate_aws_hierarchy_content(invalid)
    
    def test_invalid_constProperty_dataType_raises_error(self):
        """Const property with invalid dataType fails validation."""
        invalid = [{
            "type": "entity",
            "id": "room-1",
            "children": [{
                "type": "component",
                "name": "sensor-1",
                "componentTypeId": "temp-sensor",
                "constProperties": [{"name": "id", "value": "123", "dataType": "FLOAT"}]  # Invalid
            }]
        }]
        with pytest.raises(ValueError, match="invalid dataType"):
            validate_aws_hierarchy_content(invalid)
    
    def test_warning_for_abstract_component_type(self, caplog):
        """Component with no properties warns about being abstract."""
        abstract = [{
            "type": "entity",
            "id": "room-1",
            "children": [{
                "type": "component",
                "name": "sensor-1",
                "componentTypeId": "temp-sensor"
                # No properties or constProperties
            }]
        }]
        with caplog.at_level(logging.WARNING):
            validate_aws_hierarchy_content(abstract)
        assert "may be abstract" in caplog.text
    
    def test_valid_dataTypes_accepted(self):
        """All valid dataTypes are accepted."""
        valid_types = ["STRING", "DOUBLE", "INTEGER", "BOOLEAN", "LONG"]
        for dtype in valid_types:
            valid = [{
                "type": "entity",
                "id": "room-1",
                "children": [{
                    "type": "component",
                    "name": "sensor-1",
                    "componentTypeId": "temp-sensor",
                    "properties": [{"name": "prop", "dataType": dtype}]
                }]
            }]
            validate_aws_hierarchy_content(valid)  # Should not raise
    
    def test_nested_entities_validated(self):
        """Nested entity structure is properly validated."""
        valid = [{
            "type": "entity",
            "id": "building-1",
            "children": [{
                "type": "entity",
                "id": "floor-1",
                "children": [{
                    "type": "entity",
                    "id": "room-1",
                    "children": [{
                        "type": "component",
                        "name": "sensor-1",
                        "componentTypeId": "temp-sensor"
                    }]
                }]
            }]
        }]
        validate_aws_hierarchy_content(valid)  # Should not raise
    
    def test_properties_not_list_raises_error(self):
        """Properties that is not a list fails validation."""
        invalid = [{
            "type": "entity",
            "id": "room-1",
            "children": [{
                "type": "component",
                "name": "sensor-1",
                "componentTypeId": "temp-sensor",
                "properties": {"name": "temp", "dataType": "DOUBLE"}  # Should be a list
            }]
        }]
        with pytest.raises(ValueError, match="must be an array"):
            validate_aws_hierarchy_content(invalid)
    
    def test_constProperties_not_list_raises_error(self):
        """constProperties that is not a list fails validation."""
        invalid = [{
            "type": "entity",
            "id": "room-1",
            "children": [{
                "type": "component",
                "name": "sensor-1",
                "componentTypeId": "temp-sensor",
                "constProperties": {"name": "id", "value": "1", "dataType": "STRING"}  # Should be a list
            }]
        }]
        with pytest.raises(ValueError, match="must be an array"):
            validate_aws_hierarchy_content(invalid)
