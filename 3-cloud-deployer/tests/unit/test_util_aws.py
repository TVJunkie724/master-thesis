import pytest
from unittest.mock import MagicMock, patch
import src.providers.aws.util_aws as util_aws

class TestUtilAWS:
    
    def test_iot_rule_exists(self):
        """Verify iot_rule_exists pagination logic."""
        mock_iot = MagicMock()
        paginator = MagicMock()
        paginator.paginate.return_value = [
            {"rules": [{"ruleName": "rule1"}]},
            {"rules": [{"ruleName": "rule2"}]}
        ]
        mock_iot.get_paginator.return_value = paginator
        
        # Pass client explicitly
        assert util_aws.iot_rule_exists("rule2", iot_client=mock_iot) is True
        assert util_aws.iot_rule_exists("rule3", iot_client=mock_iot) is False

    def test_link_generation(self):
        """Verify console link generation functions."""
        region = "eu-central-1"
        
        # Test a few representative links using explicit region
        assert "eu-central-1" in util_aws.link_to_iam_role("role", region=region)
        assert "eu-central-1" in util_aws.link_to_lambda_function("func", region=region)
        assert "console.aws.amazon.com/s3/buckets/bucket" in util_aws.link_to_s3_bucket("bucket")

    @patch("src.util.zip_directory")
    @patch("builtins.open", new_callable=MagicMock)
    def test_compile_lambda_function(self, mock_open, mock_zip):
        """Verify compile_lambda_function reads zipped content."""
        mock_zip.return_value = "/tmp/test.zip"
        mock_file = MagicMock()
        mock_file.read.return_value = b"zip-content"
        mock_open.return_value.__enter__.return_value = mock_file
        
        # Pass project_path if needed (though not strictly used by simple zip_directory call in util_aws unless resolving)
        content = util_aws.compile_lambda_function("src", project_path="/app")
        assert content == b"zip-content"
        mock_zip.assert_called_with("src", project_path="/app")
