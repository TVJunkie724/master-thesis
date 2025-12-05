import pytest
import boto3
from unittest.mock import MagicMock, patch
import aws.core_deployer_aws as core_aws
import aws.globals_aws as globals_aws
import globals
from botocore.exceptions import ClientError

class TestAWSAPIGateway:
    @patch("aws.core_deployer_aws.util_aws.get_api_id_by_name")
    def test_create_destroy_api(self, mock_get_id, mock_aws_context):
        """Verify API creation and destruction."""
        # 1. Test Creation
        globals_aws.aws_apigateway_client.create_api = MagicMock(return_value={"ApiId": "test-api-id", "Name": "test-api"})
        globals_aws.aws_apigateway_client.create_stage = MagicMock(return_value={"StageName": "$default"})
        
        with patch.object(globals, 'config', {"digital_twin_name": "test-twin"}), \
             patch("globals.api_name", return_value="test-api"):
            core_aws.create_api()
            globals_aws.aws_apigateway_client.create_api.assert_called_with(Name="test-api", ProtocolType="HTTP")
            globals_aws.aws_apigateway_client.create_stage.assert_called()

        # 2. Test Destruction
        mock_get_id.return_value = "test-api-id"
        globals_aws.aws_apigateway_client.delete_api = MagicMock()
        
        with patch.object(globals, 'config', {"digital_twin_name": "test-twin"}), \
             patch("globals.api_name", return_value="test-api"):
            core_aws.destroy_api()
            globals_aws.aws_apigateway_client.delete_api.assert_called_with(ApiId="test-api-id")

    @patch("aws.core_deployer_aws.util_aws.get_api_id_by_name")
    @patch("aws.core_deployer_aws.util_aws.get_lambda_arn_by_name")
    @patch("aws.core_deployer_aws.util_aws.get_api_route_id_by_key")
    @patch("aws.core_deployer_aws.util_aws.get_api_integration_id_by_uri")
    def test_create_destroy_api_integration(self, mock_get_int_id, mock_get_route_id, mock_get_arn, mock_get_api_id, mock_aws_context):
        """Verify API integration creation and destruction."""
        mock_get_api_id.return_value = "test-api-id"
        mock_get_arn.return_value = "arn:aws:lambda:eu-central-1:123:function:hot-reader"
        
        # Mocks for Create
        globals_aws.aws_apigateway_client.create_integration = MagicMock(return_value={"IntegrationId": "int-id"})
        globals_aws.aws_apigateway_client.create_route = MagicMock()
        globals_aws.aws_lambda_client.add_permission = MagicMock()
        
        # Mocks for Destroy
        globals_aws.aws_apigateway_client.delete_route = MagicMock()
        globals_aws.aws_apigateway_client.delete_integration = MagicMock()
        globals_aws.aws_lambda_client.remove_permission = MagicMock()

        # Mock config needing BOTH digital_twin_name (for lambda name) and hot_reader_name
        mock_config = {
            "digital_twin_name": "test-twin",
            "hot_reader_name": "hot-reader"
        }

        with patch.object(globals, 'config', mock_config), \
             patch("globals.api_name", return_value="test-api"):
            
            # Test Create
            core_aws.create_api_hot_reader_integration()
            
            globals_aws.aws_apigateway_client.create_integration.assert_called()
            globals_aws.aws_apigateway_client.create_route.assert_called()
            globals_aws.aws_lambda_client.add_permission.assert_called()

            # Test Destroy
            mock_get_route_id.return_value = "route-id"
            mock_get_int_id.return_value = "int-id"
            
            core_aws.destroy_api_hot_reader_integration()
            
            globals_aws.aws_lambda_client.remove_permission.assert_called()
            globals_aws.aws_apigateway_client.delete_route.assert_called()
            globals_aws.aws_apigateway_client.delete_integration.assert_called()
