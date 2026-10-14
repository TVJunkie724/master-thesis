import httpx
import pytest

from src.clients.optimizer_client import OptimizerClient
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
async def test_calculate_puts_exact_endpoint_payload_and_correlation(
    monkeypatch,
):
    seen = {}
    monkeypatch.setattr(
        "src.clients.optimizer_client.current_request_id",
        lambda: "management-request-123",
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["url"] = str(request.url)
        seen["payload"] = request.read().decode()
        seen["request_id"] = request.headers["X-Request-ID"]
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
    assert seen["request_id"] == "management-request-123"


@pytest.mark.asyncio
async def test_calculate_maps_known_architecture_error_to_bounded_code():
    client = OptimizerClient(
        base_url="http://optimizer.test",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                409,
                json={
                    "detail": {
                        "error_code": "ARCH_NO_ADMISSIBLE_CANDIDATE",
                        "message": "unsafe upstream detail",
                    }
                },
            )
        ),
    )

    with pytest.raises(ExternalServiceError) as exc_info:
        await client.calculate({"numberOfDevices": 10})

    assert exc_info.value.upstream_status_code == 409
    assert exc_info.value.error_code == "ARCH_NO_ADMISSIBLE_CANDIDATE"
    assert exc_info.value.public_detail == (
        "Optimizer rejected architecture profile resolution."
    )
    assert "unsafe upstream detail" not in exc_info.value.message


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
async def test_json_object_rejects_non_object_payloads():
    client = OptimizerClient(
        base_url="http://optimizer.test",
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=[])),
    )

    with pytest.raises(ExternalServiceError) as exc_info:
        await client.get_pricing_catalog_baseline("aws")

    assert exc_info.value.message == "Optimizer API returned non-object JSON"
