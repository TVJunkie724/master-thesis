"""
Test Module Imports
====================

Verifies that all calculation_v2 modules can be imported correctly.
"""

import pytest


class TestModuleImports:
    """Test that all modules import without errors."""
    
    def test_formulas_import(self):
        """Formulas module should import correctly."""
        from backend.calculation_v2.formulas import (
            message_based_cost,
            execution_based_cost,
            action_based_cost,
            storage_based_cost,
            user_based_cost,
            transfer_cost,
        )
        assert callable(message_based_cost)
        assert callable(execution_based_cost)
    
    def test_types_import(self):
        """Types module should import correctly."""
        from backend.calculation_v2.components import (
            FormulaType,
            LayerType,
            Provider,
            AWSComponent,
            AzureComponent,
            GCPComponent,
            GlueRole,
        )
        assert FormulaType.CE
        assert Provider.AWS.value == "aws"
    
    def test_aws_components_import(self):
        """AWS components should import correctly."""
        from backend.calculation_v2.components.aws import (
            AWSIoTCoreCalculator,
            AWSLambdaCalculator,
            AWSStepFunctionsCalculator,
            AWSEventBridgeCalculator,
            AWSDynamoDBCalculator,
            AWSS3IACalculator,
            AWSS3GlacierCalculator,
            AWSTwinMakerCalculator,
            AWSGrafanaCalculator,
        )
        assert AWSLambdaCalculator().formula_type
    
    def test_azure_components_import(self):
        """Azure components should import correctly."""
        from backend.calculation_v2.components.azure import (
            AzureIoTHubCalculator,
            AzureFunctionsCalculator,
            AzureLogicAppsCalculator,
            AzureEventGridCalculator,
            AzureCosmosDBCalculator,
            AzureBlobCoolCalculator,
            AzureBlobArchiveCalculator,
            AzureDigitalTwinsCalculator,
            AzureGrafanaCalculator,
        )
        assert AzureFunctionsCalculator().formula_type
    
    def test_gcp_components_import(self):
        """GCP components should import correctly."""
        from backend.calculation_v2.components.gcp import (
            GCPPubSubCalculator,
            GCPCloudFunctionsCalculator,
            GCPCloudWorkflowsCalculator,
            GCPFirestoreCalculator,
            GCSNearlineCalculator,
            GCSColdlineCalculator,
            GCPComputeEngineCalculator,
        )
        assert GCPCloudFunctionsCalculator().formula_type
    
    def test_layers_import(self):
        """Layer calculators should import correctly."""
        from backend.calculation_v2.layers import (
            AWSLayerCalculators,
            AzureLayerCalculators,
            GCPLayerCalculators,
        )
        aws = AWSLayerCalculators()
        assert hasattr(aws, 'calculate_l1_cost')
        assert hasattr(aws, 'calculate_l2_cost')
