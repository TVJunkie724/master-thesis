"""Azure Functions entry points for ``five-layer-baseline@2``.

Cross-cloud ingress terminates on Event Hubs or Service Bus.  No public
function-to-function bridge endpoint is exposed by this package.
"""

from __future__ import annotations

import logging
from typing import Iterable

import azure.functions as func

from core import ContractError, decode_message_body, validate_canonical_event


app = func.FunctionApp()


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
