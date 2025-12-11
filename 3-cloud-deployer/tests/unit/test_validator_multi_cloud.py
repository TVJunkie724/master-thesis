"""
Validator Multi-Cloud Configuration Tests.

Tests cover:
- Fail-fast when layer_2_provider is missing with triggerNotificationWorkflow enabled
"""

import pytest
import json
import os
import tempfile


class TestValidatorProviderRequirements:
    """Tests for provider configuration requirements in validator."""

    def test_verify_project_structure_missing_layer_2_provider_with_workflow_fails(self):
        """verify_project_structure() should fail when layer_2_provider missing with workflow enabled."""
        from src.validator import verify_project_structure
        
        with tempfile.TemporaryDirectory() as tmpdir:
            project_name = "test-project"
            project_dir = os.path.join(tmpdir, "upload", project_name)
            os.makedirs(project_dir)
            
            # Write required configs
            with open(os.path.join(project_dir, "config.json"), 'w') as f:
                json.dump({"digital_twin_name": "test", "hot_storage_size_in_days": 7, "cold_storage_size_in_days": 30, "mode": "dev"}, f)
            with open(os.path.join(project_dir, "config_credentials.json"), 'w') as f:
                json.dump({"aws": {"aws_access_key_id": "x", "aws_secret_access_key": "x", "aws_region": "us-east-1"}}, f)
            with open(os.path.join(project_dir, "config_iot_devices.json"), 'w') as f:
                json.dump([], f)
            with open(os.path.join(project_dir, "config_events.json"), 'w') as f:
                json.dump([], f)
            with open(os.path.join(project_dir, "config_hierarchy.json"), 'w') as f:
                json.dump([], f)
            
            # Optimization with triggerNotificationWorkflow enabled
            with open(os.path.join(project_dir, "config_optimization.json"), 'w') as f:
                json.dump({"result": {"inputParamsUsed": {"triggerNotificationWorkflow": True}}}, f)
            
            # Providers WITHOUT layer_2_provider
            with open(os.path.join(project_dir, "config_providers.json"), 'w') as f:
                json.dump({"layer_1_provider": "aws", "layer_3_hot_provider": "aws", "layer_4_provider": "aws"}, f)
            
            with pytest.raises(ValueError, match="layer_2_provider"):
                verify_project_structure(project_name, project_path=tmpdir)

    def test_verify_project_structure_with_layer_2_provider_succeeds(self):
        """verify_project_structure() should succeed when layer_2_provider is present."""
        from src.validator import verify_project_structure
        
        with tempfile.TemporaryDirectory() as tmpdir:
            project_name = "test-project"
            project_dir = os.path.join(tmpdir, "upload", project_name)
            sm_dir = os.path.join(project_dir, "state_machines")
            os.makedirs(sm_dir)
            
            # Write required configs
            with open(os.path.join(project_dir, "config.json"), 'w') as f:
                json.dump({"digital_twin_name": "test", "hot_storage_size_in_days": 7, "cold_storage_size_in_days": 30, "mode": "dev"}, f)
            with open(os.path.join(project_dir, "config_credentials.json"), 'w') as f:
                json.dump({"aws": {"aws_access_key_id": "x", "aws_secret_access_key": "x", "aws_region": "us-east-1"}}, f)
            with open(os.path.join(project_dir, "config_iot_devices.json"), 'w') as f:
                json.dump([], f)
            with open(os.path.join(project_dir, "config_events.json"), 'w') as f:
                json.dump([], f)
            with open(os.path.join(project_dir, "config_hierarchy.json"), 'w') as f:
                json.dump([], f)
            
            # Optimization with triggerNotificationWorkflow enabled
            with open(os.path.join(project_dir, "config_optimization.json"), 'w') as f:
                json.dump({"result": {"inputParamsUsed": {"triggerNotificationWorkflow": True}}}, f)
            
            # Providers WITH layer_2_provider
            with open(os.path.join(project_dir, "config_providers.json"), 'w') as f:
                json.dump({"layer_1_provider": "aws", "layer_2_provider": "aws", "layer_3_hot_provider": "aws", "layer_4_provider": "aws"}, f)
            
            # AWS State Machine
            with open(os.path.join(sm_dir, "aws_step_function.json"), 'w') as f:
                json.dump({"StartAt": "Start", "States": {}}, f)
            
            # Should not raise
            verify_project_structure(project_name, project_path=tmpdir)

    def test_get_provider_for_function_missing_layer_fails(self):
        """get_provider_for_function() should fail when layer provider is missing."""
        from src.validator import get_provider_for_function
        
        with tempfile.TemporaryDirectory() as tmpdir:
            project_name = "test-project"
            project_dir = os.path.join(tmpdir, "upload", project_name)
            os.makedirs(project_dir)
            
            # Providers missing layer_2_provider
            with open(os.path.join(project_dir, "config_providers.json"), 'w') as f:
                json.dump({"layer_1_provider": "aws"}, f)
            
            with pytest.raises(ValueError, match="Provider configuration missing"):
                get_provider_for_function(project_name, "test-processor", project_path=tmpdir)

    def test_get_provider_for_function_with_layer_succeeds(self):
        """get_provider_for_function() should return provider when layer is configured."""
        from src.validator import get_provider_for_function
        
        with tempfile.TemporaryDirectory() as tmpdir:
            project_name = "test-project"
            project_dir = os.path.join(tmpdir, "upload", project_name)
            os.makedirs(project_dir)
            
            # Providers with layer_2_provider
            with open(os.path.join(project_dir, "config_providers.json"), 'w') as f:
                json.dump({"layer_1_provider": "aws", "layer_2_provider": "azure"}, f)
            
            result = get_provider_for_function(project_name, "test-processor", project_path=tmpdir)
            assert result == "azure"
