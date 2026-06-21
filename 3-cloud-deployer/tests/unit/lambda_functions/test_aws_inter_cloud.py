"""AWS inter-cloud runtime helper tests."""

import importlib
import os
import sys
from unittest.mock import patch

import pytest


@pytest.fixture(scope="function", autouse=True)
def aws_inter_cloud_path():
    aws_funcs_dir = os.path.abspath(os.path.join(
        os.path.dirname(__file__),
        "..", "..", "..", "src", "providers", "aws", "lambda_functions"
    ))
    sys.path.insert(0, aws_funcs_dir)
    for key in list(sys.modules.keys()):
        if key.startswith("_shared"):
            del sys.modules[key]

    yield aws_funcs_dir

    if aws_funcs_dir in sys.path:
        sys.path.remove(aws_funcs_dir)
    for key in list(sys.modules.keys()):
        if key.startswith("_shared"):
            del sys.modules[key]


def test_post_to_remote_rejects_non_https_url_before_network_call():
    inter_cloud = importlib.import_module("_shared.inter_cloud")

    with patch("urllib.request.urlopen") as mock_urlopen:
        with pytest.raises(ValueError, match="absolute HTTPS URL"):
            inter_cloud.post_to_remote(
                url="http://example.com/ingestion",
                token="token",
                payload={},
                target_layer="L2",
            )

    mock_urlopen.assert_not_called()


def test_post_raw_rejects_url_without_host_before_network_call():
    inter_cloud = importlib.import_module("_shared.inter_cloud")

    with patch("urllib.request.urlopen") as mock_urlopen:
        with pytest.raises(ValueError, match="absolute HTTPS URL"):
            inter_cloud.post_raw(
                url="https:///missing-host",
                token="token",
                payload={},
            )

    mock_urlopen.assert_not_called()
