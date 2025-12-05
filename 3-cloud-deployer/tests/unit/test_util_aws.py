import pytest
from unittest.mock import MagicMock, patch
import aws.util_aws as util_aws
import aws.globals_aws as globals_aws

class TestUtilAWS:
    
    @patch("aws.globals_aws.aws_iot_client")
    def test_iot_rule_exists(self, mock_iot):
        """Verify iot_rule_exists pagination logic."""
        paginator = MagicMock()
        paginator.paginate.return_value = [
            {"rules": [{"ruleName": "rule1"}]},
            {"rules": [{"ruleName": "rule2"}]}
        ]
        mock_iot.get_paginator.return_value = paginator
        
        assert util_aws.iot_rule_exists("rule2") is True
        assert util_aws.iot_rule_exists("rule3") is False

    def test_link_generation(self):
        """Verify console link generation functions."""
        # Setup region mocks - ensure clients are mocks first if they aren't
        globals_aws.aws_iam_client = MagicMock()
        globals_aws.aws_lambda_client = MagicMock()
        globals_aws.aws_s3_client = MagicMock()
        globals_aws.aws_iot_client = MagicMock()
        globals_aws.aws_dynamodb_client = MagicMock()
        globals_aws.aws_events_client = MagicMock()
        globals_aws.aws_twinmaker_client = MagicMock()
        globals_aws.aws_grafana_client = MagicMock()
        globals_aws.aws_apigateway_client = MagicMock()

        globals_aws.aws_iam_client.meta.region_name = "eu-central-1"
        globals_aws.aws_lambda_client.meta.region_name = "eu-central-1"
        globals_aws.aws_s3_client.meta.region_name = "eu-central-1"
        globals_aws.aws_events_client.meta.region_name = "eu-central-1"
        
        # Test a few representative links
        assert "eu-central-1" in util_aws.link_to_iam_role("role")
        assert "eu-central-1" in util_aws.link_to_lambda_function("func")
        assert "console.aws.amazon.com/s3/buckets/bucket" in util_aws.link_to_s3_bucket("bucket")

    @patch("util.zip_directory")
    @patch("builtins.open", new_callable=MagicMock)
    def test_compile_lambda_function(self, mock_open, mock_zip):
        """Verify compile_lambda_function reads zipped content."""
        mock_zip.return_value = "/tmp/test.zip"
        mock_file = MagicMock()
        mock_file.read.return_value = b"zip-content"
        mock_open.return_value.__enter__.return_value = mock_file
        
        content = util_aws.compile_lambda_function("src")
        assert content == b"zip-content"
        mock_zip.assert_called_with("src")
