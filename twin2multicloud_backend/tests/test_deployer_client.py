from datetime import datetime, timezone
import io
import zipfile

import httpx
import pytest

import src.clients.deployer_client as deployer_client_module
from src.clients.deployer_client import DeployerClient
from src.services.errors import ExternalServiceError, ExternalServiceUnavailable


def _client_with_handler(handler):
    return DeployerClient(
        base_url="http://deployer.test",
        transport=httpx.MockTransport(handler),
    )


def _zip_bytes() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("README.md", "simulator")
    return buffer.getvalue()


def _simulator_headers(provider: str = "azure") -> dict[str, str]:
    classes = {
        "aws": "aws_iot_device_certificate",
        "azure": "azure_iot_hub_device_identity",
        "gcp": "gcp_pubsub_topic_publisher",
    }
    return {
        "Content-Type": "application/zip",
        "Content-Disposition": f'attachment; filename="simulator_factory_{provider}.zip"',
        "X-Twin2MultiCloud-Utility": "simulator",
        "X-Twin2MultiCloud-Provider": provider,
        "X-Twin2MultiCloud-Credential-Class": classes[provider],
    }


@pytest.mark.asyncio
async def test_validate_deployer_complete_posts_exact_endpoint_and_payload():
    seen = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["url"] = str(request.url)
        seen["payload"] = request.read().decode()
        return httpx.Response(200, json={"valid": True})

    response = await _client_with_handler(handler).validate_deployer_complete(
        {"cheapest_path": {}}
    )

    assert response == {"valid": True}
    assert seen["method"] == "POST"
    assert seen["url"] == "http://deployer.test/validate/deployer-complete"
    assert seen["payload"] == '{"cheapest_path":{}}'


@pytest.mark.asyncio
async def test_verify_permissions_posts_exact_provider_endpoint_and_payload():
    seen = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["url"] = str(request.url)
        seen["payload"] = request.read().decode()
        return httpx.Response(200, json={"valid": True})

    response = await _client_with_handler(handler).verify_permissions(
        "azure",
        {"azure_region": "westeurope"},
    )

    assert response == {"valid": True}
    assert seen == {
        "method": "POST",
        "url": "http://deployer.test/permissions/verify/azure",
        "payload": '{"azure_region":"westeurope"}',
    }


@pytest.mark.asyncio
async def test_validate_config_file_posts_multipart_validation_contract():
    seen = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["url"] = str(request.url)
        seen["content_type"] = request.headers["content-type"]
        return httpx.Response(200, json={"message": "Valid"})

    result = await _client_with_handler(handler).validate_config_file(
        "function-code",
        {"file": ("code.py", b"def handler(): pass", "text/plain")},
        provider="aws",
    )

    assert result == {"message": "Valid"}
    assert seen["method"] == "POST"
    assert seen["url"] == "http://deployer.test/validate/function-code?provider=aws"
    assert seen["content_type"].startswith("multipart/form-data")


@pytest.mark.asyncio
async def test_check_cooldown_sends_expected_query_params():
    seen = {}
    destroyed_at = datetime(2026, 4, 26, 10, 15, tzinfo=timezone.utc)

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, json={"ready": False, "remaining_seconds": 120})

    response = await _client_with_handler(handler).check_cooldown(
        destroyed_at,
        uses_gcp_firestore=True,
    )

    assert response == {"ready": False, "remaining_seconds": 120}
    assert seen["url"] == (
        "http://deployer.test/infrastructure/cooldown-check?"
        "destroyed_at=2026-04-26T10%3A15%3A00%2B00%3A00Z&uses_gcp_firestore=true"
    )


@pytest.mark.asyncio
async def test_deploy_and_destroy_streams_preserve_endpoint_params_and_lines():
    seen = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen.append(
            (request.method, str(request.url), request.headers["x-operation-package"])
        )
        return httpx.Response(200, text="data: first\n\nevent: complete\n\n")

    client = _client_with_handler(handler)

    deploy_lines = [
        line async for line in client.deploy_stream("aws", "factory", "deploy-token")
    ]
    destroy_lines = [
        line async for line in client.destroy_stream("gcp", "factory", "destroy-token")
    ]

    assert deploy_lines == ["data: first", "", "event: complete", ""]
    assert destroy_lines == ["data: first", "", "event: complete", ""]
    assert seen == [
        (
            "POST",
            "http://deployer.test/infrastructure/deploy/stream?provider=aws&project_name=factory",
            "deploy-token",
        ),
        (
            "POST",
            "http://deployer.test/infrastructure/destroy/stream?provider=gcp&project_name=factory",
            "destroy-token",
        ),
    ]


@pytest.mark.asyncio
async def test_log_trace_and_verification_methods_preserve_deployer_paths():
    seen = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen.append(
            (
                request.method,
                str(request.url),
                request.read().decode(),
                request.headers["x-operation-package"],
            )
        )
        return httpx.Response(200, json={"ok": True})

    client = _client_with_handler(handler)

    assert await client.start_log_trace("factory", "token") == {"ok": True}
    assert await client.verify_infrastructure("factory", "aws", "token") == {"ok": True}

    dataflow_lines = [
        line
        async for line in client.verify_dataflow(
            "factory", {"iotDeviceId": "device-1"}, "token"
        )
    ]
    trace_lines = [
        line async for line in client.stream_log_trace("factory", "TRACE-1", "token")
    ]

    assert dataflow_lines == ['{"ok":true}']
    assert trace_lines == ['{"ok":true}']
    assert seen == [
        (
            "POST",
            "http://deployer.test/logs/trace/start?project_name=factory",
            "",
            "token",
        ),
        (
            "POST",
            "http://deployer.test/infrastructure/verify?project_name=factory&provider=aws",
            "",
            "token",
        ),
        (
            "POST",
            "http://deployer.test/dataflow/verify?project_name=factory",
            '{"payload":{"iotDeviceId":"device-1"}}',
            "token",
        ),
        (
            "GET",
            "http://deployer.test/logs/trace/stream/TRACE-1?project_name=factory",
            "",
            "token",
        ),
    ]


@pytest.mark.asyncio
async def test_download_simulator_returns_validated_archive_from_exact_path():
    seen = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["operation_token"] = request.headers["x-operation-package"]
        return httpx.Response(200, content=_zip_bytes(), headers=_simulator_headers())

    archive = await _client_with_handler(handler).download_simulator(
        "factory", "azure", "token"
    )

    assert archive.content == _zip_bytes()
    assert archive.filename == "simulator_factory_azure.zip"
    assert archive.provider == "azure"
    assert archive.credential_class == "azure_iot_hub_device_identity"
    assert (
        seen["url"] == "http://deployer.test/projects/factory/simulator/azure/download"
    )
    assert seen["operation_token"] == "token"


class _AsyncChunks(httpx.AsyncByteStream):
    def __init__(self, *chunks: bytes):
        self.chunks = chunks

    async def __aiter__(self):
        for chunk in self.chunks:
            yield chunk


@pytest.mark.asyncio
async def test_download_simulator_stops_stream_when_archive_exceeds_limit(monkeypatch):
    monkeypatch.setattr(deployer_client_module, "MAX_SIMULATOR_ARCHIVE_BYTES", 8)

    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers=_simulator_headers(),
            stream=_AsyncChunks(b"1234", b"56789"),
        )

    with pytest.raises(ExternalServiceError, match="exceeded 8 bytes") as exc_info:
        await _client_with_handler(handler).download_simulator(
            "factory", "azure", "token"
        )

    assert (
        exc_info.value.public_detail
        == "Deployer returned an invalid simulator archive size."
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("content_length", ["9", "invalid", "-1"])
async def test_download_simulator_rejects_invalid_content_length_before_reading(
    monkeypatch,
    content_length,
):
    monkeypatch.setattr(deployer_client_module, "MAX_SIMULATOR_ARCHIVE_BYTES", 8)

    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={**_simulator_headers(), "Content-Length": content_length},
            stream=_AsyncChunks(),
        )

    with pytest.raises(ExternalServiceError) as exc_info:
        await _client_with_handler(handler).download_simulator(
            "factory", "azure", "token"
        )

    assert (
        exc_info.value.public_detail
        == "Deployer returned an invalid simulator archive size."
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("headers", "content"),
    [
        (
            {
                **_simulator_headers(),
                "Content-Disposition": 'attachment; filename="../secret.zip"',
            },
            _zip_bytes(),
        ),
        (
            {
                **_simulator_headers(),
                "Content-Disposition": 'attachment; filename="simulator.zip',
            },
            _zip_bytes(),
        ),
        (
            {
                **_simulator_headers(),
                "Content-Disposition": 'attachment; filename=simulator.zip"',
            },
            _zip_bytes(),
        ),
        ({**_simulator_headers(), "Content-Type": "application/json"}, _zip_bytes()),
        ({**_simulator_headers(), "X-Twin2MultiCloud-Provider": "aws"}, _zip_bytes()),
        (
            {**_simulator_headers(), "X-Twin2MultiCloud-Credential-Class": "admin_key"},
            _zip_bytes(),
        ),
        (_simulator_headers(), b"not-a-zip"),
    ],
)
async def test_download_simulator_rejects_invalid_binary_contract(headers, content):
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=content, headers=headers)

    with pytest.raises(ExternalServiceError):
        await _client_with_handler(handler).download_simulator(
            "factory", "azure", "token"
        )


@pytest.mark.asyncio
async def test_stage_operation_package_sends_canonical_multipart_contract():
    seen = []
    payload = {
        "project_name": "factory",
        "operation_token": "a" * 43,
        "expires_at": "2099-01-01T00:00:00Z",
        "warnings": [],
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, str(request.url), request.headers["content-type"]))
        return httpx.Response(200, json=payload)

    client = _client_with_handler(handler)

    assert await client.stage_operation_package("factory", b"zip") == payload

    assert seen[0][0:2] == (
        "POST",
        "http://deployer.test/projects/factory/operation-package",
    )
    assert seen[0][2].startswith("multipart/form-data")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {
            "project_name": "other",
            "operation_token": "a" * 43,
            "expires_at": "2099-01-01T00:00:00Z",
            "warnings": [],
        },
        {
            "project_name": "factory",
            "operation_token": "short",
            "expires_at": "2099-01-01T00:00:00Z",
            "warnings": [],
        },
        {
            "project_name": "factory",
            "operation_token": "a" * 43,
            "expires_at": "2020-01-01T00:00:00Z",
            "warnings": [],
        },
        {
            "project_name": "factory",
            "operation_token": "a" * 43,
            "expires_at": "2099-01-01T00:00:00Z",
            "warnings": [1],
        },
    ],
)
async def test_stage_operation_package_rejects_invalid_downstream_contract(payload):
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    with pytest.raises(ExternalServiceError) as exc_info:
        await _client_with_handler(handler).stage_operation_package("factory", b"zip")

    assert exc_info.value.public_detail == (
        "Deployer returned an invalid operation package contract."
    )


@pytest.mark.asyncio
async def test_extract_project_zip_sends_validation_context_without_credentials():
    seen = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["url"] = str(request.url)
        seen["content_type"] = request.headers["content-type"]
        return httpx.Response(200, json={"success": True, "files": {}})

    response = await _client_with_handler(handler).extract_project_zip(
        b"zip",
        {"skip_credentials": True, "l2_provider": "aws"},
    )

    assert response == {"success": True, "files": {}}
    assert seen["method"] == "POST"
    assert seen["url"] == (
        "http://deployer.test/validate/zip/extract?"
        "validation_context=%7B%22skip_credentials%22%3Atrue%2C%22l2_provider%22%3A%22aws%22%7D"
        "&include_credentials=false"
    )
    assert seen["content_type"].startswith("multipart/form-data")


@pytest.mark.asyncio
async def test_extract_project_zip_rejects_oversized_downstream_response(monkeypatch):
    import src.clients.deployer_client as deployer_client_module

    monkeypatch.setattr(
        deployer_client_module,
        "MAX_PROJECT_EXTRACTION_RESPONSE_BYTES",
        8,
    )

    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"success": True, "files": {}})

    with pytest.raises(ExternalServiceError) as exc_info:
        await _client_with_handler(handler).extract_project_zip(
            b"zip",
            {"skip_credentials": True},
        )

    assert exc_info.value.public_detail == (
        "Deployer project extraction response is too large."
    )


@pytest.mark.asyncio
async def test_deployer_client_maps_non_200_to_external_service_error():
    client = _client_with_handler(lambda request: httpx.Response(500, text="boom"))

    with pytest.raises(ExternalServiceError) as exc_info:
        await client.verify_infrastructure("factory", "aws", "token")

    assert exc_info.value.message == "Deployer API returned 500: boom"


@pytest.mark.asyncio
async def test_deployer_stream_maps_error_response_without_response_not_read_failure():
    client = _client_with_handler(
        lambda request: httpx.Response(502, text="upstream failed")
    )

    with pytest.raises(ExternalServiceError) as exc_info:
        _ = [line async for line in client.deploy_stream("aws", "factory", "token")]

    assert exc_info.value.upstream_status_code == 502
    assert exc_info.value.public_detail == "upstream failed"


@pytest.mark.asyncio
async def test_deployer_client_maps_request_error_to_unavailable():
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    client = _client_with_handler(handler)

    with pytest.raises(ExternalServiceUnavailable) as exc_info:
        await client.start_log_trace("factory", "token")

    assert exc_info.value.message == "Deployer API unavailable"
