"""Azure Functions entry points for ``five-layer-baseline@2``.

Cross-cloud ingress terminates on Event Hubs or Service Bus.  No public
function-to-function bridge endpoint is exposed by this package.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Iterable, Mapping
import uuid

import azure.functions as func
from azure.cosmos import CosmosClient
from azure.identity import DefaultAzureCredential

from core import (
    ContractError,
    canonical_json,
    cosmos_raw_history_statement,
    decode_cursor,
    decode_message_body,
    encode_cursor,
    iso_time,
    normalize_history_points,
    parse_raw_history_query,
    raw_history_query_digest,
    validate_canonical_event,
)


app = func.FunctionApp()
REMOTE_TELEMETRY_ENABLED = (
    os.getenv("V2_REMOTE_TELEMETRY_ENABLED", "false").strip().lower() == "true"
)
DOMAIN_CONSUMER_ENABLED = (
    os.getenv("V2_DOMAIN_CONSUMER_ENABLED", "false").strip().lower() == "true"
)
IOT_PROCESSOR_ENABLED = (
    os.getenv("V2_IOT_PROCESSOR_ENABLED", "false").strip().lower() == "true"
)
RAW_HISTORY_ENABLED = (
    os.getenv("V2_RAW_HISTORY_ENABLED", "false").strip().lower() == "true"
)
_COSMOS_CONTAINER: Any | None = None


def _event_hub_events(messages: Iterable[func.EventHubEvent]):
    for message in messages:
        yield decode_message_body(message.get_body())


def _service_bus_event(message: func.ServiceBusMessage):
    return decode_message_body(message.get_body())


def _consume(event: dict) -> None:
    """Validate the landing contract before the provider-domain adapter runs."""

    validated = validate_canonical_event(event)
    logging.info(
        "Azure v2 event accepted type=%s event_id=%s",
        validated["event_type"],
        validated["event_id"],
    )


def _reader_response(status: int, payload: Mapping[str, Any]) -> func.HttpResponse:
    return func.HttpResponse(
        body=canonical_json(payload),
        status_code=status,
        mimetype="application/json",
        headers={"cache-control": "no-store"},
    )


def _cosmos_container():
    global _COSMOS_CONTAINER
    if _COSMOS_CONTAINER is not None:
        return _COSMOS_CONTAINER
    endpoint = os.getenv("V2_COSMOS_ENDPOINT", "")
    database = os.getenv("V2_COSMOS_DATABASE", "")
    container = os.getenv("V2_COSMOS_CONTAINER", "")
    if not endpoint or not database or not container:
        raise ContractError("HOT_STORAGE_NOT_CONFIGURED", 503)
    client = CosmosClient(endpoint, credential=DefaultAzureCredential())
    _COSMOS_CONTAINER = client.get_database_client(database).get_container_client(
        container
    )
    return _COSMOS_CONTAINER


def _read_history(params: Mapping[str, Any]) -> dict[str, Any]:
    query, start, end = parse_raw_history_query(params)
    hmac_key = os.getenv("V2_CURSOR_HMAC_KEY", "")
    digest = raw_history_query_digest(query, start, end)
    continuation = decode_cursor(
        query["cursor"], hmac_key=hmac_key, query_digest=digest
    )
    result = _cosmos_container().query_items(
        query=cosmos_raw_history_statement(query["bucket_seconds"]),
        parameters=[
            {"name": "@device_id", "value": query["device_id"]},
            {"name": "@metric", "value": query["metric"]},
            {"name": "@from", "value": iso_time(start)},
            {"name": "@to", "value": iso_time(end)},
        ],
        partition_key=query["device_id"],
        max_item_count=query["limit"],
    )
    pages = result.by_page(continuation_token=continuation)
    try:
        documents = list(next(pages))
    except StopIteration:
        documents = []
    next_token = pages.continuation_token
    next_cursor = (
        encode_cursor(next_token, hmac_key=hmac_key, query_digest=digest)
        if next_token
        else None
    )
    return {
        "schema_version": "raw-history-query.v1",
        "device_id": query["device_id"],
        "metric": query["metric"],
        "points": normalize_history_points(documents, query["bucket_seconds"]),
        "next_cursor": next_cursor,
        "truncated": bool(next_token),
    }


if REMOTE_TELEMETRY_ENABLED:

    @app.function_name(name="v2-remote-telemetry-consumer")
    @app.event_hub_message_trigger(
        arg_name="messages",
        event_hub_name="%V2_REMOTE_TELEMETRY_HUB_NAME%",
        connection="V2_REMOTE_TELEMETRY",
        cardinality="many",
        consumer_group="$Default",
    )
    def remote_telemetry_consumer(messages: list[func.EventHubEvent]) -> None:
        """Consume provider-managed Event Hubs batches after durable landing."""

        try:
            for event in _event_hub_events(messages):
                _consume(event)
        except ContractError as exc:
            raise RuntimeError(exc.code) from None


if DOMAIN_CONSUMER_ENABLED:

    @app.function_name(name="v2-domain-event-consumer")
    @app.service_bus_queue_trigger(
        arg_name="message",
        queue_name="%V2_DOMAIN_QUEUE_NAME%",
        connection="V2_SERVICE_BUS",
        is_sessions_enabled=True,
    )
    def domain_event_consumer(message: func.ServiceBusMessage) -> None:
        """Consume ordered domain/control events from a session-enabled queue."""

        try:
            _consume(_service_bus_event(message))
        except ContractError as exc:
            raise RuntimeError(exc.code) from None


if IOT_PROCESSOR_ENABLED:

    @app.function_name(name="v2-iot-telemetry-adapter")
    @app.event_hub_message_trigger(
        arg_name="messages",
        event_hub_name="%V2_IOT_HUB_NAME%",
        connection="V2_IOT_HUB",
        cardinality="many",
        consumer_group="$Default",
    )
    def iot_telemetry_adapter(messages: list[func.EventHubEvent]) -> None:
        """Accept canonical simulator telemetry from IoT Hub's built-in endpoint."""

        try:
            for event in _event_hub_events(messages):
                _consume(event)
        except ContractError as exc:
            raise RuntimeError(exc.code) from None


if RAW_HISTORY_ENABLED:

    @app.function_name(name="v2-raw-history-reader")
    @app.route(
        route="raw-history/v1",
        methods=["GET"],
        auth_level=func.AuthLevel.FUNCTION,
    )
    def raw_history_reader(req: func.HttpRequest) -> func.HttpResponse:
        """Serve the bounded L3-hot query used only by the L5 datasource."""

        correlation_id = str(uuid.uuid4())
        try:
            payload = _read_history(dict(req.params))
            payload["correlation_id"] = correlation_id
            return _reader_response(200, payload)
        except ContractError as exc:
            return _reader_response(
                exc.status,
                {
                    "schema_version": "architecture-runtime-error.v1",
                    "code": exc.code,
                    "correlation_id": correlation_id,
                },
            )
        except Exception:
            logging.exception(
                "Azure v2 raw-history query failed correlation_id=%s",
                correlation_id,
            )
            return _reader_response(
                503,
                {
                    "schema_version": "architecture-runtime-error.v1",
                    "code": "READER_UNAVAILABLE",
                    "correlation_id": correlation_id,
                },
            )
