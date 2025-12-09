"""
Tests for _generate_simulator_config function in iot_deployer_aws.py.
"""
import pytest
import json
import os
import sys
from unittest.mock import patch, MagicMock, mock_open

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src")))

from src.providers.aws.layers import layer_1_iot as iot_deployer_aws



class TestGenerateSimulatorConfig:
    """Tests for the _generate_simulator_config function."""

    @patch('os.makedirs')
    @patch('builtins.open', new_callable=mock_open)
    def test_generates_valid_config(self, mock_file, mock_makedirs):
        """Test that config contains all required fields."""
        # Setup mocks
        mock_provider = MagicMock()
        mock_provider.clients = {"iot": MagicMock()}
        mock_provider.clients["iot"].describe_endpoint.return_value = {
            'endpointAddress': 'test-endpoint.iot.region.amazonaws.com'
        }
        
        mock_config = MagicMock()
        mock_config.digital_twin_name = "test-twin"
        

        
        iot_device = {'id': 'device-123'}
        
        iot_deployer_aws._generate_simulator_config(
            iot_device, 
            provider=mock_provider, 
            config=mock_config,
            project_path='/fake/upload/project'
        )
        
        # Verify file was written
        mock_file.assert_called_once()
        
        # Get the written content
        written_content = ''.join(call.args[0] for call in mock_file().write.call_args_list)
        config = json.loads(written_content)
        
        # Verify required fields
        assert 'endpoint' in config
        assert config['endpoint'] == 'test-endpoint.iot.region.amazonaws.com'
        assert 'topic' in config
        assert config['topic'] == 'test-twin/iot-data'
        assert 'device_id' in config
        assert config['device_id'] == 'device-123'
        assert 'cert_path' in config
        assert 'key_path' in config
        assert 'root_ca_path' in config
        assert 'payload_path' in config

    @patch('os.makedirs')
    @patch('builtins.open', new_callable=mock_open)
    def test_topic_derived_from_digital_twin_name(self, mock_file, mock_makedirs):
        """Test that topic is correctly derived from digital_twin_name."""
        mock_provider = MagicMock()
        mock_provider.clients = {"iot": MagicMock()}
        mock_provider.clients["iot"].describe_endpoint.return_value = {'endpointAddress': 'x.iot.amazonaws.com'}
        
        mock_config = MagicMock()
        mock_config.digital_twin_name = "my-dt"
        

        
        iot_deployer_aws._generate_simulator_config(
            {'id': 'd1'},
            provider=mock_provider,
            config=mock_config,
            project_path='/fake/path'
        )
        
        written_content = ''.join(call.args[0] for call in mock_file().write.call_args_list)
        config = json.loads(written_content)
        
        assert config['topic'] == 'my-dt/iot-data'

    @patch('os.makedirs')
    @patch('builtins.open', new_callable=mock_open)
    def test_certificate_paths_relative(self, mock_file, mock_makedirs):
        """Test that certificate paths are relative to config location."""
        mock_provider = MagicMock()
        mock_provider.clients = {"iot": MagicMock()}
        mock_provider.clients["iot"].describe_endpoint.return_value = {'endpointAddress': 'x.iot.amazonaws.com'}
        
        mock_config = MagicMock()
        mock_config.digital_twin_name = "dt"
        

        
        iot_deployer_aws._generate_simulator_config(
            {'id': 'sensor-1'},
            provider=mock_provider,
            config=mock_config,
            project_path='/fake/path'
        )
        
        written_content = ''.join(call.args[0] for call in mock_file().write.call_args_list)
        config = json.loads(written_content)
        
        # Paths should be relative from config_generated.json location
        assert 'iot_devices_auth/sensor-1' in config['cert_path']
        assert 'iot_devices_auth/sensor-1' in config['key_path']
        assert config['payload_path'] == 'payloads.json'

    @patch('os.makedirs')
    @patch('builtins.open', new_callable=mock_open)
    def test_creates_directory_if_missing(self, mock_file, mock_makedirs):
        """Test that simulator directory is created if it doesn't exist."""
        mock_provider = MagicMock()
        mock_provider.clients = {"iot": MagicMock()}
        mock_provider.clients["iot"].describe_endpoint.return_value = {'endpointAddress': 'x.iot.amazonaws.com'}
        
        mock_config = MagicMock()
        mock_config.digital_twin_name = "dt"
        

        
        iot_deployer_aws._generate_simulator_config(
            {'id': 'd1'},
            provider=mock_provider,
            config=mock_config,
            project_path='/fake/upload/project'
        )
        
        mock_makedirs.assert_called_once()
        call_args = mock_makedirs.call_args
        assert 'iot_device_simulator' in call_args[0][0]
        assert 'aws' in call_args[0][0]

    def test_handles_boto_error(self):
        """Test graceful handling of AWS API errors."""
        from botocore.exceptions import ClientError
        mock_provider = MagicMock()
        mock_provider.clients = {"iot": MagicMock()}
        mock_provider.clients["iot"].describe_endpoint.side_effect = ClientError(
            {'Error': {'Code': 'AccessDenied', 'Message': 'Access denied'}},
            'DescribeEndpoint'
        )
        mock_config = MagicMock()
        mock_config.digital_twin_name = "dt"
        
        with pytest.raises(ClientError):
            iot_deployer_aws._generate_simulator_config(
                {'id': 'd1'},
                provider=mock_provider,
                config=mock_config,
                project_path='/fake/path'
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
