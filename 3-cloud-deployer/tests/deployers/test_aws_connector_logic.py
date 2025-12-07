import unittest
import os
import shutil
import tempfile
import zipfile
import json
import sys
from unittest.mock import MagicMock, patch

# Fix import path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))

# Mock fastapi before importing util
import sys
sys.modules['fastapi'] = MagicMock()
sys.modules['fastapi.responses'] = MagicMock()

import util as util
import constants as CONSTANTS
import globals as globals
import aws.globals_aws as globals_aws
import validator as validator

# Mock aws.iot_deployer_aws for logic testing without actual AWS calls
# We need to test the logic branch, not the boto3 call itself
import aws.iot_deployer_aws as iot_deployer_aws

class TestAWSConnectorLogic(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.wrapper_dir = os.path.join(self.test_dir, "wrapper")
        self.upload_dir = os.path.join(self.test_dir, "upload", "template")
        os.makedirs(self.wrapper_dir)
        os.makedirs(self.upload_dir)
        
        # Create Dummy Wrapper
        with open(os.path.join(self.wrapper_dir, "lambda_function.py"), "w") as f:
            f.write("def lambda_handler(event, context): pass")
            
        # Create Dummy Custom Code
        self.custom_path = os.path.join("lambda_functions", "processors", "device_1", "process.py")
        abs_custom_path = os.path.join(self.upload_dir, self.custom_path)
        os.makedirs(os.path.dirname(abs_custom_path), exist_ok=True)
        with open(abs_custom_path, "w") as f:
            f.write("def process(event): return event")

        # Mock Globals
        globals.CURRENT_PROJECT = "template"
        
        # Patch project_path to return self.test_dir
        self.patcher = patch('globals.project_path', return_value=self.test_dir)
        self.mock_project_path = self.patcher.start()
        
        # Patch get_project_upload_path because util uses it
        self.patcher2 = patch('globals.get_project_upload_path', return_value=self.upload_dir)
        self.mock_upload_path = self.patcher2.start()

    def tearDown(self):
        shutil.rmtree(self.test_dir)
        self.patcher.stop()
        self.patcher2.stop()

    def test_compile_merged_lambda_function(self):
        # Action
        zip_bytes = util.compile_merged_lambda_function(self.wrapper_dir, self.custom_path)
        
        # Verify
        with tempfile.NamedTemporaryFile(delete=False) as tf:
            tf.write(zip_bytes)
            tf.close()
            
            with zipfile.ZipFile(tf.name, 'r') as zf:
                files = zf.namelist()
                self.assertIn("lambda_function.py", files)
                self.assertIn("process.py", files)
                
            os.remove(tf.name)

    def test_config_inter_cloud_validation(self):
        # Invalid Schema (Not a dict)
        bad_config = json.dumps({"connections": []})
        with self.assertRaises(ValueError) as cm:
            validator.validate_config_content(CONSTANTS.CONFIG_INTER_CLOUD_FILE, bad_config)
        self.assertIn("must be a dictionary", str(cm.exception))

        # Missing Fields
        bad_config_2 = json.dumps({
            "connections": {
                "conn1": {"token": "abc"} # Missing provider, url
            }
        })
        with self.assertRaises(ValueError) as cm:
            validator.validate_config_content(CONSTANTS.CONFIG_INTER_CLOUD_FILE, bad_config_2)
        self.assertIn("missing required fields", str(cm.exception))

        # Valid
        good_config = json.dumps({
            "connections": {
                "conn1": {"token": "abc", "provider": "aws", "url": "http://..."}
            }
        })
        try:
            validator.validate_config_content(CONSTANTS.CONFIG_INTER_CLOUD_FILE, good_config)
        except ValueError:
            self.fail("validate_config_content raised ValueError unexpectedly!")

    def test_naming_helpers(self):
        # Mock global config
        globals.config = {"digital_twin_name": "MyTwin"}
        device = {"iotDeviceId": "sensor-1"}
        
        self.assertEqual(globals_aws.connector_lambda_function_name(device), "MyTwin-sensor-1-connector")
        self.assertEqual(globals_aws.ingestion_lambda_function_name(), "MyTwin-ingestion")
        self.assertEqual(globals_aws.writer_lambda_function_name(), "MyTwin-writer")

    @patch('aws.globals_aws.aws_lambda_client')
    @patch('aws.globals_aws.aws_iam_client')
    def test_deploy_connector_branch(self, mock_iam, mock_lambda):
        # Setup Multi-Cloud Scenario
        globals.config_providers = {
            "layer_1_provider": "aws",
            "layer_2_provider": "azure" # Remote!
        }
        globals.config_inter_cloud = {
             "connections": {
                 "aws_l1_to_azure_l2": {"url": "http://azure", "token": "secret"}
             }
        }
        
        device = {"iotDeviceId": "dev1", "id": "dev1"}
        mock_iam.get_role.return_value = {'Role': {'Arn': 'arn:role'}}
        
        # Action
        try:
            iot_deployer_aws.create_processor_lambda_function(device)
        except Exception as e:
            # We trap file not found because "connector" folder doesn't exist in temp dir
            # But we want to verify it TRIED to deploy connector name
            pass
            
        # Since we mocked aws_lambda_client, we check calls
        # However, util.compile_lambda_function will fail because folder doesn't exist.
        # So we should mock util.compile_lambda_function too.
        
    @patch('util.compile_lambda_function', return_value=b'zip')    
    @patch('aws.globals_aws.aws_lambda_client')
    @patch('aws.globals_aws.aws_iam_client')
    def test_deploy_connector_branch_logic(self, mock_iam, mock_lambda, mock_zip):
        globals.config_providers = {
            "layer_1_provider": "aws",
            "layer_2_provider": "azure" 
        }
        globals.config_inter_cloud = {
             "connections": {
                 "aws_l1_to_azure_l2": {"url": "http://azure", "token": "secret"}
             }
        }
        globals.config = {"digital_twin_name": "Twin"}
        
        device = {"iotDeviceId": "dev1", "id": "dev1"}
        mock_iam.get_role.return_value = {'Role': {'Arn': 'arn:role'}}
        
        iot_deployer_aws.create_processor_lambda_function(device)
        
        # Verify call arguments
        args, kwargs = mock_lambda.create_function.call_args
        self.assertEqual(kwargs['FunctionName'], 'Twin-dev1-connector')
        self.assertEqual(kwargs['Environment']['Variables']['REMOTE_INGESTION_URL'], 'http://azure')

if __name__ == '__main__':
    unittest.main()
