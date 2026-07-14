import importlib.util
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError
from urllib.request import Request

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[3]
INTER_CLOUD_MODULES = {
    "aws": PROJECT_ROOT
    / "src/providers/aws/lambda_functions/_shared/inter_cloud.py",
    "azure": PROJECT_ROOT
    / "src/providers/azure/azure_functions/_shared/inter_cloud.py",
    "gcp": PROJECT_ROOT
    / "src/providers/gcp/cloud_functions/_shared/inter_cloud.py",
}


@pytest.fixture(params=INTER_CLOUD_MODULES.items(), ids=INTER_CLOUD_MODULES.keys())
def inter_cloud_module(request):
    provider, module_path = request.param
    spec = importlib.util.spec_from_file_location(
        f"{provider}_inter_cloud_security_tests",
        module_path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com/function",
        "file:///tmp/credential.json",
        "https://user:password@example.com/function",
        "https:///function",
    ],
)
def test_safe_urlopen_rejects_non_https_or_embedded_credentials(
    inter_cloud_module,
    url,
):
    with pytest.raises(ValueError, match="HTTPS URL|user credentials"):
        inter_cloud_module.safe_urlopen(Request(url), timeout=1)


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com/function",
        "file:///tmp/credential.json",
        "https://user:password@example.com/function",
    ],
)
def test_validate_https_url_rejects_unsafe_endpoint(inter_cloud_module, url):
    with pytest.raises(ValueError, match="HTTPS URL|user credentials"):
        inter_cloud_module.validate_https_url(url)


def test_validate_https_url_accepts_absolute_https_endpoint(inter_cloud_module):
    assert inter_cloud_module.validate_https_url("https://example.com/function") is None


def test_safe_urlopen_delegates_validated_https_request(inter_cloud_module):
    response = MagicMock()

    with patch.object(
        inter_cloud_module.urllib.request,
        "urlopen",
        return_value=response,
    ) as urlopen:
        result = inter_cloud_module.safe_urlopen(
            Request("https://example.com/function"),
            timeout=7,
        )

    assert result is response
    urlopen.assert_called_once()
    assert urlopen.call_args.kwargs == {"timeout": 7}


def test_http_error_diagnostics_are_bounded_and_redacted(inter_cloud_module):
    secret = "credential-value-that-must-not-leak"
    body = (
        '{"client_secret":"'
        + secret
        + '","authorization":"Bearer header-secret","padding":"'
        + ("x" * 800)
        + '"}'
    ).encode()
    error = HTTPError(
        "https://example.com/function?code=query-secret",
        500,
        "failed",
        {},
        BytesIO(body),
    )

    diagnostic = inter_cloud_module.read_http_error_body(error, limit=128)

    assert len(diagnostic) <= 128
    assert secret not in diagnostic
    assert "header-secret" not in diagnostic
    assert "<redacted>" in diagnostic


def test_diagnostic_redaction_covers_query_and_private_key(inter_cloud_module):
    diagnostic = inter_cloud_module.redact_diagnostic(
        "https://example.com/run?code=query-secret&token=token-secret "
        "-----BEGIN PRIVATE KEY-----private-value-----END PRIVATE KEY-----"
    )

    assert "query-secret" not in diagnostic
    assert "token-secret" not in diagnostic
    assert "private-value" not in diagnostic
    assert diagnostic.count("<redacted>") == 2
    assert "<redacted-private-key>" in diagnostic
