"""Official-SDK destination data-plane publishers for the Phase 8 bridge."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any, Callable, Mapping

from .bridge_core import (
    BridgeContractError,
    BridgeRoute,
    MAX_SOURCE_ID_BYTES,
    RetryableBridgeError,
    RouteBlockingBridgeError,
    TerminalBridgeError,
)


AWS_REGION = "eu-central-1"
AZURE_NAMESPACE_SUFFIX = ".servicebus.windows.net"
GCP_PUBSUB_ENDPOINT = "europe-west1-pubsub.googleapis.com"
_AWS_STREAM_ARN = re.compile(
    rf"^arn:aws:kinesis:{AWS_REGION}:\d{{12}}:stream/[A-Za-z0-9_.-]+$"
)
_AWS_TOPIC_ARN = re.compile(
    rf"^arn:aws:sns:{AWS_REGION}:\d{{12}}:[A-Za-z0-9_.-]+\.fifo$"
)
_AZURE_NAMESPACE = re.compile(
    r"^[a-z0-9][a-z0-9-]{4,48}[a-z0-9]\.servicebus\.windows\.net$"
)
_AZURE_ENTITY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,259}$")
_GCP_TOPIC = re.compile(
    r"^projects/[a-z][a-z0-9-]{4,28}[a-z0-9]/topics/[A-Za-z][A-Za-z0-9._~+%-]{2,254}$"
)


@dataclass(frozen=True, slots=True)
class AwsDestination:
    telemetry_stream_arn: str = ""
    control_topic_arn: str = ""


@dataclass(frozen=True, slots=True)
class AzureDestination:
    telemetry_namespace: str = ""
    telemetry_entity: str = ""
    control_namespace: str = ""
    control_entity: str = ""


@dataclass(frozen=True, slots=True)
class GcpDestination:
    telemetry_topic: str = ""
    control_topic: str = ""
    api_endpoint: str = GCP_PUBSUB_ENDPOINT


def load_destination(raw: object, *, provider: str):
    """Validate one provider data-plane target without accepting endpoint overrides."""

    if not isinstance(raw, Mapping):
        raise BridgeContractError("INVALID_DESTINATION_CONFIGURATION")
    if provider == "aws":
        allowed = {"telemetry_stream_arn", "control_topic_arn"}
        if not set(raw) or not set(raw) <= allowed:
            raise BridgeContractError("INVALID_DESTINATION_CONFIGURATION")
        stream = raw.get("telemetry_stream_arn", "")
        topic = raw.get("control_topic_arn", "")
        if (
            not isinstance(stream, str)
            or not isinstance(topic, str)
            or not (stream or topic)
        ):
            raise BridgeContractError("INVALID_DESTINATION_CONFIGURATION")
        if stream and not _AWS_STREAM_ARN.fullmatch(stream):
            raise RouteBlockingBridgeError("TLS_ENDPOINT_REJECTED")
        if topic and not _AWS_TOPIC_ARN.fullmatch(topic):
            raise RouteBlockingBridgeError("TLS_ENDPOINT_REJECTED")
        return AwsDestination(stream, topic)
    if provider == "azure":
        allowed = {
            "telemetry_namespace",
            "telemetry_entity",
            "control_namespace",
            "control_entity",
        }
        if not set(raw) or not set(raw) <= allowed:
            raise BridgeContractError("INVALID_DESTINATION_CONFIGURATION")
        values = {key: raw.get(key, "") for key in allowed}
        if any(not isinstance(value, str) for value in values.values()):
            raise BridgeContractError("INVALID_DESTINATION_CONFIGURATION")
        if not any(values.values()):
            raise BridgeContractError("INVALID_DESTINATION_CONFIGURATION")
        if bool(values["telemetry_namespace"]) != bool(values["telemetry_entity"]):
            raise BridgeContractError("INVALID_DESTINATION_CONFIGURATION")
        if bool(values["control_namespace"]) != bool(values["control_entity"]):
            raise BridgeContractError("INVALID_DESTINATION_CONFIGURATION")
        if values["telemetry_namespace"] and not _AZURE_NAMESPACE.fullmatch(
            values["telemetry_namespace"]
        ):
            raise RouteBlockingBridgeError("TLS_ENDPOINT_REJECTED")
        if values["control_namespace"] and not _AZURE_NAMESPACE.fullmatch(
            values["control_namespace"]
        ):
            raise RouteBlockingBridgeError("TLS_ENDPOINT_REJECTED")
        if values["telemetry_entity"] and not _AZURE_ENTITY.fullmatch(
            values["telemetry_entity"]
        ):
            raise BridgeContractError("INVALID_DESTINATION_CONFIGURATION")
        if values["control_entity"] and not _AZURE_ENTITY.fullmatch(
            values["control_entity"]
        ):
            raise BridgeContractError("INVALID_DESTINATION_CONFIGURATION")
        return AzureDestination(**values)
    if provider == "gcp":
        allowed = {"telemetry_topic", "control_topic", "api_endpoint"}
        if (
            not set(raw)
            or not set(raw) <= allowed
            or not ({"telemetry_topic", "control_topic"} & set(raw))
        ):
            raise BridgeContractError("INVALID_DESTINATION_CONFIGURATION")
        telemetry = raw.get("telemetry_topic", "")
        control = raw.get("control_topic", "")
        endpoint = raw.get("api_endpoint", GCP_PUBSUB_ENDPOINT)
        if (
            not isinstance(telemetry, str)
            or not isinstance(control, str)
            or not (telemetry or control)
        ):
            raise BridgeContractError("INVALID_DESTINATION_CONFIGURATION")
        if endpoint != GCP_PUBSUB_ENDPOINT:
            raise RouteBlockingBridgeError("TLS_ENDPOINT_REJECTED")
        if telemetry and not _GCP_TOPIC.fullmatch(telemetry):
            raise BridgeContractError("INVALID_DESTINATION_CONFIGURATION")
        if control and not _GCP_TOPIC.fullmatch(control):
            raise BridgeContractError("INVALID_DESTINATION_CONFIGURATION")
        return GcpDestination(telemetry, control, endpoint)
    raise BridgeContractError("INVALID_DESTINATION_CONFIGURATION")


def _canonical_bytes(event: Mapping[str, Any]) -> bytes:
    return json.dumps(
        event,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _source_key(event: Mapping[str, Any]) -> str:
    value = event.get("source_id")
    if (
        not isinstance(value, str)
        or not value
        or len(value.encode("utf-8")) > MAX_SOURCE_ID_BYTES
    ):
        raise TerminalBridgeError("DESTINATION_PAYLOAD_REJECTED")
    return value


def _event_type(event: Mapping[str, Any]) -> str:
    value = event.get("event_type")
    if not isinstance(value, str) or not value:
        raise TerminalBridgeError("DESTINATION_PAYLOAD_REJECTED")
    return value


def _deduplication_id(event: Mapping[str, Any]) -> str:
    event_id = event.get("event_id")
    payload = event.get("payload")
    replay_id = payload.get("replay_id") if isinstance(payload, Mapping) else None
    if not isinstance(event_id, str) or not event_id:
        raise TerminalBridgeError("DESTINATION_PAYLOAD_REJECTED")
    identity = f"{event_id}:{replay_id if isinstance(replay_id, str) else 'live'}"
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def _status_code(exc: Exception) -> int | None:
    for name in ("status_code", "status"):
        value = getattr(exc, name, None)
        if isinstance(value, int):
            return value
    code = getattr(exc, "code", None)
    if callable(code):
        code = code()
    if isinstance(code, int):
        return code
    value = getattr(code, "value", None)
    if isinstance(value, tuple) and value:
        return value[0]
    return value if isinstance(value, int) else None


def _aws_error_code(exc: Exception) -> str:
    response = getattr(exc, "response", None)
    if not isinstance(response, Mapping):
        return ""
    error = response.get("Error")
    return str(error.get("Code", "")) if isinstance(error, Mapping) else ""


def raise_safe_publish_error(exc: Exception) -> None:
    """Map provider failures to the bounded bridge error vocabulary."""

    status = _status_code(exc)
    aws_code = _aws_error_code(exc).lower()
    if status in {401, 403} or any(
        marker in aws_code
        for marker in ("accessdenied", "unauthorized", "invalidclienttoken")
    ):
        raise RouteBlockingBridgeError("DESTINATION_PERMISSION_REJECTED") from None
    if status in {400, 404, 413, 422} or any(
        marker in aws_code
        for marker in ("invalidargument", "validation", "resourcenotfound")
    ):
        raise TerminalBridgeError("DESTINATION_PAYLOAD_REJECTED") from None
    raise RetryableBridgeError("DESTINATION_PUBLISH_RETRYABLE") from None


class AwsDestinationPublisher:
    """Publish through boto3 Kinesis/SNS clients using temporary credentials."""

    def __init__(
        self,
        destination: AwsDestination,
        client_factory: Callable[[str], object],
    ) -> None:
        self._destination = destination
        self._client_factory = client_factory
        self._sequence_by_key: dict[str, str] = {}

    def publish(self, route: BridgeRoute, event: Mapping[str, Any]) -> str:
        key = _source_key(event)
        data = _canonical_bytes(event)
        try:
            if route.destination_provider != "aws":
                raise RouteBlockingBridgeError("ROUTE_MISMATCH")
            if route.channel_class == "telemetry":
                if not self._destination.telemetry_stream_arn:
                    raise RouteBlockingBridgeError("ROUTE_MISMATCH")
                request: dict[str, Any] = {
                    "StreamARN": self._destination.telemetry_stream_arn,
                    "Data": data,
                    "PartitionKey": key,
                }
                previous = self._sequence_by_key.get(key)
                if previous:
                    request["SequenceNumberForOrdering"] = previous
                result = self._client_factory("kinesis").put_record(**request)
                shard = result.get("ShardId") if isinstance(result, Mapping) else None
                sequence = (
                    result.get("SequenceNumber") if isinstance(result, Mapping) else None
                )
                if not isinstance(shard, str) or not isinstance(sequence, str):
                    raise RetryableBridgeError("DESTINATION_NOT_ACCEPTED")
                self._sequence_by_key[key] = sequence
                return sequence
            if route.channel_class == "control":
                if not self._destination.control_topic_arn:
                    raise RouteBlockingBridgeError("ROUTE_MISMATCH")
                result = self._client_factory("sns").publish(
                    TopicArn=self._destination.control_topic_arn,
                    Message=data.decode("utf-8"),
                    MessageGroupId=key,
                    MessageDeduplicationId=_deduplication_id(event),
                    MessageAttributes={
                        "event_type": {
                            "DataType": "String",
                            "StringValue": _event_type(event),
                        }
                    },
                )
                message_id = (
                    result.get("MessageId") if isinstance(result, Mapping) else None
                )
                sequence = (
                    result.get("SequenceNumber") if isinstance(result, Mapping) else None
                )
                if not isinstance(message_id, str) or not isinstance(sequence, str):
                    raise RetryableBridgeError("DESTINATION_NOT_ACCEPTED")
                return message_id
            raise RouteBlockingBridgeError("ROUTE_MISMATCH")
        except (
            RetryableBridgeError,
            RouteBlockingBridgeError,
            TerminalBridgeError,
        ):
            raise
        except Exception as exc:
            raise_safe_publish_error(exc)


class AzureDestinationPublisher:
    """Publish through Azure Event Hubs and Service Bus SDK clients."""

    def __init__(
        self,
        destination: AzureDestination,
        credential: object,
        *,
        event_hub_factory: Callable[..., object] | None = None,
        event_data_factory: Callable[[bytes], object] | None = None,
        service_bus_factory: Callable[..., object] | None = None,
        service_bus_message_factory: Callable[..., object] | None = None,
    ) -> None:
        if event_hub_factory is None or event_data_factory is None:
            from azure.eventhub import EventData, EventHubProducerClient

            event_hub_factory = EventHubProducerClient
            event_data_factory = EventData
        if service_bus_factory is None or service_bus_message_factory is None:
            from azure.servicebus import ServiceBusClient, ServiceBusMessage

            service_bus_factory = ServiceBusClient
            service_bus_message_factory = ServiceBusMessage
        self._destination = destination
        self._credential = credential
        self._event_hub_factory = event_hub_factory
        self._event_data_factory = event_data_factory
        self._service_bus_factory = service_bus_factory
        self._service_bus_message_factory = service_bus_message_factory

    def publish(self, route: BridgeRoute, event: Mapping[str, Any]) -> bool:
        key = _source_key(event)
        data = _canonical_bytes(event)
        try:
            if route.destination_provider != "azure":
                raise RouteBlockingBridgeError("ROUTE_MISMATCH")
            if route.channel_class == "telemetry":
                if not self._destination.telemetry_namespace:
                    raise RouteBlockingBridgeError("ROUTE_MISMATCH")
                producer = self._event_hub_factory(
                    fully_qualified_namespace=self._destination.telemetry_namespace,
                    eventhub_name=self._destination.telemetry_entity,
                    credential=self._credential,
                    buffered_mode=False,
                )
                with producer:
                    producer.send_batch(
                        [self._event_data_factory(data)],
                        partition_key=key,
                        timeout=30,
                    )
                return True
            if route.channel_class == "control":
                if not self._destination.control_namespace:
                    raise RouteBlockingBridgeError("ROUTE_MISMATCH")
                client = self._service_bus_factory(
                    fully_qualified_namespace=self._destination.control_namespace,
                    credential=self._credential,
                )
                with client:
                    sender = client.get_topic_sender(
                        topic_name=self._destination.control_entity
                    )
                    with sender:
                        sender.send_messages(
                            self._service_bus_message_factory(
                                data,
                                message_id=_deduplication_id(event),
                                session_id=key,
                                application_properties={
                                    "event_type": _event_type(event)
                                },
                            )
                        )
                return True
            raise RouteBlockingBridgeError("ROUTE_MISMATCH")
        except (
            RetryableBridgeError,
            RouteBlockingBridgeError,
            TerminalBridgeError,
        ):
            raise
        except Exception as exc:
            raise_safe_publish_error(exc)


class GcpDestinationPublisher:
    """Publish ordered messages through the Google Pub/Sub SDK."""

    def __init__(self, destination: GcpDestination, publisher: object) -> None:
        self._destination = destination
        self._publisher = publisher

    def publish(self, route: BridgeRoute, event: Mapping[str, Any]) -> str:
        key = _source_key(event)
        topic = (
            self._destination.telemetry_topic
            if route.channel_class == "telemetry"
            else self._destination.control_topic
        )
        try:
            if route.destination_provider != "gcp" or route.channel_class not in {
                "telemetry",
                "control",
            }:
                raise RouteBlockingBridgeError("ROUTE_MISMATCH")
            if not topic:
                raise RouteBlockingBridgeError("ROUTE_MISMATCH")
            future = self._publisher.publish(
                topic,
                _canonical_bytes(event),
                ordering_key=key,
                event_type=_event_type(event),
            )
            message_id = future.result(timeout=30)
            if not isinstance(message_id, str) or not message_id:
                raise RetryableBridgeError("DESTINATION_NOT_ACCEPTED")
            return message_id
        except (
            RetryableBridgeError,
            RouteBlockingBridgeError,
            TerminalBridgeError,
        ):
            raise
        except Exception as exc:
            resume = getattr(self._publisher, "resume_publish", None)
            if callable(resume):
                resume(topic, key)
            raise_safe_publish_error(exc)


__all__ = [
    "AWS_REGION",
    "AZURE_NAMESPACE_SUFFIX",
    "GCP_PUBSUB_ENDPOINT",
    "AwsDestination",
    "AwsDestinationPublisher",
    "AzureDestination",
    "AzureDestinationPublisher",
    "GcpDestination",
    "GcpDestinationPublisher",
    "load_destination",
    "raise_safe_publish_error",
]
