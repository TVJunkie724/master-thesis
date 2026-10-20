"""Fixed authenticated L5 HTML read, shared by readiness and application access.

No caller-supplied URL, credentials in links, redirects, or general proxy.
Empty panels prove reachability only, never simulator/data correctness.
"""
from html.parser import HTMLParser
import re
from urllib.parse import urlsplit

import requests
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

MAX_HTML_BYTES = 1024 * 1024


class _Panels(HTMLParser):
    def __init__(self):
        super().__init__()
        self.panels = []

    def handle_starttag(self, tag, attrs):
        if tag == "section":
            values = dict(attrs)
            self.panels.append((values.get("data-bucket-seconds"),
                                values.get("data-point-count"), values.get("data-state")))


def validate_visualization_html(body: bytes) -> bytes:
    if not body or len(body) > MAX_HTML_BYTES:
        raise ValueError("L5 response size is invalid")
    parser = _Panels()
    parser.feed(body.decode("utf-8"))
    if len(parser.panels) != 2 or [p[0] for p in parser.panels] != ["0", "3600"]:
        raise ValueError("L5 graphical panels are missing")
    for _, count, state in parser.panels:
        if count is None or not count.isdecimal() or not 0 <= int(count) <= 100:
            raise ValueError("L5 point count is invalid")
        if state != ("data" if int(count) else "empty"):
            raise ValueError("L5 data state is invalid")
    return body


def _endpoint(provider_name, bundle):
    endpoint = bundle.get("access_url", "")
    parsed = urlsplit(endpoint)
    if (parsed.scheme != "https" or parsed.username or parsed.password
            or parsed.query or parsed.fragment or parsed.port not in (None, 443)):
        raise ValueError("L5 endpoint is invalid")
    host = parsed.hostname or ""
    if provider_name == "aws":
        valid = re.fullmatch(r"[a-z0-9]+\.lambda-url\.[a-z0-9-]+\.on\.aws", host) and parsed.path in ("", "/")
    else:
        name = bundle.get("reader_function_name", "")
        valid = (re.fullmatch(r"[a-zA-Z0-9-]+", name) and host == f"{name}.azurewebsites.net"
                 and parsed.path == "/api/visualization/v1")
    if not valid:
        raise ValueError("L5 endpoint does not match the deployed provider surface")
    return endpoint


def fetch_visualization(provider_name, provider, outputs, *, verify_auth=False):
    if provider_name not in {"aws", "azure"}:
        raise ValueError("L5 provider is unsupported")
    bundle = outputs.get(f"{provider_name}_component_visualization_output")
    if not isinstance(bundle, dict) or bundle.get("internal_evidence", {}).get("content_revision") != "graphical-l5.v1":
        raise ValueError("Graphical L5 output is required; L3 JSON is not L5")
    endpoint = _endpoint(provider_name, bundle)
    if verify_auth:
        with requests.get(endpoint, timeout=30, allow_redirects=False, stream=True) as response:
            if response.status_code not in (401, 403):
                raise RuntimeError("L5 must reject unauthenticated access")
    if provider_name == "aws":
        credentials = provider.clients["lambda"]._request_signer._credentials
        signed = AWSRequest(method="GET", url=endpoint)
        SigV4Auth(credentials, "lambda", provider.region).add_auth(signed)
        headers = dict(signed.headers)
    else:
        from src.providers.azure.layers.layer_5_raw_history import _reader_key
        headers = {"x-functions-key": _reader_key(provider, bundle["reader_function_name"], "six-layer-visualization", wait_for_ready=verify_auth)}
    with requests.get(endpoint, headers=headers, timeout=30, allow_redirects=False, stream=True) as response:
        if response.status_code != 200 or response.headers.get("Content-Type", "").split(";")[0] != "text/html":
            raise RuntimeError(f"L5 HTML unavailable (HTTP {response.status_code})")
        body = bytearray()
        for chunk in response.iter_content(chunk_size=65536):
            body.extend(chunk)
            if len(body) > MAX_HTML_BYTES:
                raise ValueError("L5 response size is invalid")
    return validate_visualization_html(bytes(body))
