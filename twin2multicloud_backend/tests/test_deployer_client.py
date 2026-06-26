from datetime import datetime, timezone

import httpx
import pytest

from src.clients.deployer_client import DeployerClient
from src.services.errors import ExternalServiceError, ExternalServiceUnavailable


def _client_with_handler(handler):
    return DeployerClient(
        base_url="http://deployer.test",
        transport=httpx.MockTransport(handler),
    )


@pytest.mark.asyncio
async def test_validate_deployer_complete_posts_exact_endpoint_and_payload():
    seen = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["url"] = str(request.url)
        seen["payload"] = request.read().decode()
        return httpx.Response(200, json={"valid": True})

    response = await _client_with_handler(handler).validate_deployer_complete({"cheapest_path": {}})

    assert response == {"valid": True}
    assert seen["method"] == "POST"
    assert seen["url"] == "http://deployer.test/validate/deployer-complete"
    assert seen["payload"] == '{"cheapest_path":{}}'


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
        seen.append((request.method, str(request.url)))
        return httpx.Response(200, text="data: first\n\nevent: complete\n\n")

    client = _client_with_handler(handler)

    deploy_lines = [line async for line in client.deploy_stream("aws", "factory")]
    destroy_lines = [line async for line in client.destroy_stream("gcp", "factory")]

    assert deploy_lines == ["data: first", "", "event: complete", ""]
    assert destroy_lines == ["data: first", "", "event: complete", ""]
    assert seen == [
        ("POST", "http://deployer.test/infrastructure/deploy/stream?provider=aws&project_name=factory"),
        ("POST", "http://deployer.test/infrastructure/destroy/stream?provider=gcp&project_name=factory"),
    ]


@pytest.mark.asyncio
async def test_log_trace_and_verification_methods_preserve_deployer_paths():
    seen = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, str(request.url), request.read().decode()))
        return httpx.Response(200, json={"ok": True})

    client = _client_with_handler(handler)

    assert await client.start_log_trace("factory") == {"ok": True}
    assert await client.verify_infrastructure("factory", "aws") == {"ok": True}

    dataflow_lines = [line async for line in client.verify_dataflow("factory", {"iotDeviceId": "device-1"})]
    trace_lines = [line async for line in client.stream_log_trace("factory", "TRACE-1")]

    assert dataflow_lines == ['{"ok":true}']
    assert trace_lines == ['{"ok":true}']
    assert seen == [
        ("POST", "http://deployer.test/logs/trace/start?project_name=factory", ""),
        ("POST", "http://deployer.test/infrastructure/verify?project_name=factory&provider=aws", ""),
        ("POST", "http://deployer.test/dataflow/verify?project_name=factory", '{"payload":{"iotDeviceId":"device-1"}}'),
        ("GET", "http://deployer.test/logs/trace/stream/TRACE-1?project_name=factory", ""),
    ]


@pytest.mark.asyncio
async def test_download_simulator_returns_zip_bytes_from_exact_path():
    seen = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, content=b"zip-bytes")

    content = await _client_with_handler(handler).download_simulator("factory", "azure")

    assert content == b"zip-bytes"
    assert seen["url"] == "http://deployer.test/projects/factory/simulator/azure/download"


@pytest.mark.asyncio
async def test_project_exists_preserves_404_as_false_without_throwing():
    seen = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(404, text="not found")

    exists = await _client_with_handler(handler).project_exists("factory")

    assert exists is False
    assert seen == ["http://deployer.test/projects/factory/validate"]


@pytest.mark.asyncio
async def test_project_zip_upload_methods_send_multipart_contracts():
    seen = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, str(request.url), request.headers["content-type"]))
        return httpx.Response(200, json={"project": "factory"})

    client = _client_with_handler(handler)

    assert await client.import_project_zip("factory", b"zip") == {"project": "factory"}
    assert await client.create_project_zip("factory", b"zip") == {"project": "factory"}

    assert seen[0][0:2] == ("POST", "http://deployer.test/projects/factory/import")
    assert seen[1][0:2] == ("POST", "http://deployer.test/projects?project_name=factory")
    assert seen[0][2].startswith("multipart/form-data")
    assert seen[1][2].startswith("multipart/form-data")


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
async def test_deployer_client_maps_non_200_to_external_service_error():
    client = _client_with_handler(lambda request: httpx.Response(500, text="boom"))

    with pytest.raises(ExternalServiceError) as exc_info:
        await client.verify_infrastructure("factory", "aws")

    assert exc_info.value.message == "Deployer API returned 500: boom"


@pytest.mark.asyncio
async def test_deployer_client_maps_request_error_to_unavailable():
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    client = _client_with_handler(handler)

    with pytest.raises(ExternalServiceUnavailable) as exc_info:
        await client.start_log_trace("factory")

    assert exc_info.value.message == "Deployer API unavailable"
