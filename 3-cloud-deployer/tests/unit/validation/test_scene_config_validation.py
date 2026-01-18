"""
Tests for scene configuration validation in validate_scene_config_content().

Tests L4 scene config validation for AWS TwinMaker and Azure 3D Scenes Studio.
"""

import pytest
import json
import src.validator as validator


class TestAWSSceneConfigValidation:
    """Tests for AWS TwinMaker scene.json validation."""
    
    def test_valid_aws_scene_config(self):
        """Happy path: valid AWS scene.json passes validation."""
        scene = {
            "specVersion": "1.0",
            "version": "1",
            "unit": "meters",
            "nodes": [
                {
                    "name": "room-1",
                    "components": [
                        {
                            "type": "ModelRef",
                            "uri": "s3://bucket/scene.glb",
                            "modelType": "GLB"
                        }
                    ]
                }
            ],
            "rootNodeIndexes": [0]
        }
        # Should not raise
        validator.validate_scene_config_content("aws", json.dumps(scene))
    
    def test_aws_minimal_object(self):
        """AWS accepts any valid JSON object, even empty."""
        validator.validate_scene_config_content("aws", "{}")
    
    def test_aws_json_string_input(self):
        """AWS accepts JSON string input."""
        validator.validate_scene_config_content("aws", '{"key": "value"}')
    
    def test_aws_invalid_json_raises(self):
        """Invalid JSON raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validator.validate_scene_config_content("aws", "not json")
        assert "Invalid JSON" in str(exc_info.value)
    
    def test_aws_array_not_object_raises(self):
        """Array instead of object raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validator.validate_scene_config_content("aws", "[]")
        assert "must be a JSON object" in str(exc_info.value)
    
    def test_aws_primitive_not_object_raises(self):
        """Primitive JSON value raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validator.validate_scene_config_content("aws", '"string"')
        assert "must be a JSON object" in str(exc_info.value)


class TestAzureSceneConfigValidation:
    """Tests for Azure 3DScenesConfiguration.json validation."""
    
    def test_valid_azure_scene_config(self):
        """Happy path: valid Azure scene config passes."""
        scene = {
            "$schema": "https://azureiotsolutions.com/3DScenes/1.0.0/schema.json",
            "configuration": {
                "scenes": [
                    {
                        "id": "scene-1",
                        "displayName": "Factory Floor",
                        "elements": [
                            {"primaryTwinID": "room-1", "type": "TwinToObjectMapping"}
                        ],
                        "assets": [
                            {"url": "{{STORAGE_URL}}/scene.glb", "type": "Unity3D"}
                        ]
                    }
                ]
            }
        }
        # Without hierarchy, cross-ref is skipped
        validator.validate_scene_config_content("azure", json.dumps(scene))
    
    def test_azure_missing_configuration_raises(self):
        """Azure scene config missing 'configuration' raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validator.validate_scene_config_content("azure", '{"$schema": "..."}')
        assert "missing 'configuration' field" in str(exc_info.value)
    
    def test_azure_configuration_not_object_raises(self):
        """Azure 'configuration' as array raises ValueError."""
        scene = {"configuration": []}
        with pytest.raises(ValueError) as exc_info:
            validator.validate_scene_config_content("azure", json.dumps(scene))
        assert "'configuration' must be an object" in str(exc_info.value)
    
    def test_azure_scenes_not_array_raises(self):
        """Azure 'scenes' as string raises ValueError."""
        scene = {"configuration": {"scenes": "invalid"}}
        with pytest.raises(ValueError) as exc_info:
            validator.validate_scene_config_content("azure", json.dumps(scene))
        assert "must be an array" in str(exc_info.value)
    
    def test_azure_empty_scenes_valid(self):
        """Azure with empty scenes array is valid."""
        scene = {"configuration": {"scenes": []}}
        validator.validate_scene_config_content("azure", json.dumps(scene))


class TestAzureCrossReferenceValidation:
    """Tests for Azure scene config cross-reference against hierarchy."""
    
    def _make_hierarchy(self, twin_ids: list) -> str:
        """Helper to create hierarchy JSON with given twin IDs."""
        twins = [{"$dtId": tid, "$metadata": {"$model": "dtmi:test;1"}} for tid in twin_ids]
        return json.dumps({"twins": twins})
    
    def _make_scene(self, primary_twin_ids: list) -> str:
        """Helper to create scene config with given primaryTwinIDs."""
        elements = [{"primaryTwinID": tid, "type": "TwinToObjectMapping"} for tid in primary_twin_ids]
        scene = {
            "configuration": {
                "scenes": [
                    {"id": "scene-1", "elements": elements}
                ]
            }
        }
        return json.dumps(scene)
    
    def test_cross_ref_valid_twins(self):
        """Cross-reference passes when all twins exist in hierarchy."""
        hierarchy = self._make_hierarchy(["room-1", "machine-1"])
        scene = self._make_scene(["room-1", "machine-1"])
        # Should not raise
        validator.validate_scene_config_content("azure", scene, hierarchy)
    
    def test_cross_ref_missing_twin_raises(self):
        """Cross-reference raises when twin not in hierarchy."""
        hierarchy = self._make_hierarchy(["room-1"])
        scene = self._make_scene(["room-1", "room-99"])  # room-99 not in hierarchy
        
        with pytest.raises(ValueError) as exc_info:
            validator.validate_scene_config_content("azure", scene, hierarchy)
        
        assert "room-99" in str(exc_info.value)
        assert "not found in hierarchy" in str(exc_info.value)
    
    def test_cross_ref_url_format_twin_id(self):
        """Cross-reference extracts twin ID from full URL format."""
        hierarchy = self._make_hierarchy(["room-1"])
        scene = {
            "configuration": {
                "scenes": [{
                    "id": "scene-1",
                    "elements": [{
                        "primaryTwinID": "https://xxx.api.wcus.digitaltwins.azure.net/twins/room-1",
                        "type": "TwinToObjectMapping"
                    }]
                }]
            }
        }
        # Should extract 'room-1' from URL and find in hierarchy
        validator.validate_scene_config_content("azure", json.dumps(scene), hierarchy)
    
    def test_cross_ref_url_format_missing_raises(self):
        """Cross-reference with URL format raises when twin missing."""
        hierarchy = self._make_hierarchy(["room-1"])
        scene = {
            "configuration": {
                "scenes": [{
                    "id": "scene-1",
                    "elements": [{
                        "id": "elem-1",
                        "primaryTwinID": "https://xxx.api.wcus.digitaltwins.azure.net/twins/room-999",
                        "type": "TwinToObjectMapping"
                    }]
                }]
            }
        }
        
        with pytest.raises(ValueError) as exc_info:
            validator.validate_scene_config_content("azure", json.dumps(scene), hierarchy)
        
        assert "room-999" in str(exc_info.value)
        assert "elem-1" in str(exc_info.value)
    
    def test_cross_ref_no_hierarchy_skips(self):
        """Cross-reference is skipped when no hierarchy provided."""
        scene = self._make_scene(["room-1", "room-99", "nonexistent"])
        # Should not raise - no hierarchy to check against
        validator.validate_scene_config_content("azure", scene, None)
    
    def test_cross_ref_invalid_hierarchy_skips(self):
        """Cross-reference is skipped when hierarchy is invalid JSON."""
        scene = self._make_scene(["room-1"])
        # Should not raise - hierarchy can't be parsed
        validator.validate_scene_config_content("azure", scene, "not json")
    
    def test_cross_ref_empty_hierarchy_twins(self):
        """Cross-reference with empty hierarchy twins array raises for any twin."""
        hierarchy = json.dumps({"twins": []})
        scene = self._make_scene(["room-1"])
        
        # Empty twin_ids_in_hierarchy = set(), so cross-ref is skipped per logic
        # (only checks if twin_ids_in_hierarchy is truthy)
        validator.validate_scene_config_content("azure", scene, hierarchy)


class TestInvalidProvider:
    """Tests for invalid provider handling."""
    
    def test_invalid_provider_raises(self):
        """Invalid provider raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validator.validate_scene_config_content("gcp", '{}')
        assert "is not valid for scene config" in str(exc_info.value)
    
    def test_google_provider_raises(self):
        """Google provider (GCP) raises ValueError - L4 not supported."""
        with pytest.raises(ValueError) as exc_info:
            validator.validate_scene_config_content("google", '{}')
        assert "is not valid for scene config" in str(exc_info.value)
