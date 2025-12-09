import pytest
from unittest.mock import MagicMock, call
from src.providers.aws.layers.layer_3_storage import create_l3_api_gateway, destroy_l3_api_gateway

class TestAWSAPIGateway:
    """Test API Gateway creation and destruction in Layer 3."""

    def test_create_l3_api_gateway(self, mock_provider, mock_project_config):
        """Verify API Gateway creation."""
        # Setup mocks
        apigw_client = MagicMock()
        lambda_client = MagicMock()
        sts_client = MagicMock()
        
        mock_provider.clients["apigatewayv2"] = apigw_client
        mock_provider.clients["lambda"] = lambda_client
        mock_provider.clients["sts"] = sts_client
        
        # Mock returns
        apigw_client.create_api.return_value = {"ApiId": "test-api-id"}
        lambda_client.get_function.return_value = {"Configuration": {"FunctionArn": "arn:aws:lambda:eu-central-1:123456789012:function:test-twin-hot-reader"}}
        lambda_client.meta.region_name = "eu-central-1"
        sts_client.get_caller_identity.return_value = {"Account": "123456789012"}
        apigw_client.create_integration.return_value = {"IntegrationId": "test-integration-id"}
        
        # Execute
        create_l3_api_gateway(mock_provider, mock_project_config)
        
        # Verify API creation
        apigw_client.create_api.assert_called_once_with(
            Name="test-twin-api-gateway",
            ProtocolType="HTTP",
            Description="API Gateway for cross-cloud L3 access"
        )
        
        # Verify Lambda interaction
        lambda_client.get_function.assert_called_once_with(FunctionName="test-twin-hot-reader")
        
        # Verify Integration creation
        apigw_client.create_integration.assert_called_once_with(
            ApiId="test-api-id",
            IntegrationType="AWS_PROXY",
            IntegrationUri="arn:aws:lambda:eu-central-1:123456789012:function:test-twin-hot-reader",
            PayloadFormatVersion="2.0"
        )
        
        # Verify Route creation
        apigw_client.create_route.assert_called_once_with(
            ApiId="test-api-id",
            RouteKey="GET /data",
            Target="integrations/test-integration-id"
        )
        
        # Verify Stage creation
        apigw_client.create_stage.assert_called_once_with(
            ApiId="test-api-id",
            StageName="prod",
            AutoDeploy=True
        )
        
        # Verify Permission addition
        lambda_client.add_permission.assert_called_once_with(
            FunctionName="test-twin-hot-reader",
            StatementId="apigw-invoke",
            Action="lambda:InvokeFunction",
            Principal="apigateway.amazonaws.com",
            SourceArn="arn:aws:execute-api:eu-central-1:123456789012:test-api-id/*"
        )

    def test_destroy_l3_api_gateway(self, mock_provider):
        """Verify API Gateway destruction."""
        # Setup mocks
        apigw_client = MagicMock()
        lambda_client = MagicMock()
        
        mock_provider.clients["apigatewayv2"] = apigw_client
        mock_provider.clients["lambda"] = lambda_client
        
        # Mock existing API found
        apigw_client.get_apis.return_value = {
            "Items": [
                {"Name": "other-api", "ApiId": "other-id"},
                {"Name": "test-twin-api-gateway", "ApiId": "test-api-id"}
            ]
        }
        
        # Execute
        destroy_l3_api_gateway(mock_provider)
        
        # Verify Permission removal
        lambda_client.remove_permission.assert_called_once_with(
            FunctionName="test-twin-hot-reader",
            StatementId="apigw-invoke"
        )
        
        # Verify API deletion
        apigw_client.delete_api.assert_called_once_with(ApiId="test-api-id")

    def test_destroy_l3_api_gateway_not_found(self, mock_provider):
        """Verify destruction does nothing if API not found."""
        apigw_client = MagicMock()
        mock_provider.clients["apigatewayv2"] = apigw_client
        apigw_client.get_apis.return_value = {"Items": []}
        
        destroy_l3_api_gateway(mock_provider)
        
        apigw_client.delete_api.assert_not_called()
