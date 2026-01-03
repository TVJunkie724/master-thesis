"""
Test Hierarchy Validation - AWS and Azure hierarchy format validation.

Tests for the new twin_hierarchy/ folder structure with provider-specific
hierarchy files: aws_hierarchy.json and azure_hierarchy.json.

Test Categories (per AI Layer Guide §5):
- Happy Path: Valid hierarchies pass validation
- Validation: Missing/invalid fields raise ValueError (fail-fast)
- Error Handling: Corrupt JSON, empty files handled gracefully
- Edge Cases: Empty arrays, partial data, unicode, deeply nested
"""

import unittest
import json
import src.validator as validator


class TestAWSHierarchyValidation(unittest.TestCase):
    """Tests for AWS TwinMaker hierarchy format validation."""

    # ==========================================
    # HAPPY PATH
    # ==========================================
    def test_valid_aws_hierarchy(self):
        """Happy path: valid AWS hierarchy passes validation."""
        content = [
            {
                "type": "entity",
                "id": "room-1",
                "children": [
                    {"type": "component", "name": "sensor-1", "componentTypeId": "sensor-type", "iotDeviceId": "dev-1"}
                ]
            }
        ]
        validator.validate_aws_hierarchy_content(content)

    def test_valid_aws_hierarchy_with_componentTypeId(self):
        """Happy path: component with componentTypeId is valid."""
        content = [
            {"type": "component", "name": "sensor-1", "componentTypeId": "type-1"}
        ]
        validator.validate_aws_hierarchy_content(content)

    def test_valid_aws_hierarchy_json_string(self):
        """Happy path: JSON string input is parsed and validated."""
        content = json.dumps([{"type": "entity", "id": "room-1"}])
        validator.validate_aws_hierarchy_content(content)

    # ==========================================
    # VALIDATION (FAIL-FAST)
    # ==========================================
    def test_aws_missing_type_raises(self):
        """Validation: missing 'type' field raises ValueError."""
        content = [{"id": "room-1", "name": "test"}]
        with self.assertRaises(ValueError) as cm:
            validator.validate_aws_hierarchy_content(content)
        self.assertIn("missing required 'type' field", str(cm.exception))

    def test_aws_invalid_type_raises(self):
        """Validation: invalid type (not entity/component) raises ValueError."""
        content = [{"type": "invalid", "id": "room-1"}]
        with self.assertRaises(ValueError) as cm:
            validator.validate_aws_hierarchy_content(content)
        self.assertIn("invalid type 'invalid'", str(cm.exception))

    def test_aws_component_missing_componentTypeId_raises(self):
        """Validation: component without componentTypeId raises (mandatory for 3D scenes)."""
        content = [{"type": "component", "name": "sensor-1"}]
        with self.assertRaises(ValueError) as cm:
            validator.validate_aws_hierarchy_content(content)
        self.assertIn("missing required 'componentTypeId'", str(cm.exception))

    def test_aws_entity_missing_id_raises(self):
        """Validation: entity without 'id' field raises ValueError."""
        content = [{"type": "entity", "name": "test"}]
        with self.assertRaises(ValueError) as cm:
            validator.validate_aws_hierarchy_content(content)
        self.assertIn("missing required 'id' field", str(cm.exception))

    # ==========================================
    # ERROR HANDLING
    # ==========================================
    def test_aws_corrupt_json_raises(self):
        """Error handling: corrupt JSON raises ValueError with clear message."""
        with self.assertRaises(ValueError) as cm:
            validator.validate_aws_hierarchy_content("{invalid}")
        self.assertIn("Invalid JSON", str(cm.exception))

    def test_aws_not_array_raises(self):
        """Error handling: non-array input raises ValueError."""
        content = {"type": "entity", "id": "room-1"}
        with self.assertRaises(ValueError) as cm:
            validator.validate_aws_hierarchy_content(content)
        self.assertIn("must be a JSON array", str(cm.exception))

    def test_aws_none_raises(self):
        """Error handling: None input raises ValueError."""
        with self.assertRaises(ValueError) as cm:
            validator.validate_aws_hierarchy_content(None)
        self.assertIn("cannot be None", str(cm.exception))

    # ==========================================
    # EDGE CASES
    # ==========================================
    def test_aws_empty_array_valid(self):
        """Edge case: empty array is valid (no entities)."""
        validator.validate_aws_hierarchy_content([])

    def test_aws_deeply_nested_children(self):
        """Edge case: deeply nested hierarchy (3+ levels) is valid."""
        content = [
            {
                "type": "entity",
                "id": "level-1",
                "children": [
                    {
                        "type": "entity",
                        "id": "level-2",
                        "children": [
                            {
                                "type": "entity",
                                "id": "level-3",
                                "children": [
                                    {"type": "component", "name": "deep", "componentTypeId": "deep-sensor", "iotDeviceId": "dev"}
                                ]
                            }
                        ]
                    }
                ]
            }
        ]
        validator.validate_aws_hierarchy_content(content)

    def test_aws_child_with_invalid_type_fails(self):
        """Error: nested child with invalid type raises ValueError."""
        content = [
            {
                "type": "entity",
                "id": "room-1",
                "children": [{"type": "invalid_type", "id": "child-1"}]
            }
        ]
        with self.assertRaises(ValueError) as cm:
            validator.validate_aws_hierarchy_content(content)
        self.assertIn("invalid type", str(cm.exception))

    def test_aws_component_missing_name_fails(self):
        """Error: component without 'name' field raises ValueError."""
        content = [{"type": "component", "iotDeviceId": "dev-1"}]  # Missing 'name'
        with self.assertRaises(ValueError) as cm:
            validator.validate_aws_hierarchy_content(content)
        self.assertIn("missing required 'name'", str(cm.exception))

    def test_aws_multiple_root_entities_valid(self):
        """Edge case: multiple root-level entities are valid."""
        content = [
            {"type": "entity", "id": "room-1"},
            {"type": "entity", "id": "room-2"},
            {"type": "entity", "id": "room-3"}
        ]
        validator.validate_aws_hierarchy_content(content)

    def test_aws_entity_with_empty_children_valid(self):
        """Edge case: entity with empty children array is valid."""
        content = [{"type": "entity", "id": "room-1", "children": []}]
        validator.validate_aws_hierarchy_content(content)


class TestConfigLoaderHierarchy(unittest.TestCase):
    """Tests for config_loader _load_hierarchy_for_provider function."""
    
    def test_load_hierarchy_google_returns_empty(self):
        """
        Config loader: 'google' provider returns empty hierarchy (no Digital Twin service).
        
        TODO(GCP-L4L5): When GCP L4 is implemented, update this test to verify
        GCP hierarchy loading similar to AWS/Azure.
        """
        from pathlib import Path
        from src.core.config_loader import _load_hierarchy_for_provider
        
        result = _load_hierarchy_for_provider(Path("/tmp"), "google")
        self.assertEqual(result, [])  # Empty list = no entities
    
    def test_load_hierarchy_invalid_provider_raises(self):
        """Config loader: truly invalid provider raises ValueError."""
        from pathlib import Path
        from src.core.config_loader import _load_hierarchy_for_provider
        
        with self.assertRaises(ValueError) as cm:
            _load_hierarchy_for_provider(Path("/tmp"), "invalid_provider")
        self.assertIn("Invalid provider", str(cm.exception))
        self.assertIn("only available for 'aws', 'azure', or 'google'", str(cm.exception))


class TestAzureHierarchyValidation(unittest.TestCase):
    """Tests for Azure Digital Twins DTDL hierarchy format validation."""

    # ==========================================
    # HAPPY PATH
    # ==========================================
    def test_valid_azure_hierarchy(self):
        """Happy path: valid Azure DTDL hierarchy passes validation."""
        content = {
            "header": {"fileVersion": "1.0.0"},
            "models": [
                {"@id": "dtmi:twin2clouds:Room;1", "@type": "Interface", "@context": "dtmi:dtdl:context;3"}
            ],
            "twins": [
                {"$dtId": "room-1", "$metadata": {"$model": "dtmi:twin2clouds:Room;1"}}
            ],
            "relationships": [
                {"$dtId": "room-1", "$targetId": "sensor-1", "$relationshipName": "contains"}
            ]
        }
        validator.validate_azure_hierarchy_content(content)

    def test_valid_azure_hierarchy_json_string(self):
        """Happy path: JSON string input is parsed and validated."""
        content = json.dumps({
            "models": [{"@id": "dtmi:test:Model;1", "@type": "Interface", "@context": "dtmi:dtdl:context;3"}],
            "twins": [],
            "relationships": []
        })
        validator.validate_azure_hierarchy_content(content)

    # ==========================================
    # VALIDATION (FAIL-FAST)
    # ==========================================
    def test_azure_missing_dtid_raises(self):
        """Validation: twin missing '$dtId' raises ValueError."""
        content = {
            "models": [],
            "twins": [{"$metadata": {"$model": "dtmi:test:Model;1"}}],
            "relationships": []
        }
        with self.assertRaises(ValueError) as cm:
            validator.validate_azure_hierarchy_content(content)
        self.assertIn("missing '$dtId'", str(cm.exception))

    def test_azure_missing_model_in_metadata_raises(self):
        """Validation: twin metadata missing '$model' raises ValueError."""
        content = {
            "models": [],
            "twins": [{"$dtId": "room-1", "$metadata": {}}],
            "relationships": []
        }
        with self.assertRaises(ValueError) as cm:
            validator.validate_azure_hierarchy_content(content)
        self.assertIn("metadata missing '$model'", str(cm.exception))

    def test_azure_invalid_dtmi_format_raises(self):
        """Validation: model @id not starting with 'dtmi:' raises ValueError."""
        content = {
            "models": [{"@id": "invalid:Room;1", "@type": "Interface", "@context": "dtmi:dtdl:context;3"}],
            "twins": [],
            "relationships": []
        }
        with self.assertRaises(ValueError) as cm:
            validator.validate_azure_hierarchy_content(content)
        self.assertIn("must start with 'dtmi:'", str(cm.exception))

    def test_azure_model_missing_context_raises(self):
        """Validation: model missing '@context' raises ValueError."""
        content = {
            "models": [{"@id": "dtmi:test:Model;1", "@type": "Interface"}],
            "twins": [],
            "relationships": []
        }
        with self.assertRaises(ValueError) as cm:
            validator.validate_azure_hierarchy_content(content)
        self.assertIn("missing '@context'", str(cm.exception))

    # ==========================================
    # ERROR HANDLING
    # ==========================================
    def test_azure_corrupt_json_raises(self):
        """Error handling: corrupt JSON raises ValueError."""
        with self.assertRaises(ValueError) as cm:
            validator.validate_azure_hierarchy_content("{invalid}")
        self.assertIn("Invalid JSON", str(cm.exception))

    def test_azure_not_object_raises(self):
        """Error handling: non-object (array) input raises ValueError."""
        content = [{"type": "entity"}]
        with self.assertRaises(ValueError) as cm:
            validator.validate_azure_hierarchy_content(content)
        self.assertIn("must be a JSON object", str(cm.exception))

    def test_azure_none_raises(self):
        """Error handling: None input raises ValueError."""
        with self.assertRaises(ValueError) as cm:
            validator.validate_azure_hierarchy_content(None)
        self.assertIn("cannot be None", str(cm.exception))

    # ==========================================
    # EDGE CASES
    # ==========================================
    def test_azure_empty_arrays_valid(self):
        """Edge case: empty models/twins/relationships arrays are valid."""
        content = {"models": [], "twins": [], "relationships": []}
        validator.validate_azure_hierarchy_content(content)

    def test_azure_only_models_valid(self):
        """Edge case: hierarchy with only models (no twins or relationships) is valid."""
        content = {
            "models": [{"@id": "dtmi:test:Model;1", "@type": "Interface", "@context": "dtmi:dtdl:context;3"}]
        }
        validator.validate_azure_hierarchy_content(content)

    def test_azure_unicode_in_displayname(self):
        """Edge case: unicode characters in displayName are valid."""
        content = {
            "models": [{
                "@id": "dtmi:test:Model;1",
                "@type": "Interface",
                "@context": "dtmi:dtdl:context;3",
                "displayName": "温度センサー"  # Japanese for "Temperature Sensor"
            }],
            "twins": [],
            "relationships": []
        }
        validator.validate_azure_hierarchy_content(content)

    def test_azure_header_missing_is_optional(self):
        """Edge case: header section is optional."""
        content = {
            "models": [{"@id": "dtmi:test:Model;1", "@type": "Interface", "@context": "dtmi:dtdl:context;3"}],
            "twins": [],
            "relationships": []
        }
        validator.validate_azure_hierarchy_content(content)

    def test_azure_twin_missing_metadata_fails(self):
        """Error: twin without $metadata raises ValueError."""
        content = {
            "models": [],
            "twins": [{"$dtId": "room-1"}],  # Missing $metadata
            "relationships": []
        }
        with self.assertRaises(ValueError) as cm:
            validator.validate_azure_hierarchy_content(content)
        self.assertIn("$metadata", str(cm.exception))

    def test_azure_model_missing_type_fails(self):
        """Error: model without @type raises ValueError."""
        content = {
            "models": [{"@id": "dtmi:test:Model;1", "@context": "dtmi:dtdl:context;3"}],  # Missing @type
            "twins": [],
            "relationships": []
        }
        with self.assertRaises(ValueError) as cm:
            validator.validate_azure_hierarchy_content(content)
        self.assertIn("@type", str(cm.exception))

    def test_azure_relationship_missing_relationshipname_fails(self):
        """Error: relationship without $relationshipName raises ValueError."""
        content = {
            "models": [],
            "twins": [],
            "relationships": [{"$dtId": "room-1", "$targetId": "sensor-1"}]  # Missing $relationshipName
        }
        with self.assertRaises(ValueError) as cm:
            validator.validate_azure_hierarchy_content(content)
        self.assertIn("$relationshipName", str(cm.exception))

    def test_azure_multiple_models_valid(self):
        """Edge case: multiple models in hierarchy are valid."""
        content = {
            "models": [
                {"@id": "dtmi:test:Room;1", "@type": "Interface", "@context": "dtmi:dtdl:context;3"},
                {"@id": "dtmi:test:Sensor;1", "@type": "Interface", "@context": "dtmi:dtdl:context;3"},
                {"@id": "dtmi:test:Building;1", "@type": "Interface", "@context": "dtmi:dtdl:context;3"}
            ],
            "twins": [],
            "relationships": []
        }
        validator.validate_azure_hierarchy_content(content)

    def test_azure_header_invalid_structure_fails(self):
        """Error: header that's not an object raises ValueError."""
        content = {
            "header": "invalid_string",  # Should be object
            "models": [],
            "twins": [],
            "relationships": []
        }
        with self.assertRaises(ValueError) as cm:
            validator.validate_azure_hierarchy_content(content)
        self.assertIn("header", str(cm.exception).lower())

class TestCheckHierarchyProviderMatchInZip(unittest.TestCase):
    """
    Tests for check_hierarchy_provider_match() in core.py.
    
    This validates that ZIP upload properly validates hierarchy CONTENT 
    (not just file existence) based on layer_4_provider.
    """

    def setUp(self):
        """Create a mock accessor for testing."""
        from dataclasses import dataclass, field
        from typing import Dict, List
        
        @dataclass
        class MockAccessor:
            files: Dict[str, str] = field(default_factory=dict)
            project_root: str = ""
            
            def list_files(self) -> List[str]:
                return list(self.files.keys())
            
            def file_exists(self, path: str) -> bool:
                return path in self.files
            
            def read_text(self, path: str) -> str:
                if path not in self.files:
                    raise FileNotFoundError(f"File not found: {path}")
                return self.files[path]
            
            def get_project_root(self) -> str:
                return self.project_root
        
        self.MockAccessor = MockAccessor

    # ==========================================
    # AWS HIERARCHY VALIDATION IN ZIP
    # ==========================================
    def test_aws_valid_hierarchy_passes_zip_validation(self):
        """AWS: valid hierarchy content passes during zip validation."""
        from src.validation.core import check_hierarchy_provider_match, ValidationContext
        
        valid_aws = json.dumps([{"type": "entity", "id": "room-1"}])
        accessor = self.MockAccessor(files={"twin_hierarchy/aws_hierarchy.json": valid_aws})
        ctx = ValidationContext()
        ctx.prov_config = {"layer_4_provider": "aws"}
        
        # Should not raise
        check_hierarchy_provider_match(accessor, ctx)

    def test_aws_malformed_json_fails_zip_validation(self):
        """AWS: malformed JSON fails during zip validation."""
        from src.validation.core import check_hierarchy_provider_match, ValidationContext
        
        accessor = self.MockAccessor(files={"twin_hierarchy/aws_hierarchy.json": "{invalid json"})
        ctx = ValidationContext()
        ctx.prov_config = {"layer_4_provider": "aws"}
        
        with self.assertRaises(ValueError) as cm:
            check_hierarchy_provider_match(accessor, ctx)
        self.assertIn("Invalid JSON", str(cm.exception))

    def test_aws_wrong_structure_fails_zip_validation(self):
        """AWS: hierarchy that's not an array fails during zip validation."""
        from src.validation.core import check_hierarchy_provider_match, ValidationContext
        
        wrong_structure = json.dumps({"type": "entity", "id": "room-1"})  # Object, not array
        accessor = self.MockAccessor(files={"twin_hierarchy/aws_hierarchy.json": wrong_structure})
        ctx = ValidationContext()
        ctx.prov_config = {"layer_4_provider": "aws"}
        
        with self.assertRaises(ValueError) as cm:
            check_hierarchy_provider_match(accessor, ctx)
        self.assertIn("must be a JSON array", str(cm.exception))

    def test_aws_component_missing_identifiers_fails_zip_validation(self):
        """AWS: component without componentTypeId/iotDeviceId fails during zip."""
        from src.validation.core import check_hierarchy_provider_match, ValidationContext
        
        invalid_component = json.dumps([{"type": "component", "name": "sensor-1"}])
        accessor = self.MockAccessor(files={"twin_hierarchy/aws_hierarchy.json": invalid_component})
        ctx = ValidationContext()
        ctx.prov_config = {"layer_4_provider": "aws"}
        
        with self.assertRaises(ValueError) as cm:
            check_hierarchy_provider_match(accessor, ctx)
        self.assertIn("componentTypeId", str(cm.exception))

    # ==========================================
    # AZURE HIERARCHY VALIDATION IN ZIP
    # ==========================================
    def test_azure_valid_hierarchy_passes_zip_validation(self):
        """Azure: valid DTDL hierarchy content passes during zip validation."""
        from src.validation.core import check_hierarchy_provider_match, ValidationContext
        
        valid_azure = json.dumps({
            "models": [{"@id": "dtmi:test:Model;1", "@type": "Interface", "@context": "dtmi:dtdl:context;3"}],
            "twins": [],
            "relationships": []
        })
        accessor = self.MockAccessor(files={"twin_hierarchy/azure_hierarchy.json": valid_azure})
        ctx = ValidationContext()
        ctx.prov_config = {"layer_4_provider": "azure"}
        
        # Should not raise
        check_hierarchy_provider_match(accessor, ctx)

    def test_azure_model_missing_context_fails_zip_validation(self):
        """Azure: model missing @context fails during zip validation."""
        from src.validation.core import check_hierarchy_provider_match, ValidationContext
        
        missing_context = json.dumps({
            "models": [{"@id": "dtmi:test:Model;1", "@type": "Interface"}],  # Missing @context
            "twins": [],
            "relationships": []
        })
        accessor = self.MockAccessor(files={"twin_hierarchy/azure_hierarchy.json": missing_context})
        ctx = ValidationContext()
        ctx.prov_config = {"layer_4_provider": "azure"}
        
        with self.assertRaises(ValueError) as cm:
            check_hierarchy_provider_match(accessor, ctx)
        self.assertIn("@context", str(cm.exception))

    def test_azure_relationship_missing_target_fails_zip_validation(self):
        """Azure: relationship missing $targetId fails during zip validation."""
        from src.validation.core import check_hierarchy_provider_match, ValidationContext
        
        missing_target = json.dumps({
            "models": [],
            "twins": [],
            "relationships": [{"$dtId": "room-1", "$relationshipName": "contains"}]  # Missing $targetId
        })
        accessor = self.MockAccessor(files={"twin_hierarchy/azure_hierarchy.json": missing_target})
        ctx = ValidationContext()
        ctx.prov_config = {"layer_4_provider": "azure"}
        
        with self.assertRaises(ValueError) as cm:
            check_hierarchy_provider_match(accessor, ctx)
        self.assertIn("$targetId", str(cm.exception))

    # ==========================================
    # GENERAL / EDGE CASES
    # ==========================================
    def test_missing_hierarchy_file_fails(self):
        """General: missing hierarchy file raises ValueError."""
        from src.validation.core import check_hierarchy_provider_match, ValidationContext
        
        accessor = self.MockAccessor(files={})  # No files
        ctx = ValidationContext()
        ctx.prov_config = {"layer_4_provider": "aws"}
        
        with self.assertRaises(ValueError) as cm:
            check_hierarchy_provider_match(accessor, ctx)
        self.assertIn("Missing hierarchy file", str(cm.exception))

    def test_google_provider_skips_validation(self):
        """Google: layer_4_provider=google skips hierarchy validation (no L4 service)."""
        from src.validation.core import check_hierarchy_provider_match, ValidationContext
        
        accessor = self.MockAccessor(files={})  # No files needed
        ctx = ValidationContext()
        ctx.prov_config = {"layer_4_provider": "google"}
        
        # Should not raise (Google doesn't have hierarchy file)
        check_hierarchy_provider_match(accessor, ctx)

    def test_no_l4_provider_skips_validation(self):
        """No L4: missing layer_4_provider skips hierarchy validation."""
        from src.validation.core import check_hierarchy_provider_match, ValidationContext
        
        accessor = self.MockAccessor(files={})
        ctx = ValidationContext()
        ctx.prov_config = {}  # No L4 provider
        
        # Should not raise
        check_hierarchy_provider_match(accessor, ctx)



if __name__ == "__main__":
    unittest.main()
