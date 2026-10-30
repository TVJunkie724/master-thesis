"""Fixed authenticated L5 HTML read, shared by readiness and application access.

No caller-supplied URL, credentials in links, redirects, or general proxy.
Empty panels prove reachability only, never simulator/data correctness.
"""
from html.parser import HTMLParser
import re
import time
from urllib.parse import urlsplit

import requests
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from src.logger import logger

MAX_HTML_BYTES = 1024 * 1024


def _get(endpoint, *, stage, **kwargs):
    """Record only phase/status/timing, never URLs, headers or exception text."""
    started = time.monotonic()
    try:
        response = requests.get(endpoint, **kwargs)
    except (requests.Timeout, requests.ConnectionError) as exc:
        logger.warning("L5 request phase=%s seconds=%.3f error_type=%s",
                       stage, time.monotonic() - started, type(exc).__name__)
        raise
    logger.info("L5 request phase=%s seconds=%.3f http=%s",
                stage, time.monotonic() - started, response.status_code)
    return response


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


class _L5NotReady(RuntimeError):
    """Transient platform response, never an authorization/content failure."""

    def __init__(self, message, *, status_code, request_phase, response_origin="unclassified"):
        super().__init__(message)
        self.status_code = status_code
        self.request_phase = request_phase
        self.response_origin = response_origin


def fetch_visualization(provider_name, provider, outputs, *, verify_auth=False):
    # Only deployment readiness may wait through initial Azure host admission.
    # Ordinary UI reads remain one request sequence, without hidden retries.
    initial_azure = provider_name == "azure" and verify_auth
    attempts = 21 if initial_azure else 1
    readiness_deadline = time.monotonic() + 600 if initial_azure else None
    for attempt in range(attempts):
        try:
            return _fetch_visualization_once(provider_name, provider, outputs,
                                             verify_auth=verify_auth,
                                             readiness_deadline=readiness_deadline)
        except (requests.Timeout, requests.ConnectionError, _L5NotReady):
            remaining = readiness_deadline - time.monotonic() if readiness_deadline is not None else 0
            if attempt + 1 == attempts or remaining <= 0:
                raise
            time.sleep(min(30, remaining))


def _fetch_visualization_once(provider_name, provider, outputs, *, verify_auth=False,
                             readiness_deadline=None):
    if provider_name not in {"aws", "azure"}:
        raise ValueError("L5 provider is unsupported")
    bundle = outputs.get(f"{provider_name}_component_visualization_output")
    if not isinstance(bundle, dict) or bundle.get("internal_evidence", {}).get("content_revision") != "graphical-l5.v1":
        raise ValueError("Graphical L5 output is required; L3 JSON is not L5")
    endpoint = _endpoint(provider_name, bundle)
    # A live zero-always-ready Flex probe returned valid content after 36 s,
    # before entering its millisecond-scale handler. Allow that initial delay.
    # A normal Azure snapshot uses the same scale-to-zero handler as readiness.
    # Its bounded L3 reads can exceed 30 s; do not abort a valid snapshot early.
    def request_timeout():
        timeout = 180 if provider_name == "azure" else 30
        if readiness_deadline is not None:
            remaining = readiness_deadline - time.monotonic()
            if remaining <= 0:
                raise requests.ReadTimeout("L5 initial readiness deadline exceeded")
            timeout = min(timeout, remaining)
        return timeout
    if verify_auth:
        with _get(endpoint, stage="unauthenticated", timeout=request_timeout(), allow_redirects=False, stream=True) as response:
            if response.status_code in (502, 503, 504):
                raise _L5NotReady("L5 authentication surface is not ready",
                                  status_code=response.status_code,
                                  request_phase="unauthenticated")
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
    with _get(endpoint, stage="authenticated", headers=headers, timeout=request_timeout(), allow_redirects=False, stream=True) as response:
        if response.status_code in (502, 503, 504):
            # Recognize only our fixed public error body; never log arbitrary
            # provider responses, credentials, headers or exception messages.
            sample = bytearray()
            for chunk in response.iter_content(chunk_size=128):
                sample.extend(chunk[:128 - len(sample)])
                if len(sample) == 128:
                    break
            origin = "l5-data-unavailable" if len(sample) < 128 and sample.strip() == b"L5 data unavailable" else "unclassified"
            logger.warning("L5 response unavailable phase=authenticated http=%s origin=%s",
                           response.status_code, origin)
            raise _L5NotReady("L5 HTML surface is not ready",
                              status_code=response.status_code,
                              request_phase="authenticated", response_origin=origin)
        if response.status_code != 200 or response.headers.get("Content-Type", "").split(";")[0] != "text/html":
            raise RuntimeError(f"L5 HTML unavailable (HTTP {response.status_code})")
        body = bytearray()
        for chunk in response.iter_content(chunk_size=65536):
            body.extend(chunk)
            if len(body) > MAX_HTML_BYTES:
                raise ValueError("L5 response size is invalid")
    request_timeout()  # Do not admit a response that completed after readiness expired.
    return validate_visualization_html(bytes(body))
