import httpx
import pytest

from src.clients.optimizer_client import OptimizerClient, OptimizerProviderStatus
from src.services.errors import ExternalServiceError, ExternalServiceUnavailable


@pytest.mark.asyncio
async def test_validate_optimizer_config_posts_exact_endpoint_and_payload():
    seen = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["url"] = str(request.url)
        seen["payload"] = request.read().decode()
        return httpx.Response(200, json={"valid": True})

    client = OptimizerClient(
        base_url="http://optimizer.test",
        transport=httpx.MockTransport(handler),
    )

    response = await client.validate_optimizer_config({"params": {"devices": 10}})

    assert response == {"valid": True}
    assert seen["method"] == "POST"
    assert seen["url"] == "http://optimizer.test/validate/optimizer-config"
    assert seen["payload"] == '{"params":{"devices":10}}'


@pytest.mark.asyncio
async def test_verify_permissions_posts_exact_provider_endpoint_and_payload():
    seen = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["url"] = str(request.url)
        seen["payload"] = request.read().decode()
        return httpx.Response(200, json={"valid": True})

    client = OptimizerClient(
        base_url="http://optimizer.test",
        transport=httpx.MockTransport(handler),
    )

    response = await client.verify_permissions("aws", {"aws_region": "eu-central-1"})

    assert response == {"valid": True}
    assert seen == {
        "method": "POST",
        "url": "http://optimizer.test/permissions/verify/aws",
        "payload": '{"aws_region":"eu-central-1"}',
    }


@pytest.mark.asyncio
async def test_validate_optimizer_config_maps_non_200_to_external_service_error():
    client = OptimizerClient(
        base_url="http://optimizer.test",
        transport=httpx.MockTransport(lambda request: httpx.Response(422, text="bad config")),
    )

    with pytest.raises(ExternalServiceError) as exc_info:
        await client.validate_optimizer_config({"params": None})

    assert exc_info.value.message == "Optimizer API returned 422: bad config"


@pytest.mark.asyncio
async def test_validate_optimizer_config_maps_request_error_to_unavailable():
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    client = OptimizerClient(
        base_url="http://optimizer.test",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ExternalServiceUnavailable) as exc_info:
        await client.validate_optimizer_config({"params": None})

    assert exc_info.value.message == "Optimizer API unavailable"


@pytest.mark.asyncio
async def test_calculate_puts_exact_endpoint_and_payload():
    seen = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["url"] = str(request.url)
        seen["payload"] = request.read().decode()
        return httpx.Response(200, json={"result": {"totalCost": 1.23}})

    client = OptimizerClient(
        base_url="http://optimizer.test",
        transport=httpx.MockTransport(handler),
    )

    response = await client.calculate({"numberOfDevices": 10})

    assert response == {"result": {"totalCost": 1.23}}
    assert seen["method"] == "PUT"
    assert seen["url"] == "http://optimizer.test/calculate"
    assert seen["payload"] == '{"numberOfDevices":10}'


@pytest.mark.asyncio
async def test_get_provider_capabilities_uses_read_only_contract_endpoint():
    seen = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["url"] = str(request.url)
        return httpx.Response(200, json={"service": "optimizer"})

    client = OptimizerClient(
        base_url="http://optimizer.test",
        transport=httpx.MockTransport(handler),
    )

    assert await client.get_provider_capabilities() == {"service": "optimizer"}
    assert seen == {
        "method": "GET",
        "url": "http://optimizer.test/capabilities/providers",
    }


@pytest.mark.asyncio
async def test_get_cache_status_preserves_provider_non_200_without_throwing():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "http://optimizer.test/pricing_age/aws"
        return httpx.Response(500, text="boom")

    client = OptimizerClient(
        base_url="http://optimizer.test",
        transport=httpx.MockTransport(handler),
    )

    result = await client.get_cache_status(endpoint_prefix="pricing_age", provider="aws")

    assert result == OptimizerProviderStatus(provider="aws", status_code=500, payload={})
    assert result.is_success is False


@pytest.mark.asyncio
async def test_get_cache_status_returns_object_payload_for_success():
    client = OptimizerClient(
        base_url="http://optimizer.test",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"status": "valid"})
        ),
    )

    result = await client.get_cache_status(endpoint_prefix="regions_age", provider="gcp")

    assert result.provider == "gcp"
    assert result.status_code == 200
    assert result.payload == {"status": "valid"}


@pytest.mark.asyncio
async def test_get_exact_pricing_catalog_snapshot_gets_exact_endpoint():
    seen = {}
    snapshot_id = "pcs_" + ("a" * 64)

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["url"] = str(request.url)
        return httpx.Response(200, json={"reference": {}, "pricing": {}})

    client = OptimizerClient(
        base_url="http://optimizer.test",
        transport=httpx.MockTransport(handler),
    )

    result = await client.get_exact_pricing_catalog_snapshot(
        "azure",
        "westeurope",
        snapshot_id,
    )

    assert result == {"reference": {}, "pricing": {}}
    assert seen == {
        "method": "GET",
        "url": (
            "http://optimizer.test/pricing/catalogs/azure/westeurope/"
            f"snapshots/{snapshot_id}"
        ),
    }


@pytest.mark.asyncio
async def test_refresh_azure_pricing_uses_force_fetch_endpoint():
    seen = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["url"] = str(request.url)
        return httpx.Response(200, json={"refreshed": True})

    client = OptimizerClient(
        base_url="http://optimizer.test",
        transport=httpx.MockTransport(handler),
    )

    result = await client.refresh_azure_pricing()

    assert result == {"refreshed": True}
    assert seen == {
        "method": "POST",
        "url": (
            "http://optimizer.test/fetch_pricing_with_credentials/"
            "azure?force_fetch=true"
        ),
    }


@pytest.mark.asyncio
async def test_refresh_pricing_with_credentials_posts_payload():
    seen = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["url"] = str(request.url)
        seen["payload"] = request.read().decode()
        return httpx.Response(200, json={"refreshed": True})

    client = OptimizerClient(
        base_url="http://optimizer.test",
        transport=httpx.MockTransport(handler),
    )

    await client.refresh_pricing_with_credentials("aws", {"aws_region": "eu-west-1"})

    assert seen == {
        "method": "POST",
        "url": (
            "http://optimizer.test/fetch_pricing_with_credentials/"
            "aws?force_fetch=true"
        ),
        "payload": '{"aws_region":"eu-west-1"}',
    }


@pytest.mark.asyncio
async def test_stream_pricing_refresh_posts_payload_and_yields_chunks():
    seen = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["url"] = str(request.url)
        seen["payload"] = request.read().decode()
        seen["accept"] = request.headers["accept"]
        return httpx.Response(
            200,
            text='event: complete\ndata: {"message": "Done!"}\n\n',
            headers={"content-type": "text/event-stream"},
        )

    client = OptimizerClient(
        base_url="http://optimizer.test",
        transport=httpx.MockTransport(handler),
    )

    chunks = [
        chunk
        async for chunk in client.stream_pricing_refresh(
            "gcp",
            {"gcp_project_id": "thesis-demo"},
        )
    ]

    assert "".join(chunks) == 'event: complete\ndata: {"message": "Done!"}\n\n'
    assert seen == {
        "method": "POST",
        "url": "http://optimizer.test/stream/fetch_pricing/gcp",
        "payload": '{"gcp_project_id":"thesis-demo"}',
        "accept": "text/event-stream",
    }


@pytest.mark.asyncio
async def test_json_object_rejects_non_object_payloads():
    client = OptimizerClient(
        base_url="http://optimizer.test",
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=[])),
    )

    with pytest.raises(ExternalServiceError) as exc_info:
        await client.get_exact_pricing_catalog_snapshot(
            "aws",
            "eu-central-1",
            "pcs_" + ("a" * 64),
        )

    assert exc_info.value.message == "Optimizer API returned non-object JSON"


@pytest.mark.asyncio
async def test_get_cache_status_sends_explicit_pricing_region():
    seen = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, json={"status": "valid"})

    client = OptimizerClient(
        base_url="http://optimizer.test",
        transport=httpx.MockTransport(handler),
    )

    await client.get_cache_status(
        endpoint_prefix="pricing_age",
        provider="azure",
        pricing_region="westeurope",
    )

    assert seen["url"] == (
        "http://optimizer.test/pricing_age/azure?pricing_region=westeurope"
    )
