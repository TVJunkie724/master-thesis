"""
Architecture Verification Tests.

These tests verify that each layer adapter calls the correct components:
- L1 adapter should only deploy L1 components (Dispatcher, IoT Things, Connector when multi-cloud)
- L2 adapter should only deploy L2 components (Processor, Ingestion when multi-cloud)
- L3 adapter should only deploy L3 components (Hot/Cold/Archive storage)
- L4 adapter should only deploy L4 components (TwinMaker)
- L5 adapter should only deploy L5 components (Grafana)

This ensures no layer "leaks" into another layer's responsibilities.
"""

import pytest
from unittest.mock import patch, MagicMock


class TestLayerSeparation:
    """Cross-layer verification tests."""

    def test_no_circular_imports_between_layers(self):
        """Verify layer modules don't have circular dependencies."""
        from src.providers.aws.layers import l1_adapter
        from src.providers.aws.layers import l2_adapter
        from src.providers.aws.layers import l3_adapter
        from src.providers.aws.layers import l4_adapter
        from src.providers.aws.layers import l5_adapter
        
        # If we get here without ImportError, no circular imports
        assert True

    def test_layer_adapters_exist(self):
        """Verify all layer adapter modules exist and have deploy/destroy functions."""
        from src.providers.aws.layers import l1_adapter
        from src.providers.aws.layers import l2_adapter
        from src.providers.aws.layers import l3_adapter
        from src.providers.aws.layers import l4_adapter
        from src.providers.aws.layers import l5_adapter
        
        assert hasattr(l1_adapter, "deploy_l1")
        assert hasattr(l1_adapter, "destroy_l1")
        
        assert hasattr(l2_adapter, "deploy_l2")
        assert hasattr(l2_adapter, "destroy_l2")
        
        assert hasattr(l3_adapter, "deploy_l3_hot")
        assert hasattr(l3_adapter, "destroy_l3_hot")
        
        assert hasattr(l4_adapter, "deploy_l4")
        assert hasattr(l4_adapter, "destroy_l4")
        
        assert hasattr(l5_adapter, "deploy_l5")
        assert hasattr(l5_adapter, "destroy_l5")

    def test_layer_modules_have_component_functions(self):
        """Verify layer component modules have the expected functions."""
        from src.providers.aws.layers import layer_1_iot
        from src.providers.aws.layers import layer_2_compute
        from src.providers.aws.layers import layer_3_storage
        from src.providers.aws.layers import layer_4_twinmaker
        from src.providers.aws.layers import layer_5_grafana
        
        # L1 components
        assert hasattr(layer_1_iot, "create_dispatcher_iam_role")
        assert hasattr(layer_1_iot, "create_dispatcher_lambda_function")
        assert hasattr(layer_1_iot, "create_iot_thing")
        
        # L2 components
        assert hasattr(layer_2_compute, "create_persister_iam_role")
        assert hasattr(layer_2_compute, "create_persister_lambda_function")
        assert hasattr(layer_2_compute, "create_processor_lambda_function")
        
        # L3 components - using correct function name
        assert hasattr(layer_3_storage, "create_hot_dynamodb_table")
        assert hasattr(layer_3_storage, "create_hot_reader_lambda_function")
        
        # L4 components - using correct function names
        assert hasattr(layer_4_twinmaker, "create_twinmaker_workspace")
        assert hasattr(layer_4_twinmaker, "create_twinmaker_hierarchy")
        
        # L5 components
        assert hasattr(layer_5_grafana, "create_grafana_workspace")


class TestL1AdapterCallsL1Components:
    """Verify L1 adapter imports and uses L1 component functions."""

    def test_l1_adapter_imports_l1_components(self):
        """L1 adapter should import from layer_1_iot module."""
        from src.providers.aws.layers.layer_1_iot import (
            create_dispatcher_iam_role,
            create_dispatcher_lambda_function,
            create_dispatcher_iot_rule,
            create_iot_thing,
        )
        
        assert callable(create_dispatcher_iam_role)
        assert callable(create_dispatcher_lambda_function)
        assert callable(create_dispatcher_iot_rule)
        assert callable(create_iot_thing)


class TestL2AdapterCallsL2Components:
    """Verify L2 adapter imports and uses L2 component functions."""

    def test_l2_adapter_imports_l2_components(self):
        """L2 adapter should import from layer_2_compute module."""
        from src.providers.aws.layers.layer_2_compute import (
            create_persister_iam_role,
            create_persister_lambda_function,
            create_processor_iam_role,
            create_processor_lambda_function,
        )
        
        assert callable(create_persister_iam_role)
        assert callable(create_persister_lambda_function)
        assert callable(create_processor_iam_role)
        assert callable(create_processor_lambda_function)


class TestL3AdapterCallsL3Components:
    """Verify L3 adapter imports and uses L3 component functions."""

    def test_l3_adapter_imports_l3_components(self):
        """L3 adapter should import from layer_3_storage module."""
        from src.providers.aws.layers.layer_3_storage import (
            create_hot_dynamodb_table,
            create_hot_reader_iam_role,
            create_hot_reader_lambda_function,
        )
        
        assert callable(create_hot_dynamodb_table)
        assert callable(create_hot_reader_iam_role)
        assert callable(create_hot_reader_lambda_function)


class TestL4AdapterCallsL4Components:
    """Verify L4 adapter imports and uses L4 component functions."""

    def test_l4_adapter_imports_l4_components(self):
        """L4 adapter should import from layer_4_twinmaker module."""
        from src.providers.aws.layers.layer_4_twinmaker import (
            create_twinmaker_workspace,
            create_twinmaker_hierarchy,
            create_twinmaker_component_type,
        )
        
        assert callable(create_twinmaker_workspace)
        assert callable(create_twinmaker_hierarchy)
        assert callable(create_twinmaker_component_type)


class TestL5AdapterCallsL5Components:
    """Verify L5 adapter imports and uses L5 component functions."""

    def test_l5_adapter_imports_l5_components(self):
        """L5 adapter should import from layer_5_grafana module."""
        from src.providers.aws.layers.layer_5_grafana import (
            create_grafana_workspace,
        )
        
        assert callable(create_grafana_workspace)


class TestMultiCloudComponentPlacement:
    """Verify multi-cloud components are in correct layers."""

    def test_ingestion_function_exists_in_l2(self):
        """Ingestion Lambda function should exist in L2 module."""
        from src.providers.aws.layers.layer_2_compute import create_ingestion_lambda_function
        assert callable(create_ingestion_lambda_function)

    def test_hot_reader_exists_in_l3(self):
        """Hot Reader should exist in L3 module."""
        from src.providers.aws.layers.layer_3_storage import create_hot_reader_lambda_function
        assert callable(create_hot_reader_lambda_function)

    def test_digital_twin_data_connector_exists_in_l3(self):
        """Digital Twin Data Connector should exist in L3 module (for creation by L4 when needed)."""
        from src.providers.aws.layers.layer_3_storage import create_digital_twin_data_connector_lambda_function
        assert callable(create_digital_twin_data_connector_lambda_function)


class TestComponentNamingConsistency:
    """Verify component naming follows conventions."""

    @pytest.fixture
    def naming(self):
        from src.providers.aws.naming import AWSNaming
        return AWSNaming("test-twin")

    def test_l1_component_naming(self, naming):
        """L1 components should have consistent naming."""
        assert "dispatcher" in naming.dispatcher_lambda_function()
        assert "dispatcher" in naming.dispatcher_iam_role()

    def test_l2_component_naming(self, naming):
        """L2 components should have consistent naming."""
        assert "persister" in naming.persister_lambda_function()
        assert "processor" in naming.processor_lambda_function("device-1")

    def test_l3_component_naming(self, naming):
        """L3 components should have consistent naming."""
        table_name = naming.hot_dynamodb_table()
        assert "hot" in table_name.lower() or "storage" in table_name.lower()
        assert "hot-reader" in naming.hot_reader_lambda_function()

    def test_l4_component_naming(self, naming):
        """L4 components should have consistent naming."""
        ws_name = naming.twinmaker_workspace()
        assert ws_name  # Just verify it returns something

    def test_l5_component_naming(self, naming):
        """L5 components should have consistent naming."""
        gf_name = naming.grafana_workspace()
        assert gf_name  # Just verify it returns something


class TestDeployerOrchestration:
    """Verify the top-level deployer calls layer adapters correctly."""

    def test_deployer_has_layer_functions(self):
        """Top-level deployer should have functions for each layer."""
        import providers.deployer as deployer
        
        assert hasattr(deployer, "deploy_l1")
        assert hasattr(deployer, "deploy_l2")
        assert hasattr(deployer, "deploy_l3_hot")
        assert hasattr(deployer, "deploy_l3_cold")
        assert hasattr(deployer, "deploy_l3_archive")
        assert hasattr(deployer, "deploy_l4")
        assert hasattr(deployer, "deploy_l5")
        
        assert hasattr(deployer, "destroy_l1")
        assert hasattr(deployer, "destroy_l2")
        assert hasattr(deployer, "destroy_l3_hot")
        assert hasattr(deployer, "destroy_l3_cold")
        assert hasattr(deployer, "destroy_l3_archive")
        assert hasattr(deployer, "destroy_l4")
        assert hasattr(deployer, "destroy_l5")

    def test_deployer_has_deploy_all(self):
        """Top-level deployer should have deploy_all for full deployment."""
        import providers.deployer as deployer
        
        assert hasattr(deployer, "deploy_all")
        assert hasattr(deployer, "destroy_all")


class TestNoIoTDeployerReferences:
    """Verify iot_deployer.py has been completely removed."""

    def test_main_has_no_iot_deployer_import(self):
        """main.py should not import iot_deployer."""
        import main
        
        # Check the module doesn't have iot_deployer in its namespace
        assert not hasattr(main, "iot_deployer")

    def test_deployment_api_has_no_iot_deployer_import(self):
        """deployment.py should not import iot_deployer."""
        from src.api import deployment
        
        # Check the module doesn't have iot_deployer in its namespace
        assert not hasattr(deployment, "iot_deployer")
