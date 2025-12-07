"""
Tests for _generate_simulator_config function in iot_deployer_aws.py.
"""
import pytest
import json
import os
import sys
from unittest.mock import patch, MagicMock, mock_open

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src")))

from aws import iot_deployer_aws


class TestGenerateSimulatorConfig:
    """Tests for the _generate_simulator_config function."""

    @patch('aws.iot_deployer_aws.globals_aws.aws_iot_client')
    @patch('aws.iot_deployer_aws.globals.config', {"digital_twin_name": "test-twin"})
    @patch('aws.iot_deployer_aws.util.get_path_in_project')
    @patch('os.makedirs')
    @patch('builtins.open', new_callable=mock_open)
    def test_generates_valid_config(self, mock_file, mock_makedirs, mock_get_path, mock_iot_client):
        """Test that config contains all required fields."""
        mock_iot_client.describe_endpoint.return_value = {
            'endpointAddress': 'test-endpoint.iot.region.amazonaws.com'
        }
        mock_get_path.return_value = '/fake/upload/project'
        
        iot_device = {'id': 'device-123'}
        
        iot_deployer_aws._generate_simulator_config(iot_device)
        
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

    @patch('aws.iot_deployer_aws.globals_aws.aws_iot_client')
    @patch('aws.iot_deployer_aws.globals.config', {"digital_twin_name": "my-dt"})
    @patch('aws.iot_deployer_aws.util.get_path_in_project')
    @patch('os.makedirs')
    @patch('builtins.open', new_callable=mock_open)
    def test_topic_derived_from_digital_twin_name(self, mock_file, mock_makedirs, mock_get_path, mock_iot_client):
        """Test that topic is correctly derived from digital_twin_name."""
        mock_iot_client.describe_endpoint.return_value = {'endpointAddress': 'x.iot.amazonaws.com'}
        mock_get_path.return_value = '/fake/path'
        
        iot_deployer_aws._generate_simulator_config({'id': 'd1'})
        
        written_content = ''.join(call.args[0] for call in mock_file().write.call_args_list)
        config = json.loads(written_content)
        
        assert config['topic'] == 'my-dt/iot-data'

    @patch('aws.iot_deployer_aws.globals_aws.aws_iot_client')
    @patch('aws.iot_deployer_aws.globals.config', {"digital_twin_name": "dt"})
    @patch('aws.iot_deployer_aws.util.get_path_in_project')
    @patch('os.makedirs')
    @patch('builtins.open', new_callable=mock_open)
    def test_certificate_paths_relative(self, mock_file, mock_makedirs, mock_get_path, mock_iot_client):
        """Test that certificate paths are relative to config location."""
        mock_iot_client.describe_endpoint.return_value = {'endpointAddress': 'x.iot.amazonaws.com'}
        mock_get_path.return_value = '/fake/path'
        
        iot_deployer_aws._generate_simulator_config({'id': 'sensor-1'})
        
        written_content = ''.join(call.args[0] for call in mock_file().write.call_args_list)
        config = json.loads(written_content)
        
        # Paths should be relative from config_generated.json location
        assert 'iot_devices_auth/sensor-1' in config['cert_path']
        assert 'iot_devices_auth/sensor-1' in config['key_path']
        assert config['payload_path'] == 'payloads.json'

    @patch('aws.iot_deployer_aws.globals_aws.aws_iot_client')
    @patch('aws.iot_deployer_aws.globals.config', {"digital_twin_name": "dt"})
    @patch('aws.iot_deployer_aws.util.get_path_in_project')
    @patch('os.makedirs')
    @patch('builtins.open', new_callable=mock_open)
    def test_creates_directory_if_missing(self, mock_file, mock_makedirs, mock_get_path, mock_iot_client):
        """Test that simulator directory is created if it doesn't exist."""
        mock_iot_client.describe_endpoint.return_value = {'endpointAddress': 'x.iot.amazonaws.com'}
        mock_get_path.return_value = '/fake/upload/project'
        
        iot_deployer_aws._generate_simulator_config({'id': 'd1'})
        
        mock_makedirs.assert_called_once()
        call_args = mock_makedirs.call_args
        assert 'iot_device_simulator' in call_args[0][0]
        assert 'aws' in call_args[0][0]

    @patch('aws.iot_deployer_aws.globals_aws.aws_iot_client')
    def test_handles_boto_error(self, mock_iot_client):
        """Test graceful handling of AWS API errors."""
        from botocore.exceptions import ClientError
        mock_iot_client.describe_endpoint.side_effect = ClientError(
            {'Error': {'Code': 'AccessDenied', 'Message': 'Access denied'}},
            'DescribeEndpoint'
        )
        
        with pytest.raises(ClientError):
            iot_deployer_aws._generate_simulator_config({'id': 'd1'})


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
